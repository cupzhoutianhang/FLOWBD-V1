"""Actual page views over local evidence, history and existing backend outputs."""
from __future__ import annotations

import hashlib
import html
import json
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

import streamlit as st

from . import controller, data, legacy
from .component import content


@contextmanager
def panel():
    with st.container(border=True):
        st.markdown('<span class="fb-panel-marker" aria-hidden="true">&#8203;</span>', unsafe_allow_html=True)
        yield


@st.cache_data(ttl=120, show_spinner=False)
def cached_papers():
    return data.papers()


@st.cache_data(ttl=120, show_spinner=False)
def cached_evaluation():
    return data.evaluation()


def quality_caption(quality):
    if not isinstance(quality, dict):
        return
    parts = []
    mapping = quality.get('citation_mapping_valid')
    if mapping is not None:
        parts.append('引用编号可对应来源' if mapping else '存在无法对应来源的引用')
    status = (quality.get('grounding_audit') or {}).get('status')
    labels = {'model_screened': '已完成模型辅助原文核验，仍需结合原文判断',
              'authoritative_record_rendered': '按已保存的人工审计记录回答',
              'review_failed': '事实核验未完成，请核对证据原文',
              'no_auditable_context': '本次缺少可供核验的原文'}
    if status in labels:
        parts.append(labels[status])
    if quality.get('operation_errors'):
        parts.append('部分检索未完成，本次证据范围受限')
    if (quality.get('grounding_audit') or {}).get('unresolved_repairs'):
        parts.append('有待进一步核对的内容')
    if parts:
        st.caption(' · '.join(parts))


def message_details(message, key):
    quality_caption(message.get('answer_quality'))
    if st.toggle('展开图谱、方法版图与执行流程', key=key + '_details'):
        with st.container(border=True):
            graph, flow, original = st.tabs(['图谱与方法版图', '执行流程', '完整记录与原文'])
            with graph:
                snapshot = message.get('evidence_graph')
                if isinstance(snapshot, dict) and snapshot.get('nodes'):
                    legacy.display_graph(snapshot, key + '_eg', evidence=True)
                elif message.get('graph'):
                    st.caption('本体图：从回答文本抽取，非 Neo4j 直接查询；不表示人工 confirmed。')
                    legacy.display_graph(message['graph'], key + '_ontology')
                else:
                    st.caption('该记录未保存可展示的图谱。')
                if 'atlas_hits' in message:
                    if st.button('加载方法版图', key=key + '_atlas_btn'):
                        st.session_state[key + '_atlas_show'] = True
                    if st.session_state.get(key + '_atlas_show'):
                        try:
                            legacy.helpers().render_qa_atlas(message.get('atlas_hits') or [], key=key + '_atlas')
                        except Exception as error:
                            st.warning(f'方法版图暂不可用：{error}')
            with flow:
                rows = []
                for label, milliseconds in zip(['问题解析', '多源检索', '信息融合', '答案生成'], message.get('stage_ms') or []):
                    rows.append({'阶段': label, '已记录耗时（ms）': milliseconds})
                if rows:
                    st.dataframe(rows, use_container_width=True, hide_index=True)
                if message.get('iterations'):
                    st.json({'iterations': message['iterations'], 'eg_stop_reason': message.get('eg_stop_reason')}, expanded=False)
                if message.get('logs'):
                    st.code(message['logs'] if isinstance(message['logs'], str) else '\n'.join(str(line) for line in message['logs']), language='text')
                if not rows and not message.get('logs') and not message.get('iterations'):
                    st.caption('该记录未保存流程数据。')
            with original:
                st.caption('保存的回答、来源及状态；旧历史来源可能在保存时已截断。')
                st.json(message, expanded=False)
                sources = message.get('doc_sources') or []
                if sources:
                    idx = st.selectbox('选择文献原文', range(len(sources)),
                                       format_func=lambda i: f"[Ref-{sources[i].get('ref_id', '?')}] {sources[i].get('source_label') or sources[i].get('source', '')}", key=key + '_full_source')
                    path = data.source_path(sources[idx])
                    if st.button('读取对应本地全文', disabled=path is None, key=key + '_full_btn'):
                        st.session_state[key + '_full_path'] = str(path)
                    if st.session_state.get(key + '_full_path') == str(path) and path:
                        text = path.read_text(encoding='utf-8-sig')
                        st.markdown(text)
                    if path is None:
                        st.caption('该来源未能对应到本地文献全文；保存的来源片段仍可查看。')
    if message.get('reasoning'):
        with st.expander('查看已记录的思考过程'):
            st.markdown(message['reasoning'])
    if message.get('fp_answer') or message.get('fp_reasoning'):
        with st.expander('探索性理论分析（实验）'):
            st.caption('未按本次检索原文核验；不作为实验参数或已证结论。')
            if message.get('fp_reasoning'):
                st.write(message['fp_reasoning'])
            if message.get('fp_answer'):
                st.markdown(message['fp_answer'])


