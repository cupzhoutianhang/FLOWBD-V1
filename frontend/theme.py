"""Theme scoped to the new entry; never overwrites the legacy PALETTE."""
from pathlib import Path
import streamlit as st

CSS = Path(__file__).with_name('theme.css')


def inject():
    st.markdown('<style>' + CSS.read_text(encoding='utf-8') + '</style>', unsafe_allow_html=True)


def hero(page):
    title, subtitle = {
        'qa': ('读懂方法，看清来路。', '让中文文献里的问题、知识与证据，成为一条清晰的研究路径。'),
        'lineage': ('方法的来路，清晰可见。', '沿着时间与技术分支，追踪有原文支持的关系。'),
        'corpus': ('下一条线索，就在文献里。', '阅读原文，核对方法，找到值得继续研究的问题。'),
        'evaluation': ('结果，和它的边界。', '保留每一条执行记录，区分成功返回与科学质量。'),
    }[page]
    # A full-width final stop has substantial trailing whitespace. Keep its
    # glyph and text content while trimming that whitespace for optical centering.
    title = title.removesuffix('。') + '<span class="fb-hero-stop">。</span>'
    subtitle = subtitle.removesuffix('。') + '<span class="fb-hero-stop">。</span>'
    st.markdown(f'<section class="fb-hero"><p>FlowBD <span>化工知识系统</span></p><h1>{title}</h1><div class="fb-hero-description">{subtitle}</div></section>', unsafe_allow_html=True)
