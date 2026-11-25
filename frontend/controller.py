"""UI session controller around the existing conversation and persistence contract."""
from __future__ import annotations

import copy
import json
import math
import threading
import time
import uuid
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import streamlit as st
from streamlit.runtime.scriptrunner import add_script_run_ctx

from . import legacy

HISTORY_READ_ERROR = '本地历史暂时无法读取，请检查历史目录的访问权限；仍可浏览其他本地页面。'
_PAYLOAD_STRING_LIMIT = 40000
_TRUNCATED_KEYS = {'raw_response', 'structured_calls'}
_TRUNCATION_SUFFIX = '\n…[truncated]'


def json_safe(value, *, _active=None, _key=''):
    """Return a JSON-serializable value without leaking NaN or opaque objects.

    History replay must remain deterministic even when an upstream model client
    leaves Decimal, Path, exception, set or cyclic diagnostic values in a failure
    payload. Large raw model responses are retained only as bounded diagnostics.
    """
    if value is None or isinstance(value, (bool, int, str)):
        if isinstance(value, str) and _key in _TRUNCATED_KEYS and len(value) > _PAYLOAD_STRING_LIMIT:
            keep = _PAYLOAD_STRING_LIMIT - len(_TRUNCATION_SUFFIX)
            return value[:keep] + _TRUNCATION_SUFFIX
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, BaseException):
        return f'{type(value).__name__}: {value}'

    active = set() if _active is None else _active
    marker = id(value)
    if marker in active:
        return '[circular-reference]'
    active.add(marker)
    try:
        if isinstance(value, dict):
            return {str(key): json_safe(item, _active=active, _key=str(key))
                    for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [json_safe(item, _active=active, _key=_key) for item in value]
        if isinstance(value, (set, frozenset)):
            items = [json_safe(item, _active=active, _key=_key) for item in value]
            return sorted(items, key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))
        return str(value)
    finally:
        active.discard(marker)


def storage():
    return legacy.helpers()


def conversation_factory():
    return legacy.runtime().MultiTurnConversation()


def bootstrap():
    defaults = {'messages': [], 'history': [], '_conv_hist_id': None, '_history_view_mode': False,
                'agent_conversation': None, 'agent_initialized': False, 'streaming_answer': '',
                'streaming_reasoning': '', 'iterative_mode': False, 'eg_summarized_answer': False,
                'first_principles_enabled': False, 'current_supplier': 'glm_pro', 'temperature': 0.0,
                'fb_job': None, 'fb_error': '', 'fb_history_loaded': False, 'fb_unsaved_messages': []}
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if not st.session_state.fb_history_loaded:
        try:
            st.session_state.history = legacy.history_operation(storage().load_chat_history)
            st.session_state.fb_history_loaded = True
            if st.session_state.fb_error == HISTORY_READ_ERROR:
                st.session_state.fb_error = ''
        except Exception:
            st.session_state.fb_error = HISTORY_READ_ERROR


def busy():
    job = st.session_state.get('fb_job')
    return bool(job and not job.get('finalized'))


def initialize():
    if st.session_state.agent_conversation is None:
        st.session_state.agent_conversation = conversation_factory()
        st.session_state.agent_initialized = True
    return st.session_state.agent_conversation


def new_chat():
    if busy():
        return
    st.session_state.fb_clear_draft = True
    for key, value in {'messages': [], '_conv_hist_id': None, '_history_view_mode': False,
                       'streaming_answer': '', 'streaming_reasoning': '', 'fb_job': None,
                       'fb_error': '', 'agent_conversation': None, 'agent_initialized': False}.items():
        st.session_state[key] = value


def select_history(index):
    if busy():
        return
    row = st.session_state.history[index]
    st.session_state.messages = copy.deepcopy(row.get('messages') or [])
    st.session_state._conv_hist_id = storage()._history_id_for_item(row, index)
    st.session_state._history_view_mode = True
    st.session_state.fb_error = ''
    # A backend instance must not retain another conversation's private memory.
    st.session_state.agent_conversation = None
    st.session_state.agent_initialized = False


def delete_history(index):
    if busy():
        return
    row = st.session_state.history[index]
    try:
        legacy.history_operation(storage().delete_chat_log_entry, row.get('messages') or [])
    except Exception:
        st.session_state.fb_error = '历史删除未完成，请检查本地历史目录的访问权限。当前记录仍保留在列表中。'
        return False
    if storage()._history_id_for_item(row, index) == st.session_state._conv_hist_id:
        new_chat()
    del st.session_state.history[index]
    return True


def postprocess(conv, state, answer, question):
    """Keep the legacy graph extraction and atlas matching timings after generation."""
    graph = None
    hits = []
    snapshot = getattr(state, 'evidence_graph_snapshot', None)
    if not (isinstance(snapshot, dict) and snapshot.get('nodes')):
        nodes, edges = legacy.runtime().generate_graph_data(answer)
        if nodes and edges:
            graph = {'nodes': nodes, 'edges': edges}
    try:
        entities = getattr(state, 'extracted_entities', []) or []
        vector = conv.arsenal.embedding_manager.embed_text(question + '。' + '，'.join(entities))
        if vector:
            hits, _ = legacy.helpers()._get_landscape_module().match_nodes(vector, top_k=30)
    except Exception:
        pass
    return graph, hits


