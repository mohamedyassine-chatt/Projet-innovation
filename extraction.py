"""
extraction.py : lit un plan PDF et renvoie la liste des tags (une entrée par bulle).

Fonction appelée par l'application : extraire_tags(pdf_path) -> list[dict]

Lecture du texte, par ordre de préférence :
  1. texte natif du PDF s'il existe ;
  2. reconnaissance par gabarits (dossier gabarits/) : les plans sont vectoriels,
     chaque caractère est dessiné à l'identique. On compare chaque caractère aux
     modèles de la police du plan. Beaucoup plus fiable que Tesseract, qui confond
     3/5 et I/1 avec cette police CAO (le "3" a le haut plat) ;
  3. Tesseract en dernier recours (caractère inconnu ou format de tag incorrect).

Pour apprendre un nouveau caractère : déposer une image PNG du caractère
(noir sur blanc, à 200 DPI) dans gabarits/ sous le nom <caractère>_<n>.png.
"""
import os
import re
from collections import Counter

import cv2
import numpy as np
import pytesseract

try:
    import pymupdf as fitz          # nom récent
except ImportError:
    import fitz                      # ancien nom

# Chemin de Tesseract sous Windows (adaptez-le si votre installation est ailleurs)
_TESS = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(_TESS):
    pytesseract.pytesseract.tesseract_cmd = _TESS

DPI = 200
SCALE = DPI / 72
CAR = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
CAR_JB = CAR + ".-"

# Formats attendus (ex. 204M-TIT-005M, 213I-LIT-1501A, 205A-XV-040)
RE_ZONE = r"\d{3}[A-Z]?"
RE_FONC = r"[A-Z]{1,5}"
RE_BOUCLE = r"\d{3,4}[A-Z]{0,2}"

# Élévation : 3 chiffres, un point, 3 chiffres (le "EL." est souvent mal lu, on l'ignore)
RE_EL = re.compile(r"(\d{3})[.,]?(\d{3})")
# Boîte de jonction : 204M-AJB-007, 213-CJB-003 (tolère un J/B mal lu et un tiret perdu)
RE_JB = re.compile(r"([0-9OIS]{3}[A-Z]?)[-_~.]*([ACDP0O])[JI1L]?[B83][-_~.]*([0-9OIS]{3})")

# Reconnaissance par gabarits
DOSSIER_GABARITS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gabarits")
H_NORM, W_NORM = 32, 28          # taille du cadre de comparaison (pixels à 200 DPI)
H_MIN, H_MAX = 20, 36            # hauteur d'un caractère (à 200 DPI)
SEUIL_GABARIT = 0.75             # ressemblance minimale, sinon caractère inconnu "?"


# ---------------------------------------------------------------
# Corrections des confusions OCR
# ---------------------------------------------------------------
def corr_num(s):
    """Les 3 premiers caractères sont des chiffres : O->0, I->1, S->5, B->8."""
    return s[:3].translate(str.maketrans("OIlSB", "01158")) + s[3:]


def corr_zone(s):
    """Zone = 3 chiffres + une lettre éventuelle (204M, 213I, 205A)."""
    s = corr_num(re.sub(r"[^A-Z0-9]", "", s))
    return s[:3] + s[3:].translate(str.maketrans("0158", "OISB"))


def corr_boucle(s):
    """Boucle = 3-4 chiffres + suffixe (1301B, 005M). Dans cette police le B
    du suffixe ressemble au R : un suffixe R est lu comme B."""
    s = corr_num(re.sub(r"[^A-Z0-9]", "", s))
    m = re.fullmatch(r"(\d{3,4})([A-Z]{1,2})", s)
    return m.group(1) + m.group(2).replace("R", "B") if m else s


def corr_fonc(s):
    """La fonction ISA ne contient que des lettres : 0->O, 1->I, 5->S."""
    return re.sub(r"[^A-Z0-9]", "", s).translate(str.maketrans("015", "OIS"))


