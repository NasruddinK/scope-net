"""SCoPE-Net utilities: data loading, NLP/OCR simulation, carbon engine, anomaly detection, CRUD."""
import os, re, difflib
import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
F_SUPPLY = "scope_net_supply_chain_20000.csv"
F_EF = "scope_net_emission_factors_20000.csv"
F_COMP = "scope_net_compliance_frameworks_20000.csv"
TOWNSHIPS = ["Elmina City", "Serenia City", "Bandar Bukit Raja", "Putra Heights", "Bandar Ainsdale", "Elmina City Township"]
STATUSES = ["Verified", "Pending Review", "Flagged (Anomaly)"]
_DEMO_EF = {"Cement": ("tonne", 0.83), "Steel Rebar": ("tonne", 1.85), "Concrete": ("m3", 0.30),
            "Timber": ("m3", 0.45), "Glass": ("tonne", 1.20), "Aluminium": ("tonne", 8.60),
            "Bricks": ("tonne", 0.24), "Asphalt": ("tonne", 0.05)}


def _norm(df: pd.DataFrame) -> pd.DataFrame:
    """Lower-case/underscore column names and map common aliases to the canonical schema."""
    df = df.copy()
    df.columns = [re.sub(r"\W+", "_", c.strip().lower()).strip("_") for c in df.columns]
    alias = {
        "project_site": "township", "site": "township", 
        "supplier": "vendor", "vendor_name": "vendor",
        "tier": "vendor_tier", "vendor_tier": "vendor_tier",
        "item": "material", "material_category": "material", "material_name": "material",
        "material_description": "material_description",
        "qty": "quantity", "quantity": "quantity",
        "status": "verification_status", "verification_status": "verification_status",
        "emission_factor": "factor_tco2e_per_unit", "ef": "factor_tco2e_per_unit",
        "total_emissions_tco2e": "total_emissions_tco2e", "emissions_tco2e": "total_emissions_tco2e",
        "is_anomaly": "is_anomaly",
        "id": "log_id", "transaction_id": "log_id", "date": "date", "timestamp": "date", "unit": "unit"
    }
    return df.rename(columns={k: v for k, v in alias.items() if k in df.columns and v not in df.columns})


def _read(name: str):
    """Read a CSV from data/ or current directory; return None if missing."""
    try:
        path = os.path.join(DATA_DIR, name)
        if not os.path.exists(path):
            path = name
        return _norm(pd.read_csv(path))
    except Exception:
        return None


def _demo_data(n=400, seed=7):
    """Generate synthetic stand-ins for the three datasets."""
    rng = np.random.default_rng(seed)
    ef = pd.DataFrame([(m, u, f) for m, (u, f) in _DEMO_EF.items()], columns=["material", "unit", "factor_tco2e_per_unit"])
    mats = rng.choice(ef.material, n)
    statuses = rng.choice(STATUSES, n, p=[.7, .2, .1])
    sc = pd.DataFrame({
        "log_id": [f"LOG-{i:05d}" for i in range(1, n + 1)],
        "date": pd.to_datetime("2026-01-01") + pd.to_timedelta(rng.integers(0, 280, n), unit="D"),
        "township": rng.choice(TOWNSHIPS, n), "vendor": [f"Vendor {c}" for c in rng.choice(list("ABCDEFGH"), n)],
        "vendor_tier": rng.choice(["Tier 1 - Direct", "Tier 2 - Upstream", "Tier 3"], n, p=[.5, .3, .2]), 
        "material": mats,
        "material_description": [f"Standard {m}" for m in mats],
        "quantity": rng.gamma(4, 25, n).round(1), 
        "unit": "m2",
        "verification_status": statuses})
    sc = sc.merge(ef[["material", "unit"]], on="material", how="left", suffixes=('', '_ef'))
    if 'unit_ef' in sc.columns:
        sc['unit'] = sc['unit_ef'].fillna(sc['unit'])
        sc = sc.drop(columns=['unit_ef'])
    sc["factor_tco2e_per_unit"] = sc["material"].map(factor_lookup(ef))
    sc["total_emissions_tco2e"] = (sc["quantity"] * sc["factor_tco2e_per_unit"]).round(3)
    sc["is_anomaly"] = sc["verification_status"].apply(lambda s: "Yes" if "flagged" in str(s).lower() else "No")
    
    comp = pd.DataFrame({
        "framework": ["IFRS S1"] * 3 + ["IFRS S2"] * 4 + ["NSRF"] * 3,
        "requirement_id": ["S1-GOV", "S1-STR", "S1-RSK", "S2-GHG", "S2-S3", "S2-CLM", "S2-TGT", "NSRF-A", "NSRF-B", "NSRF-C"],
        "requirement": ["Governance disclosure", "Strategy & opportunities", "Risk management", "Scope 1/2 emissions",
                        "Scope 3 emissions (cat. 1 purchased goods)", "Climate resilience", "Targets & progress",
                        "Material sustainability matters", "Data assurance/verification", "Value chain transparency"],
        "category": ["Governance", "Strategy", "Risk", "Metrics", "Metrics", "Strategy", "Metrics", "Disclosure", "Assurance", "Value chain"]})
    return sc, ef, comp