def qa_tools():
    history_col, settings_col = st.columns([1, 1])
    with history_col:
        with st.popover('历史对话', disabled=controller.busy()):
            history = st.session_state.history
            if not history:
                st.caption('暂无历史记录。')
            else:
                index = st.selectbox('选择历史对话', range(len(history)),
                                     format_func=lambda i: history[i].get('title') or '历史记录', key='fb_history_index')
                st.caption(next((str(m.get('content', '')) for m in history[index].get('messages', []) if m.get('role') == 'user'), ''))
                if st.button('打开历史', disabled=controller.busy()):
                    controller.select_history(index)
                    st.rerun()
                confirm = st.checkbox('确认删除此条历史', disabled=controller.busy())
                if st.button('删除历史', disabled=controller.busy() or not confirm):
                    controller.delete_history(index)
                    st.rerun()
    with settings_col:
        with st.popover('设置', disabled=controller.busy()):
            def preference(key):
                st.session_state[key] = st.session_state['fb_widget_' + key]
            for key in ('iterative_mode', 'eg_summarized_answer', 'first_principles_enabled'):
                widget = 'fb_widget_' + key
                if widget not in st.session_state:
                    st.session_state[widget] = st.session_state[key]
            st.toggle('迭代闭环模式（实验）', key='fb_widget_iterative_mode', on_change=preference, args=('iterative_mode',), disabled=controller.busy())
            st.toggle('答案·图摘要模式（实验）', key='fb_widget_eg_summarized_answer', on_change=preference, args=('eg_summarized_answer',), disabled=controller.busy() or not st.session_state.iterative_mode)
            st.toggle('探索性理论分析（实验）', key='fb_widget_first_principles_enabled', on_change=preference, args=('first_principles_enabled',), disabled=controller.busy() or st.session_state.iterative_mode)
            st.caption('上述实验默认关闭；严格护栏实验沿用后端环境配置，本页面不自动开启。')
            if st.button('初始化 / 重新连接服务', disabled=controller.busy()):
                try:
                    st.session_state.agent_conversation = None
                    with st.spinner('正在连接现有问答服务…'):
                        controller.initialize()
                    st.success('初始化完成。')
                except Exception as error:
                    st.error(f'初始化未完成：{error}')
            conv = st.session_state.agent_conversation
            st.caption('问答服务：' + ('已初始化' if conv else '尚未初始化，浏览历史无需连接'))
            if conv:
                st.caption('Milvus：' + ('已连接' if getattr(conv, 'traditional_rag', None) else '未就绪'))
                st.caption('Neo4j：' + ('已连接' if getattr(conv, 'graph_rag', None) else '未就绪'))


