#!/usr/bin/env python3
"""
translate_docx.py — Traduit un .docx fr → de en préservant la mise en forme.

Stratégie :
1. Lire le .docx (ZIP de XML) directement avec lxml
2. Extraire le texte de chaque paragraphe avec un ID numérique
3. Envoyer tout le texte en une seule requête Ollama (contexte global)
   → chunking par fenêtre glissante si le document est trop long
4. Réinjecter les traductions dans les <w:t> du XML d'origine
   → les <w:rPr> (gras, italique, police) et les images ne sont pas touchés
5. Réécrire le .docx

Usage : python translate_docx.py
  Lit les .docx dans fr/, écrit les traductions dans de/

Parties XML traitées : document.xml, header*.xml, footer*.xml,
                       footnotes.xml, endnotes.xml
"""

import re
from pathlib import Path

from lxml import etree

from translate_core import XML_SPACE, run_batch, translate_zip_document

# ---------------------------------------------------------------------------
# Constantes XML (namespace WordprocessingML)
# ---------------------------------------------------------------------------

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{W_NS}}}"

TRANSLATABLE_PARTS = re.compile(
    r"^word/(document|header\d*|footer\d*|footnotes|endnotes)\.xml$"
)

# ---------------------------------------------------------------------------
# Extraction et réinjection (spécifique DOCX)
# ---------------------------------------------------------------------------


def extract_catalogue(root: etree._Element) -> list[dict]:
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


def set_para_text(para_elem: etree._Element, new_text: str) -> None:
    """
    Réinjecte new_text dans un paragraphe <w:p>.

    Place tout le texte traduit dans le premier <w:r> contenant un <w:t>,
    en conservant son <w:rPr> (gras, italique, police).
    Les runs suivants purement textuels (<w:rPr> + <w:t> uniquement) sont
    supprimés entièrement pour éviter les runs vides parasites.
    Les runs contenant d'autres éléments (<w:drawing>, <w:br>, <w:sym>…)
    voient simplement leur <w:t> vidé — leur contenu non-texte est préservé.
    """
    # Tous les <w:r> descendants contenant au moins un <w:t>
    text_runs = [
        r for r in para_elem.iter(f"{W}r")
        if any(child.tag == f"{W}t" for child in r)
    ]
    if not text_runs:
        return

    # Texte traduit dans le premier run
    first_run = text_runs[0]
    first_t_list = [c for c in first_run if c.tag == f"{W}t"]
    first_t = first_t_list[0]
    first_t.text = new_text
    first_t.set(XML_SPACE, "preserve")
    for extra_t in first_t_list[1:]:
        first_run.remove(extra_t)

    # Runs suivants : supprimer si purement textuels, vider <w:t> sinon
    for run in text_runs[1:]:
        non_text_children = [
            c for c in run if c.tag not in (f"{W}t", f"{W}rPr")
        ]
        if non_text_children:
            # Contient des dessins, sauts de ligne, etc. → vider seulement les <w:t>
            for t in run:
                if t.tag == f"{W}t":
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
    run_batch("*.docx", translate_document)


if __name__ == "__main__":
    main()
