import pandas as pd
import numpy as np
from . import config


def robust_profile(amounts:pd.Series)->dict:
    med=amounts.median()
    mad=1.4826*(amounts-med).abs().median()
    return{
        "centre":med,
        "spread":max(mad,config.SPREAD_FLOOR_PCT*med) if med else 0.0,
        "cv":(mad/med) if med else 0.0,
    }


def build_profiles(df: pd.DataFrame)->pd.DataFrame:
    clean=df[df["is_clean_approval"]].sort_values("submission_date")
    rows = []
    for(emp, cat), g in clean.groupby(["employee_id", "expense_category_code"]#, observed=True
):
        stats=robust_profile(g["payout_amount"])
        gaps=g["submission_date"].diff().dt.days.dropna()
        rows.append({
            "employee_id":emp,
            "expense_category_code":cat,
            "n_prior_approved":len(g),
            "centre":stats["centre"],
            "spread":stats["spread"],
            "cv":stats["cv"],
            "median_gap_days":gaps.median() if len(gaps) else np.nan,
            "months_claiming":(g["submission_date"].max() - g["submission_date"].min()).days / 30.44,
            # "prior_rejection": (df[(df.employee_id == emp) &
            #                         (df.expense_category_code == cat)]
            #                      .item_status.eq("Rejected").any()),
        })

    return pd.DataFrame(rows)


def is_eligible(profile_row)->bool:
    return (profile_row["n_prior_approved"]>=config.MIN_PRIOR_APPROVALS and profile_row["months_claiming"]>=config.MIN_TENURE_MONTHS)