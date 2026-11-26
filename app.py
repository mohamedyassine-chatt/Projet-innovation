"""P&ID Analyzer V0.3 — interface industrielle, sans extraction automatique intégrée."""
import hashlib
import io
import json
from pathlib import Path

import pandas as pd
import pymupdf
import streamlit as st
from pdf_viewer import show_viewer

BASE = Path(__file__).resolve().parent
st.set_page_config(
    page_title="P&ID Analyzer | Innovation ECC",
    page_icon="📐", layout="wide", initial_sidebar_state="expanded",
)
st.markdown(f"<style>{(BASE / 'theme.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

COLUMNS = [
    "tag", "description", "equipment", "io_type", "signal", "service",
    "pid", "page", "datasheet", "confidence", "validation", "commentaire",
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
            sheet.column_dimensions[letter].width = min(
                40, max(12, max(len(str(c.value or "")) for c in col) + 2)
            )
    return buffer.getvalue()


st.markdown('''
<div class="app-header">
  <div class="app-brand">
    <div class="app-mark">P&amp;ID</div>
    <div>
      <div class="app-name">P&amp;ID Analyzer</div>
      <div class="app-subtitle">ECC × Actemium · Instrumentation &amp; contrôle-commande</div>
    </div>
  </div>
  <div class="app-tag">PROTOTYPE · VERSION 0.3</div>
</div>
''', unsafe_allow_html=True)

with st.sidebar:
    st.markdown('''<div class="sidebar-brand">
      <div class="sidebar-title">ESPACE DE TRAVAIL</div>
      <div class="sidebar-sub">Gestion des documents et des sources</div>
    </div>''', unsafe_allow_html=True)
    st.markdown("**01 / DOCUMENT SOURCE**")
    pdf = st.file_uploader("Importer un plan P&ID", type=["pdf"], help="Plan technique au format PDF")
    st.divider()
    st.markdown("**02 / DONNÉES I/O**")
    mode = st.radio("Source des résultats", ["Exemple fictif", "Importer un JSON"])
    imported = st.file_uploader("Importer les résultats JSON", type=["json"]) if mode == "Importer un JSON" else None
    st.caption("Format d'intégration : data/README_INTEGRATION.md")
    st.divider()
    st.caption("Projet Innovation 2026–2027 · École Centrale Casablanca")

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
            records = json.loads((BASE / "data" / "demo_results.json").read_text(encoding="utf-8"))
        st.session_state.io_df = as_table(records)
        st.session_state.dataset_error = ""
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        st.session_state.io_df = as_table([])
        st.session_state.dataset_error = f"JSON invalide : {exc}"
    st.session_state.dataset_id = state_id

if st.session_state.get("dataset_error"):
    st.error(st.session_state.dataset_error)

source_status = "Mode démonstration — aucune détection automatique" if mode == "Exemple fictif" else "Données JSON importées — validation requise"
st.markdown(f'<div class="status-strip">● &nbsp;{source_status}</div>', unsafe_allow_html=True)

df = st.session_state.io_df
n_total = len(df)
n_validated = int((df["validation"] == "Validé").sum()) if n_total else 0
n_pending = n_total - n_validated
m1, m2, m3, m4 = st.columns(4, gap="small")
m1.metric("Plans chargés", 1 if file_bytes else 0)
m2.metric("Signaux I/O", n_total)
m3.metric("Validés", n_validated)
m4.metric("Non validés", n_pending)

st.write("")
left, right = st.columns([1.18, 1.05], gap="medium")
with left:
    with st.container(border=True):
        st.markdown('<div class="section-heading">01 &nbsp; Visionneuse P&ID</div>', unsafe_allow_html=True)
        if file_bytes:
            try:
                with pymupdf.open(stream=file_bytes, filetype="pdf") as doc:
                    total_pages = len(doc)
                st.caption(f"{pdf.name}  ·  {total_pages} page(s)")
                page_no = st.number_input(
                    "Page", min_value=1, max_value=total_pages,
                    value=1, step=1, key=f"page_{file_id}"
                )
                show_viewer(file_bytes, page_no - 1, height=620)
                st.caption("Molette : zoom · Glisser : déplacer · Double-clic : ajuster")
            except Exception as exc:
                st.error(f"Impossible d'afficher le PDF : {exc}")
        else:
            st.info("Importez un plan PDF dans le panneau latéral pour commencer.")

with right:
    with st.container(border=True):
        st.markdown('<div class="section-heading">02 &nbsp; Liste I/O &amp; validation</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-note">Une ligne correspond à un signal. Cliquez dans une cellule pour modifier sa valeur.</div>', unsafe_allow_html=True)
        if mode == "Exemple fictif":
            st.caption("Les données affichées sont fictives et indépendantes du PDF.")
        edited = st.data_editor(
            st.session_state.io_df,
            num_rows="dynamic",
            hide_index=True,
            use_container_width=True,
            height=530,
            column_config={
                "tag": st.column_config.TextColumn("Tag", width="small"),
                "description": st.column_config.TextColumn("Description", width="medium"),
                "io_type": st.column_config.SelectboxColumn("Type I/O", options=["AI", "AO", "DI", "DO", "À déterminer"]),
                "validation": st.column_config.SelectboxColumn("Validation", options=["À vérifier", "Validé", "Rejeté"]),
                "confidence": st.column_config.SelectboxColumn("Confiance", options=["Élevé", "Moyen", "Faible", "À vérifier"]),
                "page": st.column_config.NumberColumn("Page", min_value=1, step=1),
            },
            key=f"editor_{state_id}",
        )
        st.session_state.io_df = edited
        st.download_button(
            "↓ Exporter la liste I/O (.xlsx)",
            data=excel_bytes(edited),
            file_name="liste_IO_a_valider.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            type="primary",
        )
        st.caption("Vérifier les statuts avant tout usage industriel.")

st.markdown('''<div class="footerline">P&amp;ID Analyzer · Projet académique ECC × Actemium ·
Extraction automatique non connectée · Données à confirmer par un ingénieur</div>''', unsafe_allow_html=True)
