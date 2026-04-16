#!/usr/bin/env python3
"""
translate_core.py — Fonctions partagées entre translate_docx.py et translate_pptx.py.

Contient : configuration Ollama, chunking, appel au modèle,
           pipeline XML générique et boucle principale.
"""

import json
import re
import traceback
import zipfile
from pathlib import Path
from typing import Callable

import requests
from lxml import etree

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "mistral-small3.2"

# Nombre max de mots par chunk (si le document dépasse le contexte d'Ollama)
MAX_WORDS_PER_CHUNK = 800

# Chevauchement en nombre de segments entre deux chunks consécutifs
CHUNK_OVERLAP = 5

SYSTEM_PROMPT = (
    "Tu es un moteur de traduction automatique français vers allemand. "
    "Tu reçois une liste de segments numérotés au format [ID] texte. "
    "Tu réponds EXCLUSIVEMENT avec la liste traduite au même format [ID] texte, "
    "sans aucun mot introductif, salutation, explication, commentaire ou signature. "
    "Règles de traduction : "
    "utilise toujours 'ss' à la place de 'ß' (le ß n'existe pas en Suisse) ; "
    "utilise les guillemets suisses « » ; "
    "emploie le vocabulaire administratif helvétique (ex: 'Offerte' plutôt que 'Angebot', "
    "'Submission', 'Kanton', 'Gemeinde', etc.) ; "
    "maintiens un registre formel et neutre adapté aux marchés publics suisses ; "
    "ne rien ajouter ni retirer au contenu. "
    "IMPORTANT : conserve EXACTEMENT le format [ID] pour chaque segment traduit. "
    "Ne fusionne, ne divise et ne réordonne aucun segment."
)

XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

Catalogue = list[dict]


def chunk_catalogue(catalogue: Catalogue) -> list[Catalogue]:
    """
    Découpe le catalogue en chunks de MAX_WORDS_PER_CHUNK mots max,
    avec un chevauchement de CHUNK_OVERLAP segments pour la continuité
    terminologique.

    Si le document tient en un seul chunk, retourne [[all entries]].
    """
    total_words = sum(len(e["text"].split()) for e in catalogue)
    if total_words <= MAX_WORDS_PER_CHUNK:
        return [catalogue]

    chunks: list[Catalogue] = []
    i = 0
    while i < len(catalogue):
        chunk: Catalogue = []
        words = 0
        j = i
        while j < len(catalogue) and words + len(catalogue[j]["text"].split()) <= MAX_WORDS_PER_CHUNK:
            chunk.append(catalogue[j])
            words += len(catalogue[j]["text"].split())
            j += 1
        if not chunk:
            # Paragraphe seul trop long — on le force dans son propre chunk
            chunk = [catalogue[j]]
            j += 1
        chunks.append(chunk)
        # Chevauchement : reculer de CHUNK_OVERLAP segments pour le prochain chunk
        i = max(i + 1, j - CHUNK_OVERLAP)

    return chunks


# ---------------------------------------------------------------------------
# Traduction via Ollama
# ---------------------------------------------------------------------------


