# ---------- 1. Outils ----------
import sys, re, difflib, csv                 # lecture des arguments, texte, comparaison de mots, export CSV
from collections import Counter              # compte les valeurs les plus fréquentes (vote)
import cv2, numpy as np, pytesseract         # images, tableaux, OCR
from pdf2image import convert_from_path      # PDF -> image
from PIL import Image

Image.MAX_IMAGE_PIXELS = None                # autorise les très grandes images
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"   # où se trouve Tesseract

PDF = sys.argv[1] if len(sys.argv) > 1 else "Plan PID Process 3.pdf"   # nom du PDF

# ---------- 2. Règles : fonctions ISA connues -> type d'E/S ("" = pas de ligne d'E/S) ----------
FONCTIONS = {
    "LIT": "AI", "PIT": "AI", "TIT": "AI", "FIT": "AI", "AIT": "AI", "ZIT": "AI", "DIT": "AI",   # transmetteurs
    "ZSH": "DI", "ZSL": "DI", "FSLL": "DI",                                                      # fins de course / contacteurs
    "PY": "AO", "TY": "AO", "FY": "AO", "LY": "AO",                                              # convertisseurs de commande
    "EV": "DO",                                                                                  # électrovanne
    "TE": "", "PE": "", "LE": "", "FE": "", "AE": "", "DE": "", "PI": "", "TI": "", "FI": "",    # capteurs et indicateurs
    "XV": "", "HV": "", "AV": "", "AY": "", "PV": "", "FV": "", "LV": "", "TV": "",              # corps de vannes
}
# lettres souvent confondues avec des chiffres par l'OCR
CONF = str.maketrans({"O": "0", "Q": "0", "D": "0", "Z": "2", "S": "5", "I": "1", "L": "1", "B": "8", "G": "6", "T": "7"})
WL = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"  # caractères autorisés pour l'OCR

# ---------- 3. Charger l'image à 300 DPI et les candidats ----------
img = cv2.cvtColor(np.array(convert_from_path(PDF, dpi=300)[0]), cv2.COLOR_RGB2BGR)   # image haute résolution pour lire les lettres
cercles = (np.load("cercles.npy") * 2).tolist()      # candidats trouvés à 150 DPI : on double les coordonnées pour 300 DPI
cercles.sort(key=lambda t: (round(t[0] / 120), t[1]))   # tri par colonne puis de haut en bas
print(len(cercles), "candidats à lire (patience)...")


# ---------- 4. Lire le texte d'une bulle ----------
def lire(crop, mode):
    if mode == "bleu":                                           # lecture 1 : on isole le texte bleu ou noir
        c = crop.astype(int)
        txt = ((c[:, :, 0] - np.maximum(c[:, :, 1], c[:, :, 2])) > 40) | (c.sum(2) < 250)   # pixels bleus ou très sombres
        b = np.where(txt, 0, 255).astype(np.uint8)              # texte noir sur fond blanc
        b = cv2.resize(b, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)   # agrandit x2
    else:                                                        # lecture 2 : simple noir et blanc
        g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)              # niveaux de gris
        g = cv2.resize(g, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        _, b = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)   # seuil automatique
    b = cv2.copyMakeBorder(b, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=255)  # marge blanche autour
    t = pytesseract.image_to_string(b, config=f"--psm 6 -c tessedit_char_whitelist={WL}")   # OCR en bloc de texte
    return [l.strip() for l in t.split("\n") if l.strip()]      # liste des lignes lues, sans lignes vides


# ---------- 5. Valider la fonction (2e ligne de la bulle) ----------
def valider_fonction(lectures):
    meilleur, score_max, ambigu = None, 0, False
    for l in lectures:                                           # pour chaque lecture
        mot = re.sub(r"[^A-Z]", "", l)                           # garde uniquement les lettres
        if mot in FONCTIONS:                                     # mot exact connu -> sûr
            return mot, "sûr"
        proches = difflib.get_close_matches(mot, FONCTIONS.keys(), n=2, cutoff=0.6)   # sinon, cherche le mot connu le plus proche
        if proches:
            s = difflib.SequenceMatcher(None, mot, proches[0]).ratio()   # score de ressemblance
            if s > score_max:
                meilleur, score_max = proches[0], s
                ambigu = len(proches) > 1 and difflib.SequenceMatcher(None, mot, proches[1]).ratio() >= s - 0.01   # deux candidats équivalents = ambigu
    if meilleur is None:
        return None, "rejeté"                                    # rien de ressemblant : ce n'est pas une bulle
    return meilleur, ("ambigu" if ambigu else "corrigé")