# ---------------------------------------------------------------
# Lecture de la page
# ---------------------------------------------------------------
def rendre_page(page):
    pix = page.get_pixmap(dpi=DPI)
    img = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)
    code = cv2.COLOR_RGB2BGR if pix.n == 3 else cv2.COLOR_RGBA2BGR
    return cv2.cvtColor(img, code)


def preparer(img):
    """Renvoie (rouge, texte, encre) :
    - rouge : masque des cercles et traits rouges (pour détecter les bulles)
    - texte : image noir sur blanc épaissie, pour Tesseract
    - encre : intensité de l'encre non rouge (0 = blanc), sans les longs traits,
              pour la reconnaissance par gabarits."""
    b, g, r = (img[:, :, i].astype(np.int16) for i in range(3))
    rouge = (((r > 120) & (r - g > 50) & (r - b > 50)) * 255).astype(np.uint8)

    encre = 255 - img.min(axis=2)                      # uint8, 0 = blanc
    binaire = ((encre > 40) * 255).astype(np.uint8)

    # On repère les longs traits horizontaux et verticaux (les lettres sont trop courtes)
    h = cv2.morphologyEx(binaire, cv2.MORPH_OPEN,
                         cv2.getStructuringElement(cv2.MORPH_RECT, (90, 1)))
    v = cv2.morphologyEx(binaire, cv2.MORPH_OPEN,
                         cv2.getStructuringElement(cv2.MORPH_RECT, (1, 90)))
    traits = cv2.dilate(cv2.bitwise_or(h, v), np.ones((3, 3), np.uint8))

    encre[(rouge > 0) | (traits > 0)] = 0

    # Version Tesseract : on épaissit les traits fins
    texte = cv2.dilate(cv2.subtract(binaire, traits), np.ones((3, 3), np.uint8))
    return rouge, 255 - texte, encre


def masques(img):
    """(rouge, texte) — conservé pour les scripts de diagnostic."""
    rouge, texte, _ = preparer(img)
    return rouge, texte


def mots_natifs(page):
    """Mots du texte natif (s'il existe), en pixels, dans le repère de l'image."""
    m = page.rotation_matrix
    out = []
    for x0, y0, x1, y1, w, *_ in page.get_text("words"):
        r = fitz.Rect(x0, y0, x1, y1) * m
        out.append(((r.x0 + r.x1) / 2 * SCALE, (r.y0 + r.y1) / 2 * SCALE, w))
    return out


def detecter_bulles(rouge):
    """Cercles rouges (x, y, rayon). On baisse le seuil jusqu'à en trouver.
    minDist = 150 : deux bulles empilées sont à ~220 px, un même cercle
    ne peut donc pas être détecté deux fois."""
    r = cv2.GaussianBlur(cv2.dilate(rouge, np.ones((5, 5), np.uint8)), (7, 7), 0)
    for p2 in (45, 35, 28, 22):
        c = cv2.HoughCircles(r, cv2.HOUGH_GRADIENT, dp=1.5, minDist=150,
                             param1=100, param2=p2, minRadius=90, maxRadius=130)
        if c is not None and len(c[0]) >= 10:
            return [tuple(int(v) for v in b) for b in c[0]]
    return []


# ---------------------------------------------------------------
# Reconnaissance par gabarits
# ---------------------------------------------------------------
def normaliser(g):
    """Place un caractère dans un cadre fixe (en haut, centré), floute légèrement
    et normalise : la comparaison devient un simple produit scalaire."""
    c = np.zeros((H_NORM, W_NORM), np.float32)
    h, w = min(g.shape[0], H_NORM), min(g.shape[1], W_NORM)
    ox = (W_NORM - w) // 2
    c[:h, ox:ox + w] = g[:h, :w]
    c = cv2.GaussianBlur(c, (5, 5), 1.2)
    v = (c - c.mean()).ravel()
    return v / (np.linalg.norm(v) + 1e-6)


_GABARITS = None


