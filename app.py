"""SCoPE-Net — Scope 3 Embodied Carbon & Supply Chain Transparency Platform (Sime Darby Property). Run: streamlit run app.py"""
import streamlit as st, pandas as pd, plotly.express as px
import utils as U

st.set_page_config(page_title="SCoPE-Net", page_icon="🌿", layout="wide")
GREEN, MINT = "#046C4E", "#6EE7B7"

# ---- Load external CSS file ----
def load_css(file_name):
    try:
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning(f"External stylesheet '{file_name}' not found.")

load_css("style.css")

def format_display_df(dataframe):
    """Format dataframe: add 1-based numbering, rename headers to proper names, and hide raw index."""
    if dataframe is None or dataframe.empty:
        return dataframe
    
    df_formatted = dataframe.copy()
    
    # Insert 1-based numbering column at the very beginning
    df_formatted.insert(0, "No.", range(1, len(df_formatted) + 1))
    
    # Proper column name mapping
    column_rename_map = {
        "log_id": "Log ID",
        "date": "Date & Time",
        "vendor": "Vendor Name",
        "vendor_tier": "Vendor Tier",
        "township": "Township Site",
        "material": "Material",
        "material_description": "Material Description",
        "quantity": "Quantity",
        "unit": "Unit",
        "factor_tco2e_per_unit": "Emission Factor (tCO₂e/Unit)",
        "factor": "Emission Factor (tCO₂e/Unit)",
        "total_emissions_tco2e": "Total Emissions (tCO₂e)",
        "verification_status": "Verification Status",
        "is_anomaly": "Is Anomaly",
        "matched_material": "Matched Material",
        "match_confidence": "Confidence Rate",
        "raw_line": "Raw Line",
        # Compliance report columns mapping
        "requirement_id": "Requirement ID",
        "framework": "Framework",
        "category": "Category",
        "reporting_entity": "Reporting Entity",
        "disclosure_year": "Disclosure Year",
        "reported_emissions_tco2e": "Reported Emissions (tCO₂e)",
        "assurance_level": "Assurance Level",
        "audit_compliance_status": "Audit Compliance Status",
        "penalty_risk_score": "Penalty Risk Score",
        "requirement": "Requirement Description",
        "status": "Status",
        "evidence": "Evidence"
    }
    
    df_formatted = df_formatted.rename(columns=column_rename_map)
    return df_formatted

def card(col, value, label):
    """Render a white KPI metric card with centered styling and larger numbers."""
    col.markdown(f'<div class="card"><h3>{value}</h3><span>{label}</span></div>', unsafe_allow_html=True)


# ---- Session state: load once, then CRUD operates on st.session_state.df ----
if "df" not in st.session_state:
    sc, ef, comp, demo = U.load_data()
    df = U.detect_anomalies(sc)
    st.session_state.update(df=df, ef=ef, comp=comp, demo=demo)
df, ef, comp = st.session_state.df, st.session_state.ef, st.session_state.comp

# ---- Header banner + quick stats ----
st.markdown('<div class="banner"><h1>🌿 SCoPE-Net</h1><p>Scope 3 Embodied Carbon &amp; Supply Chain Transparency Platform · Sime Darby Property</p></div>', unsafe_allow_html=True)
if st.session_state.demo:
    st.info("Some master CSVs were not found in /data — running with synthetic demo data.")

total_carbon = pd.to_numeric(df.get("total_emissions_tco2e", 0), errors='coerce').sum()
verified_rate = (df.get("verification_status") == "Verified").mean() if len(df) and "verification_status" in df else 0
ml_anomalies = int((df.get("is_anomaly") == "Yes").sum()) if "is_anomaly" in df else 0

k = st.columns(4)
card(k[0], f"{total_carbon:,.0f}", "Total Carbon (tCO₂e)")
card(k[1], f"{len(df):,}", "Delivery Logs")
card(k[2], f"{verified_rate:.0%}", "Verified Rate")
card(k[3], f"{ml_anomalies}", "ML Anomalies")

