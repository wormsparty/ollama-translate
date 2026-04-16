#!/usr/bin/env python3
"""
translate_docx.py — Traduction de fichiers .docx (WordprocessingML).

Parties traitées : document.xml, header*.xml, footer*.xml, footnotes.xml, endnotes.xml
"""

import re
from pathlib import Path

from lxml import etree

from translate_core import XML_SPACE, translate_zip_document

# ---------------------------------------------------------------------------
# Namespace WordprocessingML
# ---------------------------------------------------------------------------

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{W_NS}}}"

DOCX_PARTS = re.compile(
    r"^word/(document|header\d*|footer\d*|footnotes|endnotes)\.xml$"
)


# ---------------------------------------------------------------------------
# Extraction / injection
# ---------------------------------------------------------------------------


def docx_extract(root: etree._Element) -> list[dict]:
    """
    Parcourt tous les <w:p> et retourne un catalogue de segments non vides.
    Gère automatiquement les tableaux, en-têtes, pieds de page et contrôles
    de contenu (w:sdt) via iter().
    """
    catalogue = []
    seg_id = 0
    for para in root.iter(f"{W}p"):
        text = "".join((t.text or "") for t in para.iter(f"{W}t")).strip()
        if text:
            seg_id += 1
            catalogue.append({"id": seg_id, "text": text, "elem": para})
    return catalogue


def docx_inject(para_elem: etree._Element, new_text: str) -> None:
    """
    Réinjecte new_text dans un paragraphe <w:p>.

    Met la traduction dans le premier <w:t>, vide les suivants.
    Les <w:rPr> (gras, italique, police) et les <w:drawing> (images)
    ne sont jamais modifiés.
    """
    t_elements = list(para_elem.iter(f"{W}t"))
    if not t_elements:
        return

    first_t = t_elements[0]
    first_t.text = new_text
    first_t.set(XML_SPACE, "preserve")

    for t_elem in t_elements[1:]:
        t_elem.text = ""
        if XML_SPACE in t_elem.attrib:
            del t_elem.attrib[XML_SPACE]


# ---------------------------------------------------------------------------
# Point d'entrée format
# ---------------------------------------------------------------------------


def translate_docx(path: Path, output_dir: Path) -> None:
    translate_zip_document(path, output_dir, DOCX_PARTS, docx_extract, docx_inject)
