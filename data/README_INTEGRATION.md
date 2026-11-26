# Contrat d'intégration avec le pôle Extraction

L'application NE fait pas encore d'OCR. Le pôle Extraction devra produire une liste JSON de dictionnaires conformes au schéma suivant :

- tag: str
- description: str
- equipment: str
- io_type: str (AI / AO / DI / DO / À déterminer)
- signal: str
- service: str
- pid: str (référence ou nom du fichier)
- page: int (1-indexé)
- datasheet: str
- confidence: str (Élevé / Moyen / Faible / À vérifier)
- validation: str (À vérifier / Validé / Rejeté)
- commentaire: str

Un enregistrement correspond à UN SIGNAL I/O, pas simplement à un équipement.
Un équipement peut produire plusieurs lignes : commande, retours, défauts, etc.
Ajouter des coordonnées source et des preuves lors de l'intégration future.

Interface cible (dans un module `extractor.py` futur) :

def extract_io(pdf_bytes: bytes, filename: str) -> list[dict]:
    ...

En attendant, l'application propose uniquement des exemples fictifs, une importation JSON, des modifications et l'export Excel.
