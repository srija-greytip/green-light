import pandas as pd
import numpy as np

SPREAD_FLOOR_PCT = 0.05 # a wobble can never be measured as smaller than 5% of the centre - stops divide-by-zero later

def _centre_and_spread(values: pd.Series) -> tuple:
    values = values.dropna()
    if len(values) == 0:
        return np.nan, np.nan
    centre = values.median()
    mad = 1.4826 * (values - centre).abs().median()
    spread = max(mad, SPREAD_FLOOR_PCT * abs(centre)) if centre else 0.0
    return centre, spread

def _classify(n_claims, amount_cv, gap_centre, months_active) -> str:
    if n_claims < 3:
        return "too_few"
    if months_active < 2:
        return "new"
    if amount_cv is None or np.isnan(amount_cv):
        return "unknown"
    if amount_cv < 0.10:
        return "steady"
    if amount_cv < 0.30:
        return "moderate" 
    return "erratic"

def extract_patterns(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (emp, cat, typ), g_all in df.groupby(
        ["employee_id", "expense_category_code", "expense_type_id"],
        observed=True
    ):
        g = g_all[g_all["is_clean_approval"]].sort_values("submission_date")

        if len(g) == 0:
            continue
        # amount
        amt_centre, amt_spread = _centre_and_spread(g["bill_amount"])
        amt_cv = (amt_spread / amt_centre) if amt_centre else np.nan

        # rhythm 
        gaps = g["submission_date"].diff().dt.days.dropna()
        gap_centre, gap_spread = _centre_and_spread(gaps)

        # timing (bill date -> submission date)
        lags = (g["submission_date"] - g["bill_date"]).dt.days
        lag_centre, lag_spread = _centre_and_spread(lags)

        # outcome (uses all claims, not just clean ones)
        n_total = len(g_all)
        n_rejected = int(g_all["is_rejected"].sum())

        # how long have they been claiming this type
        months_active = (g["submission_date"].max() - g["submission_date"].min()).days / 30.44

        rows.append({
            "employee_id": emp,
            "expense_category_code": cat,
            "expense_type_id": typ,

            # counts
            "n_claims_total": n_total,
            "n_clean_approved": len(g),
            "n_rejected": n_rejected,
            "reject_rate": n_rejected / n_total if n_total else np.nan,

            # amount
            "amount_centre": round(amt_centre, 2) if not np.isnan(amt_centre) else np.nan,
            "amount_spread": round(amt_spread, 2) if not np.isnan(amt_spread) else np.nan,
            "amount_cv": round(amt_cv, 4) if not np.isnan(amt_cv) else np.nan,
            "amount_min": g["bill_amount"].min(),
            "amount_max": g["bill_amount"].max(),

            # rhythm
            "gap_centre_days": round(gap_centre, 1) if not np.isnan(gap_centre) else np.nan,
            "gap_spread_days": round(gap_spread, 1) if not np.isnan(gap_spread) else np.nan,

            # timing
            "lag_centre_days": round(lag_centre, 1) if not np.isnan(lag_centre) else np.nan,
            "lag_spread_days": round(lag_spread, 1) if not np.isnan(lag_spread) else np.nan,

            # tenure
            "months_active": round(months_active, 1),
            "first_claim": g["submission_date"].min(),
            "last_claim": g["submission_date"].max(),

            # label
            "pattern_type": _classify(len(g), amt_cv, gap_centre, months_active),
        })

    return pd.DataFrame(rows)

def load_and_prepare(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=["", "NULL", "null"])

    for c in ["bill_date", "submission_date", "approval_date", "rejection_date", "item_created_on", "item_updated_on"]:
        df[c] = pd.to_datetime(df[c], errors="coerce")

    for c in ["bill_amount", "overridden_amount", "override_count","duplicate_match_count", "limit_per_claim"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    for c in ["auto_approved", "is_duplicate_flagged"]:
        df[c] = df[c].map({"TRUE": True, "True": True, "true": True, "FALSE": False, "False": False, "false": False})

    for c in ["employee_id", "expense_type_id"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")

    df["expense_category_code"] = df["expense_category_code"].astype("category")

    df["is_approved"] = df["item_status"].isin(["Accepted", "Paid"])
    df["is_rejected"] = df["item_status"] == "Rejected"
    df["is_clean_approval"] = (
        df["is_approved"] & (df["auto_approved"] != True) & (df["override_count"].fillna(0) == 0)
    )
    return df

df = load_and_prepare("data/raw/claims_regular_mbu_highvolume.csv")
patterns = extract_patterns(df)

print(patterns)
patterns.to_csv("outputs/patterns_regular_mbu_highvolume.csv", index=False)  # Save to file

def is_eligible(pattern_row, min_claims=3, min_months=1) -> bool:
    return (pattern_row["n_clean_approved"] >= min_claims
            and pattern_row["months_active"] >= min_months)