def _find(df, keywords, exclude=()):
    """Return the first column whose name contains any keyword."""
    for c in df.columns:
        if any(k in c for k in keywords) and not any(x in c for x in exclude):
            return c
    return None


def _coerce_ef(ef):
    """Map an arbitrary emission-factor table to material / unit / factor_tco2e_per_unit."""
    if ef is None:
        return None
    num = [c for c in ef.columns if pd.api.types.is_numeric_dtype(ef[c])]
    txt = [c for c in ef.columns if c not in num]
    mat = _find(ef[txt], ["material", "item", "product", "description", "name", "category"]) if txt else None
    mat = mat or (txt[0] if txt else None)
    fac = _find(ef[num], ["factor", "tco2e", "co2", "emission"], exclude=["id"]) if num else None
    fac = fac or (num[-1] if num else None)
    unit = _find(ef[txt], ["unit", "uom"]) if txt else None
    if mat is None or fac is None:
        return None
    out = pd.DataFrame({"material": ef[mat].astype(str).str.strip(),
                        "factor_tco2e_per_unit": pd.to_numeric(ef[fac], errors="coerce"),
                        "unit": ef[unit].astype(str) if unit else ""})
    return out.dropna(subset=["factor_tco2e_per_unit"]).groupby("material", as_index=False).agg(
        factor_tco2e_per_unit=("factor_tco2e_per_unit", "mean"), unit=("unit", "first"))


def _coerce_sc(sc):
    """Rename detected columns of the delivery-log table to the canonical schema."""
    if sc is None:
        return None
    guess = {"log_id": (["log", "id", "delivery", "ref"], ["vendor", "supplier"]),
             "date": (["date", "time"], []), "township": (["township", "site", "project", "location"], []),
             "vendor": (["vendor_name", "vendor", "supplier"], ["tier"]),
             "vendor_tier": (["tier"], []), "material": (["material", "item", "product", "description"], []),
             "quantity": (["quantity", "qty", "amount", "volume", "weight"], []),
             "verification_status": (["verif", "status"], [])}
    ren, used = {}, set()
    for canon, (kw, ex) in guess.items():
        if canon in sc.columns:
            used.add(canon); continue
        c = _find(sc[[x for x in sc.columns if x not in used]], kw, ex)
        if c: ren[c] = canon; used.add(c)
    sc = sc.rename(columns=ren)
    return sc if "material" in sc.columns and "quantity" in sc.columns else None


def _coerce_comp(comp):
    """Map an arbitrary compliance table to framework / requirement_id / requirement / category."""
    if comp is None:
        return None
    comp = _norm(comp)
    guess_fw = _find(comp, ["framework", "standard", "regulation", "law", "guideline"], [])
    guess_req = _find(comp, ["requirement", "criteria", "disclosure", "item", "description"], [])
    guess_id = _find(comp, ["id", "code", "req_id"], [])
    guess_cat = _find(comp, ["category", "pillar", "domain", "topic"], [])
    
    rename_map = {}
    if guess_fw and guess_fw != "framework": rename_map[guess_fw] = "framework"
    if guess_req and guess_req != "requirement": rename_map[guess_req] = "requirement"
    if guess_id and guess_id != "requirement_id": rename_map[guess_id] = "requirement_id"
    if guess_cat and guess_cat != "category": rename_map[guess_cat] = "category"
    
    comp = comp.rename(columns=rename_map)
    if "framework" not in comp.columns:
        comp["framework"] = "General ESG"
    if "requirement" not in comp.columns:
        txt_cols = [c for c in comp.columns if not pd.api.types.is_numeric_dtype(comp[c])]
        comp["requirement"] = comp[txt_cols[0]] if txt_cols else "Requirement"
    if "requirement_id" not in comp.columns:
        comp["requirement_id"] = [f"REQ-{i+1:03d}" for i in range(len(comp))]
    if "category" not in comp.columns:
        comp["category"] = "General"
    return comp


