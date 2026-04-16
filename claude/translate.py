#!/usr/bin/env python3
"""
translate.py — Traduit tous les .docx et .pptx du dossier fr/ vers de/.

Usage : python translate.py
"""

from translate_claude import run_batch
from translate_docx import translate_document as translate_docx
from translate_pptx import translate_document as translate_pptx


def main() -> None:
    run_batch("../*.docx", translate_docx)
    run_batch("../*.pptx", translate_pptx)


if __name__ == "__main__":
    main()
