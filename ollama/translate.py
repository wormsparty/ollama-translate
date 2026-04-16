#!/usr/bin/env python3
"""
translate.py — Point d'entrée : traduit tous les .docx et .pptx de fr/ vers de/.

Usage : python translate.py

Architecture :
  translate_core.py  — config Ollama, chunking, pipeline XML générique, boucle batch
  translate_docx.py  — extraction / injection WordprocessingML (DOCX)
  translate_pptx.py  — extraction / injection DrawingML (PPTX)
"""

from translate_ollama import run_batch
from translate_docx import translate_docx
from translate_pptx import translate_pptx


def main() -> None:
    run_batch("*.docx", translate_docx)
    run_batch("*.pptx", translate_pptx)


if __name__ == "__main__":
    main()
