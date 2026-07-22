import pandas as pd
import numpy as np
from . import config

def robust_profile(amounts: pd.Series) -> dict:
    med=amounts.median()
    mad=1.4826*(amounts-med).abs().median()
    return {
        "centre":med,
        "spread":max(mad, config.SPREAD_FLOOR_PCT * med) if med else 0.0,
        "cv":(mad/med) if med else 0.0,
    }
def _grain_columns() -> list:
    if config.PROFILE_GRAIN == "type":
        return ["employee_id", "expense_category_code", "expense_type_name"]
    elif config.PROFILE_GRAIN == "category":
        return ["employee_id", "expense_category_code"]
    else:
        raise ValueError(f"Unknown profile grain: {config.PROFILE_GRAIN!r}")
def build_profiles(df: pd.DataFrame) -> pd.DataFrame:
    grain=_grain_columns()
    clean=df[df["is_clean_approval"]].sort_values("submission_date")
    rows=[]
    for key, g in clean.groupby(grain, observed=True):
        key=key if isinstance(key, tuple) else (key,)
        key_dict=dict(zip(grain, key))

        stats=robust_profile(g["bill_amount"])
        gaps=g["submission_date"].diff().dt.days.dropna()

        mask=pd.Series(True, index=df.index)
        for c, v in key_dict.items():
            mask&=(df[c]==v)
        prior_rejection=bool(df.loc[mask, "is_rejected"].any())

        rows.append({
            **key_dict,
            "n_prior_approved":len(g),
            "centre":stats["centre"],
            "spread":stats["spread"],
            "cv":stats["cv"],
            "median_gap_days":gaps.median() if len(gaps) else np.nan,
            "months_claiming":(g["submission_date"].max() - g["submission_date"].min()).days / 30.44,
            "prior_rejection":prior_rejection,
        })
    return pd.DataFrame(rows)
def is_eligible(profile_row) -> bool:
    return (profile_row["n_prior_approved"] >= config.MIN_PRIOR_APPROVALS
            and profile_row["months_claiming"] >= config.MIN_TENURE_MONTHS)