def submit(question):
    if busy() or not question.strip():
        return False
    question = question.strip()
    try:
        conv = initialize()
    except Exception as error:
        st.session_state.fb_error = f'初始化未完成：{error}。可检查服务后重试；历史与本地页面仍可使用。'
        return False
    st.session_state.streaming_answer = ''
    st.session_state.streaming_reasoning = ''
    st.session_state.fb_error = ''
    st.session_state.fb_clear_draft = True
    st.session_state._history_view_mode = False
    st.session_state.messages.append({'role': 'user', 'content': question})
    job = {'id': uuid.uuid4().hex, 'question': question, 'done': False, 'finalized': False,
           'state': None, 'error': '', 'stage_ms': [None] * 4, 'started': time.monotonic(),
           'graph': None, 'atlas_hits': [], 'postprocess_error': ''}
    st.session_state.fb_job = job
    iterative = bool(st.session_state.iterative_mode)
    summarized = bool(st.session_state.eg_summarized_answer)
    theory = bool(st.session_state.first_principles_enabled) and not iterative
    session_id = st.session_state._conv_hist_id or 'pending_iterative'

    def worker():
        try:
            generator = (conv.run_iterative_conversation(question, session_id=session_id, summarized_answer=summarized)
                         if iterative else conv.run_conversation(question, enable_first_principles=theory))
            previous_end = job['started']
            for state in generator:
                job['state'] = state
                now = time.monotonic()
                for index in range(4):
                    if getattr(state, f'stage_{index+1}_complete', False) and job['stage_ms'][index] is None:
                        job['stage_ms'][index] = round((now - previous_end) * 1000)
                        previous_end = now
            state = job['state']
            if state and getattr(state, 'final_answer', ''):
                try:
                    job['graph'], job['atlas_hits'] = postprocess(conv, state, state.final_answer, question)
                except Exception as error:
                    job['postprocess_error'] = str(error)
        except Exception as error:
            job['error'] = str(error)
        finally:
            job['done'] = True

    thread = threading.Thread(target=worker, name='flowbd-ui-question', daemon=True)
    add_script_run_ctx(thread)
    thread.start()
    return True


def finalize():
    job = st.session_state.get('fb_job')
    if not job or not job['done'] or job['finalized']:
        return False
    state = job['state']
    answer = getattr(state, 'final_answer', '') if state else ''
    quality = (getattr(state, 'answer_quality', None) or {}) if state else {}
    backend_failed = (quality.get('generation_status') == 'failed' or
                      any(str(error).startswith('generation_failure:') for error in quality.get('operation_errors', [])) or
                      answer.strip() == '无法生成答案')
    if job['error'] or not answer or backend_failed:
        reason = job['error'] or ('答案未通过完整性或来源检查。' if backend_failed else '未收到有效最终回答。')
        st.session_state.fb_error = '本次生成未完成：' + reason
        failure = {'role': 'assistant', 'content': st.session_state.fb_error,
                   'answer_quality': quality or None,
                   'doc_sources': getattr(state, 'doc_sources', []) if state else [],
                   'evidence_graph': getattr(state, 'evidence_graph_snapshot', None) if state else None,
                   'iterations': getattr(state, 'iterations', None) if state else None,
                   'eg_stop_reason': getattr(state, 'eg_stop_reason', None) if state else None,
                   'stage_ms': job['stage_ms']}
        persist_message(job['question'], failure)
        job['finalized'] = True
        return True
    from agent.answer_cleaner import clean_final_answer
    sources = getattr(state, 'doc_sources', []) or []
    answer = clean_final_answer(answer, sources=sources)
    iterations = list(getattr(state, 'iterations', None) or [])
    stop = getattr(state, 'eg_stop_reason', '') or next((e.get('reason') for e in reversed(iterations) if str(e.get('action', '')).upper() == 'TERMINATE'), None)
    message = {'role': 'assistant', 'content': answer,
               'reasoning': getattr(state, 'llm_reasoning', '') or st.session_state.streaming_reasoning,
               'fp_answer': getattr(state, 'first_principles_answer', ''),
               'fp_reasoning': getattr(state, 'fp_reasoning', ''),
               'logs': getattr(state, 'agent_logs', []) or [], 'graph': job['graph'],
               'evidence_graph': getattr(state, 'evidence_graph_snapshot', None),
               'iterations': iterations or None, 'eg_stop_reason': stop,
               'answer_quality': getattr(state, 'answer_quality', None),
               'atlas_hits': job['atlas_hits'], 'doc_sources': sources, 'stage_ms': job['stage_ms']}
    # Same legacy whitelist and saved-source truncation policy, no new business keys.
    saved = persist_message(job['question'], message)
    job['finalized'] = True
    if saved and job['postprocess_error']:
        st.session_state.fb_error = '回答已保存；图谱展示处理未完成：' + job['postprocess_error']
    return True


def persist_message(question, message):
    question = json_safe(question)
    message = json_safe(message)
    saved = True
    try:
        legacy.history_operation(storage().save_chat_log, question, message)
    except Exception:
        saved = False
        st.session_state.fb_unsaved_messages.append({'question': question, 'message': copy.deepcopy(message)})
        st.session_state.fb_error = '本次对话未能确认写入本地历史，内容仍保留在当前会话。请在刷新或关闭页面前下载备份，并检查历史目录的访问权限。'
    st.session_state.messages.append(message)
    history = st.session_state.history
    position = next((i for i, row in enumerate(history) if str(row.get('history_id')) == str(st.session_state._conv_hist_id)), None) if st.session_state._conv_hist_id else None
    if position is None:
        record = storage()._history_record_from_messages(st.session_state.messages)
        history.insert(0, record)
        st.session_state._conv_hist_id = record['history_id']
    else:
        history[position]['messages'] = copy.deepcopy(st.session_state.messages)
    if saved and st.session_state.iterative_mode:
        conv = st.session_state.agent_conversation
        if hasattr(conv, '_migrate_evidence_store'):
            try:
                conv._migrate_evidence_store(st.session_state._conv_hist_id)
            except Exception as error:
                st.session_state.fb_error = f'回答已保存；证据图会话迁移未完成：{error}'
    return saved
