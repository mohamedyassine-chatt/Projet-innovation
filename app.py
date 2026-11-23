"""Prototype interface P&ID Analyzer, sans moteur de reconnaissance."""
import hashlib
import io
import json
from pathlib import Path

import pandas as pd
import pymupdf
import streamlit as st

st.set_page_config(page_title="P&ID Analyzer | ECC", page_icon="📐", layout="wide")

COLUMNS = [
    "tag", "description", "equipment", "io_type", "signal", "service",
    "pid", "page", "datasheet", "confidence", "validation", "commentaire"
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


st.title("P&ID Analyzer")
st.caption("Prototype du pôle Application — Projet Innovation ECC × Actemium")
st.info("Cette version visualise les PDF et permet de travailler sur des données I/O. Elle ne détecte PAS encore automatiquement les instruments.")

with st.sidebar:
    st.header("Documents")
    pdf = st.file_uploader("Charger un plan P&ID (PDF)", type=["pdf"])
    st.divider()
    st.header("Données de test")
    mode = st.radio("Source des résultats", ["Exemple fictif", "Importer un JSON"], index=0)
    imported = st.file_uploader("Fichier JSON du pôle Extraction", type=["json"]) if mode == "Importer un JSON" else None
    st.caption("Un JSON importé doit contenir une liste de signaux I/O et respecter le schéma du dossier data.")

file_bytes = pdf.getvalue() if pdf else None
file_id = hashlib.sha256(file_bytes).hexdigest() if file_bytes else "no-pdf"
raw_json = imported.getvalue() if imported else None
json_id = hashlib.sha256(raw_json).hexdigest() if raw_json else "demo"
state_id = f"{file_id}:{mode}:{json_id}"

if st.session_state.get("dataset_id") != state_id:
    try:
        if mode == "Importer un JSON":
            records = json.loads(raw_json.decode("utf-8")) if raw_json else []
        else:
            records = json.loads((Path(__file__).parent / "data" / "demo_results.json").read_text(encoding="utf-8"))
        st.session_state.io_df = as_table(records)
        st.session_state.dataset_error = ""
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        st.session_state.io_df = as_table([])
        st.session_state.dataset_error = f"JSON invalide : {exc}"
    st.session_state.dataset_id = state_id

if st.session_state.get("dataset_error"):
    st.error(st.session_state.dataset_error)

left, right = st.columns([1, 1.2], gap="large")

with left:
    st.subheader("1. Visualisation du plan")
    if file_bytes:
        try:
            with pymupdf.open(stream=file_bytes, filetype="pdf") as doc:
                count = len(doc)
                st.write(f"**Document :** {pdf.name} — **{count} page(s)**")
                number = st.number_input("Page à afficher", min_value=1, max_value=count, value=1)
                page = doc.load_page(number - 1)
                pix = page.get_pixmap(dpi=135, alpha=False)
                st.image(pix.tobytes("png"), caption=f"Page {number}", use_container_width=True)
        except Exception as exc:
            st.error(f"Impossible d'ouvrir le PDF : {exc}")
    else:
        st.warning("Commencez par charger un fichier PDF dans la barre latérale.")

with right:
    st.subheader("2. Liste I/O et validation")
    if mode == "Exemple fictif":
        st.warning("Les lignes ci-dessous sont FICTIVES. Elles ne proviennent pas du PDF chargé.")
    st.write("Ajoutez, modifiez ou supprimez des lignes. Une ligne = un signal I/O.")
    edited = st.data_editor(
        st.session_state.io_df,
        num_rows="dynamic",
        hide_index=True,
        use_container_width=True,
        column_config={
            "io_type": st.column_config.SelectboxColumn("Type", options=["AI", "AO", "DI", "DO", "À déterminer"], required=False),
            "validation": st.column_config.SelectboxColumn("Validation", options=["À vérifier", "Validé", "Rejeté"], required=False),
            "confidence": st.column_config.SelectboxColumn("Confiance", options=["Élevé", "Moyen", "Faible", "À vérifier"], required=False),
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
