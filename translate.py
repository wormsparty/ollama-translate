import os
import requests
from pathlib import Path
from docx import Document

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "mistral-small3.2"
MAX_WORDS = 3000
OVERLAP_PARAGRAPHS = 2

SYSTEM_PROMPT = (
    "Tu es un traducteur professionnel français vers allemand. "
    "Traduis le texte suivant du français vers l'allemand. "
    "Conserve la structure logique et les sauts de paragraphes. "
    "Ne rien ajouter ni retirer au contenu. "
    "Réponds uniquement avec la traduction, sans commentaire."
)


def extract_paragraphs(docx_path: Path) -> list[str]:
    doc = Document(docx_path)
    return [p.text for p in doc.paragraphs if p.text.strip()]


def count_words(paragraphs: list[str]) -> int:
    return sum(len(p.split()) for p in paragraphs)


def split_into_chunks(paragraphs: list[str], max_words: int, overlap: int) -> list[list[str]]:
    chunks = []
    current_chunk = []
    current_words = 0

    for para in paragraphs:
        para_words = len(para.split())
        if current_words + para_words > max_words and current_chunk:
            chunks.append(current_chunk)
            # Keep last `overlap` paragraphs for context continuity
            current_chunk = current_chunk[-overlap:]
            current_words = sum(len(p.split()) for p in current_chunk)
        current_chunk.append(para)
        current_words += para_words

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def translate_text(text: str) -> str:
    prompt = f"{SYSTEM_PROMPT}\n\n{text}"
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
    }
    response = requests.post(OLLAMA_URL, json=payload, timeout=300)
    response.raise_for_status()
    return response.json()["response"].strip()


def translate_document(docx_path: Path, output_dir: Path) -> None:
    print(f"[→] Traitement : {docx_path.name}")
    paragraphs = extract_paragraphs(docx_path)

    if not paragraphs:
        print(f"  [!] Document vide, ignoré.")
        return

    total_words = count_words(paragraphs)
    print(f"  Mots détectés : {total_words}")

    if total_words <= MAX_WORDS:
        text = "\n\n".join(paragraphs)
        print(f"  Traduction en un seul bloc...")
        translated = translate_text(text)
        translated_parts = [translated]
    else:
        chunks = split_into_chunks(paragraphs, MAX_WORDS, OVERLAP_PARAGRAPHS)
        print(f"  Document long : {len(chunks)} sections")
        translated_parts = []
        for i, chunk in enumerate(chunks, 1):
            print(f"  Section {i}/{len(chunks)}...")
            text = "\n\n".join(chunk)
            translated_parts.append(translate_text(text))

    output_path = output_dir / (docx_path.stem + ".txt")
    output_path.write_text("\n\n".join(translated_parts), encoding="utf-8")
    print(f"  [✓] Sauvegardé : {output_path}")


def main() -> None:
    input_dir = Path("fr")
    output_dir = Path("de")

    if not input_dir.exists():
        print(f"[!] Dossier source '{input_dir}' introuvable.")
        return

    output_dir.mkdir(exist_ok=True)

    docx_files = sorted(input_dir.glob("*.docx"))
    if not docx_files:
        print(f"[!] Aucun fichier .docx trouvé dans '{input_dir}'.")
        return

    print(f"[i] {len(docx_files)} fichier(s) trouvé(s) dans '{input_dir}'\n")

    for i, docx_path in enumerate(docx_files, 1):
        print(f"--- Fichier {i}/{len(docx_files)} ---")
        try:
            translate_document(docx_path, output_dir)
        except requests.exceptions.ConnectionError:
            print(f"  [✗] Impossible de joindre Ollama sur {OLLAMA_URL}. Est-il démarré ?")
        except requests.exceptions.Timeout:
            print(f"  [✗] Timeout pour {docx_path.name}.")
        except Exception as e:
            print(f"  [✗] Erreur inattendue : {e}")
        print()

    print("[i] Terminé.")


if __name__ == "__main__":
    main()
