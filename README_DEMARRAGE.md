# P&ID Analyzer — démarrage débutant (Windows)

## 1. Installer les outils
- Python 3.11+ depuis https://www.python.org/downloads/ (cocher « Add Python to PATH » si proposé)
- VS Code depuis https://code.visualstudio.com/
- Extension Python pour VS Code

## 2. Ouvrir le dossier
Décompresser l'archive et ouvrir `pid_analyzer_starter` dans VS Code (`File > Open Folder`).
Ouvrir un terminal intégré (`Terminal > New Terminal`).

## 3. Créer un environnement virtuel
En terminal PowerShell :

    py -m venv .venv
    .\.venv\Scripts\python.exe -m pip install --upgrade pip
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt

Cette méthode évite de devoir changer la politique d'exécution PowerShell.

## 4. Lancer l'application

    .\.venv\Scripts\python.exe -m streamlit run app.py

Ouvrir l'adresse locale indiquée, souvent http://localhost:8501.
Arrêter le serveur avec Ctrl+C.

## 5. Tester
- Importer un des PDF P&ID fournis pour visualiser ses pages.
- Vérifier l'avertissement « Exemple fictif » : l'app NE détecte rien encore.
- Modifier une cellule dans le tableau de démonstration, changer le statut à « Validé ».
- Exporter Excel et vérifier la modification.
- Passer en mode « Importer un JSON » et utiliser le format documenté dans `data/README_INTEGRATION.md`.

## 6. Répartition à deux
Personne A : chargement/rendu PDF, navigation, zoom, futur encadrement des tags.
Personne B : tableau, corrections, validation, structure JSON et export Excel.
Intégration : vérification commune du flux JSON et des corrections.

## 7. Notes importantes
- L'application s'exécute localement. Ne publiez pas de P&ID industriels sans autorisation.
- Aucune extraction/OCR réelle n'est incluse dans cette première version.
- Les exemples du tableau sont entièrement fictifs.
- Les données éditées résident dans la session Streamlit et ne sont pas enregistrées durablement.