def load_data():
    """Return (supply, emission_factors, compliance, using_demo_flag)."""
    sc, ef, comp = _coerce_sc(_read(F_SUPPLY)), _coerce_ef(_read(F_EF)), _coerce_comp(_read(F_COMP))
    demo = sc is None or ef is None or comp is None
    if demo:
        d_sc, d_ef, d_comp = _demo_data()
        sc, ef, comp = (d_sc if sc is None else sc), (d_ef if ef is None else ef), (d_comp if comp is None else comp)
    if "log_id" not in sc.columns: sc.insert(0, "log_id", [f"LOG-{i:05d}" for i in range(1, len(sc) + 1)])
    for col, default in [("township", "Unknown"), ("vendor", "Unknown"), ("vendor_tier", "Tier 1 - Direct"),
                         ("verification_status", "Pending Review"), ("material", "Unknown"),
                         ("material_description", ""), ("unit", "m2"), ("is_anomaly", "No")]:
        if col not in sc.columns: sc[col] = default
    sc["quantity"] = pd.to_numeric(sc.get("quantity", 0), errors="coerce").fillna(0)
    sc["factor_tco2e_per_unit"] = pd.to_numeric(sc.get("factor_tco2e_per_unit", 0), errors="coerce").fillna(0)
    sc["total_emissions_tco2e"] = pd.to_numeric(sc.get("total_emissions_tco2e", sc["quantity"] * sc["factor_tco2e_per_unit"]), errors="coerce").fillna(0).round(3)
    sc["date"] = pd.to_datetime(sc.get("date", pd.Timestamp.today()), errors="coerce", dayfirst=True).dt.strftime('%d/%m/%Y')
    sc = detect_anomalies(sc)
    return sc.reset_index(drop=True), ef, comp, demo


# ---------------- Carbon engine ----------------
def factor_lookup(ef: pd.DataFrame) -> dict:
    """material (lower) -> tCO2e per unit."""
    return {str(m).lower(): float(f) for m, f in zip(ef["material"], ef["factor_tco2e_per_unit"])}


def calculate_emissions(df: pd.DataFrame, ef: pd.DataFrame) -> pd.DataFrame:
    """Embodied carbon (tCO2e) = quantity x emission factor."""
    df = df.copy()
    lk = factor_lookup(ef)
    df["factor_tco2e_per_unit"] = df["material"].astype(str).str.lower().map(lk).fillna(df.get("factor_tco2e_per_unit", 0))
    df["total_emissions_tco2e"] = (df["quantity"] * df["factor_tco2e_per_unit"]).fillna(0).round(3)
    return df


# ---------------- Anomaly detection sync ----------------
def detect_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """Sync is_anomaly with verification_status: Flagged -> Yes, Verified/Pending -> No."""
    df = df.copy()
    if "verification_status" in df.columns:
        df["is_anomaly"] = df["verification_status"].apply(
            lambda s: "Yes" if "flagged" in str(s).lower() else "No"
        )
    else:
        df["is_anomaly"] = "No"
    return df

# ---------------- NLP / OCR simulation ----------------
# Updated units: added sq.m / sqm for glass/panels and refined unit matching
_UNITS = r"(?:tonnes?|tons?|t|kg|m3|m³|cubic\s*m(?:eters?)?|sq\.?m|square\s*m(?:eters?)?)"

# Expanded synonym and keyword mapping covering all requested construction materials
_SYN = {
    # Cement
    "opc": "cement", "portland": "cement", "cement": "cement",
    # Steel / Rebar
    "rebar": "steel rebar", "reinforcing": "steel rebar", "steel": "steel rebar", 
    "structural steel": "steel rebar", "h-beam": "steel rebar", "coils": "steel rebar", 
    "wire rods": "steel rebar", "wire rod": "steel rebar",
    # Concrete
    "readymix": "concrete", "ready-mix": "concrete", "concrete": "concrete", 
    "conc": "concrete", "precast": "concrete", "low-carbon concrete": "concrete",
    # Aluminium
    "aluminum": "aluminium", "aluminium": "aluminium", "frames": "aluminium", 
    "framing": "aluminium", "extrusions": "aluminium", "curtain panels": "aluminium",
    # Timber / Wood
    "wood": "timber", "timber": "timber", "lumber": "timber",
    # Glass
    "glass": "glass", "float glass": "glass", "security glass": "glass", 
    "architectural glass": "glass", "double-glazed": "glass", "laminated": "glass", "tempered": "glass",
    # Asphalt
    "asphalt": "asphalt", "bitumen": "asphalt", "macadam": "asphalt"
}