def translate_chunk(chunk: Catalogue) -> dict[int, str]:
    """
    Envoie un chunk de catalogue à Ollama.
    Retourne {id: texte_traduit}.
    """
    full_text = "\n".join(f"[{e['id']}] {e['text']}" for e in chunk)

    payload = {
        "model": MODEL,
        "system": SYSTEM_PROMPT,
        "prompt": full_text,
        "stream": True,
    }
    response = requests.post(OLLAMA_URL, json=payload, stream=True, timeout=600)
    response.raise_for_status()

    raw_parts: list[str] = []
    for line in response.iter_lines():
        if line:
            data = json.loads(line)
            raw_parts.append(data.get("response", ""))
            if data.get("done"):
                break
    raw = "".join(raw_parts).strip()

    translated: dict[int, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^\[(\d+)\]\s*(.*)", line)
        if m:
            seg_id = int(m.group(1))
            text = m.group(2).replace("ß", "ss")
            translated[seg_id] = text

    return translated


# ---------------------------------------------------------------------------
# Pipeline XML générique
# ---------------------------------------------------------------------------

ExtractFn = Callable[[etree._Element], Catalogue]
InjectFn = Callable[[etree._Element, str], None]


def translate_xml_part(
    xml_bytes: bytes,
    part_label: str,
    extract_fn: ExtractFn,
    inject_fn: InjectFn,
) -> bytes:
    """
    Traduit une partie XML d'un document Office Open XML.

    extract_fn(root) → catalogue de segments à traduire
    inject_fn(elem, text) → réinjecte la traduction dans l'élément
    """
    root = etree.fromstring(xml_bytes)
    catalogue = extract_fn(root)

    if not catalogue:
        return xml_bytes

    total_words = sum(len(e["text"].split()) for e in catalogue)
    chunks = chunk_catalogue(catalogue)
    nb_chunks = len(chunks)
    print(f"    {part_label}: {len(catalogue)} segments, {total_words} mots, {nb_chunks} chunk(s)")

    all_translations: dict[int, str] = {}
    for i, chunk in enumerate(chunks, 1):
        if nb_chunks > 1:
            ids = f"{chunk[0]['id']}–{chunk[-1]['id']}"
            print(f"      Chunk {i}/{nb_chunks} (segments {ids})...")
        translations = translate_chunk(chunk)
        # En cas de chevauchement : le dernier chunk gagne (version la plus contextualisée)
        all_translations.update(translations)

    missing = [e["id"] for e in catalogue if e["id"] not in all_translations]
    if missing:
        sample = missing[:5]
        suffix = "..." if len(missing) > 5 else ""
        print(f"    [!] {len(missing)} segment(s) non traduit(s) — IDs: {sample}{suffix} (texte original conservé)")

    for entry in catalogue:
        if entry["id"] in all_translations:
            inject_fn(entry["elem"], all_translations[entry["id"]])

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def translate_zip_document(
    path: Path,
    output_dir: Path,
    parts_pattern: re.Pattern,
    extract_fn: ExtractFn,
    inject_fn: InjectFn,
) -> None:
    """
    Traduit toutes les parties XML d'un fichier Office Open XML (docx, pptx…).

    parts_pattern : regex qui sélectionne les entrées ZIP à traduire
    extract_fn / inject_fn : fonctions spécifiques au format (voir translate_xml_part)
    """
    print(f"[→] Traitement : {path.name}")
    output_path = output_dir / path.name

    with zipfile.ZipFile(path, "r") as zin:
        names = zin.namelist()
        entries: dict[str, bytes] = {name: zin.read(name) for name in names}

    parts_to_translate = sorted(n for n in names if parts_pattern.match(n))
    if not parts_to_translate:
        print("  [!] Aucune partie XML traduisible trouvée.")
        return

    print(f"  Parties : {', '.join(parts_to_translate)}")

    for part_name in parts_to_translate:
        print(f"  Traduction de {part_name}...")
        entries[part_name] = translate_xml_part(entries[part_name], part_name, extract_fn, inject_fn)

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, data in entries.items():
            zout.writestr(name, data)

    print(f"  [✓] Sauvegardé : {output_path}")


# ---------------------------------------------------------------------------
# Boucle principale partagée
# ---------------------------------------------------------------------------

TranslateFn = Callable[[Path, Path], None]


def run_batch(glob: str, translate_fn: TranslateFn) -> None:
    """
    Scanne fr/ pour les fichiers correspondant à glob, traduit chacun dans de/.

    glob : motif passé à Path.glob(), ex. "*.docx" ou "*.pptx"
    translate_fn : fonction(path, output_dir) spécifique au format
    """
    input_dir = Path("../fr")
    output_dir = Path("../de")

    if not input_dir.exists():
        print(f"[!] Dossier source '{input_dir}' introuvable.")
        return

    output_dir.mkdir(exist_ok=True)

    files = sorted(input_dir.glob(glob))
    if not files:
        print(f"[!] Aucun fichier {glob} trouvé dans '{input_dir}'.")
        return

    print(f"[i] {len(files)} fichier(s) trouvé(s) dans '{input_dir}'\n")

    for i, path in enumerate(files, 1):
        print(f"--- Fichier {i}/{len(files)} ---")
        try:
            translate_fn(path, output_dir)
        except requests.exceptions.ConnectionError:
            print(f"  [✗] Impossible de joindre Ollama sur {OLLAMA_URL}. Est-il démarré ?")
        except requests.exceptions.Timeout:
            print(f"  [✗] Timeout pour {path.name}.")
        except Exception as e:
            print(f"  [✗] Erreur inattendue : {e}")
            traceback.print_exc()
        print()

    print("[i] Terminé.")
