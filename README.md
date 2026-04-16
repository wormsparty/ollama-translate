# Traduction ollama locale

Ce projet vise à traduire des documents en français vers l'allemand (pour des documents officiels suisses). Il transforme des .docx et .pptx, tout en garantissant la confidentialité des documents.

## Lancement

0. Placer vos documents à traduire dans `fr/`
1. Aller dans le dossier `claude/` ou `ollama/`
2. Lancer `run.sh` pour traduire les .docx et .pptx
3. Le résultat seront dans `de/`

## Prérequis

- Si Ollama: 
 * `mistral-small3.2` requiert 15 GB de RAM, à adapter en fonction du hardware cible
- Windows: Utiliser WSL

## Limitations

- Si Ollama:
 * Compter environ 1 minute par page (pour le hardware testé avec le modèle `mistral-small3.2`)
 * Quelques erreurs de style et des caractères étrangers peuvent apparaitre
- Les images sont gardées telles quelles
