from __future__ import annotations

import streamlit as st

from . import controller, pages, theme

ROUTES = {'qa': '研究问答', 'lineage': '方法谱系', 'corpus': '语料库', 'evaluation': '评测报告'}


def navigate(page):
    st.session_state.fb_page = page
    st.query_params['page'] = page


def main():
    st.set_page_config(page_title='FlowBD · 化工知识系统', layout='wide', initial_sidebar_state='collapsed')
    theme.inject()
    controller.bootstrap()
    if st.session_state.pop('fb_clear_draft', False):
        st.session_state.fb_question_draft = ''
        st.session_state.fb_question_widget = ''
    requested = st.query_params.get('page', 'qa')
    if requested not in ROUTES:
        requested = 'qa'
        st.query_params['page'] = requested
    st.session_state.fb_page = requested
    columns = st.columns([7.2, 1.1, 1.1, 1.1, 1.1, 1], gap='small')
    columns[0].markdown('<div class="fb-brand">FlowBD</div>', unsafe_allow_html=True)
    for col, (route, label) in zip(columns[1:5], ROUTES.items()):
        if route == requested:
            col.markdown(f'<div class="fb-nav-current" aria-current="page">{label}</div>', unsafe_allow_html=True)
        else:
            col.button(label, key='fb_nav_' + route, on_click=navigate, args=(route,), disabled=controller.busy(), use_container_width=True)
    if columns[5].button('新建问题', type='primary', disabled=controller.busy(), use_container_width=True):
        controller.new_chat()
        navigate('qa')
        st.rerun()
    theme.hero(requested)
    if requested == 'qa':
        actions = st.columns([4.8, 1.25, 1.8, 4.4])
        actions[0].markdown('<span class="fb-hero-actions-marker" aria-hidden="true">&#8203;</span>', unsafe_allow_html=True)
        if actions[1].button('开始研究', key='fb_start_research', type='primary', disabled=controller.busy()):
            controller.new_chat()
            st.rerun()
        actions[2].button('探索方法谱系', on_click=navigate, args=('lineage',), disabled=controller.busy())
        with actions[3]:
            pages.qa_tools()
    {'qa': pages.qa, 'lineage': pages.lineage, 'corpus': pages.corpus, 'evaluation': pages.evaluation}[requested]()
    st.markdown('<footer class="fb-footer"><span>FlowBD · 化工知识系统</span><span>原文、候选与人工审计状态分别呈现</span></footer>', unsafe_allow_html=True)
