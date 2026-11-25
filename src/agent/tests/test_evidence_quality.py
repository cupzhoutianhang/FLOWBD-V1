"""Meaningful regressions for real retrieval shapes and citation identity."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from agent.evidence_sources import SourceRegistry, prepare_sources
from agent.answer_grounding import check_citations
from agent.corpus_evidence import lineage_sources, search_corpus
from agent.evidence_graph import EvidenceExtractor, EvidenceGraphStore, merge_round


class LLM:
    def __init__(self, data):
        self.data = data

    def call_llm(self, **kwargs):
        return json.dumps(self.data, ensure_ascii=False)


class TestEvidenceQuality(unittest.TestCase):
    def test_unrelated_new_question_does_not_inject_previous_sources(self):
        registry = SourceRegistry().register([{"source": "甲论文", "content": "甲材料效率87%。"}])
        state = SimpleNamespace(vector_chunks=[{"source": "乙论文", "content": "乙材料容量90%。"}],
                                doc_sources=[], lineage_sources=[])
        prepare_sources(state, registry)
        self.assertEqual([d["source"] for d in state.doc_sources], ["乙论文"])
        self.assertEqual(state.doc_sources[0]["ref_id"], 2)
        self.assertEqual(len(registry.documents()), 2)

    def test_quote_id_binds_exact_ocr_source_without_rewriting(self):
        docs = SourceRegistry().register([{"source": "论文", "content": "基盐加热温度 $3 0 0 \\mathrm{C}$。"}]).documents()
        data = {"entities": [{"name": "高温熔融法", "type": "METHOD", "observations": [
            {"text": "加热温度300", "quote_id": "Q0001"}]}]}
        ex = EvidenceExtractor(LLM(data))
        sid = docs[0]["chunks"][0]["source_id"]
        result = ex.extract("工艺", f"[{sid}] 原文", "", docs, 1)
        self.assertEqual(result.entities[0]["_prov"].quote, docs[0]["content"])

    def test_invalid_quote_id_is_rejected(self):
        docs = SourceRegistry().register([{"source": "论文", "content": "材料效率87%。"}]).documents()
        data = {"entities": [{"name": "材料", "type": "MATERIAL", "observations": [
            {"text": "效率87%", "quote_id": "Q9999"}]}]}
        self.assertFalse(EvidenceExtractor(LLM(data)).extract("问题", "", "", docs, 1))

    def test_relation_cannot_invent_number_from_real_quote(self):
        data = {"relations": [{"src": "A", "dst": "B", "type": "SUPPORTS",
                                "obs": "效率98%", "evidence_quote": "材料效率87%。"}]}
        docs = SourceRegistry().register([{"source": "论文", "content": "材料效率87%。"}]).documents()
        ex = EvidenceExtractor(LLM(data))
        self.assertFalse(ex.extract("问题", "", "", docs, 1))
        self.assertTrue(any("数值" in e for e in ex.last_errors))

    def test_different_sample_or_conditions_are_not_conflicts(self):
        from agent.evidence_graph.schema import EdgeRel, Provenance
        with tempfile.TemporaryDirectory() as tmp:
            store = EvidenceGraphStore("test", base_dir=tmp)
            a = EdgeRel("a", "method-a", "capacity", "SUPPORTS", obs="提升至90%",
                        prov=Provenance(1, "论文甲", "25℃提升至90%", 1))
            b = EdgeRel("b", "method-b", "capacity", "SUPPORTS", obs="下降至40%",
                        prov=Provenance(2, "论文乙", "25℃下降至40%", 1))
            self.assertFalse(store.comparable_conflict(a, b))
            b.src = a.src
            b.prov.quote = "50℃下降至40%"
            self.assertFalse(store.comparable_conflict(a, b))
            b.prov.quote = "25℃下降至40%"
            self.assertTrue(store.comparable_conflict(a, b))
            b.obs = '下降至40mAh/g'
            self.assertFalse(store.comparable_conflict(a, b))

    def test_instant_json_payload_and_length_rejection(self):
        from unittest.mock import patch
        from agent.structured_llm import call_structured
        llm = SimpleNamespace(model="kimi-k2.6", base_url="https://api.moonshot.cn/v1", api_key="test-key")
        response = SimpleNamespace(status_code=200)
        from unittest.mock import MagicMock
        response = MagicMock(status_code=200)
        response.json.return_value = {"choices": [{"finish_reason": "length", "message": {"content": "{bad"}}],
                                      "usage": {"total_tokens": 10}}
        with patch("requests.post", return_value=response) as post:
            result = call_structured(llm, "JSON问题")
        self.assertIn("拒绝", result)
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["temperature"], 0.6)
        self.assertEqual(payload["thinking"], {"type": "disabled"})
        self.assertEqual(payload['response_format'], {'type': 'json_object'})
        self.assertEqual(llm.structured_calls[0]["usage"]["total_tokens"], 10)

    def test_thinking_stream_requires_finish_and_captures_usage(self):
        from unittest.mock import patch, MagicMock
        from agent.structured_llm import call_structured
        llm = SimpleNamespace(model='kimi-k2.6', base_url='https://api.moonshot.cn/v1', api_key='test-key')
        response = MagicMock(status_code=200)
        response.iter_lines.return_value = iter([
            b'data: {"choices":[{"delta":{"reasoning_content":"private reasoning"}}]}',
            b'data: {"choices":[{"delta":{"content":"{\\"ok\\":true}"}}]}',
            b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}',
            b'data: {"choices":[],"usage":{"total_tokens":42}}', b'data: [DONE]'])
        with patch('requests.post', return_value=response) as post:
            self.assertEqual(call_structured(llm, 'audit', thinking=True), '{"ok":true}')
        self.assertTrue(post.call_args.kwargs['stream'])
        self.assertEqual(llm.structured_calls[0]['usage']['total_tokens'], 42)
        response.iter_lines.side_effect = lambda: iter([b'data: {"choices":[{"delta":{"content":"{}"}}]}'])
        with patch('requests.post', return_value=response):
            self.assertTrue(call_structured(llm, 'audit', thinking=True).startswith('❌'))

    def test_method_comparison_cannot_become_refutes(self):
        from agent.evidence_graph import EdgeNode, node_id
        from agent.evidence_graph.schema import Provenance
        from agent.evidence_graph.extractor import ExtractionResult
        with tempfile.TemporaryDirectory() as tmp:
            store = EvidenceGraphStore("test", base_dir=tmp)
            for name in ("高温熔融法", "两步水溶液法"):
                store.upsert_node(EdgeNode(node_id("METHOD", name), "METHOD", name))
            extraction = ExtractionResult(relations=[{"src": "高温熔融法", "dst": "两步水溶液法",
                  "type": "REFUTES", "obs": "高温熔融法热稳定性更高",
                  "_prov": Provenance(1, "论文", "高温熔融法制备的纳米流体热稳定性高于两步水溶液法。", 1)}])
            report = merge_round(store, extraction, 1)
            self.assertEqual(len(store.edges), 0)
            self.assertTrue(any("语义端点" in e for e in report.dropped))

    def test_query_keeps_hydrogen_reaction_and_conditions(self):
        # Load only this production method so the regression needs no model initialization.
        import ast
        p = Path(__file__).resolve().parents[1] / "part5_multiagent_integration.py"
        tree = ast.parse(p.read_text(encoding="utf-8"))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "MultiSourceRetrievalAgent")
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_build_vector_query")
        namespace = {"AgentPipelineState": SimpleNamespace}
        exec(compile(ast.Module([method], type_ignores=[]), str(p), "exec"), namespace)
        state = SimpleNamespace(original_question="如何在25℃抑制铁铬电池的析氢反应？",
                                extracted_entities=["铁铬电池"], query_intent="mechanism", molecule_names=[])
        query = namespace["_build_vector_query"](None, state)
        self.assertIn(state.original_question, query)
        self.assertIn("hydrogen evolution reaction", query)
        self.assertIn("iron chromium", query)

    def test_grouped_references_expand_before_footer_and_validation(self):
        from agent.answer_grounding import normalize_citations
        answer = normalize_citations("结论[Ref-4, Ref-13, Ref-18]及[Ref-1,2]")
        self.assertEqual(answer, "结论[Ref-4][Ref-13][Ref-18]及[Ref-1][Ref-2]")
        result = check_citations(answer, [{"ref_id": i} for i in (1, 2, 4, 13)])
        self.assertEqual(result["invalid_refs"], [18])

    def test_authoritative_borrower_is_not_rewritten_to_previous_author(self):
        from agent.lineage_answer import render_lineage_answer
        docs = SourceRegistry().register(lineage_sources("扩散-渗出圈法被哪些方法借鉴了")).documents()
        answer = render_lineage_answer("扩散-渗出圈法被哪些方法借鉴了", docs)
        self.assertIn("Zhou", answer)
        self.assertIn("ADAPTS", answer)
        self.assertIn("符合问题范围的关系有 1 条", answer)
        self.assertNotIn("孙建忠等将", answer)
        self.assertFalse(check_citations(answer, docs)["invalid_refs"])

    def test_nonexistent_replaces_not_fabricated(self):
        from agent.lineage_answer import render_lineage_answer
        question = "谱系中是否记录了扩散-渗出圈法被水热法替代（REPLACES）的关系？"
        docs = SourceRegistry().register(lineage_sources(question)).documents()
        answer = render_lineage_answer(question, docs)
        self.assertIn("没有记录", answer)
        self.assertNotIn("**REPLACES**", answer)
        self.assertIn("**ADAPTS**", answer)

    def test_other_four_cases_not_upgraded_to_confirmed(self):
        from agent.lineage_answer import render_lineage_answer
        question = "扩散-渗出圈法之外，系统谱系中还记录了哪些方法演化关系？"
        docs = SourceRegistry().register(lineage_sources(question)).documents()
        answer = render_lineage_answer(question, docs)
        self.assertIn("符合问题范围的关系有 4 条", answer)
        self.assertIn("**REPLACES**", answer)
        self.assertIn("**EXTENDS**", answer)
        self.assertIn("accepted", answer)
        self.assertFalse(check_citations(answer, docs)["invalid_refs"])
        self.assertIsNone(render_lineage_answer("纳米熔盐的制备步骤是什么", docs))

    def test_title_scope_excludes_other_battery_and_keeps_multiple_papers(self):
        from agent.corpus_evidence import title_filtered_recall
        class Collection:
            name = "test_collection"
            schema = SimpleNamespace(fields=[SimpleNamespace(name=n) for n in
                                            ("id", "block_type", "original_filename", "content", "doc_id")])
            def query(self, **kwargs):
                return [{"id": i, "doc_id": title, "original_filename": title,
                         "content": "Hydrogen evolution reaction HER suppression"} for i, title in enumerate([
                             "Iron-chromium HER suppression", "Iron-chromium HER suppression",
                             "Iron-chromium HER suppression", "Glycine for iron-chromium battery",
                             "Chromium doping for zinc-manganese batteries"])]
        rows = title_filtered_recall(Collection(), "如何抑制铁铬电池的析氢反应")
        self.assertEqual(len(rows), 3)
        self.assertFalse(any("zinc" in r["source"] for r in rows))
        self.assertTrue(any("Glycine" in r["source"] for r in rows))

    def test_sources_exist_before_fusion_and_stable_across_questions(self):
        registry = SourceRegistry()
        state = SimpleNamespace(vector_chunks=[{"source": "甲论文", "parent_id": "a",
                                                  "content": "甲材料效率87%。"}],
                                doc_sources=[], lineage_sources=[])
        prepare_sources(state, registry)
        original = state.doc_sources[0]
        state.vector_chunks = [{"source": "乙论文", "parent_id": "b", "content": "乙材料效率90%。"}]
        prepare_sources(state, registry)
        self.assertEqual(len(state.doc_sources), 2)
        self.assertEqual(state.doc_sources[0]["ref_id"], original["ref_id"])
        self.assertEqual(state.doc_sources[0]["chunks"][0]["source_id"], original["chunks"][0]["source_id"])
        restored = SourceRegistry(json.loads(json.dumps(registry.to_dict())))
        self.assertEqual(restored.documents(), registry.documents())

    def test_repeat_chunk_dedup_and_changed_content_not_overwrite(self):
        registry = SourceRegistry()
        a = {"source": "论文", "parent_id": "1", "content": "原始证据"}
        registry.register([a, a])
        self.assertEqual(len(registry.chunks), 1)
        registry.register([{**a, "content": "更新内容"}])
        self.assertEqual(len(registry.chunks), 2)
        self.assertEqual({c["ref_id"] for c in registry.chunks.values()}, {1})

    def test_case_changes_in_chemical_source_are_different_immutable_chunks(self):
        registry = SourceRegistry()
        registry.register([{'source':'论文','parent_id':'1','content':'Co 催化剂提高效率。'},
                           {'source':'论文','parent_id':'1','content':'CO 催化剂提高效率。'}])
        self.assertEqual(len(registry.chunks), 2)
        self.assertEqual({c['content'] for c in registry.chunks.values()}, {'Co 催化剂提高效率。','CO 催化剂提高效率。'})

    def test_individual_observation_has_own_original_quote(self):
        registry = SourceRegistry().register([
            {"source": "甲论文", "content": "材料效率87%。"},
            {"source": "乙论文", "content": "材料容量保持率90%。"}])
        chunks = list(registry.chunks.values())
        data = {"entities": [{"name": "材料", "type": "MATERIAL", "observations": [
            {"text": "效率87%", "evidence_quote": "材料效率87%。", "source_id": chunks[0]["source_id"]},
            {"text": "容量保持率90%", "evidence_quote": "材料容量保持率90%。", "source_id": chunks[1]["source_id"]}]}]}
        result = EvidenceExtractor(LLM(data)).extract("问题", "", "", registry.documents(), 1)
        with tempfile.TemporaryDirectory() as tmp:
            store = EvidenceGraphStore("test", base_dir=tmp)
            merge_round(store, result, 1)
            obs = next(iter(store.nodes.values())).observations
            self.assertEqual([o.prov.paper_title for o in obs], ["甲论文", "乙论文"])
            self.assertEqual([o.prov.quote for o in obs], ["材料效率87%。", "材料容量保持率90%。"])
            store.save()
            self.assertEqual(EvidenceGraphStore("test", base_dir=tmp).snapshot()["nodes"], store.snapshot()["nodes"])

    def test_context_without_source_cannot_create_ref_zero(self):
        data = {"entities": [{"name": "材料", "type": "MATERIAL", "observations": ["效率87%"]}]}
        ex = EvidenceExtractor(LLM(data))
        self.assertFalse(ex.extract("问题", "材料效率87%。", "", [], 1))

    def test_original_slice_preserves_whitespace_and_case(self):
        ex = EvidenceExtractor(LLM({}))
        p = ex._resolve_quote("fe 效率87%", [{"ref_id": 1, "source": "论文",
                                               "content": "原文 Fe  效率87% 后文"}], 1)
        self.assertEqual(p.quote, "Fe  效率87%")

    def test_same_quote_in_wrong_source_rejected(self):
        ex = EvidenceExtractor(LLM({}))
        docs = SourceRegistry().register([{"source": "论文", "content": "材料效率87%。"}]).documents()
        self.assertIsNone(ex._resolve_quote("效率87%", docs, 1, "SRC:wrong"))

    def test_invented_number_rejected_even_when_quote_exists(self):
        data = {"entities": [{"name": "材料", "type": "MATERIAL", "observations": [
            {"text": "效率98%", "evidence_quote": "材料效率87%。"}]}]}
        docs = SourceRegistry().register([{"source": "论文", "content": "材料效率87%。"}]).documents()
        ex = EvidenceExtractor(LLM(data))
        self.assertFalse(ex.extract("问题", "材料效率87%。", "", docs, 1))
        self.assertTrue(any("数值" in e for e in ex.last_errors))

    def test_ambiguous_same_name_different_types_not_connected(self):
        from agent.evidence_graph import EdgeNode, node_id
        with tempfile.TemporaryDirectory() as tmp:
            store = EvidenceGraphStore("test", base_dir=tmp)
            for kind in ("METHOD", "MATERIAL"):
                store.upsert_node(EdgeNode(id=node_id(kind, "X"), ntype=kind, name="X"))
            self.assertIsNone(store.find_node("X"))

    def test_citations_flag_invalid_refs_without_claiming_semantic_verification(self):
        result = check_citations("结论[Ref-9]", [{"ref_id": 1}])
        self.assertEqual(result["invalid_refs"], [9])
        self.assertFalse(result["semantic_support_verified"])

    def test_final_lineage_excludes_machine_accepted_false_positive(self):
        content = "\n".join(s["content"] for s in lineage_sources("有哪些谱系演化关系？"))
        self.assertIn("FINAL_STORAGE_REPLACES_01", content)
        self.assertNotIn("SEHA", content)
        self.assertNotIn("Wang等硝酸溶剂热", content)

    def test_parser_uses_bounded_json_and_preserves_original_question(self):
        from unittest.mock import patch
        from agent.part5_multiagent_integration import QuestionParsingAgent, AgentPipelineState
        state = AgentPipelineState('parse', '如何抑制铁铬电池析氢？')
        payload = json.dumps({'entities': ['铁铬电池', '析氢'], 'query_intent': 'mechanism'})
        with patch('agent.structured_llm.call_structured', return_value=payload) as call:
            QuestionParsingAgent(LLM({})).parse(state)
        self.assertLessEqual(call.call_args.kwargs['max_tokens'], 1600)
        self.assertEqual(state.parsed_question, state.original_question)
        self.assertEqual(state.extracted_entities, ['铁铬电池', '析氢'])

    def test_valid_json_with_invalid_graph_schema_is_safe_and_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'bad.json').write_text('[]', encoding='utf-8')
            store = EvidenceGraphStore('bad', base_dir=tmp)
            self.assertEqual(store.stats()['nodes'], 0)
            self.assertEqual(store.meta['load_error'], 'invalid_graph_schema')

    def test_reused_graph_entities_do_not_call_llm_parser_again(self):
        import ast
        from typing import Dict, List
        from unittest.mock import Mock
        path = Path(__file__).resolve().parents[2] / 'graph_rag/graph_qa_v2.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        methods = [n for cls in tree.body if isinstance(cls, ast.ClassDef) for n in cls.body
                   if isinstance(n, ast.FunctionDef) and n.name in {'get_raw_search_results', 'get_raw_search_results_from_entities'}]
        namespace = {'Dict': Dict, 'List': List}
        exec(compile(ast.Module(body=methods, type_ignores=[]), str(path), 'exec'), namespace)
        owner = SimpleNamespace(reasoning_engine=True, question_analyzer=Mock(), _intelligent_search=Mock(return_value={'entities': []}))
        owner.get_raw_search_results = lambda q, analysis=None: namespace['get_raw_search_results'](owner, q, analysis)
        namespace['get_raw_search_results_from_entities'](owner, '原问题', ['铁铬', '铁铬', '析氢'], 'mechanism')
        owner.question_analyzer.analyze.assert_not_called()
        self.assertEqual(owner._intelligent_search.call_args.args[0]['entities'], ['铁铬', '析氢'])

    def test_memory_ranks_later_parameter_and_emits_relation_original_quote(self):
        from agent.evidence_graph import EdgeNode, node_id
        from agent.evidence_graph.schema import Observation, Provenance, EdgeRel
        with tempfile.TemporaryDirectory() as tmp:
            store = EvidenceGraphStore('memory', base_dir=tmp)
            a = EdgeNode(node_id('METHOD', '熔融法'), 'METHOD', '熔融法')
            b = EdgeNode(node_id('PROPERTY', '搅拌时间'), 'PROPERTY', '搅拌时间')
            store.upsert_node(a)
            store.upsert_node(b)
            for text in ['材料发生熔融', '可制备复合材料', '搅拌时间90 min']:
                store.append_observation(a.id, Observation(text=text, prov=Provenance(1, '原论文', text, 1, source_id='SRC:real')))
            store.upsert_edge(EdgeRel('r', a.id, b.id, 'ASSOCIATED_WITH', obs='搅拌时间90 min',
                              prov=Provenance(1, '原论文', '熔融法搅拌时间90 min。', 1, source_id='SRC:real')))
            summary = store.retrieve_from_graph(['熔融法的搅拌时间'], max_lines=3)
            self.assertIn('搅拌时间90 min', summary)
            self.assertIn('ASSOCIATED_WITH', summary)
            self.assertIn('熔融法搅拌时间90 min。', summary)
            self.assertLessEqual(len(summary.splitlines()), 3)

    def test_answer_audit_cannot_introduce_unquoted_number_or_ref(self):
        from unittest.mock import patch
        from agent.grounding_audit import audit_answer
        llm = SimpleNamespace(model='kimi-k2.6', base_url='https://api.moonshot.cn/v1')
        docs = SourceRegistry().register([{'source': '论文', 'content': '材料效率为87%，仅在25℃下测量。'}]).documents()
        data = {'review_complete': True, 'requirements': [], 'issues': [
            {'span_id': 'A0001', 'original_fragment': '效率98%[Ref-1]', 'replacement': '效率98%[Ref-9]', 'quote_ids': ['Q0001'], 'reason': '假修复'}]}
        with patch('agent.grounding_audit.call_structured', side_effect=[json.dumps(data),json.dumps({'review_complete':True,'verified_issue_ids':['I0001']})]):
            answer, audit = audit_answer(llm, '效率是多少', '效率98%[Ref-1]', docs, docs[0]['content'])
        self.assertNotIn('98', answer)
        self.assertNotIn('Ref-9', answer)
        self.assertFalse(audit['changes'][0]['repair_constraints_passed'])
        self.assertFalse(audit['semantic_support_verified'])

    def test_local_semantic_repair_preserves_other_supported_facts_and_citation(self):
        from unittest.mock import patch
        from agent.grounding_audit import audit_answer
        llm = SimpleNamespace(model='kimi-k2.6', base_url='https://api.moonshot.cn/v1')
        docs = SourceRegistry().register([{'source':'论文','content':'HiPIMS制备材料，效率87%。'}]).documents()
        text = 'HiPIMS（无证全称）制备材料，效率87%[Ref-1]'
        data={'review_complete':True,'requirements':[], 'issues':[{'span_id':'A0001',
              'original_fragment':'（无证全称）','replacement':'','quote_ids':['Q0001']}]}
        with patch('agent.grounding_audit.call_structured',side_effect=[json.dumps(data),json.dumps({'review_complete':True,'verified_issue_ids':['I0001']})]):
            answer,_=audit_answer(llm,'如何制备？',text,docs,docs[0]['content'])
        self.assertEqual(answer,'HiPIMS制备材料，效率87%[Ref-1]')

    def test_summary_audit_does_not_secretly_reintroduce_full_sources(self):
        from agent.grounding_audit import evidence_catalog
        docs = SourceRegistry().register([{'source': '论文', 'content': '材料效率87%。未选入摘要的温度900℃。'}]).documents()
        context = '观察：材料效率87%，原句=材料效率87%。)'
        catalog = evidence_catalog(docs, context, {1})
        self.assertTrue(catalog)
        self.assertNotIn('900', json.dumps(catalog, ensure_ascii=False))

    def test_unconfirmed_repair_cannot_delete_supported_answer(self):
        from unittest.mock import patch
        from agent.grounding_audit import audit_answer
        llm = SimpleNamespace(model='kimi-k2.6', base_url='https://api.moonshot.cn/v1')
        docs = SourceRegistry().register([{'source':'论文','content':'HiPIMS制备材料，效率87%。'}]).documents()
        text='HiPIMS制备材料，效率87%[Ref-1]'
        proposal={'review_complete':True,'issues':[{'span_id':'A0001','original_fragment':text,'replacement':'','quote_ids':['Q0001']}], 'requirements':[]}
        with patch('agent.grounding_audit.call_structured',side_effect=[json.dumps(proposal), '❌ 请求失败']):
            answer,metadata=audit_answer(llm,'如何制备？',text,docs,docs[0]['content'])
        self.assertEqual(answer,text)
        self.assertEqual(metadata['repair_confirmation_status'],'review_failed')
        self.assertTrue(metadata['unresolved_repairs'])

    def test_graph_screening_failed_review_does_not_pass_claims(self):
        from unittest.mock import patch
        from agent.grounding_audit import screen_graph
        llm = SimpleNamespace(model='kimi-k2.6', base_url='https://api.moonshot.cn/v1')
        with patch('agent.grounding_audit.call_structured', return_value='❌ 请求失败'):
            accepted, audit = screen_graph(llm, {'N0001': {'claim': '效率98%'}})
        self.assertEqual(accepted, set())
        self.assertEqual(audit['status'], 'review_failed')

    def test_specific_process_recalls_actual_method_paragraph(self):
        result = search_corpus("纳米熔盐储热材料的高温熔融法具体工艺步骤是什么？", ["纳米熔盐储热材料"])
        self.assertIn("高温熔融法高温熔融法制备", result[0]["content"])
        self.assertIn("石英坩埚", result[0]["content"])
        self.assertTrue(any("10种搅拌时长" in c["content"] for c in result))


if __name__ == "__main__":
    unittest.main()
