# Traduction ollama locale

Ce projet vise à traduire des documents en français vers l'allemand (pour des documents officiels suisses). Il transforme des .docx et .pptx, tout en garantissant la confidentialité des documents.

## Lancement

1. Placer vos documents à traduire dans `fr/`
2. Lancer `run_docx.sh` pour traduire les .docx
3. Lancer `run_pptx.sh` pour traduire les .pptx
4. Le résultat sera placé dans `de/`

## Prérequis

- `mistral-small3.2` requiert 15 GB de RAM, à adapter en fonction du hardware cible
- Windows: Utiliser WSL

## Limitations

- Compter environ 1 minute par page (pour le hardware testé avec le modèle `mistral-small3.2`)
- Les images sont gardées telles quelles
- Quelques erreurs de style et des caractères étrangers peuvent apparaitre