"""Reuse selected legacy functions verbatim without executing the legacy UI.

Only trusted repository Python is compiled. No model/user text enters this loader.
The backend prefix (including its compatibility patches) is loaded only on explicit
initialization or question submission. Protected source files are never rewritten.
"""
from __future__ import annotations

import ast
import functools
import hashlib
import html
import json
import math
import os
import sys
import time
import types
import copy
import importlib.util
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from .data import PROJECT

LEGACY = PROJECT / 'src/KnowledgeGraph-Streamlit-main/app.py'


def setup_paths():
    for path in (PROJECT / 'src', PROJECT / 'src/agent', LEGACY.parent):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


def history_operation(function, *args):
    """Surface legacy IO failures without editing its persistence implementation.

    The trusted legacy save/load/delete functions catch IO errors and print them.
    A private globals copy captures that diagnostic for this call only; other
    sessions and the old app keep their own globals and logging behavior.
    """
    diagnostics = []
    namespace = dict(function.__globals__, print=lambda *values, **kwargs: diagnostics.append(' '.join(map(str, values))))
    operation = types.FunctionType(function.__code__, namespace, function.__name__, function.__defaults__, function.__closure__)
    result = operation(*args)
    if diagnostics:
        raise OSError(diagnostics[-1])
    return result


@functools.lru_cache(maxsize=1)
def helpers():
    setup_paths()
    tree = ast.parse(LEGACY.read_text(encoding='utf-8-sig'), filename=str(LEGACY))
    selected = {'_make_history_id', '_history_record_from_messages', '_history_id_for_item',
                'save_chat_log', 'load_chat_history', 'delete_chat_log_entry',
                'render_static_history_graph', 'render_qa_atlas', '_atlas_data_for_qa',
                '_get_landscape_module', 'prepare_graph_visualization', 'render_evidence_graph', '_quote_short'}
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in selected]
    constants = [n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in {'EG_TYPE_COLORS', 'EG_EDGE_COLORS'} for t in n.targets)]
    import ui_style
    namespace = dict(st=st, components=components, json=json, re=__import__('re'), os=os,
                     time=time, hashlib=hashlib, html=html, math=math, copy=copy,
                     PROJECT_ROOT=str(PROJECT), SCRIPT_DIR=str(LEGACY.parent),
                     __file__=str(LEGACY), ui_style=ui_style)
    exec(compile(ast.Module(body=constants + nodes, type_ignores=[]), str(LEGACY), 'exec'), namespace)
    namespace['_source_functions'] = sorted(selected)
    return types.SimpleNamespace(**namespace)


@functools.lru_cache(maxsize=1)
def runtime():
    setup_paths()
    tree = ast.parse(LEGACY.read_text(encoding='utf-8-sig'), filename=str(LEGACY))
    # Exact boundary: before the first st.set_page_config call. Never executes UI,
    # auto-initialization, history deletion, question submission or persistence.
    boundary = next(i for i, n in enumerate(tree.body) if isinstance(n, ast.Expr)
                    and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Attribute)
                    and n.value.func.attr == 'set_page_config')
    namespace = {'__file__': str(LEGACY), '__name__': 'flowbd_legacy_runtime'}
    exec(compile(ast.Module(body=tree.body[:boundary], type_ignores=[]), str(LEGACY), 'exec'), namespace)
    return types.SimpleNamespace(**namespace)


def display_graph(snapshot, key, evidence=False):
    helper = helpers()
    if evidence:
        from streamlit_agraph import agraph, Node, Edge, Config
        helper.render_evidence_graph.__globals__.update(agraph=agraph, Node=Node, Edge=Edge, Config=Config)
        # Historical rendering remains static, retaining the existing teardown fix.
        return helper.render_evidence_graph(snapshot, key=key, interactive=False)
    return helper.render_static_history_graph(snapshot, key=key)


@functools.lru_cache(maxsize=1)
def lineage_module():
    setup_paths()
    path = PROJECT / 'src/graph_rag/method_extraction/landscape/landscape_v3.py'
    spec = importlib.util.spec_from_file_location('flowbd_preserved_lineage_v3', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
