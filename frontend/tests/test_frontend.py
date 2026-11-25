"""Behavior checks using actual legacy persistence in an isolated temporary project."""
import copy
import hashlib
import json
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from frontend import controller, data, legacy


class Session(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as error:
            raise AttributeError(key) from error

    def __setattr__(self, key, value):
        self[key] = value


def temporary_storage(project):
    original = legacy.helpers()
    env = dict(original.load_chat_history.__globals__, PROJECT_ROOT=str(project))
    for name in original._source_functions:
        function = getattr(original, name)
        env[name] = types.FunctionType(function.__code__, env, name, function.__defaults__, function.__closure__)
    return types.SimpleNamespace(**env)


class FakeConversation:
    def __init__(self, failure=False):
        self.failure = failure
        self.calls = []

    def run_conversation(self, question, enable_first_principles=False):
        self.calls.append((question, enable_first_principles))
        state = types.SimpleNamespace(final_answer='', stage_1_complete=True, doc_sources=[], agent_logs=['测试检索'])
        yield state
        time.sleep(.03)
        if self.failure:
            raise RuntimeError('测试连接中断')
        state.final_answer = '已保存的测试回答。[Ref-7]'
        state.doc_sources = [{'ref_id': 7, 'source': '测试文献', 'content': '原文' * 1000}, {'ref_id': 20, 'source': '其他来源', 'content': '完整保留引用列表'}]
        state.stage_2_complete = state.stage_3_complete = state.stage_4_complete = True
        state.evidence_graph_snapshot = {'nodes': [{'id': 'n', 'status': 'candidate'}], 'edges': []}
        yield state

    def run_iterative_conversation(self, question, session_id, summarized_answer):
        self.calls.append(('iterative', session_id, summarized_answer))
        yield from self.run_conversation(question)


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.project = Path(self.folder.name)
        self.store = temporary_storage(self.project)
        self.state = Session()
        self.fake = FakeConversation()
        self.patches = [patch.object(controller, 'st', types.SimpleNamespace(session_state=self.state)),
                        patch.object(controller, 'storage', return_value=self.store),
                        patch.object(controller, 'conversation_factory', return_value=self.fake),
                        patch.object(controller, 'add_script_run_ctx', lambda thread: None),
                        patch.object(controller, 'postprocess', return_value=(None, []))]
        for item in self.patches:
            item.start()
        controller.bootstrap()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.folder.cleanup()

    def finish(self):
        deadline = time.monotonic() + 3
        while not self.state.fb_job['done'] and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertTrue(controller.finalize())

    def test_browsing_does_not_initialize_and_defaults_stay_off(self):
        self.assertIsNone(self.state.agent_conversation)
        self.assertFalse(self.state.iterative_mode)
        self.assertFalse(self.state.eg_summarized_answer)
        self.assertFalse(self.state.first_principles_enabled)
        self.assertEqual(self.fake.calls, [])

    def test_one_submission_persists_once_and_replays_legacy_fields(self):
        self.assertTrue(controller.submit('问题'))
        self.assertFalse(controller.submit('重复提交'))
        self.finish()
        self.assertFalse(controller.finalize())
        self.assertEqual(len(self.fake.calls), 1)
        rows = self.store.load_chat_history()
        self.assertEqual(len(rows), 1)
        message = rows[0]['messages'][-1]
        self.assertEqual([s['ref_id'] for s in message['doc_sources']], [7, 20])
        self.assertEqual(len(message['doc_sources'][0]['content']), 1600)
        self.assertEqual(message['evidence_graph']['nodes'][0]['status'], 'candidate')
        self.assertIn('stage_ms', message)
        self.assertIn('answer_quality', message)
        self.assertIn('logs', message)
        self.assertEqual(message['content'], self.state.messages[-1]['content'])

    def test_failure_is_saved_without_a_fake_successful_answer(self):
        self.fake.failure = True
        controller.submit('失败问题')
        self.finish()
        self.assertIn('生成未完成', self.state.messages[-1]['content'])
        self.assertEqual(len(self.store.load_chat_history()), 1)
        self.assertFalse(controller.busy())

    def test_actual_backend_declared_failure_stays_failed_and_retains_evidence(self):
        path=Path(__file__).with_name('fixtures')/'backend_declared_failure.json'
        row=json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(row['answer_quality']['generation_status'],'failed')
        backend=types.SimpleNamespace(final_answer=row['answer'],answer_quality=row['answer_quality'],
            doc_sources=row['doc_sources'],evidence_graph_snapshot=row['evidence_graph'],iterations=row['iterations'],eg_stop_reason=row['eg_stop_reason'])
        self.state.messages.append({'role':'user','content':row['question']})
        self.state.fb_job={'done':True,'finalized':False,'state':backend,'error':'','question':row['question'],'stage_ms':[1,2,3,4]}
        self.assertTrue(controller.finalize())
        self.assertIn('生成未完成',self.state.fb_error)
        message=self.state.messages[-1]
        self.assertIn('未通过完整性或来源检查',message['content'])
        self.assertEqual(message['answer_quality']['generation_status'],'failed')
        self.assertEqual(len(message['doc_sources']),len(row['doc_sources']))
        self.assertEqual(message['evidence_graph'],row['evidence_graph'])
        saved=self.store.load_chat_history()[0]['messages'][-1]
        self.assertEqual(saved['answer_quality']['generation_status'],'failed')
        self.assertFalse(controller.finalize())

    def test_multi_turn_history_new_chat_and_confirmed_deletion_use_temp_only(self):
        controller.submit('第一问')
        self.finish()
        controller.submit('第二问')
        self.finish()
        self.assertEqual(len(self.state.history), 1)
        self.assertEqual(len(self.state.history[0]['messages']), 4)
        controller.new_chat()
        self.assertEqual(len(self.state.history), 1)
        controller.select_history(0)
        self.assertEqual(len(self.state.messages), 4)
        self.assertIsNone(self.state.agent_conversation)
        controller.delete_history(0)
        self.assertEqual(self.store.load_chat_history(), [])
        self.assertEqual(self.state.messages, [])

    def test_iterative_summary_keeps_complete_source_list(self):
        self.state.iterative_mode = True
        self.state.eg_summarized_answer = True
        controller.submit('迭代问题')
        self.finish()
        self.assertEqual(self.fake.calls[0], ('iterative', 'pending_iterative', True))
        self.assertEqual(len(self.state.messages[-1]['doc_sources']), 2)

    def test_legacy_save_error_is_visible_without_losing_answer_or_retrying_generation(self):
        controller.submit('磁盘写入失败测试')
        with patch.dict(self.store.save_chat_log.__globals__, {'open': unittest.mock.Mock(side_effect=PermissionError('test write denied'))}):
            self.finish()
        self.assertFalse(controller.busy())
        self.assertFalse(controller.finalize())
        self.assertIn('未能确认写入', self.state.fb_error)
        self.assertIn('已保存的测试回答', self.state.messages[-1]['content'])
        self.assertEqual(len(self.state.fb_unsaved_messages), 1)
        self.assertEqual(self.store.load_chat_history(), [])
        self.assertEqual(len(self.fake.calls), 1)
        controller.new_chat()
        self.assertEqual(len(self.state.fb_unsaved_messages), 1)

    def test_legacy_delete_error_keeps_visible_history_and_file(self):
        controller.submit('删除权限测试')
        self.finish()
        path = self.project / 'src/data/chat_history.jsonl'
        before = path.read_bytes()
        with patch.dict(self.store.delete_chat_log_entry.__globals__, {'open': unittest.mock.Mock(side_effect=PermissionError('test denied'))}):
            self.assertFalse(controller.delete_history(0))
        self.assertEqual(len(self.state.history), 1)
        self.assertEqual(path.read_bytes(), before)
        self.assertIn('删除未完成', self.state.fb_error)

    def test_legacy_read_error_is_visible_and_recovers_when_access_restored(self):
        controller.submit('读取权限测试')
        self.finish()
        self.state.fb_history_loaded = False
        with patch.dict(self.store.load_chat_history.__globals__, {'open': unittest.mock.Mock(side_effect=PermissionError('test denied'))}):
            controller.bootstrap()
        self.assertFalse(self.state.fb_history_loaded)
        self.assertIn('暂时无法读取', self.state.fb_error)
        controller.bootstrap()
        self.assertTrue(self.state.fb_history_loaded)
        self.assertEqual(len(self.state.history), 1)
        self.assertEqual(self.state.fb_error, '')


class AdapterTests(unittest.TestCase):
    def test_missing_auxiliary_metadata_keeps_local_full_text_browsable(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            corpus = base / 'papers'
            methods = base / 'methods'
            methods.mkdir()
            (corpus / '测试论文').mkdir(parents=True)
            (corpus / '测试论文/full.md').write_text('已保存的本地全文', encoding='utf-8')
            (corpus / '无全文论文').mkdir()
            with patch.object(data, 'CORPUS', corpus), patch.object(data, 'METHODS', methods):
                rows = data.papers()
                self.assertEqual(len(rows), 2)
                self.assertTrue(all(r['year'] == '' and r['methods'] == [] for r in rows))
                self.assertEqual(sum(r['has_text'] for r in rows), 1)
                self.assertEqual(data.paper_text('测试论文'), '已保存的本地全文')

    def test_source_identity_is_not_positional_and_missing_ids_not_invented(self):
        sources = [{'ref_id': 20, 'content': 'a'}, {'ref_id': 7, 'content': 'b'}, {'content': 'legacy'}]
        before = copy.deepcopy(sources)
        self.assertEqual([r['ref_id'] for r in data.source_views(sources)], [20, 7, None])
        self.assertEqual(sources, before)

    def test_raw_failure_reason_from_saved_log(self):
        reason = data.failure_reason({'record': {'logs': "['开始', '答案生成失败: 原因：400 cm 未匹配']"}})
        self.assertEqual(reason, '原因：400 cm 未匹配')

    @unittest.skipUnless((data.SUITE / 'completion_receipt_20261015.json').is_file(), 'Private evaluation dataset is not distributed')
    def test_real_evaluation_keeps_denominator_and_all_failed_attempts(self):
        result = data.evaluation()
        self.assertEqual(result['receipt']['formal_jobs'], 158)
        self.assertEqual(len(result['issues']), 6)
        self.assertTrue(all(i.get('record') for i in result['issues']))
        self.assertFalse(result['receipt']['quality_acceptance_met'])

    def test_case_payload_preserves_raw_status_and_edge_classes(self):
        cases = data.lineage_cases()
        self.assertTrue({'pcm_stability', 'co_co2_hydrogenation', 'aorfb_active_materials'} <= {c['case_id'] for c in cases})
        for case in cases:
            payload = data.lineage_case(case['case_id'])
            self.assertTrue(payload['nodes'])
            self.assertTrue(all('verification_status' in n for n in payload['nodes']))
            self.assertTrue(all('relation_class' in e for e in payload['edges']))

    def test_local_path_rejects_traversal(self):
        self.assertIsNone(data.source_path({'source': '../README.md'}))
        self.assertIsNone(data.source_path({'source': str(data.PROJECT / 'README.md')}))

    @unittest.skipUnless(data.CORPUS.is_dir(), 'Private corpus is not distributed')
    def test_real_corpus_is_complete_and_unknown_year_not_fabricated(self):
        rows = data.papers()
        self.assertEqual(len(rows), len([p for p in data.CORPUS.iterdir() if p.is_dir()]))
        self.assertTrue(all(not p['year'] or len(p['year']) == 4 for p in rows))
        self.assertTrue(all(p['category'] for p in rows))


if __name__ == '__main__':
    unittest.main()