def qa():
    pairs = []
    question = ''
    for index, message in enumerate(st.session_state.messages):
        if message.get('role') == 'user':
            question = message.get('content', '')
        elif message.get('role') == 'assistant':
            pairs.append((index, question, message))
    if pairs:
        if len(pairs) > 1:
            index = st.selectbox('当前轮次', range(len(pairs)), index=len(pairs)-1,
                                 format_func=lambda i: f"第 {i+1} 轮 · {pairs[i][1][:70]}", key='fb_turn_' + str(st.session_state._conv_hist_id))
        else:
            index = 0
        position, question, message = pairs[index]
        key = f"message_{st.session_state._conv_hist_id}_{position}"
        content('reader', {'identity': key, 'question': question, 'answer': message.get('content', ''),
                           'sources': data.source_views(message.get('doc_sources')), 'context': '研究回答 · 原文对照'}, key)
        message_details(message, key)
    elif not controller.busy():
        with panel():
            st.subheader('从你的研究问题开始')
            st.caption('可以输入新问题，也可以从上方打开已保存的历史对话。')
    if st.session_state.fb_error:
        st.warning(st.session_state.fb_error)
    if st.session_state.fb_unsaved_messages:
        st.caption(f'当前会话有 {len(st.session_state.fb_unsaved_messages)} 条对话尚未确认保存；新建问题不会清除这份临时备份，刷新或关闭页面后它可能丢失。')
        st.download_button('下载未保存对话备份', json.dumps(st.session_state.fb_unsaved_messages, ensure_ascii=False, indent=2, default=str),
                           file_name='FlowBD_未保存对话备份.json', mime='application/json', key='fb_unsaved_download')

    if controller.busy():
        @st.fragment(run_every=0.5)
        def progress():
            if controller.finalize():
                st.rerun()
            job = st.session_state.fb_job
            state = job.get('state')
            completed = sum(bool(getattr(state, f'stage_{i}_complete', False)) for i in range(1, 5)) if state else 0
            st.progress(completed / 4, text='正在研究 · ' + ['问题解析', '多源检索', '信息融合', '答案生成', '整理回答'][completed])
            answer = st.session_state.streaming_answer or getattr(state, 'final_answer', '')
            content('reader', {'identity': job['id'], 'question': job['question'], 'answer': answer or '正在处理问题，检索完成后可对照来源。',
                               'sources': data.source_views(getattr(state, 'doc_sources', []) if state else []), 'context': '生成中 · 尚未保存最终回答'}, 'stream_' + job['id'])
            if state and getattr(state, 'agent_logs', None):
                with st.expander('当前执行日志'):
                    st.code('\n'.join(map(str, state.agent_logs)), language='text')
        progress()
    # The draft has a separate non-widget key: Streamlit removes widget values
    # when their page is not rendered. A form would also buffer an unsent draft.
    if 'fb_question_widget' not in st.session_state:
        st.session_state.fb_question_widget = st.session_state.get('fb_question_draft', '')
    def save_draft():
        st.session_state.fb_question_draft = st.session_state.fb_question_widget
    with panel():
        value = st.text_area('继续研究' if pairs else '研究问题', key='fb_question_widget', height=100,
                             on_change=save_draft, placeholder='输入研究问题…', disabled=controller.busy())
        submitted = st.button('开始研究' if not pairs else '继续提问', key='fb_submit_question', type='primary', disabled=controller.busy())
    if submitted:
        if not value.strip():
            st.info('请先输入研究问题。')
        else:
            with st.spinner('准备问答服务…'):
                started = controller.submit(value)
            if started:
                st.rerun()


