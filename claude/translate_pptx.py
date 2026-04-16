#!/usr/bin/env python3
"""
translate_pptx.py — Traduit un .pptx fr → de en préservant la mise en forme.

Stratégie identique à translate_docx.py, adaptée au format PPTX :
1. Lire le .pptx (ZIP de XML) directement avec lxml
2. Extraire le texte de chaque paragraphe <a:p> avec un ID numérique
3. Envoyer tout le texte en une seule requête Ollama (contexte global)
   → chunking par fenêtre glissante si le document est trop long
4. Réinjecter les traductions dans les <a:t> du XML d'origine
   → les <a:rPr> (gras, italique, police) et les images ne sont pas touchés
5. Réécrire le .pptx

Usage : python translate_pptx.py
  Lit les .pptx dans fr/, écrit les traductions dans de/

Parties XML traitées : ppt/slides/slide*.xml, ppt/notesSlides/notesSlide*.xml

Limitation : si un paragraphe contient plusieurs runs avec des mises en forme
  différentes (ex. un mot en gras au milieu), tout le texte traduit est fusionné
  dans le premier <a:t>. La mise en forme du premier run est préservée, celle
  des runs suivants est perdue.
  Les champs automatiques (<a:fld> : numéros de slide, date) sont ignorés.
"""

import re
from pathlib import Path

from lxml import etree

from translate_core import XML_SPACE, run_batch, translate_zip_document

# ---------------------------------------------------------------------------
# Constantes XML (namespace DrawingML, utilisé par PPTX pour le texte)
# ---------------------------------------------------------------------------

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
A = f"{{{A_NS}}}"

TRANSLATABLE_PARTS = re.compile(
    r"^ppt/(slides/slide|notesSlides/notesSlide)\d+\.xml$"
)

# ---------------------------------------------------------------------------
# Extraction et réinjection (spécifique PPTX)
# ---------------------------------------------------------------------------


def extract_catalogue(root: etree._Element) -> list[dict]:
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


def set_para_text(para_elem: etree._Element, new_text: str) -> None:
    """
    Réinjecte new_text dans un paragraphe <a:p>.

    Place tout le texte traduit dans le premier <a:r> (hors champ <a:fld>)
    contenant un <a:t>, en conservant son <a:rPr> (gras, italique, police).
    Les runs suivants purement textuels (<a:rPr> + <a:t> uniquement) sont
    supprimés entièrement.
    Les runs contenant d'autres éléments voient leur <a:t> vidé.
    Les champs automatiques (<a:fld> : numéros de slide, date) sont ignorés.
    """
    # Tous les <a:r> hors <a:fld> contenant au moins un <a:t>
    text_runs = [
        r for r in para_elem.iter(f"{A}r")
        if r.getparent() is not None
        and r.getparent().tag != f"{A}fld"
        and any(child.tag == f"{A}t" for child in r)
    ]
    if not text_runs:
        return

    # Texte traduit dans le premier run
    first_run = text_runs[0]
    first_t_list = [c for c in first_run if c.tag == f"{A}t"]
    first_t = first_t_list[0]
    first_t.text = new_text
    first_t.set(XML_SPACE, "preserve")
    for extra_t in first_t_list[1:]:
        first_run.remove(extra_t)

    # Runs suivants : supprimer si purement textuels, vider <a:t> sinon
    for run in text_runs[1:]:
        non_text_children = [
            c for c in run if c.tag not in (f"{A}t", f"{A}rPr")
        ]
        if non_text_children:
            # Contient des éléments non-texte → vider seulement les <a:t>
            for t in run:
                if t.tag == f"{A}t":
                    t.text = ""
                    t.attrib.pop(XML_SPACE, None)
        else:
            # Run purement textuel → supprimer
            parent = run.getparent()
            if parent is not None:
                parent.remove(run)


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------


def translate_document(path: Path, output_dir: Path) -> None:
    translate_zip_document(path, output_dir, TRANSLATABLE_PARTS, extract_catalogue, set_para_text)


def main() -> None:
    run_batch("*.pptx", translate_document)


if __name__ == "__main__":
    main()
