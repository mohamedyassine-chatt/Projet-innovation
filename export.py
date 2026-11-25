import os

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

POLICE = "Arial"
ENTETE = PatternFill("solid", start_color="7B0000")


def _feuille(wb, titre, colonnes, lignes, largeurs):
    ws = wb.create_sheet(titre)
    ws.append(colonnes)
    for c in ws[1]:
        c.font = Font(name=POLICE, bold=True, color="FFFFFF")
        c.fill = ENTETE
        c.alignment = Alignment(horizontal="center")
    for l in lignes:
        ws.append(l)
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.font = Font(name=POLICE)
    for i, w in enumerate(largeurs, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    return ws


def exporter_excel(signaux, anomalies, path):
    io = [s for s in signaux if s["type_io"] in ("AI", "AO", "DI", "DO")]
    autres = [s for s in signaux if s["type_io"] not in ("AI", "AO", "DI", "DO")]

    wb = Workbook()
    wb.remove(wb.active)

    # Résumé (formules qui comptent la feuille Signaux)
    ws = wb.create_sheet("Résumé")
    ws.append(["Type", "Nombre"])
    for i, t in enumerate(["AI", "AO", "DI", "DO"], 2):
        ws.append([t, f'=COUNTIF(Signaux!$E:$E,A{i})'])
    ws.append(["Total", "=SUM(B2:B5)"])
    ws.append(["À vérifier", '=COUNTIF(Signaux!$K:$K,"?*")'])
    for c in ws[1]:
        c.font = Font(name=POLICE, bold=True, color="FFFFFF")
        c.fill = ENTETE
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.font = Font(name=POLICE, bold=(row[0].value in ("Total", "À vérifier")))
    ws.column_dimensions["A"].width = 16
    ws.column_dimensions["B"].width = 12

    cols = ["Tag", "Zone", "Fonction", "Boucle", "Type I/O", "Boîte de jonction",
            "Élévation", "Page", "Règle appliquée", "Source", "À vérifier", "Plan", "Description"]
    _feuille(wb, "Signaux", cols,
             [[s["tag"], s["zone"], s["fonction"], s["boucle"], s["type_io"], s["jb"],
               s["elevation"], s["page"], s["regle"], s["source"], s["a_verifier"],
               os.path.basename(s["fichier"]), s["description"]]
              for s in io],
             [20, 8, 10, 10, 10, 18, 12, 8, 16, 10, 40, 24, 40])

    _feuille(wb, "Sans I-O", ["Tag", "Fonction", "Type", "Description", "Page", "Plan"],
             [[s["tag"], s["fonction"], s["type_io"], s["description"], s["page"],
               os.path.basename(s["fichier"])]
              for s in autres],
             [20, 10, 10, 45, 8, 24])

    _feuille(wb, "À rectifier", ["Tag", "Type", "Message", "Page"],
             [[a["tag"], a["type"], a["message"], a["page"]] for a in anomalies],
             [20, 16, 55, 8])

    wb.save(path)