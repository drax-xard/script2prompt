"""Final Draft (.fdx) XML parser (stdlib ``xml.etree``).

Maps Final Draft ``<Paragraph Type="...">`` nodes to screenplay elements. Each
paragraph's text is the concatenation of its ``<Text>`` runs (which may carry
``Style`` attributes). Only the script ``<Content>`` is read, so title-page
paragraphs are ignored. Unknown paragraph types (cast lists, act breaks, notes)
are skipped.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from . import plaintext
from .base import Element

_TYPE_MAP = {
    "Scene Heading": "heading",
    "Action": "action",
    "General": "action",
    "Character": "character",
    "Parenthetical": "parenthetical",
    "Dialogue": "dialogue",
    "Transition": "transition",
}
_WS = re.compile(r"\s+")


def _paragraph_text(para: ET.Element) -> str:
    return _WS.sub(" ", "".join(t.text or "" for t in para.findall("Text"))).strip()


def _elements(root: ET.Element) -> list[Element]:
    content = root if root.tag == "Content" else root.find("Content")
    if content is None:
        return []
    elements: list[Element] = []
    for lineno, para in enumerate(content.iter("Paragraph"), start=1):
        kind = _TYPE_MAP.get(para.get("Type", ""))
        if not kind:
            continue
        text = _paragraph_text(para)
        if not text:
            continue
        meta: dict = {"line": lineno}
        if kind == "character":
            name, ext = plaintext.normalize_cue(text)
            meta.update({"name": name, "extension": ext})
        elements.append(Element(kind, text, meta))
    return elements


def parse_string(xml: str | bytes) -> list[Element]:
    """Parse FDX XML text/bytes into elements."""
    return _elements(ET.fromstring(xml))


def parse(path: str) -> list[Element]:
    """Parse a .fdx file into elements."""
    with open(path, "rb") as fh:
        return parse_string(fh.read())
