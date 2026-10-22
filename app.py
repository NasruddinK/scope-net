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


def card(col, value, label):
    """Render a white KPI metric card with centered styling."""
    col.markdown(f'<div class="card"><h3>{value}</h3><span>{label}</span></div>', unsafe_allow_html=True)


# ---- Session state: load once, then CRUD operates on st.session_state.df ----
if "df" not in st.session_state:
    sc, ef, comp, demo = U.load_data()
    df = U.detect_anomalies(U.calculate_emissions(sc, ef))
    st.session_state.update(df=df, ef=ef, comp=comp, demo=demo)
df, ef, comp = st.session_state.df, st.session_state.ef, st.session_state.comp

# ---- Header banner + quick stats ----
st.markdown('<div class="banner"><h1>🌿 SCoPE-Net</h1><p>Scope 3 Embodied Carbon &amp; Supply Chain Transparency Platform · Sime Darby Property</p></div>', unsafe_allow_html=True)
if st.session_state.demo:
    st.info("Some master CSVs were not found in /data — running with synthetic demo data.")

k = st.columns(4)
card(k[0], f"{df.emissions_tco2e.sum():,.0f}", "Total Carbon (tCO₂e)")
card(k[1], f"{len(df):,}", "Delivery Logs")
card(k[2], f"{(df.verification_status=='Verified').mean():.0%}" if len(df) else "0%", "Verified Rate")
card(k[3], f"{int(df.is_anomaly.sum())}", "ML Anomalies")

# ---- Sidebar: CREATE (Updated with material description & square meters) ----
with st.sidebar:
    st.header("➕ Submit Delivery Log")
    with st.form("create", clear_on_submit=True):
        township = st.selectbox("Township site", sorted(set(U.TOWNSHIPS) | set(df.township.dropna().astype(str))))
        vendor = st.text_input("Vendor")
        tier = st.selectbox("Vendor tier", ["Tier 1 - Direct", "Tier 2 - Upstream"])
        mats = sorted(ef.material.astype(str).unique())
        material = st.selectbox("Material", mats)
        material_description = st.text_input("Material Description")
        qty = st.number_input("Quantity (square meter)", min_value=0.0, step=1.0)
        unit = st.text_input("Unit", value="m2")
        
        # Pull default factor based on selected material
        default_fac = float(ef[ef.material == material]["factor_tco2e_per_unit"].values[0]) if material in ef.material.values else 0.5
        factor_tco2e_per_unit = st.number_input("Factor (tCO₂e per unit)", min_value=0.0, value=default_fac, step=0.01)
        
        is_anomaly_input = st.selectbox("Is Anomaly (y/n)", ["n", "y"])
        date = st.date_input("Delivery date")
        
        if st.form_submit_button("Submit & calculate"):
            if not vendor.strip() or qty <= 0:
                st.error("Vendor and a positive quantity are required.")
            else:
                st.session_state.df = U.detect_anomalies(U.create_record(
                    df, ef, township=township, vendor=vendor.strip(), vendor_tier=tier, 
                    material=material, material_description=material_description.strip(), 
                    quantity=qty, unit=unit.strip(), factor_tco2e_per_unit=factor_tco2e_per_unit,
                    is_anomaly=is_anomaly_input, date=date))
                st.success("Log added successfully.")
                st.rerun()

# ---- GAP BETWEEN KPIS AND NAVIGATION HUB ----
st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)

# ---- NAVIGATION HUB BOX (With Gap & White Background) ----
st.markdown("### 🗂️ Platform Navigation Hub")
nav_selection = st.segmented_control(
    "Select a section to view:",
    ["📊 Executive Dashboard", "🛠️ Live CRUD Operations", "🧾 NLP/OCR Ingestion Portal", "📑 Audit Compliance Reports"],
    default="📊 Executive Dashboard",
    label_visibility="collapsed"
)

st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

# ---- Tab 1: READ (filters + charts) ----
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
        a.plotly_chart(px.bar(v.groupby("township", as_index=False).emissions_tco2e.sum(), x="township", y="emissions_tco2e",
                              title="Emissions by Township", color_discrete_sequence=[GREEN]), use_container_width=True)
        b.plotly_chart(px.pie(v.groupby("material", as_index=False).emissions_tco2e.sum(), names="material", values="emissions_tco2e",
                              title="Emissions by Material", color_discrete_sequence=px.colors.sequential.Greens_r), use_container_width=True)
        ts = v.dropna(subset=["date"]).assign(month=lambda d: d.date.dt.to_period("M").astype(str)).groupby("month", as_index=False).emissions_tco2e.sum()
        st.plotly_chart(px.line(ts, x="month", y="emissions_tco2e", markers=True, title="Monthly Carbon Trend", color_discrete_sequence=[GREEN]), use_container_width=True)
        st.subheader("🚩 Flagged Anomalies")
        st.dataframe(v[v.is_anomaly][["log_id", "township", "vendor", "material", "quantity", "emissions_tco2e", "verification_status"]], use_container_width=True)

