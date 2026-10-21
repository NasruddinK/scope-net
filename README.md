# 🌿 SCoPE-Net
**Scope 3 Embodied Carbon & Supply Chain Transparency Platform** for Sime Darby Property — Team HUNE, Sime Darby Property University Hackathon (Township of Tomorrow).

## Features
- **Ingestion & NLP/OCR simulation** – regex extraction + fuzzy matching of messy invoice/BOM lines to emission factors (tCO₂e/unit).
- **Carbon engine** – emissions = quantity × factor.
- **Anomaly screening** – Isolation Forest + per-material z-score + unmatched-material rule.
- **CRUD** – create (sidebar form), read (township / vendor tier / status filters), update (e.g. clear a flag to *Verified*), delete.
- **Compliance** – IFRS S1/S2 and NSRF requirement status from Dataset 3 with evidence, CSV export.

## Architecture
```
app.py    Streamlit UI (tabs, CSS, state)
utils.py  loading, OCR/NLP, carbon engine, ML, CRUD, compliance
data/     three master CSVs (see data/README.md); demo data auto-generated if absent
```
State lives in `st.session_state`; swap in a database for persistence in production.

## Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# copy the 3 CSVs into data/
streamlit run app.py
```
Google Colab: `pip install -r requirements.txt`, then run Streamlit via a localtunnel.

## Notes
Compliance statuses are heuristic readiness indicators, not assurance. Edits are in-memory (export CSV to keep them).
