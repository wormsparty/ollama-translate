import requests
from pathlib import Path
from docx import Document

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "mistral-small3.2"

SYSTEM_PROMPT = (
    "Tu es un traducteur professionnel français vers allemand spécialisé dans les documents administratifs et appels d'offre suisses. "
    "Traduis le texte suivant du français vers l'allemand standard suisse (Schweizer Hochdeutsch) en respectant ces règles : "
    "utilise toujours 'ss' à la place de 'ß' (le ß n'existe pas en Suisse) ; "
    "utilise les guillemets suisses « » ; "
    "emploie le vocabulaire administratif helvétique (ex: 'Offerte' plutôt que 'Angebot', 'Submission', 'Kanton', 'Gemeinde', etc.) ; "
    "maintiens un registre formel et neutre adapté aux marchés publics suisses. "
    "Conserve la structure logique et les sauts de paragraphes. "
    "Ne rien ajouter ni retirer au contenu. "
    "Réponds uniquement avec la traduction, sans commentaire."
)


def extract_text(docx_path: Path) -> str:
    doc = Document(docx_path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)


def translate_text(text: str) -> str:
    payload = {
        "model": MODEL,
        "system": SYSTEM_PROMPT,
        "prompt": text,
        "stream": False,
    }
    response = requests.post(OLLAMA_URL, json=payload, timeout=600)
    response.raise_for_status()
    return response.json()["response"].strip().replace("ß", "ss")


def translate_document(docx_path: Path, output_dir: Path) -> None:
    print(f"[→] Traitement : {docx_path.name}")

    text = extract_text(docx_path)
    if not text:
        print(f"  [!] Document vide, ignoré.")
        return

    word_count = len(text.split())
    print(f"  Mots détectés : {word_count}")
    print(f"  Traduction en cours...")

    translated = translate_text(text)

    output_path = output_dir / (docx_path.stem + ".md")
    output_path.write_text(translated, encoding="utf-8-sig")
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