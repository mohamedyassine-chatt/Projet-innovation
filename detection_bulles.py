import sys
import cv2
import numpy as np
from pdf2image import convert_from_path
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

PDF = sys.argv[1] if len(sys.argv) > 1 else "Plan PID Process 3.pdf"
DPI = 150

# Étape 1 : PDF -> image
page = convert_from_path(PDF, dpi=DPI)[0]
img = cv2.cvtColor(np.array(page), cv2.COLOR_RGB2BGR)
H, W = img.shape[:2]
print("Taille image :", W, "x", H)

# Étape 2 : détection par la FORME (aucune couleur utilisée)
gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
traits = ((gris < 200).astype(np.uint8)) * 255      # tout ce qui n'est pas blanc
traits = cv2.dilate(traits, np.ones((3, 3), np.uint8))

flou = cv2.GaussianBlur(traits, (5, 5), 0)
cercles = cv2.HoughCircles(flou, cv2.HOUGH_GRADIENT, dp=1.5, minDist=60,
                           param1=100, param2=45, minRadius=70, maxRadius=100)
cercles = np.round(cercles[0]).astype(int)

# Exclure légende, carte et cartouche
cercles = [c for c in cercles if c[0] < 0.83 * W and c[1] < 0.90 * H]

# Garder seulement les cercles qui contiennent du texte (ni vides, ni pleins)
gardes = []
for x, y, r in cercles:
    centre = traits[y - r // 2:y + r // 2, x - r // 2:x + r // 2]
    taux = (centre > 0).mean()
    if 0.08 < taux < 0.6:
        gardes.append((x, y, r))
cercles = gardes
print("Candidats détectés :", len(cercles))

# Image de contrôle
sortie = img.copy()
for x, y, rayon in cercles:
    cv2.circle(sortie, (x, y), rayon, (0, 160, 0), 8)
cv2.imwrite("bulles_detectees.png", cv2.resize(sortie, None, fx=0.25, fy=0.25))
np.save("cercles.npy", np.array(cercles))
print("Image de contrôle : bulles_detectees.png")