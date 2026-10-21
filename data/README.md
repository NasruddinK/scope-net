# data/ — master datasets (placeholders)

Place the three hackathon master datasets here:

| File | Purpose |
|------|---------|
| `scope_net_supply_chain_20000.csv` | Dataset 1: delivery logs (log_id, date, township, vendor, vendor_tier, material, quantity, unit, verification_status) |
| `scope_net_emission_factors_20000.csv` | Dataset 2: factors (material, unit, factor_tco2e_per_unit) |
| `scope_net_compliance_frameworks_20000.csv` | Dataset 3: framework, requirement_id, requirement, category |

If any file is missing, `utils.py` generates small synthetic demo data so the app still runs.
Column names are normalised (lower-case, underscores); a few common aliases are mapped automatically.
