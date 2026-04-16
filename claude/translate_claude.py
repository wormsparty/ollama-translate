#!/usr/bin/env python3
"""
translate_core.py — Fonctions partagées entre translate_docx.py et translate_pptx.py.

Utilise `claude -p` (Claude Code CLI) pour la traduction et la vérification.
Pas de chunking : le document entier est envoyé en un seul appel (contexte 200k).
"""

import re
import subprocess
import traceback
import zipfile
from pathlib import Path
from typing import Callable

from lxml import etree

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL_TRANSLATE = "claude-sonnet-4-6"
MODEL_VERIFY = "claude-haiku-4-5-20251001"

SYSTEM_TRANSLATE = (
    "Tu es un moteur de traduction automatique français → allemand suisse. "
    "Tu reçois une liste de segments numérotés au format [ID] texte. "
    "Tu réponds EXCLUSIVEMENT avec la liste traduite au même format [ID] texte, "
    "sans aucun mot introductif, salutation, explication, commentaire ou signature. "
    "Règles Schweizer Hochdeutsch : "
    "utilise 'ss' à la place de 'ß' (le ß n'existe pas en Suisse) ; "
    "utilise les guillemets suisses « » ; "
    "emploie le vocabulaire administratif helvétique (ex: 'Offerte' plutôt que 'Angebot', "
    "'Submission', 'Kanton', 'Gemeinde') ; "
    "registre formel et neutre, marchés publics suisses ; "
    "ne rien ajouter ni retirer au contenu. "
    "IMPORTANT : conserve EXACTEMENT le format [ID] pour chaque segment. "
    "Ne fusionne, ne divise et ne réordonne aucun segment."
)

SYSTEM_VERIFY = (
    "Tu es un relecteur spécialisé en traduction français → allemand suisse. "
    "Tu reçois deux listes de segments numérotés : source FR et traduction DE. "
    "Pour chaque segment, vérifie le sens, la fidélité et les règles suisses "
    "(pas de ß, guillemets « », vocabulaire helvétique, registre formel). "
    "Réponds UNIQUEMENT au format suivant, un segment par ligne :\n"
    "[ID] OK\n"
    "[ID] CORRECTION: <texte corrigé complet>\n"
    "[ID] ALERTE: <explication courte du problème>\n"
    "Si tout est correct, réponds uniquement : TOUT_OK"
)

XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

Catalogue = list[dict]
ExtractFn = Callable[[etree._Element], Catalogue]
InjectFn = Callable[[etree._Element, str], None]
TranslateFn = Callable[[Path, Path], None]

# ---------------------------------------------------------------------------
# Appel Claude CLI
# ---------------------------------------------------------------------------


