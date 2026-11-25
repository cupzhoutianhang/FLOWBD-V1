"""Locally built, bidirectional component; no model or persistence operations."""
from pathlib import Path
import streamlit.components.v1 as components
from .. import controller

_component = components.declare_component('flowbd_content', path=str(Path(__file__).parent / 'dist'))


def content(mode, payload, key):
    return _component(mode=str(mode), payload=controller.json_safe(payload), key=key, default=None)