# ---------- 6. Nettoyer le numéro de boucle (3e ligne) ----------
def norm_boucle(s):
    s = s.translate(CONF)                                        # corrige O->0, Z->2, S->5...
    m = re.match(r"(\d{3,4})([A-Z]?)", re.sub(r"[^0-9A-Z]", "", s))   # attend 3 ou 4 chiffres + lettre éventuelle
    return (m.group(1) + (m.group(2) if m.group(2) in "MAB" else "")) if m else None


# ---------- 7. OCR de tous les candidats ----------
bulles = []
for (x, y, r) in cercles:
    m = int(r * 0.78)                                            # on découpe un carré à l'intérieur du cercle
    crop = img[y - m:y + m, x - m:x + m]
    if crop.size == 0:                                           # candidat trop près du bord : ignoré
        continue
    reads = [lire(crop, "bleu"), lire(crop, "otsu")]             # deux lectures de la même bulle
    zones = [l[0] for l in reads if len(l) >= 3]                 # 1re ligne : zone
    fonc = [l[1] for l in reads if len(l) >= 3]                  # 2e ligne : fonction
    boucles = [norm_boucle(l[-1]) for l in reads if len(l) >= 3] # dernière ligne : boucle
    f, statut = valider_fonction(fonc) if fonc else (None, "rejeté")
    bulles.append(dict(x=x, y=y, zones=zones, f=f, statut=statut, boucles=[b for b in boucles if b]))

# ---------- 8. FILTRE PAR LE CONTENU : on jette tout candidat sans fonction ISA valide ----------
avant = len(bulles)
bulles = [b for b in bulles if b["f"]]
print(f"Validation : {len(bulles)} bulles confirmées sur {avant} candidats")

# ---------- 9. Regrouper les bulles empilées (elles partagent le même numéro de boucle) ----------
bulles.sort(key=lambda b: (round(b["x"] / 120), b["y"]))
piles, cur = [], []
for b in bulles:
    if cur and abs(b["x"] - cur[-1]["x"]) < 60 and b["y"] - cur[-1]["y"] < 460:   # même colonne et proches verticalement
        cur.append(b)
    else:
        if cur:
            piles.append(cur)
        cur = [b]
if cur:
    piles.append(cur)

# ---------- 10. Zone du plan : lecture la plus fréquente ----------
toutes = [re.sub(r"[^0-9A-Z]", "", z).translate(str.maketrans("OQ", "00")) for b in bulles for z in b["zones"]]
zones_ok = Counter(z for z in toutes if re.fullmatch(r"\d{3}[A-Z]", z))   # format attendu : 3 chiffres + lettre
zone = zones_ok.most_common(1)[0][0] if zones_ok else "???"

# ---------- 11. Construire les lignes du tableau ----------
lignes = []
for k, p in enumerate(piles, 1):
    votes = Counter(bl for b in p for bl in b["boucles"])        # vote du numéro de boucle dans la pile
    boucle, nb = votes.most_common(1)[0] if votes else ("???", 0)
    if nb == 0:                                                  # aucun numéro de boucle lisible dans toute la pile
        continue                                                 # ce n'est pas un vrai instrument : on l'ignore
    fiable = nb >= 2                                             # fiable si au moins 2 lectures concordent                                             # fiable si au moins 2 lectures concordent
    for b in p:
        conf = "OK" if (b["statut"] == "sûr" and fiable) else "À vérifier"
        lignes.append(dict(pile=k, pos=f"{b['x']//2},{b['y']//2}", zone=zone, fonction=b["f"],
                           boucle=boucle, tag=f"{zone}-{b['f']}-{boucle}",
                           io=FONCTIONS.get(b["f"], ""), statut_fonction=b["statut"], confiance=conf))

# ---------- 12. Export CSV et affichage ----------
with open("bulles_lues.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(lignes[0].keys()), delimiter=";")
    w.writeheader()
    w.writerows(lignes)

print(f"{len(lignes)} bulles lues, zone = {zone}")
for l in lignes:
    print(f"{l['tag']:<18} I/O={l['io'] or '-':<3} {l['statut_fonction']:<8} {l['confiance']}")
print("Fichier : bulles_lues.csv")