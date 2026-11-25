import csv
import os

REGLES_DEFAUT = """fonction,type_io,description
TIT,AI,Transmetteur de température
PIT,AI,Transmetteur de pression
FIT,AI,Transmetteur de débit
LIT,AI,Transmetteur de niveau
AIT,AI,Transmetteur d'analyse
DIT,AI,Transmetteur de densité
ZIT,AI,Transmetteur de position
PDIT,AI,Transmetteur de pression différentielle
ZSH,DI,Fin de course haut (ouvert)
ZSL,DI,Fin de course bas (fermé)
FSLL,DI,Contacteur de débit très bas
FSL,DI,Contacteur de débit bas
LSH,DI,Contacteur de niveau haut
LSL,DI,Contacteur de niveau bas
PSH,DI,Contacteur de pression haut
PSL,DI,Contacteur de pression bas
EV,DO,Électrovanne (commande)
AY,AO,Positionneur / convertisseur (à valider)
LY,AO,Convertisseur de niveau (à valider)
AV,AUCUN,Vanne (actionneur)
XV,AUCUN,Vanne tout-ou-rien (signaux via EV / ZSH / ZSL)
LV,AUCUN,Vanne de régulation (signal via LY)
TE,AUCUN,Élément primaire température
PE,AUCUN,Élément primaire pression
FE,AUCUN,Élément primaire débit
LE,AUCUN,Élément primaire niveau
AE,AUCUN,Élément primaire analyse
DE,AUCUN,Élément primaire densité
PI,AUCUN,Indicateur local pression
TI,AUCUN,Indicateur local température
FI,AUCUN,Indicateur local débit
LI,AUCUN,Indicateur local niveau
PY,AO,Convertisseur I/P pression (commande vanne)
TY,AO,Convertisseur I/P température (commande vanne)
FY,AO,Convertisseur I/P débit (commande vanne)
PV,AUCUN,Vanne de régulation pression (signal via PY)
TV,AUCUN,Vanne de régulation température (signal via TY)
FV,AUCUN,Vanne de régulation débit (signal via FY)
HV,AUCUN,Vanne manuelle / tout-ou-rien (signaux via EV / ZSH / ZSL)
"""

# Type de boîte de jonction -> types de signaux attendus (None = non vérifié)
JB_ATTENDU = {"A": {"AI", "AO"}, "D": {"DI", "DO"}, "C": None, "P": None}


def charger_regles(chemin="regles.csv"):
    if not os.path.exists(chemin):
        with open(chemin, "w", encoding="utf-8", newline="") as f:
            f.write(REGLES_DEFAUT)
    with open(chemin, encoding="utf-8", newline="") as f:
        return {r["fonction"]: r for r in csv.DictReader(f)}


def regle_generique(fonc):
    if fonc.endswith("IT"):
        return "AI", "Transmetteur (règle générique)"
    if len(fonc) >= 3 and fonc[1] == "S" and fonc[-1] in "HL":
        return "DI", "Contacteur (règle générique)"
    return None, None


def classifier(tags, regles_csv="regles.csv"):
    regles = charger_regles(regles_csv)
    signaux = []
    for t in tags:
        fonc = t["fonction"]
        remarques = [t["a_verifier"]] if t.get("a_verifier") else []
        if fonc in regles:
            r = regles[fonc]
            type_io, desc, id_regle = r["type_io"], r["description"], f"CSV:{fonc}"
        else:
            type_io, desc = regle_generique(fonc)
            id_regle = "générique"
            if type_io is None:
                type_io, desc, id_regle = "INCONNU", "Fonction non reconnue", "aucune"
                remarques.append(f"Fonction '{fonc}' absente de regles.csv")

        # Contrôle croisé avec le type de boîte de jonction
        attendu = JB_ATTENDU.get(t.get("jb_type") or "")
        if attendu and type_io in ("AI", "AO", "DI", "DO") and type_io not in attendu:
            remarques.append(f"{type_io} sur une boîte {t['jb_type']}JB")
        if type_io in ("AI", "AO", "DI", "DO") and not t.get("jb"):
            remarques.append("Boîte de jonction non lue")

        signaux.append({
            "tag": t["tag"], "zone": t["zone"], "fonction": fonc, "boucle": t["boucle"],
            "type_io": type_io, "description": desc, "jb": t.get("jb") or "",
            "elevation": t.get("elevation") or "", "page": t["page"],
            "regle": id_regle, "source": t["source"], "fichier": t["fichier"],
            "a_verifier": " ; ".join(remarques),
        })
    return signaux