def parse_invoice_text(text: str, ef: pd.DataFrame, cutoff=0.4) -> pd.DataFrame:
    """Simulated OCR/NLP: regex-extract 'qty unit item' lines, normalise noise/synonyms, fuzzy-match to factors."""
    lk, rows = factor_lookup(ef), []
    for line in (text or "").splitlines():
        # Match lines starting with a number, optional unit, optional connector (of/x), followed by description
        m = re.search(rf"^\s*(\d+(?:[.,]\d+)?)\s*({_UNITS})?\s*(?:of|x)?\s*([A-Za-z][\w\s\-/().]+)", line, re.I)
        if not m:
            continue
            
        qty = float(m.group(1).replace(",", ""))
        unit = (m.group(2) or "").lower()
        desc = m.group(3).strip().lower()
        
        # Unit normalization / conversions
        if unit in ["kg"]: 
            qty, unit = qty / 1000, "tonne"
        elif any(u in unit for u in ["sq", "square"]):
            unit = "sq.m"
            
        clean = re.sub(r"[^a-z\s\-]", " ", desc)
        
        # Check matching against synonyms
        matched_sub = False
        for k, v in _SYN.items():
            if k in clean: 
                clean = v
                matched_sub = True
                break
        
        # If no explicit synonym hit, keep core tokens for matching
        hit = difflib.get_close_matches(clean.strip(), list(lk), n=1, cutoff=cutoff)
        score = difflib.SequenceMatcher(None, clean.strip(), hit[0]).ratio() if hit else 0
        f = lk.get(hit[0]) if hit else None
        
        rows.append({
            "raw_line": line.strip(), 
            "matched_material": hit[0].title() if hit else "NO MATCH",
            "match_confidence": round(score, 2), 
            "quantity": round(qty, 3),
            "unit": unit,
            "factor": f, 
            "emissions_tco2e": round(qty * f, 3) if f else 0.0
        })
    return pd.DataFrame(rows)

# ---------------- CRUD ----------------
def create_record(df, ef, **f):
    """Append a new delivery log."""
    nid = f"LOG-{len(df) + 1:05d}"
    while nid in set(df["log_id"]): nid = f"LOG-{np.random.randint(10**5, 10**6)}"
    row = pd.DataFrame([{
        "log_id": nid, 
        "date": pd.to_datetime(f.get("date")), 
        "township": f["township"],
        "vendor": f["vendor"], 
        "vendor_tier": f["vendor_tier"], 
        "material": f["material"],
        "material_description": f.get("material_description", ""),
        "quantity": float(f["quantity"]), 
        "unit": f.get("unit", "m2"),
        "factor_tco2e_per_unit": float(f.get("factor_tco2e_per_unit", 0.0)),
        "total_emissions_tco2e": float(f["quantity"]) * float(f.get("factor_tco2e_per_unit", 0.0)),
        "verification_status": f.get("verification_status", "Pending Review"),
        "is_anomaly": "Yes" if "flagged" in str(f.get("verification_status", "")).lower() else "No"
    }])
    return pd.concat([df, row], ignore_index=True)


def update_record(df, ef, log_id, **changes):
    """Edit fields of one record, then recompute emissions and anomaly status."""
    i = df.index[df["log_id"] == log_id]
    if len(i) == 0: return df
    for k, v in changes.items(): df.loc[i, k] = v
    df = calculate_emissions(df, ef)
    df = detect_anomalies(df)
    return df


def delete_records(df, ids):
    """Remove rows by log_id."""
    return df[~df["log_id"].isin(ids)].reset_index(drop=True)


# ---------------- Compliance ----------------
def compliance_summary(df, comp):
    """Map platform capabilities onto each framework requirement."""
    total = max(len(df), 1)
    ver = (df["verification_status"] == "Verified").mean() if len(df) and "verification_status" in df else 0
    cov = (df["factor_tco2e_per_unit"] > 0).mean() if "factor_tco2e_per_unit" in df and len(df) else 0
    out = comp.copy()
    def status(r):
        txt = f"{r.get('requirement','')} {r.get('category','')}".lower()
        if "assur" in txt or "verif" in txt: s = ver
        elif "scope 3" in txt or "metric" in txt or "ghg" in txt or "value chain" in txt: s = cov
        else: s = (ver + cov) / 2
        return "Aligned" if s >= .8 else "Partial" if s >= .5 else "Gap"
    out["status"] = out.apply(status, axis=1)
    out["evidence"] = f"{ver:.0%} records verified; {cov:.0%} emission-factor coverage over {total:,} logs"
    return out
