Je veux un script Python qui traduit des fichiers .docx du français vers l'allemand en utilisant Ollama avec le modèle Mistral-small3.2 en local (confidentialité totale, aucune donnée envoyée vers un service externe).
Workflow souhaité :

Lire tous les fichiers .docx dans un dossier fr/
Extraire le texte brut de chaque document (en préservant les sauts de paragraphes/sections pour donner du contexte au modèle)
Envoyer le texte en bloc à Ollama (http://localhost:11434) avec un prompt de traduction FR→DE — ne pas segmenter phrase par phrase, envoyer le document entier ou par grandes sections pour préserver le contexte
Écrire le texte traduit dans un fichier .txt du même nom dans un dossier de/

Contraintes techniques :

Utiliser python-docx pour l'extraction
Utiliser requests pour appeler l'API Ollama (/api/generate ou /api/chat)
Le prompt système doit préciser : traducteur professionnel FR→DE, conserver la mise en forme logique (paragraphes), ne rien ajouter ni retirer
Gérer les documents longs : si le texte dépasse ~3000 mots, le découper en grandes sections (par paragraphes groupés) avec chevauchement de contexte entre les morceaux
Logger la progression fichier par fichier dans le terminal
Créer le dossier de/ s'il n'existe pas

Structure du projet :
translate.py
fr/    ← fichiers .docx source
de/    ← fichiers .txt traduits (sortie)
Génère le script complet avec les dépendances nécessaires (requirements.txt).