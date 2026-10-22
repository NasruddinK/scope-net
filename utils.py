"""SCoPE-Net utilities: data loading, NLP/OCR simulation, carbon engine, anomaly detection, CRUD."""
import os, re, difflib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
F_SUPPLY = "scope_net_supply_chain_20000.csv"
F_EF = "scope_net_emission_factors_20000.csv"
F_COMP = "scope_net_compliance_frameworks_20000.csv"
TOWNSHIPS = ["Elmina City", "Serenia City", "Bandar Bukit Raja", "Putra Heights"]
STATUSES = ["Verified", "Pending", "Flagged"]
_DEMO_EF = {"Cement": ("tonne", 0.83), "Steel Rebar": ("tonne", 1.85), "Concrete": ("m3", 0.30),
            "Timber": ("m3", 0.45), "Glass": ("tonne", 1.20), "Aluminium": ("tonne", 8.60),
            "Bricks": ("tonne", 0.24), "Asphalt": ("tonne", 0.05)}


def _norm(df: pd.DataFrame) -> pd.DataFrame:
    """Lower-case/underscore column names and map common aliases to the canonical schema."""
    df = df.copy()
    df.columns = [re.sub(r"\W+", "_", c.strip().lower()).strip("_") for c in df.columns]
    alias = {"project_site": "township", "site": "township", "supplier": "vendor", "tier": "vendor_tier",
             "item": "material", "material_name": "material", "qty": "quantity", "status": "verification_status",
             "emission_factor": "factor_tco2e_per_unit", "ef": "factor_tco2e_per_unit", "id": "log_id"}
    return df.rename(columns={k: v for k, v in alias.items() if k in df.columns and v not in df.columns})


def _read(name: str):
    """Read a CSV from data/; return None if missing/unreadable (robust to missing inputs)."""
    try:
        return _norm(pd.read_csv(os.path.join(DATA_DIR, name)))
    except Exception:
        return None


def _demo_data(n=400, seed=7):
    """Generate synthetic stand-ins for the three datasets."""
    rng = np.random.default_rng(seed)
    ef = pd.DataFrame([(m, u, f) for m, (u, f) in _DEMO_EF.items()], columns=["material", "unit", "factor_tco2e_per_unit"])
    mats = rng.choice(ef.material, n)
    sc = pd.DataFrame({
        "log_id": [f"LOG-{i:05d}" for i in range(1, n + 1)],
        "date": pd.to_datetime("2026-01-01") + pd.to_timedelta(rng.integers(0, 280, n), unit="D"),
        "township": rng.choice(TOWNSHIPS, n), "vendor": [f"Vendor {c}" for c in rng.choice(list("ABCDEFGH"), n)],
        "vendor_tier": rng.choice(["Tier 1", "Tier 2", "Tier 3"], n, p=[.5, .3, .2]), "material": mats,
        "quantity": rng.gamma(4, 25, n).round(1), "verification_status": rng.choice(STATUSES, n, p=[.7, .2, .1])})
    sc = sc.merge(ef[["material", "unit"]], on="material", how="left")
    sc.loc[rng.choice(n, 8, replace=False), "quantity"] *= 15  # injected spikes
    comp = pd.DataFrame({
        "framework": ["IFRS S1"] * 3 + ["IFRS S2"] * 4 + ["NSRF"] * 3,
        "requirement_id": ["S1-GOV", "S1-STR", "S1-RSK", "S2-GHG", "S2-S3", "S2-CLM", "S2-TGT", "NSRF-A", "NSRF-B", "NSRF-C"],
        "requirement": ["Governance disclosure", "Strategy & opportunities", "Risk management", "Scope 1/2 emissions",
                        "Scope 3 emissions (cat. 1 purchased goods)", "Climate resilience", "Targets & progress",
                        "Material sustainability matters", "Data assurance/verification", "Value chain transparency"],
        "category": ["Governance", "Strategy", "Risk", "Metrics", "Metrics", "Strategy", "Metrics", "Disclosure", "Assurance", "Value chain"]})
    return sc, ef, comp

