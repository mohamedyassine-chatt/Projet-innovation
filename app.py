"""Prototype interface P&ID Analyzer, sans moteur de reconnaissance."""
import hashlib
import io
import json
from pathlib import Path

import pandas as pd
import pymupdf
import streamlit as st

import os
import tempfile

from extraction import extraire_tags
from classification import classifier
from controles import verifier
from export import exporter_excel

st.set_page_config(page_title="P&ID Analyzer | ECC", page_icon="📐", layout="wide")

COLUMNS = [
    "tag", "type_io", "description", "zone", "fonction", "boucle",
    "jb", "elevation", "page", "x", "y", "regle", "source",
    "a_verifier", "validation", "commentaire", "fichier",
]


def as_table(records):
    if not isinstance(records, list) or not all(isinstance(x, dict) for x in records):
        raise ValueError("Le JSON doit être une liste d'objets.")
    df = pd.DataFrame(records)
    for column in COLUMNS:
        if column not in df:
            df[column] = ""
    df = df[COLUMNS].fillna("")
    df["page"] = pd.to_numeric(df["page"], errors="coerce").fillna(1).astype(int)
    return df


def excel_bytes(df):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        output = df.rename(columns={
            "tag": "Tag", "description": "Description", "equipment": "Equipment",
            "io_type": "Type", "signal": "Signal", "service": "Service",
            "pid": "P&ID", "page": "Page", "datasheet": "Datasheet",
            "confidence": "Confiance", "validation": "Validation", "commentaire": "Commentaire",
        })
        output.insert(0, "I/O Number", range(1, len(output) + 1))
        output.to_excel(writer, sheet_name="IO_List", index=False)
        sheet = writer.sheets["IO_List"]
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for col in sheet.columns:
            letter = col[0].column_letter
            sheet.column_dimensions[letter].width = min(40, max(12, max(len(str(c.value or "")) for c in col) + 2))
    return buffer.getvalue()

@st.cache_data
def render_page(file_bytes, number):
    with pymupdf.open(stream=file_bytes, filetype="pdf") as doc:
        page = doc.load_page(number - 1)
        pix = page.get_pixmap(dpi=135, alpha=False)
        return pix.tobytes("png")

@st.cache_data(show_spinner="Analyse du plan en cours…")
def analyser(file_bytes, nom):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(file_bytes)
        chemin = f.name
    try:
        tags = extraire_tags(chemin)
    finally:
        try:
            os.remove(chemin)
        except OSError:
            pass
    signaux = classifier(tags)
    for s, t in zip(signaux, tags):
        s["x"], s["y"] = t["x"], t["y"]
        s["fichier"] = nom
        s["validation"] = "À vérifier" if s["a_verifier"] else "OK"
    return signaux  

st.title("P&ID Analyzer")
st.caption("Prototype du pôle Application — Projet Innovation ECC × Actemium")
st.info("Chargez un plan, cliquez sur Analyser, puis vérifiez les lignes marquées À vérifier.")

with st.sidebar:
    st.header("Documents")
    pdf = st.file_uploader("Charger un plan P&ID (PDF)", type=["pdf"])
    lancer = st.button("🔍 Analyser le plan", disabled=pdf is None, width="stretch")

file_bytes = pdf.getvalue() if pdf else None
file_id = hashlib.sha256(file_bytes).hexdigest() if file_bytes else "no-pdf"

if lancer:
    st.session_state.io_df = as_table(analyser(file_bytes, pdf.name))
    st.session_state.dataset_id = file_id

if st.session_state.get("dataset_id") != file_id:
    st.session_state.io_df = as_table([])

state_id = st.session_state.get("dataset_id", "vide")

left, right = st.columns([1, 1.2], gap="large")

with left:
    st.subheader("1. Visualisation du plan")
    if file_bytes:
        try:
            with pymupdf.open(stream=file_bytes, filetype="pdf") as doc:
                count = len(doc)
                st.write(f"**Document :** {pdf.name} — **{count} page(s)**")
                number = st.number_input("Page à afficher", min_value=1, max_value=count, value=1)
                png = render_page(file_bytes, number)
                st.image(png, caption=f"Page {number}", use_container_width=True)
        except Exception as exc:
            st.error(f"Impossible d'ouvrir le PDF : {exc}")
    else:
        st.warning("Commencez par charger un fichier PDF dans la barre latérale.")

with right:
    st.subheader("2. Liste I/O et validation")
    st.write("Ajoutez, modifiez ou supprimez des lignes. Une ligne = un signal I/O.")
    edited = st.data_editor(
        st.session_state.io_df,
        num_rows="dynamic",
        hide_index=True,
        use_container_width=True,
        column_config={
            "type_io": st.column_config.SelectboxColumn("Type", options=["AI", "AO", "DI", "DO", "AUCUN", "INCONNU"]),
            "validation": st.column_config.SelectboxColumn("Validation", options=["À vérifier", "OK", "Validé", "Rejeté"]),
            "a_verifier": st.column_config.TextColumn("À vérifier", disabled=True),
            "page": st.column_config.NumberColumn("Page", min_value=1, step=1),
        },
        key=f"editor_{state_id}",
    )
    st.session_state.io_edited = edited
    total = len(edited)
    validated = int((edited["validation"] == "Validé").sum()) if total else 0
    a, b = st.columns(2)
    a.metric("Signaux dans le tableau", total)
    b.metric("Lignes validées", validated)
    st.download_button(
        "📥 Exporter la liste I/O vers Excel",
        data=excel_bytes(edited),
        file_name="liste_IO_a_valider.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    st.caption("L'export peut contenir des données non validées : vérifier les statuts avant tout usage industriel.")

st.divider()
st.subheader("Prochaines étapes")
st.write("1. Brancher la vraie fonction d'extraction des autres membres. 2. Encadrer les tags détectés sur l'image à partir de leurs coordonnées. 3. Sauvegarder les validations et mesurer les performances.")