def lineage():
    view = st.radio('查看范围', ['专题谱系', '全局方法版图'], horizontal=True, key='fb_lineage_scope')
    if view == '全局方法版图':
        try:
            active, versions = data.atlas_versions()
            labels = {v: ('新增文献接入版' if v == active else '接收前原版') for v in versions}
            version = st.selectbox('版图版本', versions, format_func=labels.get, key='fb_atlas_version')
            atlas = data.method_atlas(version)
            content('atlas', {**atlas, 'identity': 'atlas_' + version}, 'fb_method_atlas')
            st.caption(atlas.get('meta', {}).get('evidence_boundary', '语义空间不代表历史继承关系。'))
            st.download_button('下载当前版图数据', json.dumps(atlas, ensure_ascii=False, indent=2),
                               file_name=version + '.json', mime='application/json')
        except (OSError, ValueError, KeyError) as error:
            st.warning(f'全局版图暂不可用：{error}。可切回专题谱系查看原有案例。')
        return
    try:
        cases = data.lineage_cases()
    except (OSError, ValueError, KeyError) as error:
        st.warning(f'统一专题不可用，显示原 PCM 数据：{error}')
        lineage_fallback()
        return
    labels = {c['case_id']: c.get('title_cn', c['case_id']) for c in cases}
    case_col, _ = st.columns([1.6, 2.4])
    if 'fb_case' not in st.session_state and st.query_params.get('case') in labels:
        st.session_state.fb_case = st.query_params['case']
    case_id = case_col.selectbox('专题案例', list(labels), format_func=labels.get, key='fb_case')
    case = data.lineage_case(case_id)
    manifest = case.get('manifest') or {}
    identity = 'lineage_' + case_id
    event = content('lineage', {**case, 'identity': identity, 'title': labels[case_id],
                               'view': st.session_state.get('fb_graph_view_' + case_id, {})}, 'fb_lineage')
    component_event(event, identity, 'fb_graph_view_' + case_id)
    columns = st.columns(4)
    for col, (label, name, mime) in zip(columns, [('原论文主图 SVG', 'main_figure.svg', 'image/svg+xml'), ('原论文主图 PNG', 'main_figure_300dpi.png', 'image/png'), ('原论文主图 PDF', 'main_figure.pdf', 'application/pdf'), ('专题 JSON', 'frontend_case.json', 'application/json')]):
        path = data.LINEAGE / 'lineage_cases_unified' / case_id / name
        if path.is_file():
            col.download_button(label, path.read_bytes(), file_name=name, mime=mime, key='fb_download_' + case_id + name)
    with st.expander('案例说明与审计口径'):
        st.json({'manifest': manifest, 'legend': case.get('legend'), 'audit_summary': case.get('audit_summary')}, expanded=False)
        st.caption('按专题文件保留证据层级与核验状态；review_text_locatable 和 accepted 不自动升级为 confirmed。')
    with st.expander('原 PCM 谱系、审计记录与历史实验入口'):
        lineage_fallback()
        st.caption('旧 V3、V2 仍可按原命令独立运行；V2 的 confidence=high 不代表人工 confirmed。')
        st.code('python -m streamlit run src/graph_rag/method_extraction/landscape/landscape_v3.py --server.port 8511\npython -m streamlit run src/graph_rag/method_extraction/landscape/landscape_v2.py --server.port 8512', language='powershell')