def gabarits():
    """Charge (une seule fois) les gabarits : matrice des vecteurs + étiquettes."""
    global _GABARITS
    if _GABARITS is None:
        vecteurs, etiquettes = [], []
        if os.path.isdir(DOSSIER_GABARITS):
            for f in sorted(os.listdir(DOSSIER_GABARITS)):
                if not f.lower().endswith(".png"):
                    continue
                # imdecode : fonctionne aussi avec des accents dans le chemin
                im = cv2.imdecode(np.fromfile(os.path.join(DOSSIER_GABARITS, f), np.uint8),
                                  cv2.IMREAD_GRAYSCALE)
                if im is not None:
                    vecteurs.append(normaliser(255 - im))
                    etiquettes.append(f[0].upper())
        _GABARITS = (np.array(vecteurs), etiquettes)
    return _GABARITS


def reconnaitre(g):
    """Caractère le plus ressemblant, ou '?' si aucun gabarit n'est assez proche."""
    vecteurs, etiquettes = gabarits()
    if not etiquettes:
        return "?"
    s = vecteurs @ normaliser(g)
    j = int(s.argmax())
    return etiquettes[j] if s[j] >= SEUIL_GABARIT else "?"


def lire_gabarits(encre):
    """Lit un morceau de l'image d'encre. Renvoie la liste des lignes, de haut en bas."""
    nb, lab, st, _ = cv2.connectedComponentsWithStats((encre > 40).astype(np.uint8), 8)

    # Morceaux d'un même caractère (ex. un 5 coupé en deux) : on les fusionne
    morceaux = []
    for i in sorted(range(1, nb), key=lambda i: st[i][0]):
        x, y, w, h, _ = st[i]
        for m in morceaux:
            recouvre = min(m[2], x + w) - max(m[0], x)
            if (recouvre > 0.5 * min(m[2] - m[0], w)
                    and max(m[3], y + h) - min(m[1], y) <= H_MAX):
                m[0], m[1] = min(m[0], x), min(m[1], y)
                m[2], m[3] = max(m[2], x + w), max(m[3], y + h)
                m[4].append(i)
                break
        else:
            morceaux.append([x, y, x + w, y + h, [i]])

    caracteres, ponctuation = [], []
    for x0, y0, x1, y1, ids in morceaux:
        w, h = x1 - x0, y1 - y0
        if H_MIN <= h <= H_MAX and w <= 32:
            g = np.where(np.isin(lab[y0:y1, x0:x1], ids), encre[y0:y1, x0:x1], 0)
            caracteres.append((x0, y0, y1, reconnaitre(g)))
        elif h <= 5 and 6 <= w <= 22:
            ponctuation.append((x0, (y0 + y1) / 2, "-"))
        elif h <= 6 and w <= 6:
            ponctuation.append((x0, (y0 + y1) / 2, "."))

    # Regroupement en lignes (d'après le centre vertical des caractères)
    lignes = []
    for c in sorted(caracteres, key=lambda c: (c[1] + c[2]) / 2):
        cy = (c[1] + c[2]) / 2
        if lignes and cy - lignes[-1]["cy"] <= 14:
            lignes[-1]["car"].append((c[0], c[3]))
            lignes[-1]["y0"] = min(lignes[-1]["y0"], c[1])
            lignes[-1]["y1"] = max(lignes[-1]["y1"], c[2])
        else:
            lignes.append({"cy": cy, "y0": c[1], "y1": c[2], "car": [(c[0], c[3])]})
    for x, cy, p in ponctuation:
        for l in lignes:
            if l["y0"] - 4 <= cy <= l["y1"] + 4:
                l["car"].append((x, p))
                break
    return ["".join(t for _, t in sorted(l["car"])) for l in lignes]


