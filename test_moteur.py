"""Extrait les tags de plans PID et produit un fichier Excel.

Exemples :
    python test_moteur.py                                -> tous les PDF du dossier -> tous_les_plans.xlsx
    python test_moteur.py "Plan PID Process 10.pdf"      -> un seul plan -> Plan PID Process 10.xlsx
    python test_moteur.py "C:\\...\\Nouveau plan.pdf"     -> un plan situé ailleurs (Excel créé à côté du PDF)
    python test_moteur.py plan1.pdf plan2.pdf            -> plusieurs plans -> tous_les_plans.xlsx
    python test_moteur.py "C:\\...\\dossier_plans"        -> tous les PDF d'un dossier
    python test_moteur.py plan.pdf -o resultat.xlsx      -> nom du fichier Excel au choix
"""
import argparse
import glob
import os
from collections import Counter

from extraction import extraire_tags
from classification import classifier
from controles import verifier
from export import exporter_excel

ap = argparse.ArgumentParser(description="Extraction des tags de plans PID vers Excel")
ap.add_argument("plans", nargs="*", help="fichiers PDF ou dossiers (par défaut : le dossier courant)")
ap.add_argument("-o", "--sortie", help="nom du fichier Excel à créer")
args = ap.parse_args()

# Liste des PDF à traiter
plans = []
for p in args.plans or ["."]:
    if os.path.isdir(p):
        plans += sorted(glob.glob(os.path.join(p, "*.pdf")))
    elif os.path.isfile(p):
        plans.append(p)
    else:
        print(f"Introuvable : {p}")
if not plans:
    raise SystemExit("Aucun plan PDF à traiter.")

# Nom du fichier Excel : celui du plan s'il n'y en a qu'un
if args.sortie:
    sortie = args.sortie
elif len(plans) == 1:
    sortie = os.path.splitext(plans[0])[0] + ".xlsx"
else:
    sortie = "tous_les_plans.xlsx"

tags = []
for pdf in plans:
    print(f"Lecture de {os.path.basename(pdf)} ...", end=" ", flush=True)
    t = extraire_tags(pdf)
    print(f"{len(t)} bulles lues, {sum(1 for x in t if x['a_verifier'])} à vérifier")
    tags += t

signaux = classifier(tags)
print("\nTypes de signaux :", dict(Counter(s["type_io"] for s in signaux)))
try:
    exporter_excel(signaux, verifier(signaux), sortie)
except PermissionError:
    raise SystemExit(f"Impossible d'écrire {sortie} : fermez-le dans Excel puis relancez.")
print("Fichier Excel :", os.path.abspath(sortie))
