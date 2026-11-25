"""Real-browser acceptance for the new app, with an isolated streaming fixture.

Run from FlowBD系统 with its Python 3.12 environment. The production server must
already be available; this script never submits a question to that server.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from urllib.parse import urlparse
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
REPO = PROJECT.parent
OUT = REPO / 'qa_runs/frontend_redesign_20261020'
sys.path.insert(0, str(REPO / 'qa_runs/evidence_quality_20261010/browser_tools'))
from playwright.sync_api import sync_playwright, expect


def main():
    base = os.environ.get('FLOWBD_UI_URL', 'http://localhost:8520')
    report = {'checks': [], 'jsErrors': [], 'remoteRequests': [], 'environmentRequests': [], 'screenshots': []}
    bad_ui_markers = ('Bad message format', 'setIn index 2', '页面数据异常', '无法显示这条消息')

    def check(value, label):
        assert value, label
        report['checks'].append(label)

    def check_no_failure_replay_error(page, label):
        texts = [page.locator('body').inner_text()]
        for frame in page.frames[1:]:
            try:
                texts.append(frame.locator('body').inner_text())
            except Exception:
                pass
        found = [marker for marker in bad_ui_markers
                 if any(marker in text for text in texts)]
        check(not found, label + ': ' + ','.join(found))

    def check_graph_colors(graph, label):
        graph.wait_for()
        colors = graph.evaluate('''el => {
            const style = getComputedStyle(el), node = el.querySelector('circle');
            const texts = [...el.querySelectorAll('text')];
            const luminance = color => {
                const channels = color.match(/\\d+/g).slice(0, 3).map(Number).map(c => {
                    const s = c / 255;
                    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
                });
                return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
            };
            const background = luminance(style.backgroundColor);
            return {background: style.backgroundColor,
                    nodeFill: getComputedStyle(node).fill,
                    nodeStroke: getComputedStyle(node).stroke,
                    textColors: texts.map(t => getComputedStyle(t).fill),
                    minTextContrast: Math.min(...texts.map(t => {
                        const text = luminance(getComputedStyle(t).fill);
                        return (Math.max(background, text) + 0.05) / (Math.min(background, text) + 0.05);
                    }))};
        }''')
        check(colors['background'] == 'rgb(255, 255, 255)', label + ': opaque light canvas')
        check(colors['nodeFill'] == 'rgb(231, 239, 251)' and colors['nodeStroke'] == 'rgb(0, 113, 227)', label + ': visible node fill and outline')
        check(all(c in {'rgb(29, 29, 31)', 'rgb(81, 81, 84)', 'rgb(99, 99, 105)'} for c in colors['textColors']), label + ': explicit readable label colors')
        check(colors['minTextContrast'] >= 4.5, label + ': label contrast at least 4.5:1')

    with tempfile.TemporaryDirectory(prefix='flowbd-browser-fixture-') as folder:
        env = os.environ.copy()
        env.update(PYTHONIOENCODING='utf-8', PYTHONUTF8='1', FLOWBD_UI_TEST_HOME=folder)
        log = (OUT / 'browser_fixture.log').open('w', encoding='utf-8')
        proc = subprocess.Popen([sys.executable, '-m', 'streamlit', 'run', str(Path(__file__).with_name('browser_fixture_app.py')),
                                 '--server.port', '8521', '--server.headless', 'true', '--browser.gatherUsageStats', 'false',
                                 '--theme.primaryColor', '#0071e3', '--theme.backgroundColor', '#f5f5f7'],
                                cwd=PROJECT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(executable_path='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless=True)
                context = browser.new_context(viewport={'width': 1440, 'height': 900}, reduced_motion='reduce')
                def request_seen(request):
                    host = urlparse(request.url).hostname or ''
                    if host in {'localhost', '127.0.0.1', ''}:
                        return
                    # The installed security software injects this script into Edge.
                    # Record the host separately; do not disable or reconfigure it.
                    if host.endswith('.kaspersky-labs.com'):
                        if host not in report['environmentRequests']:
                            report['environmentRequests'].append(host)
                    elif request.url.startswith(('http:', 'https:')):
                        report['remoteRequests'].append(request.url)
                context.on('request', request_seen)
                page = context.new_page()
                page.on('pageerror', lambda error: report['jsErrors'].append(str(error)))
                page.set_default_timeout(15000)
                page.goto(base)
                page.get_by_role('heading', name=re.compile(r'读懂方法，看清来路\s*。')).wait_for()
                check(page.get_by_text('让中文文献里的问题、知识与证据，成为一条清晰的研究路径。', exact=True).is_visible(), 'Approved hero copy')
                page.get_by_role('button', name='历史对话', exact=True).click()
                page.get_by_role('button', name='打开历史', exact=True).click()
                reader = page.frame_locator('iframe').first
                reader.locator('.answer h2').wait_for()
                check('扩散' in reader.locator('.answer h2').inner_text(), 'Production history opens without a model call')
                page.get_by_text('展开图谱、方法版图与执行流程', exact=True).click()
                check_graph_colors(page.locator('.fb-history-graph'), 'Saved historical graph')
                page.get_by_text('展开图谱、方法版图与执行流程', exact=True).click()
                reader.locator('.citation[data-ref="21"]').first.click()
                check('查询' in reader.locator('.inspector').inner_text(), 'Citation selects its recorded scope source')
                reader.locator('[data-action="sources"]').click()
                check(reader.locator('dialog details').count() == 21, 'All source identities retained')
                page.keyboard.press('Escape')
                reader.locator('[data-action="pane"]').click()
                check(not reader.locator('.inspector').is_visible(), 'Source pane hides')
                reader.locator('.citation[data-ref="20"]').first.click()
                check(reader.locator('.inspector').is_visible(), 'Citation reopens source pane')
                for width, height in [(1440, 900), (1280, 800), (1920, 1080)]:
                    page.set_viewport_size({'width': width, 'height': height})
                    for route, label, selector in [('qa', '研究问答', '.answer'), ('lineage', '方法谱系', '.lineage-diagram-frame'), ('corpus', '语料库', '.paper-row'), ('evaluation', '评测报告', 'tbody tr')]:
                        if page.get_by_role('button', name=label, exact=True).count():
                            page.get_by_role('button', name=label, exact=True).click()
                        frame = page.frame_locator('iframe').first
                        frame.locator(selector).first.wait_for()
                        check(page.locator('[data-testid="stException"]').count() == 0, f'{route}/{width}: no Streamlit exception')
                        check(not page.evaluate('document.documentElement.scrollWidth > innerWidth+1'), f'{route}/{width}: no outer overflow')
                        check(not frame.locator('html').evaluate('(e)=>e.scrollWidth>innerWidth+1'), f'{route}/{width}: no component overflow')
                        if width == 1440:
                            page.evaluate("document.querySelector('.main')?.scrollTo(0,0); window.scrollTo(0,0)")
                            path = PROJECT / 'frontend/review' / f'{route}.png'
                            path.parent.mkdir(exist_ok=True)
                            page.screenshot(path=str(path))
                            report['screenshots'].append(str(path.relative_to(REPO)))
                # Actual component graph nodes and filters; raw state remains visible.
                page.get_by_role('button', name='方法谱系', exact=True).click()
                graph = page.frame_locator('iframe').first
                diagram = graph.frame_locator('.lineage-diagram-frame')
                diagram.locator('svg > g[data-node-id]').first.wait_for()
                check(diagram.locator('svg > g[data-node-id]').count() == 8, 'Interactive main figure retains eight actual nodes')
                graph.get_by_role('button', name='浏览全部候选与筛选').click()
                graph.locator('.node').first.wait_for()
                check(graph.locator('.node').count() == 8, 'PCM includes eight actual nodes')
                graph.locator('.node').first.focus()
                page.keyboard.press('Enter')
                expect(graph.locator('.inspector')).to_be_visible()
                check('原始核验状态' in graph.locator('.inspector').inner_text(), 'Graph keyboard selection retains raw status')
                graph.get_by_role('combobox', name='技术分支').select_option('称重法')
                check(graph.locator('.node').count() == 3, 'Graph branch filter')
                for case_label in ['CO/CO₂', '液流']:
                    page.get_by_role('combobox', name='专题案例').click()
                    options = page.get_by_role('option')
                    target = next((options.nth(i) for i in range(options.count()) if case_label in options.nth(i).inner_text()), None)
                    if target is None:
                        # Full case names vary; select the next actual manifest entry.
                        target = options.nth(1 if case_label == 'CO/CO₂' else 2)
                    target.click()
                    diagram.locator('svg > g[data-node-id]').first.wait_for()
                    check(diagram.locator('svg > g[data-node-id]').count() == 8, 'Additional actual case: ' + case_label)
                    check(page.get_by_role('button', name='原论文主图 PDF', exact=True).count() == 1, 'Case PDF download preserved: ' + case_label)
                # Search, empty results, pagination and state after navigation.
                page.get_by_role('button', name='语料库', exact=True).click()
                library = page.frame_locator('iframe').first
                library.get_by_role('searchbox', name='搜索文献').fill('脂肪类复合相变')
                expect(library.locator('.paper-row')).to_have_count(1)
                check('脂肪' in library.locator('.inspector h4').inner_text(), 'Search inspector matches visible paper')
                library.get_by_role('searchbox', name='搜索文献').fill('NO_MATCH_20261020')
                expect(library.locator('.paper-row')).to_have_count(0)
                check(library.locator('.inspector h4').count() == 0, 'Empty search removes unrelated inspector')
                library.get_by_role('button', name='清除', exact=True).click()
                first = library.locator('.paper-row').first.inner_text()
                library.get_by_role('button', name='下一页', exact=True).click()
                check(library.locator('.paper-row').first.inner_text() != first, 'Library pagination')
                library.get_by_role('searchbox', name='搜索文献').fill('脂肪类复合相变')
                page.get_by_role('button', name='评测报告', exact=True).click()
                evaluation = page.frame_locator('iframe').first
                evaluation.locator('tbody tr').first.wait_for()
                evaluation.get_by_role('combobox', name='模式').select_option('Q1')
                expect(evaluation.locator('tbody tr')).to_have_count(2)
                evaluation.get_by_role('button', name='查看', exact=True).first.click()
                check('原始批次' in evaluation.locator('.inspector').inner_text(), 'Failure inspector contains actual attempt')
                page.get_by_role('button', name='语料库', exact=True).click()
                library.get_by_role('searchbox', name='搜索文献').wait_for()
                check(library.get_by_role('searchbox', name='搜索文献').input_value() == '脂肪类复合相变', 'Filter survives page navigation')
                # Isolated application: generation, failure, multi-turn and restart.
                test_page = context.new_page()
                test_page.on('pageerror', lambda error: report['jsErrors'].append(str(error)))
                test_page.set_default_timeout(20000)
                test_page.goto('http://localhost:8521')
                test_page.get_by_role('button', name='设置', exact=True).click()
                test_page.get_by_role('button', name='初始化 / 重新连接服务', exact=True).click()
                expect(test_page.get_by_text('问答服务：已初始化', exact=True)).to_be_visible()
                check(True, 'Service status updates in the initialization render')
                test_page.keyboard.press('Escape')
                test_page.get_by_role('textbox', name='研究问题', exact=True).fill('未提交的研究草稿')
                test_page.get_by_role('button', name='语料库', exact=True).click()
                test_page.frame_locator('iframe').first.locator('.paper-row').first.wait_for()
                test_page.get_by_role('button', name='研究问答', exact=True).click()
                expect(test_page.get_by_role('textbox', name='研究问题', exact=True)).to_have_value('未提交的研究草稿')
                check(True, 'Unsubmitted question draft survives navigation')
                test_page.get_by_role('button', name='设置', exact=True).click()
                test_page.get_by_text('迭代闭环模式（实验）', exact=True).click()
                page_keyboard = test_page.keyboard
                page_keyboard.press('Escape')
                test_page.get_by_role('button', name='语料库', exact=True).click()
                test_page.frame_locator('iframe').first.locator('.paper-row').first.wait_for()
                test_page.get_by_role('button', name='研究问答', exact=True).click()
                test_page.get_by_role('button', name='设置', exact=True).click()
                check(test_page.get_by_role('checkbox', name='迭代闭环模式（实验）', exact=True).is_checked(), 'Explicit experimental preference survives navigation')
                test_page.get_by_text('迭代闭环模式（实验）', exact=True).click()
                page_keyboard.press('Escape')
                test_page.get_by_role('textbox', name='研究问题', exact=True).fill('测试问题')
                test_page.get_by_role('button', name='开始研究', exact=True).last.click()
                expect(test_page.get_by_role('button', name='新建问题', exact=True)).to_be_disabled()
                test_reader = test_page.frame_locator('iframe').first
                test_reader.locator('.markdown').filter(has_text='已保存的测试回答').wait_for()
                expect(test_page.get_by_role('button', name='新建问题', exact=True)).to_be_enabled()
                test_reader.locator('.katex').first.wait_for()
                test_reader.locator('.markdown table').wait_for()
                check(test_reader.locator('.katex').count() > 0, 'Math renders locally')
                check(test_reader.locator('.markdown table').count() == 1, 'Markdown table renders')
                check(test_reader.locator('.markdown script').count() == 0 and not test_reader.locator('html').evaluate('()=>window.untrustedExecuted'), 'Answer HTML is not executable')
                test_page.get_by_text('展开图谱、方法版图与执行流程', exact=True).click()
                expect(test_page.get_by_role('tab', name='图谱与方法版图', exact=True)).to_be_visible()
                check(test_page.locator('[data-testid="stException"]').count() == 0, 'Preserved candidate evidence graph renders without nested-expander regression')
                check_graph_colors(test_page.locator('.fb-history-graph'), 'Candidate evidence graph')
                test_page.get_by_role('textbox', name='继续研究', exact=True).fill('第二问')
                test_page.get_by_role('button', name='继续提问', exact=True).click()
                expect(test_page.get_by_role('button', name='新建问题', exact=True)).to_be_enabled()
                test_page.get_by_role('combobox', name='当前轮次').wait_for()
                check(True, 'Multi-turn view retained')
                test_page.get_by_role('textbox', name='继续研究', exact=True).fill('测试失败')
                test_page.get_by_role('button', name='继续提问', exact=True).click()
                test_page.get_by_text('本次生成未完成：测试连接中断', exact=True).wait_for()
                check(True, 'Failed generation is visible and retained')
                check_no_failure_replay_error(test_page, 'Failed generation has no component render error')
                before = Path(folder, 'src/data/chat_history.jsonl').read_bytes()
                test_page.reload()
                test_page.get_by_role('button', name='历史对话', exact=True).click()
                test_page.get_by_role('button', name='打开历史', exact=True).click()
                test_page.frame_locator('iframe').first.locator('.answer').wait_for()
                check(before == Path(folder, 'src/data/chat_history.jsonl').read_bytes(), 'Restart history replay is read-only')
                check_no_failure_replay_error(test_page, 'Failure history replay has no component render error')
                check(not report['jsErrors'], 'No JavaScript errors')
                check(not report['remoteRequests'], 'No external application assets; generation uses only the test fixture')
                browser.close()
            report['passed'] = True
        finally:
            if not report.get('passed') and 'test_page' in locals():
                try:
                    test_page.screenshot(path=str(OUT / 'failed_fixture.png'), full_page=True)
                    (OUT / 'failed_fixture_text.txt').write_text(test_page.locator('body').inner_text(), encoding='utf-8')
                    candidate = Path(folder, 'src/data/chat_history.jsonl')
                    if candidate.exists():
                        (OUT / 'failed_fixture_history.jsonl').write_bytes(candidate.read_bytes())
                except Exception:
                    pass
            proc.terminate()
            proc.wait(timeout=20)
            log.close()
            OUT.mkdir(exist_ok=True, parents=True)
            (OUT / 'browser_acceptance.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f"Browser checks: {len(report['checks'])}; passed: {report.get('passed', False)}")


if __name__ == '__main__':
    main()
