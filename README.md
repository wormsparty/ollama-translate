# Traduction ollama locale

Ce projet vise à traduire des documents en français vers l'allemand (pour des documents officiels suisses). Il transforme des .docx et .pptx

1. Placer vos documents à traduire dans `fr/`
2. Lancer `run_docx.sh` pour traduire les .docx
3. Lancer `run_pptx.sh` pour traduire les .pptx
4. Le résultat sera placé dans `de/`

## Prérequis

- Linux: Aucun, `ollama` sera installé et le modèle `mistral` sera installé
- Windows: Utiliser WSL

## Limitations

- Compter environ 1 minute par page
- Les images sont gardées telles quelles
- Quelques erreurs de style et des caractères étrangers peuvent apparaitre