def _find(df, keywords, exclude=()):
    """Return the first column whose name contains any keyword (None if not found)."""
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
    if "log_id" not in sc: sc.insert(0, "log_id", [f"LOG-{i:05d}" for i in range(1, len(sc) + 1)])
    for col, default in [("township", "Unknown"), ("vendor", "Unknown"), ("vendor_tier", "Tier 1"),
                         ("verification_status", "Pending"), ("material", "Unknown")]:
        if col not in sc: sc[col] = default
    sc["quantity"] = pd.to_numeric(sc.get("quantity", 0), errors="coerce").fillna(0)
    sc["date"] = pd.to_datetime(sc.get("date", pd.Timestamp.today()), errors="coerce")
    return sc.reset_index(drop=True), ef, comp, demo


# ---------------- Carbon engine ----------------
def factor_lookup(ef: pd.DataFrame) -> dict:
    """material (lower) -> tCO2e per unit."""
    return {str(m).lower(): float(f) for m, f in zip(ef["material"], ef["factor_tco2e_per_unit"])}


def calculate_emissions(df: pd.DataFrame, ef: pd.DataFrame) -> pd.DataFrame:
    """Embodied carbon (tCO2e) = quantity x emission factor; unmatched materials get 0 and are flagged."""
    df = df.copy()
    lk = factor_lookup(ef)
    df["factor"] = df["material"].astype(str).str.lower().map(lk)
    df["emissions_tco2e"] = (df["quantity"] * df["factor"]).fillna(0).round(3)
    return df


# ---------------- Anomaly detection ----------------
def detect_anomalies(df: pd.DataFrame, contamination=0.03) -> pd.DataFrame:
    """Isolation Forest on log-quantity/emissions plus a per-material z-score rule; adds `is_anomaly`."""
    df = df.copy()
    df["is_anomaly"] = False
    if len(df) < 20:
        return df
    X = np.log1p(df[["quantity", "emissions_tco2e"]].clip(lower=0))
    iso = IsolationForest(contamination=contamination, random_state=42).fit_predict(X) == -1
    grp = df.groupby("material")["quantity"]
    z = ((df["quantity"] - grp.transform("mean")) / grp.transform("std").replace(0, np.nan)).abs().fillna(0)
    df["is_anomaly"] = iso | (z > 3.5) | df["factor"].isna()
    return df


# ---------------- NLP / OCR pipeline ----------------
_UNITS = r"(tonnes?|tons?|t|kg|g|m3|m³|cubic\s*m(?:eters?)?)"
_SYN = {
    "opc": "cement", "portland": "cement", "cement": "cement",
    "rebar": "steel rebar", "reinforcing": "steel rebar", "steel": "steel rebar",
    "readymix": "concrete", "ready-mix": "concrete", "conc": "concrete", "concrete": "concrete",
    "timber": "timber", "wood": "timber",
    "glass": "glass",
    "aluminium": "aluminium", "aluminum": "aluminium", "alumnium": "aluminium",
    "bricks": "bricks", "brick": "bricks",
    "asphalt": "asphalt"
}