def _call_claude(system_prompt: str, user_text: str, model: str, timeout: int = 600) -> str:
    """Appelle `claude -p` en subprocess et retourne le texte brut de la réponse."""
    result = subprocess.run(
        ["claude", "-p", "--model", model, "--system-prompt", system_prompt],
        input=user_text,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"claude CLI erreur (code {result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Traduction
# ---------------------------------------------------------------------------


def translate_catalogue(catalogue: Catalogue) -> dict[int, str]:
    """Traduit tout le catalogue en un seul appel Claude. Retourne {id: texte_traduit}."""
    user_text = "\n".join(f"[{e['id']}] {e['text']}" for e in catalogue)
    raw = _call_claude(SYSTEM_TRANSLATE, user_text, MODEL_TRANSLATE)

    translated: dict[int, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^\[(\d+)\]\s+(.*)", line)
        if m:
            translated[int(m.group(1))] = m.group(2)
    return translated


# ---------------------------------------------------------------------------
# Vérification
# ---------------------------------------------------------------------------


def verify_translations(
    catalogue: Catalogue, translations: dict[int, str]
) -> dict[int, dict]:
    """
    Envoie source + traductions à Claude pour vérification.
    Seuls les segments effectivement traduits sont envoyés (les manquants sont ignorés).
    Retourne {id: {"type": "CORRECTION"|"ALERTE", "text": str}}.
    """
    translated_entries = [e for e in catalogue if e["id"] in translations]
    if not translated_entries:
        return {}

    source_lines = "\n".join(f"[{e['id']}] {e['text']}" for e in translated_entries)
    trans_lines = "\n".join(
        f"[{e['id']}] {translations[e['id']]}" for e in translated_entries
    )
    user_text = f"=== SOURCE FR ===\n{source_lines}\n\n=== TRADUCTION DE ===\n{trans_lines}"

    raw = _call_claude(SYSTEM_VERIFY, user_text, MODEL_VERIFY)

    if raw.strip() == "TOUT_OK":
        return {}

    issues: dict[int, dict] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^\[(\d+)\]\s+CORRECTION:\s+(.*)", line)
        if m:
            issues[int(m.group(1))] = {"type": "CORRECTION", "text": m.group(2)}
            continue
        m = re.match(r"^\[(\d+)\]\s+ALERTE:\s+(.*)", line)
        if m:
            issues[int(m.group(1))] = {"type": "ALERTE", "text": m.group(2)}
    return issues


# ---------------------------------------------------------------------------
# Rapport Markdown
# ---------------------------------------------------------------------------


def write_report(
    source_file: Path,
    catalogue: Catalogue,
    translations: dict[int, str],
    issues: dict[int, dict],
    applied_corrections: set[int],
    missing_ids: set[int],
    report_path: Path,
) -> None:
    """Génère un rapport Markdown des corrections appliquées, alertes et segments non traduits."""
    corrections = {k: v for k, v in issues.items() if v["type"] == "CORRECTION"}
    alertes = {k: v for k, v in issues.items() if v["type"] == "ALERTE"}
    seg_map = {e["id"]: e["text"] for e in catalogue}

    lines = [
        f"# Rapport de vérification — {source_file.name}",
        "",
        f"**Segments traduits :** {len(translations)}  ",
        f"**Corrections appliquées :** {len(corrections)}  ",
        f"**Alertes :** {len(alertes)}  ",
        f"**Segments non traduits :** {len(missing_ids)}  ",
        "",
    ]

    if not issues and not missing_ids:
        lines.append("Aucun problème détecté.")
    else:
        if corrections:
            lines += ["## Corrections appliquées", ""]
            for seg_id, issue in sorted(corrections.items()):
                statut = "✓ appliquée" if seg_id in applied_corrections else "⚠ non appliquée"
                lines += [
                    f"### Segment [{seg_id}] — {statut}",
                    f"**Source FR :** {seg_map.get(seg_id, '?')}  ",
                    f"**Traduction finale :** {translations.get(seg_id, '?')}",
                    "",
                ]

        if alertes:
            lines += ["## Alertes", ""]
            for seg_id, issue in sorted(alertes.items()):
                lines += [
                    f"### Segment [{seg_id}]",
                    f"**Source FR :** {seg_map.get(seg_id, '?')}  ",
                    f"**Traduction actuelle :** {translations.get(seg_id, '?')}  ",
                    f"**Problème :** {issue['text']}",
                    "",
                ]

        if missing_ids:
            lines += [
                "## Segments non traduits",
                "",
                f"*{len(missing_ids)} segment(s) n'ont pas pu être traduits après deux tentatives.*"
                " *Le texte source français a été conservé dans le document.*",
                "",
            ]
            for seg_id in sorted(missing_ids):
                lines += [
                    f"### Segment [{seg_id}]",
                    f"**Source FR :** {seg_map.get(seg_id, '?')}",
                    "",
                ]

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  [rapport] {report_path.name}")


# ---------------------------------------------------------------------------
# Pipeline XML générique
# ---------------------------------------------------------------------------


def translate_zip_document(
    path: Path,
    output_dir: Path,
    parts_pattern: re.Pattern,
    extract_fn: ExtractFn,
    inject_fn: InjectFn,
) -> None:
    """
    Traduit toutes les parties XML d'un fichier Office Open XML (docx, pptx…).

    Les racines XML sont conservées en mémoire après traduction initiale.
    Les corrections suggérées par la vérification sont appliquées directement
    sur les éléments XML avant sérialisation.
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

    # Les IDs globaux sont décalés à chaque partie pour éviter les collisions.
    global_catalogue: Catalogue = []
    global_translations: dict[int, str] = {}
    global_id_to_elem: dict[int, etree._Element] = {}
    global_missing_ids: set[int] = set()
    part_roots: dict[str, etree._Element] = {}
    id_offset = 0

    for part_name in parts_to_translate:
        print(f"  Traduction de {part_name}...")
        root = etree.fromstring(entries[part_name])
        catalogue = extract_fn(root)

        if not catalogue:
            continue

        total_words = sum(len(e["text"].split()) for e in catalogue)
        print(f"    {part_name}: {len(catalogue)} segments, {total_words} mots")

        translations = translate_catalogue(catalogue)

        missing_entries = [e for e in catalogue if e["id"] not in translations]
        if missing_entries:
            print(f"    [!] {len(missing_entries)} segment(s) non traduit(s), nouvelle tentative...")
            retry = translate_catalogue(missing_entries)
            translations.update(retry)
            still_missing = [e for e in missing_entries if e["id"] not in translations]
            if still_missing:
                ids = [e["id"] for e in still_missing]
                sample = ids[:5]
                suffix = "..." if len(ids) > 5 else ""
                print(f"    [✗] {len(ids)} segment(s) toujours non traduit(s) — IDs: {sample}{suffix}")

        for entry in catalogue:
            if entry["id"] in translations:
                inject_fn(entry["elem"], translations[entry["id"]])

        for entry in catalogue:
            gid = entry["id"] + id_offset
            global_catalogue.append({"id": gid, "text": entry["text"]})
            if entry["id"] in translations:
                global_translations[gid] = translations[entry["id"]]
                global_id_to_elem[gid] = entry["elem"]
            else:
                global_missing_ids.add(gid)
        id_offset += len(catalogue)
        part_roots[part_name] = root

    # Vérification globale + application directe des corrections
    if global_catalogue:
        print(f"  Vérification ({len(global_translations)} segments)...")
        issues = verify_translations(global_catalogue, global_translations)

        applied_corrections: set[int] = set()
        for seg_id, issue in issues.items():
            if issue["type"] == "CORRECTION" and seg_id in global_id_to_elem:
                inject_fn(global_id_to_elem[seg_id], issue["text"])
                global_translations[seg_id] = issue["text"]
                applied_corrections.add(seg_id)

        nb_corrections = len(applied_corrections)
        nb_alertes = sum(1 for v in issues.values() if v["type"] == "ALERTE")
        if issues:
            print(f"  [vérif] {nb_corrections} correction(s) appliquée(s), {nb_alertes} alerte(s)")
        else:
            print("  [vérif] Aucun problème détecté")
        if global_missing_ids:
            print(f"  [!] {len(global_missing_ids)} segment(s) non traduits conservés en français")

        report_path = output_dir / (path.stem + "_rapport.md")
        write_report(
            path, global_catalogue, global_translations,
            issues, applied_corrections, global_missing_ids, report_path,
        )

    # Sérialisation des racines modifiées (traduction + corrections)
    for part_name, root in part_roots.items():
        entries[part_name] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, data in entries.items():
            zout.writestr(name, data)

    print(f"  [✓] Sauvegardé : {output_path}")


# ---------------------------------------------------------------------------
# Boucle principale partagée
# ---------------------------------------------------------------------------


def run_batch(glob: str, translate_fn: TranslateFn) -> None:
    """Scanne fr/ pour les fichiers correspondant à glob, traduit chacun dans de/."""
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
        except subprocess.TimeoutExpired:
            print(f"  [✗] Timeout pour {path.name}.")
        except RuntimeError as e:
            print(f"  [✗] {e}")
        except Exception as e:
            print(f"  [✗] Erreur inattendue : {e}")
            traceback.print_exc()
        print()

    print("[i] Terminé.")
