#!/usr/bin/env python3
"""
translate_pptx.py — Traduction de fichiers .pptx (DrawingML).

Parties traitées : ppt/slides/slide*.xml, ppt/notesSlides/notesSlide*.xml

Limitation : si un paragraphe contient plusieurs runs avec des mises en forme
  différentes (ex. un mot en gras au milieu), tout le texte traduit est fusionné
  dans le premier <a:t>. La mise en forme du premier run est préservée, celle
  des runs suivants est perdue.
  Les champs automatiques (<a:fld> : numéros de slide, date) sont ignorés.
"""

import re
from pathlib import Path

from lxml import etree

from translate_core import XML_SPACE, translate_zip_document

# ---------------------------------------------------------------------------
# Namespace DrawingML
# ---------------------------------------------------------------------------

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
A = f"{{{A_NS}}}"

PPTX_PARTS = re.compile(
    r"^ppt/(slides/slide|notesSlides/notesSlide)\d+\.xml$"
)


# ---------------------------------------------------------------------------
# Extraction / injection
# ---------------------------------------------------------------------------


def pptx_extract(root: etree._Element) -> list[dict]:
    """
    Parcourt tous les <a:p> et retourne un catalogue de segments non vides.
    Les <a:t> enfants d'un <a:fld> (champs automatiques : n° de slide, date)
    sont exclus car ils ne doivent pas être traduits.
    """
    catalogue = []
    seg_id = 0
    for para in root.iter(f"{A}p"):
        text = "".join(
            (t.text or "")
            for t in para.iter(f"{A}t")
            if t.getparent() is not None and t.getparent().tag != f"{A}fld"
        ).strip()
        if text:
            seg_id += 1
            catalogue.append({"id": seg_id, "text": text, "elem": para})
    return catalogue


def pptx_inject(para_elem: etree._Element, new_text: str) -> None:
    """
    Réinjecte new_text dans un paragraphe <a:p>.

    Met la traduction dans le premier <a:t> hors champ, vide les suivants.
    Les <a:rPr> (gras, italique, police) ne sont jamais modifiés.
    """
    t_elements = [
        t for t in para_elem.iter(f"{A}t")
        if t.getparent() is not None and t.getparent().tag != f"{A}fld"
    ]
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


def translate_pptx(path: Path, output_dir: Path) -> None:
    translate_zip_document(path, output_dir, PPTX_PARTS, pptx_extract, pptx_inject)
