"""Browser regressions for missing metadata and failed history IO.

Every server uses an explicit test fixture and a temporary history directory.
No production server or real model is used by this script.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

PROJECT = Path(__file__).resolve().parents[2]
REPO = PROJECT.parent
OUT = REPO / 'qa_runs/frontend_recheck_20261020'
sys.path.insert(0, str(REPO / 'qa_runs/evidence_quality_20261010/browser_tools'))
from playwright.sync_api import sync_playwright, expect


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {'checks': [], 'jsErrors': []}

    def check(value, label):
        assert value, label
        report['checks'].append(label)

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless=True)
            for mode in ['missing-data', 'history-write-error']:
                with tempfile.TemporaryDirectory(prefix='flowbd-edge-fixture-') as folder:
                    with socket.socket() as reservation:
                        reservation.bind(('127.0.0.1', 0))
                        port = reservation.getsockname()[1]
                    env = os.environ.copy()
                    env.update(PYTHONIOENCODING='utf-8', PYTHONUTF8='1', FLOWBD_UI_TEST_HOME=folder, FLOWBD_UI_FIXTURE=mode)
                    log = (OUT / (mode + '.log')).open('w', encoding='utf-8')
                    proc = subprocess.Popen([sys.executable, '-m', 'streamlit', 'run', str(Path(__file__).with_name('browser_fixture_app.py')),
                                             '--server.port', str(port), '--server.headless', 'true', '--browser.gatherUsageStats', 'false',
                                             '--theme.backgroundColor', '#f5f5f7', '--theme.primaryColor', '#0071e3'],
                                            cwd=PROJECT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                            creationflags=subprocess.CREATE_NO_WINDOW)
                    try:
                        base = f'http://127.0.0.1:{port}'
                        for attempt in range(60):
                            try:
                                with urlopen(base + '/_stcore/health', timeout=1):
                                    break
                            except OSError:
                                if proc.poll() is not None:
                                    raise RuntimeError('Isolated fixture exited before startup')
                                time.sleep(.2)
                        page = browser.new_page(viewport={'width': 1440, 'height': 900})
                        page.on('pageerror', lambda error: report['jsErrors'].append(str(error)))
                        if mode == 'missing-data':
                            page.goto(base + '/?page=corpus')
                            frame = page.frame_locator('iframe').first
                            expect(frame.locator('.paper-row')).to_have_count(2)
                            check('方法抽取记录暂不可用' in frame.locator('.page-column').inner_text(), 'Missing method index is unavailable, not zero')
                            check('年份待核对' in frame.locator('.paper-row').first.inner_text(), 'Missing year is not inferred')
                            frame.locator('.paper-row').filter(has_text='测试无全文文献').click()
                            expect(frame.get_by_role('button', name='阅读本地原文')).to_be_disabled()
                            check(True, 'Missing full text disables the open action')
                            frame.locator('.paper-row').filter(has_text='测试本地文献').click()
                            frame.get_by_role('button', name='阅读本地原文').click()
                            page.get_by_text('这是隔离测试中已保存的本地全文。', exact=True).wait_for()
                            check(True, 'Local full text opens without auxiliary metadata')
                            frame.get_by_role('searchbox', name='搜索文献').fill('NO_MATCH_EDGE_CASE')
                            expect(frame.locator('.paper-row')).to_have_count(0)
                            expect(page.locator('[data-testid=stExpander]').filter(has_text='文献原文 ·')).to_have_count(0)
                            check(True, 'Empty filtering removes a previously expanded full text')
                            page.goto(base + '/?page=evaluation')
                            page.get_by_text('正式评测产物不可用', exact=False).wait_for()
                            check(page.locator('iframe').count() == 0, 'Missing formal report is not filled with demo numbers')
                            page.goto(base + '/?page=lineage')
                            page.get_by_text('统一专题不可用', exact=False).wait_for()
                            check(page.locator('[data-testid=stException]').count() == 0, 'Missing lineage files show a recoverable message')
                        else:
                            page.goto(base)
                            page.get_by_role('button', name='历史对话', exact=True).click()
                            history_path = Path(folder) / 'src/data/chat_history.jsonl'
                            before = history_path.read_bytes()
                            page.get_by_text('确认删除此条历史', exact=True).click()
                            page.get_by_role('button', name='删除历史', exact=True).click()
                            page.get_by_text('历史删除未完成', exact=False).wait_for()
                            check(history_path.read_bytes() == before, 'Failed delete leaves history bytes unchanged')
                            page.get_by_role('button', name='历史对话', exact=True).click()
                            check(page.get_by_role('combobox').count() == 1, 'Failed delete keeps history selectable')
                            page.keyboard.press('Escape')
                            page.get_by_role('textbox', name='研究问题', exact=True).fill('测试写入权限')
                            page.get_by_role('button', name='开始研究', exact=True).last.click()
                            backup = page.get_by_role('button', name='下载未保存对话备份', exact=True)
                            backup.wait_for(timeout=30000)
                            expect(page.get_by_role('button', name='新建问题', exact=True)).to_be_enabled()
                            check(True, 'Failed save releases the generation controls')
                            page.frame_locator('iframe').first.locator('.markdown').filter(has_text='已保存的测试回答').wait_for()
                            check(True, 'Failed save keeps the complete answer in the current session')
                            with page.expect_download() as download:
                                backup.click()
                            records = json.loads(Path(download.value.path()).read_text(encoding='utf-8'))
                            check(len(records) == 1 and len(records[0]['message']['doc_sources']) == 2, 'Backup retains the answer and full source list')
                            page.get_by_role('button', name='新建问题', exact=True).click()
                            expect(backup).to_be_visible()
                            check(history_path.read_bytes() == before, 'New question retains backup without writing failed records')
                        check(page.locator('[data-testid=stException]').count() == 0, mode + ': no Streamlit exception')
                        page.close()
                    finally:
                        proc.terminate()
                        proc.wait(timeout=20)
                        log.close()
            browser.close()
        check(not report['jsErrors'], 'No JavaScript errors in edge fixtures')
        report['passed'] = True
    finally:
        (OUT / 'browser_edge_cases.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(f"Edge browser checks: {len(report['checks'])}; passed: {report.get('passed', False)}")


if __name__ == '__main__':
    main()