# ---- Sidebar: CREATE (Updated with all requested fields & placeholders) ----
with st.sidebar:
    st.header("➕ Submit Delivery Log")
    with st.form("create", clear_on_submit=True):
        vendor = st.text_input("Vendor", placeholder="Enter your vendor name")
        vendor_tier = st.selectbox("Vendor tier", ["Choose tier...", "Tier 1 - Direct", "Tier 2 - Upstream"], index=0)
        township = st.selectbox("Township site", ["Choose township..."] + sorted(set(U.TOWNSHIPS) | set(df.township.dropna().astype(str))), index=0)
        
        mats = sorted(ef.material.astype(str).unique()) if ef is not None else []
        material = st.selectbox("Material", ["Choose material..."] + mats, index=0)
        material_description = st.text_input("Material description", placeholder="Enter your material description")
        
        qty = st.number_input("Quantity", min_value=0.0, step=1.0, format="%.2f", value=0.0)
        unit = st.selectbox("Unit", ["Choose unit...", "Tons", "Cubic Meters", "Square Meters"], index=0)
        
        # Date and Time inputs for timestamp
        c_date, c_time = st.columns(2)
        delivery_date = c_date.date_input("Delivery date")
        delivery_time = c_time.time_input("Delivery time")
        
        v_status = st.selectbox("Verification status", ["Choose status..."] + U.STATUSES, index=0)
        
        if st.form_submit_button("Submit & calculate"):
            # Validation check for default/invalid selections
            if (vendor_tier == "Choose tier..." or 
                township == "Choose township..." or 
                material == "Choose material..." or 
                unit == "Choose unit..." or 
                v_status == "Choose status..." or 
                not vendor.strip() or 
                qty <= 0):
                st.error("Please fill in all fields correctly and select valid dropdown options.")
            else:
                st.session_state.df = U.create_record(
                    df, ef, township=township, vendor=vendor.strip(), vendor_tier=vendor_tier, 
                    material=material, material_description=material_description.strip(), 
                    quantity=qty, unit=unit, verification_status=v_status, 
                    date=delivery_date, time=delivery_time
                )
                st.success("Delivery log added successfully!"); st.rerun()

# ---- GAP BETWEEN KPIS AND NAVIGATION HUB ----
st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)

# ---- NAVIGATION HUB BOX ----
st.markdown("### 🗂️ Platform Navigation Hub")
nav_selection = st.segmented_control(
    "Select a section to view:",
    ["📊 Executive Dashboard", "🛠️ Live CRUD Operations", "🧾 NLP/OCR Ingestion Portal", "📑 Audit Compliance Reports"],
    default="📊 Executive Dashboard",
    label_visibility="collapsed"
)

st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

# ---- ACTIVE SECTION CONTENT ----
if nav_selection == "📊 Executive Dashboard":
    
    c = st.columns(3)
    sel_t = c[0].multiselect("Township", sorted(df.township.astype(str).unique()))
    sel_v = c[1].multiselect("Vendor tier", sorted(df.vendor_tier.astype(str).unique()))
    sel_s = c[2].multiselect("Verification status", sorted(df.verification_status.astype(str).unique()))
    v = df
    
    if sel_t: v = v[v.township.isin(sel_t)]
    if sel_v: v = v[v.vendor_tier.isin(sel_v)]
    if sel_s: v = v[v.verification_status.isin(sel_s)]
    if v.empty:
        st.warning("No records match the filters.")
    else:
        a, b = st.columns(2)
        a.plotly_chart(px.bar(v.groupby("township", as_index=False).total_emissions_tco2e.sum(), x="township", y="total_emissions_tco2e",
                              title="Emissions by Township", color_discrete_sequence=[GREEN]), use_container_width=True)
        b.plotly_chart(px.pie(v.groupby("material", as_index=False).total_emissions_tco2e.sum(), names="material", values="total_emissions_tco2e",
                              title="Emissions by Material", color_discrete_sequence=px.colors.sequential.Greens_r), use_container_width=True)
        # Convert date to datetime safely for grouping, handling both strings and datetimes
        chart_df = v.dropna(subset=["date"]).copy()
        chart_df["dt_parsed"] = pd.to_datetime(chart_df["date"], errors="coerce", dayfirst=True)
        
        ts = chart_df.dropna(subset=["dt_parsed"]).assign(
            month=lambda d: d.dt_parsed.dt.to_period("M").astype(str)
        ).groupby("month", as_index=False).total_emissions_tco2e.sum()
        
        st.plotly_chart(px.line(ts, x="month", y="total_emissions_tco2e", markers=True, title="Monthly Carbon Trend", color_discrete_sequence=[GREEN]), width='stretch')
        
        st.subheader("🚩 Flagged Anomalies")
        anomalies_df = v[v.is_anomaly == "Yes"][["log_id", "township", "vendor", "material", "quantity", "total_emissions_tco2e", "verification_status"]]
        st.dataframe(format_display_df(anomalies_df), width='stretch', hide_index=True)

