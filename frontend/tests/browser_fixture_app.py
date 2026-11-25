"""Explicit test-only entry: isolated history and a deterministic conversation stub.

Never imported by frontend_app.py. This process cannot call a production model.
"""
import json
import os
import sys
import tempfile
import time
import builtins
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))

from frontend import controller, data
from frontend.app import main
from frontend.tests.test_frontend import FakeConversation, temporary_storage

test_home = Path(os.environ['FLOWBD_UI_TEST_HOME']).resolve()
if not test_home.is_relative_to(Path(tempfile.gettempdir()).resolve()):
    raise RuntimeError('Browser fixture requires a temporary project directory.')
history = test_home / 'src/data/chat_history.jsonl'
if not history.exists():
    history.parent.mkdir(parents=True, exist_ok=True)
    original = PROJECT / 'src/data/chat_history.jsonl'
    rows = [json.loads(line) for line in original.read_text(encoding='utf-8').splitlines() if line.strip()]
    saved = next(r for r in reversed(rows) if r['question'].startswith('扩散-渗出圈法用于评价什么') and 'Ref-20' in r.get('answer', ''))
    history.write_text(json.dumps(saved, ensure_ascii=False) + '\n', encoding='utf-8')


class BrowserConversation(FakeConversation):
    def run_conversation(self, question, enable_first_principles=False):
        self.failure = '测试失败' in question
        for state in super().run_conversation(question, enable_first_principles):
            time.sleep(.7)
            if state.final_answer:
                state.final_answer += '\n\n公式：$E=mc^2$。\n\n|材料|记录|\n|---|---|\n|测试材料|保留来源|\n\n<script>window.untrustedExecuted=true</script>'
            yield state


fixture_mode = os.environ.get('FLOWBD_UI_FIXTURE', '')
if fixture_mode == 'missing-data':
    data.METHODS = test_home / 'missing-methods'
    data.SUITE = test_home / 'missing-evaluation'
    data.LINEAGE = test_home / 'missing-lineage'
    data.CORPUS = test_home / 'fixture-papers'
    (data.CORPUS / '测试本地文献').mkdir(parents=True, exist_ok=True)
    (data.CORPUS / '测试本地文献/full.md').write_text('这是隔离测试中已保存的本地全文。', encoding='utf-8')
    (data.CORPUS / '测试无全文文献').mkdir(exist_ok=True)


def fixture_storage():
    adapter = temporary_storage(test_home)
    if fixture_mode == 'history-write-error':
        def readonly_open(path, mode='r', *args, **kwargs):
            if any(flag in mode for flag in 'awx+'):
                raise PermissionError('isolated fixture: write denied')
            return builtins.open(path, mode, *args, **kwargs)
        adapter.save_chat_log.__globals__['open'] = readonly_open
    return adapter


controller.storage = fixture_storage
controller.conversation_factory = BrowserConversation
controller.postprocess = lambda *_: (None, [])
main()
