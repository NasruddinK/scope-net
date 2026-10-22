"""SCoPE-Net — Scope 3 Embodied Carbon & Supply Chain Transparency Platform (Sime Darby Property). Run: streamlit run app.py"""
import streamlit as st, pandas as pd, plotly.express as px
import utils as U

st.set_page_config(page_title="SCoPE-Net", page_icon="🌿", layout="wide")
GREEN, MINT, ACCENT = "#064E3B", "#34D399", "#10B981"

# ---- Global styling: Google Font (Poppins), vibrant colors, bigger & practical font sizes ----
st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&display=swap');
html, body, [class*="css"] {{ font-family:'Poppins',sans-serif; font-size: 17px; color: #1F2937; }}
.stApp {{ background:#F0FDF4; }}

/* Vibrant Banner */
.banner {{ 
    background:linear-gradient(135deg, {GREEN}, #047857 60%, {ACCENT}); 
    color:#FFFFFF; 
    padding:36px 42px; 
    border-radius:20px; 
    margin-bottom:24px; 
    box-shadow: 0 10px 25px -5px rgba(6, 78, 59, 0.25);
}}
.banner h1 {{ margin:0; font-weight:800; font-size:2.8rem; letter-spacing:.5px; color:#FFFFFF; }} 
.banner p {{ margin:8px 0 0; color:{MINT}; font-size:1.15rem; font-weight:600; }}

/* Poppin KPI Cards with larger font sizes */
.card {{ 
    background:#FFFFFF; 
    border-radius:16px; 
    padding:22px 24px; 
    border-left:8px solid {ACCENT}; 
    box-shadow:0 6px 16px rgba(0,0,0,0.08); 
    transition: transform 0.2s ease;
}}
.card:hover {{ transform: translateY(-3px); }}
.card h3 {{ margin:0; color:{GREEN}; font-size:2.2rem; font-weight:700; }} 
.card span {{ color:#4B5563; font-size:0.95rem; font-weight:600; text-transform: uppercase; letter-spacing: 0.5px; }}

/* Enhanced Footers & Tabs */
.footer {{ background:{GREEN}; color:#ECFDF5; padding:22px 30px; border-radius:16px; margin-top:35px; font-size:0.9rem; line-height: 1.5; }}
.stTabs [aria-selected="true"] {{ color:{GREEN} !important; border-bottom-color:{ACCENT} !important; font-weight: 700; font-size: 1.1rem; }}
.stTabs [aria-selected="false"] {{ font-weight: 600; font-size: 1.05rem; }}

/* Headers & Form Labels */
h1, h2, h3, h4 {{ color: #064E3B; font-weight: 700; }}
.stButton>button {{ background-color: {GREEN}; color: white; font-weight: 700; border-radius: 10px; padding: 0.6rem 1.2rem; font-size: 1rem; }}
.stButton>button:hover {{ background-color: #047857; border-color: #047857; color: white; }}
</style>""", unsafe_allow_html=True)


def card(col, value, label):
    """Render a white KPI metric card with popping typography."""
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
card(k[0], f"{df.emissions_tco2e.sum():,.0f}", "Total embodied carbon (tCO₂e)")
card(k[1], f"{len(df):,}", "Delivery logs")
card(k[2], f"{(df.verification_status=='Verified').mean():.0%}" if len(df) else "0%", "Verified Rate")
card(k[3], f"{int(df.is_anomaly.sum())}", "ML-flagged anomalies")

st.markdown("<br>", unsafe_allow_html=True)

# ---- Sidebar: CREATE ----
with st.sidebar:
    st.header("➕ Submit Delivery Log")
    with st.form("create", clear_on_submit=True):
        township = st.selectbox("Township site", sorted(set(U.TOWNSHIPS) | set(df.township.dropna().astype(str))))
        vendor = st.text_input("Vendor")
        tier = st.selectbox("Vendor tier", ["Tier 1 - Direct", "Tier 2 - Upstream"])
        mats = sorted(ef.material.astype(str).unique())
        material = st.selectbox("Material", mats)
        qty = st.number_input("Quantity", min_value=0.0, step=1.0)
        date = st.date_input("Delivery date")
        if st.form_submit_button("Submit & calculate"):
            if not vendor.strip() or qty <= 0:
                st.error("Vendor and a positive quantity are required.")
            else:
                st.session_state.df = U.detect_anomalies(U.create_record(
                    df, ef, township=township, vendor=vendor.strip(), vendor_tier=tier, material=material, quantity=qty, date=date))
                st.success("Log added."); st.rerun()

t1, t2, t3, t4 = st.tabs(["📊 Executive Dashboard", "🛠️ Live CRUD Operations", "🧾 NLP/OCR Ingestion Portal", "📑 Audit Compliance Reports"])

# ---- Tab 1: READ (filters + charts) ----
with t1:
    st.markdown("<br>", unsafe_allow_html=True)
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
        st.markdown("<br>", unsafe_allow_html=True)
        a, b = st.columns(2)
        a.plotly_chart(px.bar(v.groupby("township", as_index=False).emissions_tco2e.sum(), x="township", y="emissions_tco2e",
                              title="Emissions by township", color_discrete_sequence=[GREEN]), use_container_width=True)
        b.plotly_chart(px.pie(v.groupby("material", as_index=False).emissions_tco2e.sum(), names="material", values="emissions_tco2e",
                              title="Emissions by material", color_discrete_sequence=px.colors.sequential.Greens_r), use_container_width=True)
        ts = v.dropna(subset=["date"]).assign(month=lambda d: d.date.dt.to_period("M").astype(str)).groupby("month", as_index=False).emissions_tco2e.sum()
        st.plotly_chart(px.line(ts, x="month", y="emissions_tco2e", markers=True, title="Monthly trend", color_discrete_sequence=[GREEN]), use_container_width=True)
        st.subheader("🚩 Flagged anomalies")
        st.dataframe(v[v.is_anomaly][["log_id", "township", "vendor", "material", "quantity", "emissions_tco2e", "verification_status"]], use_container_width=True)

# ---- Tab 2: UPDATE + DELETE (+ raw READ) ----
with t2:
    st.markdown("<br>", unsafe_allow_html=True)
    st.dataframe(df, use_container_width=True, height=250)
    st.markdown("<br>", unsafe_allow_html=True)
    u, d = st.columns(2)
    with u:
        st.subheader("✏️ Update record")
        if df.empty: st.caption("No records.")
        else:
            lid = st.selectbox("Select log", df.log_id, key="upd")
            r = df[df.log_id == lid].iloc[0]
            with st.form("update"):
                nq = st.number_input("Quantity", min_value=0.0, value=float(r.quantity))
                nm = st.selectbox("Material", sorted(ef.material.astype(str).unique()),
                                  index=max(0, sorted(ef.material.astype(str).unique()).index(r.material)) if r.material in set(ef.material) else 0)
                ns = st.selectbox("Verification status", U.STATUSES, index=U.STATUSES.index(r.verification_status) if r.verification_status in U.STATUSES else 1)
                if st.form_submit_button("Save changes"):
                    st.session_state.df = U.update_record(df, ef, lid, quantity=nq, material=nm, verification_status=ns)
                    st.success(f"{lid} updated."); st.rerun()
    with d:
        st.subheader("🗑️ Delete records")
        ids = st.multiselect("Select erroneous/duplicate logs", df.log_id)
        if st.button("Delete selected", disabled=not ids):
            st.session_state.df = U.delete_records(df, ids); st.rerun()
    st.markdown("<br>", unsafe_allow_html=True)
    st.download_button("⬇️ Export CSV", df.to_csv(index=False), "scope_net_export.csv")

# ---- Tab 3: NLP/OCR ----
with t3:
    st.markdown("<br>", unsafe_allow_html=True)
    st.write("Paste raw invoice/BOM text (or upload a .txt). Lines are parsed, messy descriptions fuzzy-matched to emission factors.")
    sample = "Invoice #4471\n120 tonnes OPC Portland cement\n35 t reinforcing rebar 12mm\n80 m3 readymix conc. grade 30\n2500 kg alumnium frames"
    up = st.file_uploader("Invoice/BOM text file", type=["txt"])
    txt = st.text_area("Raw text", value=up.read().decode("utf-8", "ignore") if up else sample, height=160)
    if st.button("Run OCR/NLP pipeline"):
        res = U.parse_invoice_text(txt, ef)
        if res.empty: st.warning("No line items recognised.")
        else:
            st.dataframe(res, use_container_width=True)
            st.metric("Parsed embodied carbon (tCO₂e)", f"{res.emissions_tco2e.sum():,.2f}")

# ---- Tab 4: Compliance ----
with t4:
    st.markdown("<br>", unsafe_allow_html=True)
    rep = U.compliance_summary(df, comp)
    fw = st.multiselect("Framework", sorted(rep.framework.astype(str).unique()), default=sorted(rep.framework.astype(str).unique()))
    rep = rep[rep.framework.isin(fw)] if fw else rep
    st.plotly_chart(px.histogram(rep, x="framework", color="status", barmode="group",
                                 color_discrete_map={"Aligned": GREEN, "Partial": "#F59E0B", "Gap": "#DC2626"}), use_container_width=True)
    st.dataframe(rep, use_container_width=True)
    st.download_button("⬇️ Download audit report (CSV)", rep.to_csv(index=False), "scope_net_audit_report.csv")

# ---- Footer ----
st.markdown('<div class="footer"><b>Disclaimer:</b> Outputs support, but do not replace, formal disclosures under IFRS S1/S2 and Malaysia\'s National Sustainability Reporting Framework (NSRF). Emission estimates rely on benchmark factors and require independent assurance before publication.<br>Built by <b>Team HUNE</b> · Sime Darby Property University Hackathon — Township of Tomorrow</div>', unsafe_allow_html=True)