elif nav_selection == "🛠️ Live CRUD Operations":
    st.dataframe(format_display_df(df), width='stretch', height=300, hide_index=True)
    u, d = st.columns(2)
    with u:
        st.subheader("✏️ Update Record")
        if df.empty: 
            st.caption("No records available.")
        else:
            lid = st.selectbox("Select log ID to update", df.log_id, key="upd")
            r = df[df.log_id == lid].iloc[0]
            with st.form("update"):
                up_vendor = st.text_input("Vendor", value=str(r.get("vendor", "")), placeholder="Enter vendor name")
                up_tier = st.selectbox("Vendor tier", ["Tier 1 - Direct", "Tier 2 - Upstream"], 
                                       index=0 if r.get("vendor_tier") not in ["Tier 2 - Upstream", "Tier 3"] else (1 if r.get("vendor_tier") == "Tier 2 - Upstream" else 2))
                up_township = st.selectbox("Township site", sorted(set(U.TOWNSHIPS) | set(df.township.dropna().astype(str))),
                                          index=0 if r.get("township") not in U.TOWNSHIPS else U.TOWNSHIPS.index(r.get("township")))
                up_material = st.text_input("Material", value=str(r.get("material", "")), placeholder="Enter material type")
                up_desc = st.text_input("Material description", value=str(r.get("material_description", "")), placeholder="Enter detailed description")
                up_qty = st.number_input("Quantity (square meter)", min_value=0.0, value=float(r.get("quantity", 0.0)), step=1.0)
                up_unit = st.text_input("Unit", value=str(r.get("unit", "m2")), placeholder="e.g. m2")
                up_factor = st.number_input("Factor (tCO₂e per unit)", min_value=0.0, value=float(r.get("factor_tco2e_per_unit", 0.0)), step=0.01)
                up_status = st.selectbox("Verification status", U.STATUSES, 
                                        index=U.STATUSES.index(r.get("verification_status")) if r.get("verification_status") in U.STATUSES else 0)
                
                if st.form_submit_button("Save changes"):
                    st.session_state.df = U.update_record(
                        df, ef, lid, 
                        vendor=up_vendor.strip(), 
                        vendor_tier=up_tier, 
                        township=up_township, 
                        material=up_material.strip(), 
                        material_description=up_desc.strip(), 
                        quantity=up_qty, 
                        unit=up_unit.strip(), 
                        factor_tco2e_per_unit=up_factor, 
                        verification_status=up_status
                    )
                    st.success(f"Record {lid} updated successfully!"); st.rerun()
                    
    with d:
        st.subheader("🗑️ Delete Records")
        ids = st.multiselect("Select erroneous/duplicate logs", df.log_id)
        if st.button("Delete selected", disabled=not ids):
            st.session_state.df = U.delete_records(df, ids); st.rerun()
    st.download_button("⬇️ Export Full Dataset (CSV)", df.to_csv(index=False), "scope_net_export.csv")

elif nav_selection == "🧾 NLP/OCR Ingestion Portal":
    st.write("Paste raw invoice/BOM text (or upload a .txt). Lines are parsed, messy descriptions fuzzy-matched to emission factors.")
    sample = "Invoice #4471\n120 tonnes OPC Portland cement\n35 t reinforcing rebar 12mm\n80 m3 readymix conc. grade 30\n2500 kg alumnium frames"
    up = st.file_uploader("Invoice/BOM text file", type=["txt"])
    txt = st.text_area("Raw text input", value=up.read().decode("utf-8", "ignore") if up else sample, height=160)
    if st.button("Run OCR/NLP pipeline"):
        res = U.parse_invoice_text(txt, ef)
        if res.empty: st.warning("No line items recognised.")
        else:
            st.dataframe(format_display_df(res), width='stretch', hide_index=True)
            st.metric("Parsed embodied carbon (tCO₂e)", f"{res.emissions_tco2e.sum():,.2f}")

elif nav_selection == "📑 Audit Compliance Reports":
    rep = U.compliance_summary(df, comp)
    if rep is not None and "framework" in rep.columns:
        fw = st.multiselect("Framework", sorted(rep.framework.astype(str).unique()), default=sorted(rep.framework.astype(str).unique()))
        rep = rep[rep.framework.isin(fw)] if fw else rep
        st.plotly_chart(px.histogram(rep, x="framework", color="status", barmode="group",
                                     color_discrete_map={"Aligned": GREEN, "Partial": "#F59E0B", "Gap": "#DC2626"}), width='stretch')
        st.dataframe(format_display_df(rep), width='stretch', hide_index=True)
        st.download_button("⬇️ Download audit report (CSV)", rep.to_csv(index=False), "scope_net_audit_report.csv")
    else:
        st.error("Compliance framework data could not be loaded.")

# ---- Footer ----
st.markdown('<div class="footer"><b>Disclaimer:</b> Outputs support, but do not replace, formal disclosures under IFRS S1/S2 and Malaysia\'s National Sustainability Reporting Framework (NSRF). Emission estimates rely on benchmark factors and require independent assurance before publication.<br>Built by <b>Team HUNE</b> · Sime Darby Property University Hackathon — Township of Tomorrow</div>', unsafe_allow_html=True)