def lineage_fallback():
    base = data.LINEAGE / 'lineage_mvp'
    if not (base / 'lineage_methods_normalized_v2.csv').is_file():
        st.info('公开包未附带历史 PCM 全量数据；上方三个专题案例可正常浏览。')
        return
    try:
        nodes = data.read_csv(base / 'lineage_methods_normalized_v2.csv')
        edges = data.read_csv(base / 'lineage_edges_confirmed_v2.csv')
        st.caption(f'原 PCM 文件：{len(nodes)} 个方法节点，{len(edges)} 条正式关系文件记录；保留文件原始 validation_status。')
        st.dataframe(nodes, use_container_width=True, hide_index=True)
        st.dataframe(edges, use_container_width=True, hide_index=True)
        st.download_button('下载原节点 CSV', (base / 'lineage_methods_normalized_v2.csv').read_bytes(), 'lineage_methods_normalized_v2.csv')
        st.download_button('下载原关系 CSV', (base / 'lineage_edges_confirmed_v2.csv').read_bytes(), 'lineage_edges_confirmed_v2.csv')
        if st.checkbox('显示原 PCM 图与节点详情', key='fb_legacy_pcm_graph'):
            module = legacy.lineage_module()
            old = module.load_lineage_v2()
            dag, metro = st.tabs(['原年份谱系图', '原地铁时间轴与导出'])
            with dag:
                module.render_lineage_dag(old['methods_df'], old['edges_confirmed_df'])
            with metro:
                import io
                import matplotlib.pyplot as plt
                figure = module.render_metro_figure(old['methods_df'], old['edges_confirmed_df'])
                st.pyplot(figure, use_container_width=True)
                buffer = io.BytesIO()
                figure.savefig(buffer, format='png', dpi=180, bbox_inches='tight')
                st.download_button('导出原地铁图 PNG', buffer.getvalue(), 'lineage_metro_v3.png', 'image/png')
                plt.close(figure)
            module.render_detail_drawer(old['methods_df'], old['edges_confirmed_df'])
        path = base / 'excluded_lineage_candidates.csv'
        if path.is_file():
            st.caption('下列记录已排除，不进入主图。')
            st.dataframe(data.read_csv(path), use_container_width=True, hide_index=True)
    except Exception as error:
        st.error(f'原 PCM 文件不可用：{error}')


def component_event(event, identity, key):
    if not isinstance(event, dict) or event.get('identity') != identity:
        return None
    token = (event.get('sequence'), event.get('action'), json.dumps(event.get('view'), sort_keys=True))
    if st.session_state.get(key + '_event') == token:
        return None
    st.session_state[key + '_event'] = token
    view = event.get('view')
    if isinstance(view, dict):
        st.session_state[key] = view
    return event.get('action')


def corpus():
    if not data.CORPUS.is_dir():
        st.info('公开包不包含论文全文。配置自己的文献目录后，此处将展示文献列表。')
        return
    try:
        papers = cached_papers()
    except Exception as error:
        st.error(f'文献目录暂不可用：{error}')
        return
    methods_path = data.METHODS / 'methods.csv'
    methods = data.optional_csv(methods_path)
    indexed_papers = {m['paper_id'] for m in methods}
    method_count = len(methods) + sum(len(p['methods']) for p in papers if p['id'] not in indexed_papers)
    event = content('corpus', {'identity': 'corpus', 'papers': papers,
                              'methodCount': method_count if methods_path.is_file() or method_count else None,
                              'view': st.session_state.get('fb_library_view', {})}, 'fb_library')
    action = component_event(event, 'corpus', 'fb_library_view')
    view = st.session_state.get('fb_library_view', {})
    selected = next((p for p in papers if p['id'] == view.get('paper')), None)
    if action == 'open-paper' and selected and selected['has_text']:
        st.session_state.fb_open_paper = selected['id']
    if selected and st.session_state.get('fb_open_paper') == selected['id']:
        with st.expander('文献原文 · ' + selected['title'], expanded=True):
            try:
                st.markdown(data.paper_text(selected['id']))
            except OSError:
                st.warning('该文献原文目前无法读取，请刷新目录或检查文件访问权限。')
    with st.expander('Stage A 统计、年份分布与 Milvus 集合状态'):
        st.caption('统计不会将高置信候选关系称为 confirmed。')
        edges_path = data.METHODS / 'edges.csv'
        edges = data.optional_csv(edges_path)
        method_count = str(len(methods)) + ' 条' if methods_path.is_file() else '暂不可用'
        edge_count = str(len(edges)) + ' 条' if edges_path.is_file() else '暂不可用'
        st.write(f'Stage A 方法记录 {method_count}；候选关系记录 {edge_count}。')
        if not (data.METHODS / 'publish_year_report.csv').is_file():
            st.caption('年份索引暂不可用；仅显示其他已保存元数据中的年份，不推断缺失年份。')
        years = {}
        for row in methods:
            if row.get('year'):
                years[row['year']] = years.get(row['year'], 0) + 1
        st.dataframe([{'年份': y, '方法记录数': count} for y, count in sorted(years.items())], use_container_width=True, hide_index=True)
        if st.button('查询 Milvus 集合状态'):
            try:
                from pymilvus import MilvusClient
                client = MilvusClient(uri='http://localhost:19530', timeout=5)
                try:
                    st.dataframe([{'集合': name, '统计': client.get_collection_stats(name)} for name in client.list_collections()], use_container_width=True, hide_index=True)
                finally:
                    client.close()
            except Exception as error:
                st.warning(f'Milvus 统计暂不可用：{error}')