def parse_invoice_text(text: str, ef: pd.DataFrame, cutoff=0.4) -> pd.DataFrame:
    """Advanced OCR/NLP parser: regex-extract quantities, units, and descriptions, resolving synonyms, typos, and fuzzy matches."""
    lk, rows = factor_lookup(ef), []
    for line in (text or "").splitlines():
        if not line.strip() or line.strip().startswith("#") or line.strip().lower().startswith("invoice"):
            continue
        
        m = re.search(rf"(\d+(?:[.,]\d+)?)\s*{_UNITS}?\s*(?:of|x)?\s*([A-Za-z][\w\s\-/().]+)", line, re.I)
        if not m:
            m2 = re.search(rf"(\d+(?:[.,]\d+)?)\s*([A-Za-z][\w\s\-/().]+)", line, re.I)
            if not m2:
                continue
            qty, unit, desc = float(m2.group(1).replace(",", "")), "", m2.group(2).strip().lower()
        else:
            qty, unit, desc = float(m.group(1).replace(",", "")), (m.group(2) or "").lower(), m.group(3).strip().lower()

        if unit in ("kg", "g"): 
            qty, unit = (qty / 1000 if unit == "kg" else qty / 1000000), "tonne"
        
        clean = re.sub(r"[^a-z\s\-]", " ", desc).strip()
        
        matched_mat = None
        for k, v in _SYN.items():
            if k in clean or any(k == w for w in clean.split()):
                matched_mat = v
                break
        
        score = 1.0
        if not matched_mat:
            words = clean.split()
            best_match, best_score = None, 0.0
            for w in words:
                hits = difflib.get_close_matches(w, list(lk), n=1, cutoff=0.6)
                if hits:
                    best_match, best_score = hits[0], 0.75
                    break
            if not best_match:
                hits = difflib.get_close_matches(clean, list(lk), n=1, cutoff=cutoff)
                if hits:
                    best_match = hits[0]
                    best_score = round(difflib.SequenceMatcher(None, clean, best_match).ratio(), 2)
                else:
                    best_score = 0.0
            matched_mat = best_match
            score = best_score

        f = lk.get(matched_mat.lower()) if matched_mat and matched_mat.lower() in lk else None
        rows.append({
            "raw_line": line.strip(),
            "matched_material": matched_mat.title() if (matched_mat and matched_mat.lower() in lk) else "NO MATCH",
            "match_confidence": score,
            "quantity": round(qty, 3),
            "unit": unit if unit else "tonne",
            "factor": f,
            "emissions_tco2e": round(qty * f, 3) if f else 0.0
        })
    return pd.DataFrame(rows)


# ---------------- CRUD ----------------
def create_record(df, ef, **f):
    """Append a new delivery log; emissions are computed automatically."""
    nid = f"LOG-{len(df) + 1:05d}"
    while nid in set(df["log_id"]): nid = f"LOG-{np.random.randint(10**5, 10**6)}"
    row = pd.DataFrame([{"log_id": nid, "date": pd.to_datetime(f.get("date")), "township": f["township"],
                         "vendor": f["vendor"], "vendor_tier": f["vendor_tier"], "material": f["material"],
                         "quantity": float(f["quantity"]), "verification_status": "Pending"}])
    return pd.concat([df, calculate_emissions(row, ef).assign(is_anomaly=False)], ignore_index=True)


def update_record(df, ef, log_id, **changes):
    """Edit fields of one record, then recompute its emissions."""
    i = df.index[df["log_id"] == log_id]
    if len(i) == 0: return df
    for k, v in changes.items(): df.loc[i, k] = v
    df.loc[i, "is_anomaly"] = False if changes.get("verification_status") == "Verified" else df.loc[i, "is_anomaly"]
    return recompute_row(df, ef, i)


def recompute_row(df, ef, idx):
    lk = factor_lookup(ef)
    for i in idx:
        f = lk.get(str(df.at[i, "material"]).lower())
        df.at[i, "factor"] = f
        df.at[i, "emissions_tco2e"] = round(df.at[i, "quantity"] * f, 3) if f else 0.0
    return df


def delete_records(df, ids):
    """Remove erroneous/duplicate rows by log_id."""
    return df[~df["log_id"].isin(ids)].reset_index(drop=True)


# ---------------- Compliance ----------------
def compliance_summary(df, comp):
    """Map platform capabilities/data readiness onto each framework requirement (audit-ready table)."""
    total = max(len(df), 1)
    ver = (df["verification_status"] == "Verified").mean() if len(df) else 0
    cov = (df["factor"].notna()).mean() if "factor" in df and len(df) else 0
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