# ---- Tab 2: UPDATE + DELETE (+ raw READ) ----
elif nav_selection == "🛠️ Live CRUD Operations":
    st.dataframe(df, use_container_width=True, height=300)
    u, d = st.columns(2)
   with u:
        st.subheader("✏️ Update Record")
        if df.empty: 
            st.caption("No records.")
        else:
            lid = st.selectbox("Select log ID", df.log_id, key="upd")
            r = df[df.log_id == lid].iloc[0]
            with st.form("update"):
                nvendor = st.text_input("vendor", value=str(r.get("vendor", "")))
                ntier = st.selectbox("vendor_tier", ["Tier 1 - Direct", "Tier 2 - Upstream"], index=0 if r.get("vendor_tier")=="Tier 1 - Direct" else 1)
                ntownship = st.selectbox("township", sorted(set(U.TOWNSHIPS) | {r.get("township")}))
                nmat = st.selectbox("material", sorted(ef.material.astype(str).unique()), index=0)
                nmat_desc = st.text_input("material_description", value=str(r.get("material_description", "")))
                nq = st.number_input("quantity (square meter)", min_value=0.0, value=float(r.get("quantity", 0.0)))
                nunit = st.text_input("unit", value=str(r.get("unit", "m2")))
                nfac = st.number_input("factor_tco2e_per_unit", min_value=0.0, value=float(r.get("factor_tco2e_per_unit", 0.5)))
                
                cur_anom = "y" if r.get("is_anomaly", False) else "n"
                nis_anom = st.selectbox("is_anomaly (y/n)", ["n", "y"], index=0 if cur_anom=="n" else 1)
                
                if st.form_submit_button("Save changes"):
                    st.session_state.df = U.update_record(
                        df, ef, lid, 
                        vendor=nvendor, vendor_tier=ntier, township=ntownship,
                        material=nmat, material_description=nmat_desc, quantity=nq,
                        unit=nunit, factor_tco2e_per_unit=nfac, is_anomaly=nis_anom
                    )
                    st.success(f"Record {lid} updated successfully.")
                    st.rerun()
    with d:
        st.subheader("🗑️ Delete Records")
        ids = st.multiselect("Select erroneous/duplicate logs", df.log_id)
        if st.button("Delete selected", disabled=not ids):
            st.session_state.df = U.delete_records(df, ids); st.rerun()
    st.download_button("⬇️ Export Full Dataset (CSV)", df.to_csv(index=False), "scope_net_export.csv")

# ---- Tab 3: NLP/OCR ----
elif nav_selection == "🧾 NLP/OCR Ingestion Portal":
    st.write("Paste raw invoice/BOM text (or upload a .txt). Lines are parsed, messy descriptions fuzzy-matched to emission factors.")
    sample = "Invoice #4471\n120 tonnes OPC Portland cement\n35 t reinforcing rebar 12mm\n80 m3 readymix conc. grade 30\n2500 kg alumnium frames"
    up = st.file_uploader("Invoice/BOM text file", type=["txt"])
    txt = st.text_area("Raw text input", value=up.read().decode("utf-8", "ignore") if up else sample, height=160)
    if st.button("Run OCR/NLP pipeline"):
        res = U.parse_invoice_text(txt, ef)
        if res.empty: st.warning("No line items recognised.")
        else:
            st.dataframe(res, use_container_width=True)
            st.metric("Parsed embodied carbon (tCO₂e)", f"{res.emissions_tco2e.sum():,.2f}")

# ---- Tab 4: Compliance ----
elif nav_selection == "📑 Audit Compliance Reports":
    rep = U.compliance_summary(df, comp)
    fw = st.multiselect("Framework", sorted(rep.framework.astype(str).unique()), default=sorted(rep.framework.astype(str).unique()))
    rep = rep[rep.framework.isin(fw)] if fw else rep
    st.plotly_chart(px.histogram(rep, x="framework", color="status", barmode="group",
                                 color_discrete_map={"Aligned": GREEN, "Partial": "#F59E0B", "Gap": "#DC2626"}), use_container_width=True)
    st.dataframe(rep, use_container_width=True)
    st.download_button("⬇️ Download audit report (CSV)", rep.to_csv(index=False), "scope_net_audit_report.csv")

# ---- Footer ----
st.markdown('<div class="footer"><b>Disclaimer:</b> Outputs support, but do not replace, formal disclosures under IFRS S1/S2 and Malaysia\'s National Sustainability Reporting Framework (NSRF). Emission estimates rely on benchmark factors and require independent assurance before publication.<br>Built by <b>Team HUNE</b> · Sime Darby Property University Hackathon — Township of Tomorrow</div>', unsafe_allow_html=True)
