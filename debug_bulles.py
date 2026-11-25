import cv2
import numpy as np
import pymupdf as fitz
import pytesseract

from extraction import (rendre_page, masques, detecter_bulles,
                        lignes_bulle, interpreter, grouper_piles)

PDF = "Plan PID Process 1.pdf"

page = fitz.open(PDF)[0]
print("Rotation de la page :", page.rotation)
print("Mots de texte natif :", len(page.get_text("words")))

img = rendre_page(page)
print("Taille de l'image :", img.shape)

rouge, texte = masques(img)
print("Pixels rouges :", int((rouge > 0).sum()))
print("Pixels de texte :", int((texte == 0).sum()))

# Test de plusieurs réglages de détection
r = cv2.GaussianBlur(cv2.dilate(rouge, np.ones((3, 3), np.uint8)), (7, 7), 0)
for p2 in (30, 40, 45, 60):
    for rmin, rmax in ((60, 100), (90, 130), (100, 150)):
        c = cv2.HoughCircles(r, cv2.HOUGH_GRADIENT, dp=1.5, minDist=80,
                             param1=100, param2=p2,
                             minRadius=rmin, maxRadius=rmax)
        n = 0 if c is None else len(c[0])
        print(f"param2={p2}  rayon {rmin}-{rmax} : {n} cercles")

# Détection avec les réglages actuels
bulles = detecter_bulles(rouge)
print("\nBulles détectées (réglage actuel) :", len(bulles))

# Image de contrôle : cercles dessinés en vert
controle = img.copy()
for x, y, rad in bulles:
    cv2.circle(controle, (x, y), rad, (0, 200, 0), 6)
cv2.imwrite("controle_bulles.png", cv2.resize(controle, None, fx=0.25, fy=0.25))
print("Image enregistrée : controle_bulles.png")

# Lecture OCR des 10 premières bulles
print("\n--- Lecture des 10 premières bulles ---")
for x, y, rad in bulles[:10]:
    lignes = lignes_bulle(texte, None, x, y, rad)
    print((x, y, rad), "->", lignes, "->", interpreter(lignes))

# Version OCR de ce que voit Tesseract sur la première bulle
if bulles:
    x, y, rad = bulles[0]
    crop = texte[max(0, y - rad):y + rad, max(0, x - rad):x + rad]
    cv2.imwrite("bulle_exemple.png", crop)
    print("Image enregistrée : bulle_exemple.png")

# ---------- Diagnostic OCR sur la première bulle ----------
print("\nVersion de Tesseract :", pytesseract.get_tesseract_version())

x, y, rad = bulles[0]
y0, y1 = max(0, y - rad), y + rad
x0, x1 = max(0, x - rad), x + rad

gris_complet = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
variantes = {
    "texte": texte[y0:y1, x0:x1],
    "gris": gris_complet[y0:y1, x0:x1],
}

cv2.imwrite("test_couleur.png", img[y0:y1, x0:x1])

for nom, c in variantes.items():
    cv2.imwrite(f"test_{nom}.png", c)
    c3 = cv2.resize(c, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    c3 = cv2.copyMakeBorder(c3, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=255)
    for psm in (6, 11, 7):
        for liste in (True, False):
            cfg = f"--psm {psm}"
            if liste:
                cfg += " -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
            rep = pytesseract.image_to_string(c3, config=cfg)
            rep = rep.strip().replace("\n", " | ")
            print(nom, "| psm", psm, "|", "liste" if liste else "libre", "->", repr(rep))

# ---------- Test : bulle redessinée à haute résolution ----------
print("\n--- Rendu haute résolution de la première bulle ---")
x, y, rad = bulles[0]
SC = 200 / 72
rect_img = fitz.Rect((x - rad) / SC, (y - rad) / SC, (x + rad) / SC, (y + rad) / SC)
clip = rect_img * page.derotation_matrix   # retour dans le repère du PDF

for dpi in (400, 600, 900):
    pix = page.get_pixmap(dpi=dpi, clip=clip)
    a = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)
    a = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY if pix.n == 1 else
                     (cv2.COLOR_RGB2GRAY if pix.n == 3 else cv2.COLOR_RGBA2GRAY))
    cv2.imwrite(f"test_{dpi}dpi.png", a)

    # variante épaissie : on grossit les traits fins
    _, bin_ = cv2.threshold(a, 200, 255, cv2.THRESH_BINARY)
    epais = cv2.erode(bin_, np.ones((3, 3), np.uint8))  # noir qui grossit
    for nom, im in (("gris", a), ("epais", epais)):
        im = cv2.copyMakeBorder(im, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=255)
        for psm in (6, 11):
            rep = pytesseract.image_to_string(im, config=f"--psm {psm}")
            print(dpi, "dpi |", nom, "| psm", psm, "->", repr(rep.strip().replace("\n", " | ")))