# ---------------------------------------------------------------
# Lecture Tesseract (secours) et texte natif
# ---------------------------------------------------------------
def ocr(img_bin, psm=6, car=CAR):
    img = cv2.resize(img_bin, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    img = cv2.copyMakeBorder(img, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
    cfg = f"--psm {psm} -c tessedit_char_whitelist={car}"
    return pytesseract.image_to_string(img, config=cfg)


def regrouper_lignes(mots, tol=25):
    """Regroupe des mots natifs (cx, cy, texte) en lignes, de haut en bas."""
    lignes, courant, dernier = [], [], None
    for cx, cy, t in sorted(mots, key=lambda m: m[1]):
        if dernier is not None and cy - dernier > tol:
            lignes.append(courant)
            courant = []
        courant.append((cx, t))
        dernier = cy
    if courant:
        lignes.append(courant)
    return ["".join(t for _, t in sorted(l)) for l in lignes]


def lire_zone(img, natifs, x0, y0, x1, y1, car=CAR_JB):
    """Lit le texte d'un rectangle : natif si dispo, sinon OCR Tesseract."""
    x0, y0 = max(0, int(x0)), max(0, int(y0))
    x1, y1 = int(x1), int(y1)
    if natifs is not None:
        mots = [(cx, cy, w) for cx, cy, w in natifs if x0 <= cx <= x1 and y0 <= cy <= y1]
        return regrouper_lignes(mots)
    crop = img[y0:y1, x0:x1]
    if crop.size == 0:
        return []
    txt = ocr(crop, 6, car)
    return [l.replace(" ", "") for l in txt.splitlines() if l.strip()]


def lignes_bulle(texte, natifs, x, y, r):
    """Lit les lignes de texte à l'intérieur d'une bulle (texte natif ou Tesseract)."""
    if natifs is not None:
        return lire_zone(None, natifs, x - r, y - r, x + r, y + r)
    h, w = texte.shape
    x0, x1, y0, y1 = max(0, x - r), min(w, x + r), max(0, y - r), min(h, y + r)
    crop = texte[y0:y1, x0:x1].copy()
    masque = np.zeros_like(crop)
    cv2.circle(masque, (x - x0, y - y0), int(r * 0.85), 255, -1)
    crop[masque == 0] = 255          # on efface tout ce qui est hors du cercle
    return [l.replace(" ", "") for l in ocr(crop, 6, CAR).splitlines() if l.strip()]


def lignes_bulle_gabarits(encre, x, y, r):
    """Lit les lignes à l'intérieur d'une bulle par gabarits."""
    h, w = encre.shape
    x0, x1, y0, y1 = max(0, x - r), min(w, x + r), max(0, y - r), min(h, y + r)
    crop = encre[y0:y1, x0:x1].copy()
    masque = np.zeros_like(crop)
    cv2.circle(masque, (x - x0, y - y0), int(r * 0.82), 255, -1)
    crop[masque == 0] = 0
    return lire_gabarits(crop)


def lire_bulle(texte, encre, natifs, x, y, r):
    """(lignes, méthode) : gabarits d'abord, Tesseract si la lecture est incomplète."""
    if natifs is not None:
        return lignes_bulle(None, natifs, x, y, r), "natif"
    lignes = lignes_bulle_gabarits(encre, x, y, r)
    res = interpreter(lignes)
    if res and res[3] and not any("?" in l for l in lignes[:3]):
        return lignes, "gabarits"
    lignes_t = lignes_bulle(texte, None, x, y, r)
    res_t = interpreter(lignes_t)
    if res_t and res_t[3]:
        return lignes_t, "ocr"
    return lignes, "gabarits"        # aucune lecture parfaite : on garde les gabarits


def lire_voisinage(texte_hors, encre_hors, natifs_hors, x0, y0, x1, y1):
    """(élévation, boîte de jonction) à côté d'une bulle : gabarits puis Tesseract."""
    if natifs_hors is not None:
        return chercher_voisinage(lire_zone(None, natifs_hors, x0, y0, x1, y1))
    h, w = encre_hors.shape
    crop = encre_hors[max(0, int(y0)):min(h, int(y1)), max(0, int(x0)):min(w, int(x1))]
    el, jb = chercher_voisinage(lire_gabarits(crop)) if crop.size else (None, None)
    if el is None or jb is None:
        el_t, jb_t = chercher_voisinage(lire_zone(texte_hors, None, x0, y0, x1, y1))
        el, jb = el or el_t, jb or jb_t
    return el, jb


# ---------------------------------------------------------------
# Logique du plan
# ---------------------------------------------------------------
def grouper_piles(bulles):
    """Bulles empilées verticalement = même colonne / même boucle."""
    piles = []
    for b in sorted(bulles, key=lambda b: b[1]):
        for p in piles:
            d = p[-1]
            if abs(b[0] - d[0]) < 0.5 * b[2] and 0 < b[1] - d[1] < 2.6 * b[2]:
                p.append(b)
                break
        else:
            piles.append([b])
    return piles


def interpreter(lignes):
    """(zone, fonction, boucle, format_ok) ou None si ce n'est pas une bulle d'instrument."""
    lignes = [l for l in lignes if l]
    if len(lignes) < 2:
        return None
    zone, fonc = lignes[0], lignes[1]
    boucle = lignes[2] if len(lignes) >= 3 else ""
    zone, boucle, fonc = corr_zone(zone), corr_boucle(boucle), corr_fonc(fonc)
    ok = bool(re.fullmatch(RE_ZONE, zone)
              and re.fullmatch(RE_FONC, fonc)
              and re.fullmatch(RE_BOUCLE, boucle))
    return zone, fonc, boucle, ok


def proche(a, b):
    """Vrai si a et b ne diffèrent que d'un caractère (erreur de lecture isolée)."""
    if abs(len(a) - len(b)) > 1:
        return False
    return sum(x != y for x, y in zip(a, b)) + abs(len(a) - len(b)) <= 1


def voter_pile(infos):
    """Les bulles d'une pile partagent la zone et le numéro de boucle :
    une lecture isolée qui diffère d'un seul caractère de la majorité est corrigée."""
    for champ in ("zone", "boucle"):
        c = Counter(i[champ] for i in infos if i[champ])
        if not c:
            continue
        (maj, nb), *autres = c.most_common()
        if nb < 2 or (autres and autres[0][1] == nb):
            continue                                   # pas de majorité nette
        for i in infos:
            if i[champ] and i[champ] != maj and proche(i[champ], maj):
                i["notes"].append(f"{champ.capitalize()} corrigée par la pile ({i[champ]} -> {maj})")
                i[champ] = maj


def chercher_voisinage(lignes):
    """Cherche (élévation, boîte de jonction) dans le texte lu à côté d'une bulle."""
    s = "".join(lignes).replace("—", "-").replace("–", "-")
    jb = RE_JB.search(s)
    jb_txt = None
    if jb:
        a, t, b = jb.groups()
        t = "C" if t in "0O" else t                   # C mal lu en 0
        jb_txt = f"{corr_zone(a)}-{t}JB-{corr_num(b)}"
        s = s[:jb.start()] + s[jb.end():]    # on retire la boîte avant de chercher l'élévation
    el = RE_EL.search(s)
    return (f"{el.group(1)}.{el.group(2)}" if el else None), jb_txt


def forcer_prefixe(jb, zone):
    """Le nom de la boîte commence par la zone de la bulle : on l'impose."""
    if not jb or not zone:
        return jb
    parties = jb.split("-")          # ["404M", "AJB", "007"]
    if len(parties) != 3:
        return jb
    return f"{zone}-{parties[1]}-{parties[2]}"


def corriger_elevations(resultats):
    """Les élévations d'un plan ont presque toutes la même centaine (ici 5xx)."""
    c = Counter(r["elevation"][0] for r in resultats if r["elevation"])
    if not c:
        return
    dominant = c.most_common(1)[0][0]
    for r in resultats:
        e = r["elevation"]
        if e and e[0] != dominant:
            r["elevation"] = dominant + e[1:]
            r["a_verifier"] = (r["a_verifier"] + " ; " if r["a_verifier"] else "") \
                + "Élévation corrigée (OCR)"


def signaler_doublons(resultats):
    """Un même tag lu deux fois sur un plan = probablement une erreur de lecture :
    on garde les deux bulles et on les signale (au lieu d'en supprimer une)."""
    c = Counter((r["fichier"], r["tag"]) for r in resultats)
    for r in resultats:
        if c[(r["fichier"], r["tag"])] > 1:
            r["a_verifier"] = (r["a_verifier"] + " ; " if r["a_verifier"] else "") \
                + "Tag en double sur le plan"


# ---------------------------------------------------------------
# Fonction appelée par l'application
# ---------------------------------------------------------------
def extraire_tags(pdf_path):
    doc = fitz.open(pdf_path)
    resultats = []

    for num, page in enumerate(doc, 1):
        img = rendre_page(page)
        rouge, texte, encre = preparer(img)
        bulles = detecter_bulles(rouge)

        # Texte natif si le PDF en contient, sinon lecture de l'image
        natifs = mots_natifs(page)
        source = "natif" if len(natifs) > 50 else "ocr"
        if source == "ocr":
            natifs = None

        # Texte SANS le contenu des bulles (pour lire élévation et boîtes de jonction)
        texte_hors, encre_hors = texte.copy(), encre.copy()
        for x, y, r in bulles:
            cv2.circle(texte_hors, (x, y), int(r * 1.1), 255, -1)
            cv2.circle(encre_hors, (x, y), int(r * 1.1), 0, -1)
        natifs_hors = None
        if natifs is not None:
            natifs_hors = [w for w in natifs
                           if not any((w[0] - x) ** 2 + (w[1] - y) ** 2 < (r * 1.1) ** 2
                                      for x, y, r in bulles)]

        for pile in grouper_piles(bulles):
            infos = []
            for x, y, r in pile:
                lignes, methode = lire_bulle(texte, encre, natifs, x, y, r)
                res = interpreter(lignes)
                if res is None:
                    continue                    # cercle qui n'est pas une bulle d'instrument
                zone, fonc, boucle, _ = res
                el, jb = lire_voisinage(texte_hors, encre_hors, natifs_hors,
                                        x + r, y - int(0.9 * r), x + int(6.5 * r), y + int(1.5 * r))
                notes = []
                if any("?" in l for l in lignes[:3]):
                    notes.append("Caractère non reconnu")
                infos.append({"x": x, "y": y, "lignes": lignes, "methode": methode,
                              "zone": zone, "fonction": fonc, "boucle": boucle,
                              "jb": jb, "el": el, "notes": notes})

            voter_pile(infos)

            # Boîte de jonction et élévation partagées dans la pile si une bulle ne les a pas
            jb_pile = next((i["jb"] for i in infos if i["jb"]), None)
            el_pile = next((i["el"] for i in infos if i["el"]), None)

            for i in infos:
                zone, fonc, boucle = i["zone"], i["fonction"], i["boucle"]
                jb = i["jb"] or jb_pile     # (pas de préfixe forcé : une bulle 203A peut être sur une boîte 213I)
                ok = bool(re.fullmatch(RE_ZONE, zone) and re.fullmatch(RE_FONC, fonc)
                          and re.fullmatch(RE_BOUCLE, boucle))
                notes = ([] if ok else ["Format du tag douteux (OCR ?)"]) + i["notes"]
                resultats.append({
                    "tag": "-".join(p for p in (zone, fonc, boucle) if p),
                    "zone": zone, "fonction": fonc, "boucle": boucle,
                    "jb": jb, "jb_type": jb.split("-")[1][0] if jb else None,
                    "elevation": i["el"] or el_pile,
                    "texte_brut": " ".join(i["lignes"]),
                    "page": num, "x": i["x"], "y": i["y"], "fichier": str(pdf_path),
                    "source": source if source == "natif" else i["methode"],
                    "a_verifier": " ; ".join(notes),
                })

    # corriger_elevations() n'est plus appelée : avec les gabarits les élévations sont
    # lues correctement, et certaines sont réellement hors de la centaine dominante (EL. 107.187)
    signaler_doublons(resultats)
    return resultats