def evaluation():
    try:
        result = cached_evaluation()
    except Exception as error:
        st.warning(f'正式评测产物不可用：{error}。不使用演示数字补齐。')
        result = None
    if result:
        issues = [{**{k: v for k, v in issue.items() if k != 'record'},
                   'reason': data.failure_reason(issue),
                   'stage': '保留题' if 'holdout' in issue['run_id'] else '稳定性',
                   'question': (issue.get('record') or {}).get('question', '')}
                  for issue in result['issues']]
        event = content('evaluation', {'identity': 'evaluation', 'receipt': result['receipt'],
                                      'issues': issues, 'view': st.session_state.get('fb_report_view', {})}, 'fb_report')
        action = component_event(event, 'evaluation', 'fb_report_view')
        if action == 'open-issue':
            st.session_state.fb_open_issue = st.session_state.get('fb_report_view', {}).get('issue')
        selected = next((i for i in result['issues'] if i['attempt'] == st.session_state.get('fb_report_view', {}).get('issue')), None)
        if selected and st.session_state.get('fb_open_issue') == selected['attempt']:
            with st.expander('原始失败记录', expanded=True):
                st.json(selected.get('record') or selected, expanded=False)
        with st.expander('完成回执与原始验收记录'):
            st.caption(str(data.SUITE.relative_to(data.REPO)))
            st.json(result['receipt'], expanded=False)
            st.json(result['acceptance'], expanded=False)
    with st.expander('后续候选与离线回归（不合并统计）'):
        for name in ['CURRENT_STATE.json', 'status.json', 'offline_replay.json']:
            path = data.REPO / 'qa_runs/evidence_quality_20261019' / name
            if path.is_file():
                st.caption('2026-10-19 · ' + name)
                st.json(data.read_json(path), expanded=False)
        st.caption('旧正式未通过结论保持；小批回归不是新的盲评，也不替代原 PDF 与独立人工核验。')
    with st.expander('人工复核进度、历史问题与保护测试'):
        review = data.REPO / '人工复核记录表_模板.csv'
        if review.is_file():
            st.dataframe(data.read_csv(review), use_container_width=True, hide_index=True)
        else:
            st.caption('未找到人工复核记录表；不推定已完成复核。')
        st.caption('历史问题记录：量子隧穿储热材料题曾有实质输出；钙基储热题曾检索跑偏。出处为 2026-09-03/04 工作日志，不作为实时评测结果。')
        if st.button('运行回答清洗保护测试'):
            import os
            env = os.environ.copy()
            env.update(PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
            with st.spinner('运行本地保护测试，不调用模型…'):
                completed = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'src/agent/tests', '-p', 'test_answer_cleaner.py', '-t', 'src'], cwd=data.PROJECT, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
            st.session_state.fb_test_result = completed.stdout + completed.stderr
            st.session_state.fb_test_code = completed.returncode
        if 'fb_test_result' in st.session_state:
            (st.success if st.session_state.fb_test_code == 0 else st.error)('最近一次本地测试：' + ('通过' if st.session_state.fb_test_code == 0 else '未通过'))
            st.code(st.session_state.fb_test_result, language='text')
