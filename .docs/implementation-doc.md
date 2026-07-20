## 1. Environment and Repo

| Item | Detail |
|---|---|
| Python | 3.11 |
| Env | venv + requirements.txt (Docker can also be used) |
| Notebooks | Jupyter Lab — data exploration *only* |
| Version control | Git |

### Libraries — and exactly where each is used

| Library | Purpose | Section |
|---|---|---|
| pandas | Extraction, cleaning, profiling, feature building | §3, §4, §5 |
| numpy | np.where, percentiles, NaN handling | §4, §5 |
| ydata-profiling | One-line data-quality HTML report | §3.4 |
| matplotlib | Static plots for the report | §3.4, §7 |
| scikit-learn | LogisticRegression, CalibratedClassifierCV, metrics | §6, §7 |
| LightGBM | Coverage-ceiling benchmark | §7 |
| SHAP | LightGBM attributions | §7 |
| pytest | Tests — especially leakage | §5 |
| google-generativeai | Gemini, comparison arm | §8 |
| pyarrow | Parquet I/O between stages | §3 |

Each stage writes Parquet to `data/`. Any stage can be re-run without redoing the one before it.

### Repo

```
ec1062/
  data/          notebooks/     src/
  tests/         reports/       requirements.txt
```

`src/` is importable and tested. Notebooks import from `src/`, never redefine logic.

---

## 2. Pipeline

```
SQL extract → load & type → profile → clean → outlier policy
    → build profiles → featurise (point-in-time) → score → evaluate
```

---

## 3. Extraction and Cleaning

### 3.1 What We Pull

TBP with Vinay Parida.
Update §3.2, §3.3 later.

### 3.2 Collapsing Workflow Steps Into One Label

A claim has many workflow rows. We need one outcome per claim.

Rejections terminate the chain — approved means every level said yes; rejected means the first objector said no. We model the first veto.

### 3.3 Load With Explicit Types

Never let pandas infer.

- `bill_number` inferred as `int64` silently drops leading zeros and breaks duplicate detection. So we make it a string.
- `errors="coerce"` turns unparseable dates into `NaT` instead of throwing — we then count them, rather than discovering them later.

### 3.4 Profile the Raw Data

```python
from ydata_profiling import ProfileReport
ProfileReport(df, minimal=True).to_file("reports/raw_profile.html")
```

Understanding what the data looks like before doing anything with it.

**What we're looking for, and what a bad answer costs:**

| Check | If it's bad |
|---|---|
| `bill_number` null rate | Duplicate detection dies |
| `bill_date` null rate | `submit_lag` feature dies |
| category cardinality | Free-text categories → no per-category thresholds |
| amount distribution | Currency/unit inconsistency |
| Claims per employee | If most have <3, almost nothing is eligible to score |

List all the possible features and their weights.

---

## 4. Outliers — And Why We Do NOT Remove Them

Can be part of low-weighted features. We should not drop outliers.

Standard EDA says drop outliers. Here that would destroy the feature.

An anomalous claim is exactly what we're trying to detect. A ₹9,000 Food claim from someone who always claims ₹800 isn't noise to be cleaned — it's the signal.

**So: no outlier removal from the dataset. Ever.**

### But Outliers Must Not Poison the Profile

There is a real problem. If Ravi's history is `[800, 800, 820, 9000, 800]`:

```
mean = 2,244    std = 3,668
```

His profile is now garbage. Every future claim looks "normal" against a mean of ₹2,244 with an enormous spread. One freak claim destroys his tolerance band forever.

### The Policy — Two Different Treatments

| Context | Treatment |
|---|---|
| The claim being scored | Never clipped, never dropped. Score it as it is. |
| A claim's contribution to profile statistics | Robust statistics — resistant to a single extreme value |

Median and MAD instead of mean and std. One ₹9,000 claim moves the median by nothing and the MAD by nothing. Ravi's band stays tight — which is correct — and next month's ₹850 claim still scores well.

**Detecting outliers for the report only:** Used to answer "how common are out-of-pattern claims?" in the exploration report. Never used to filter.

### Tests

- `test_future_claims_do_not_affect_past_features` — If this fails, every number in the report is wrong. Runs on every commit.
- **Split**: Train on months 1..N, test on N+1..

---

## 6. Profiles, Features, Scorers

### Profile → can add more into this

```python
@dataclass
class Profile:
    n_prior_approved: int
    centre: float          # median amount
    spread: float          # MAD, floored
    cv: float              # spread / centre — how unpredictable they are
    median_gap_days: float
    days_since_last: float
    prior_rejection: bool
    months_claiming: float
```

`cv` is the load-bearing feature. It separates a Ravi (₹800 every time, tight) from a Priya (₹600–₹1,400, wide), and it's what lets the tolerance band adapt per person.

### Feature Vector → TBD

| Feature | Definition |
|---|---|
| `n_prior_approved` | from profile |
| `amount_z` | `(amount - centre) / spread` |
| `cv` | from profile |
| `pct_of_policy_limit` | `amount / policy_limit` |
| `rhythm_z` | `(days_since_last - median_gap) / median_gap` |
| `submit_lag_days` | `submitted_at - bill_date` |
| `submit_lag_z` | vs. their own usual lag |
| `months_claiming` | tenure in this category |
| `bill_number_missing` | bool |

Category-specific vs. global approval rate — as a way to distinguish an individual's pattern from general behaviour.

### Guardrails — Inside the Scorer, Evaluated First

(Nothing but a threshold for this feature to work → assigning less weight.)

Hard caps, not weights. A -30 penalty could be outvoted by a strong pattern and auto-approve a duplicate. A cap cannot.

```python
def apply_guardrails(claim, profile) -> int | None:
    if profile.n_prior_approved < MIN_PRIOR:   return 0      # ineligible
    if profile.months_claiming  < MIN_TENURE:  return 0
    if duplicate_same_period(claim):           return 0
    if claimed_by_other_employee(claim):       return 0
    if profile.prior_rejection:                return CAP_REJECTED   # 40
    if claim.amount > ABS_CEILING:              return CAP_LARGE      # 40
    return None      # no override — proceed to scoring


def duplicate_same_period(claim) -> bool:
    return exists(bill_number == claim.bill_number
                  and bill_period == claim.bill_period)   # ← period, not just number
```

### Three Scorers

```python
def score(claim: Claim, profile: Profile) -> tuple[int, list[str]]
```

| Module | Band |
|---|---|
| `rule.py` | fixed ±20% of centre |
| `stddev.py` | scaled by their own MAD |
| `learned.py` | logistic regression |

```python
# rule.py --> pseudocode
in_band = abs(amount - centre) <= 0.20 * centre  # (certain amount in certain range)
score   = 90 if (n_prior >= 3 and in_band) else 30

# stddev.py
# ...

# learned.py --> pseudocode
model = CalibratedClassifierCV(
    LogisticRegression(random_state=42),
    method="isotonic",
)
```

Calibration makes the output a real probability: "70" means "70% of claims like this were approved unchanged" — which survives a model version bump. ~8 features, because every coefficient has to be explainable to a finance admin.

### Reasons — Templates → Need to Decide Accordingly

```python
TEMPLATES = {
  "n_prior_approved": "Approved {n} times before in {category}, always ₹{lo}–₹{hi}.",
  "amount_z":         "This claim is ₹{amt} — {k:.1f}× their usual variation.",
  "submit_lag_z":     "Submitted {d} days after the bill; they usually submit within {u}.",
}
```

Faithful by construction — same numbers, same weights that produced the score. A guardrail hit bypasses the templates and emits a fixed string: `"Duplicate: bill 4471 already claimed for June 2026."`

---

## 7. Evaluation

**We are not optimising for accuracy.**

A one-off hospital bill was approved — so a model scoring it 92 is accurate, and it's exactly the claim we don't want auto-approved. A more accurate model would be a worse product.

| Metric | Definition |
|---|---|
| Coverage | `n_auto_approved / n_manual_queue` |
| Leakage (count) | share of auto-approved claims a human would have rejected |
| Leakage (value) | same, weighted by rupee amount |
| Abstention | of claims with no precedent, share correctly left alone. High is good, and it costs accuracy on purpose. |

### Threshold Sweep

This table is the answer to "60 or 70?" — here's what each choice costs; pick your risk appetite.

Bootstrap CIs on leakage. If rejections are rare, a leakage figure rests on very few claims — and finance will treat a precise number as a promise.

- **Bootstrap** = A statistical technique where you repeatedly sample your data (with replacement) to estimate how stable your results are.
- **CI** = Confidence Interval, which gives a range instead of a single number.

### LightGBM — Coverage Ceiling

One question: how much more of the queue could a stronger model automate at the same leakage rate?

```python
LGBMClassifier(random_state=42, n_estimators=200)
# → CalibratedClassifierCV → same threshold sweep
```

Not necessarily needed.

---

## 8. LLM Comparison

> After all of the above is executed, then we can compare it with LLM.

Gemini, structured JSON, one claim per call. Prompt carries the claim plus that employee's history (the most a prompt can hold).

1. **Determinism** — 100 claims × 10 runs. Count score changes, report the spread. Run first; it's cheap.
2. **Calibration** — bucket its scores; were claims it scored 70 approved ~70% of the time?
3. **Corpus blindness** — seed the test set with duplicate-bill cases. A prompt holds one employee's history; it cannot hold 40,000 claims across the company. Failures should cluster here.
4. **Head-to-head** — same sweep, same table, one chart.

Report the numbers either way.

---

## 9. Demo

```
$ python score_claim.py --claim-id 5407
Score: 88  →  AUTO-APPROVE  (threshold 70, Food)
  • Approved 6 times before in Food, always ₹800–₹820.
  • This claim is ₹815 — 0.4× their usual variation.
  • Submitted 3 days after the bill; they usually submit within 4.

$ python score_claim.py --claim-id 5537
Score: 0   →  MANUAL REVIEW
  • Duplicate: bill 4471 already claimed for June 2026.
```

---

## 10. End-to-End Walkthrough (Input → Output)

*The full flow once the data arrives.*

### Stage 1 — Extraction

Train and Test split: 80-20 or 70-30 → depends on data.

**Input:** SQL/CSV extract from data (claims + workflow).
**Libraries:** pandas, pyarrow, ydata-profiling, matplotlib.
**Output:** one clean claims table + a data-quality report.

```python
load claims.csv and workflow.csv          # pandas.read_csv / read_parquet
cast types explicitly                      # bill_number → string, dates → datetime
join workflow → one label per claim        # see §3.2
ProfileReport(df).to_file(...)             # ydata-profiling → raw_profile.html
plot amount + claims-per-employee dists    # matplotlib
save → data/claims_clean.parquet
```

**Deliverables:**
- Category breakdown — which categories exist, volume each.
- What a "normal" employee looks like — median claims, median amount, typical rhythm. We need to experiment with all the types.

### Stage 2 — Profiles

**Input:** `claims_clean.parquet`.
**Libraries:** pandas, numpy.
**Output:** a Profile per (employee, category).
**Key idea:** the profile is a query, not a model — pure aggregation over that person's own past claims.

```python
for each (employee, category) group:            # pandas groupby
    approved = group[status == "Accepted"]
    centre   = median(approved.amount)          # numpy — robust to outliers
    spread   = max(MAD(approved.amount),         # MAD, not std
                   0.05 * centre)                # floor, avoids divide-by-zero
    cv       = spread / centre
    median_gap = median(diff(approved.submitted_at))
    → Profile(n_prior_approved, centre, spread, cv,
              median_gap, days_since_last,
              prior_rejection, months_claiming)
```

### Stage 3 — Feature Engineering

**Input:** each claim + its employee's profile.
**Libraries:** pandas, numpy.
**Output:** one feature row per claim.
**Note:** same pass as profiles — for each claim, look up the profile, compute the deltas.

```python
for each claim:
    p = profile[(claim.employee, claim.category)]
    amount_z      = (claim.amount - p.centre) / p.spread
    rhythm_z      = (p.days_since_last - p.median_gap) / p.median_gap
    submit_lag    = claim.submitted_at - claim.bill_date
    pct_of_limit  = claim.amount / policy_limit[claim.category]
    → feature_row(n_prior_approved, amount_z, cv,
                  pct_of_limit, rhythm_z, submit_lag, ...)
save → data/features.parquet
```

**Deliverables:**
- Discuss features + weights (this will be done once data is available).
- Final feature table.

### Stage 4 — Scoring

**Input:** feature table.
**Libraries:** scikit-learn (LogisticRegression, CalibratedClassifierCV).
**Output:** score 0–100 + reasons per claim.

```python
for each claim:
    cap = apply_guardrails(claim, profile)       # hard caps first
    if cap is not None:
        score = cap
    else:
        rule   → in_band check
        stddev → band scaled by cv
        learned→ CalibratedClassifierCV(LogReg)
        score  = round(P(approve) * 100)
    reasons = top-3 feature contributions
```

### Stage 5 — Evaluation

**Input:** scored test set (time-split from training).
**Libraries:** scikit-learn (metrics), matplotlib, numpy (bootstrap).
**Output:** the threshold table — the deliverable that answers "60 or 70?".

```python
for scorer in [rule, stddev, learned]:
  for category, for threshold 0..100:
      coverage, leakage_count, leakage_value
bootstrap CIs on leakage                         # numpy resampling
→ reports/threshold_table.csv + curves
```

### Later (Separate Tasks)

- **LLM benchmarking** — Gemini, once the above runs end-to-end.
- **Attachment reading** — Gemini bill extraction via S3 API. Enhancement only; test-env bills are mock data.

### Library Summary

| Stage | Libraries |
|---|---|
| Extraction | pandas, pyarrow, ydata-profiling, matplotlib |
| Profiles | pandas, numpy |
| Features | pandas, numpy |
| Scoring | scikit-learn |
| Evaluation | scikit-learn, matplotlib, numpy |
| LLM (later) | google-generativeai |

---

## 3. Stage 1 — Extraction & Preparation

### 3.1 Source

The SQL and data dictionary are provided. One row per claim item, definitive outcomes only, claims that went through ≥1 reviewer level.

### 3.2 The Label — Already on the Row

`item_status` is the item-level outcome. No collapse needed.

| Label | From | Meaning |
|---|---|---|
| Positive | `item_status ∈ {Accepted, Paid}` | approved (Paid is downstream of Accepted — same outcome) |
| Negative | `item_status = Rejected` | rejected |

Two refinements the schema forces:

- `auto_approved = TRUE` → the report bypassed human review by rule. These are precedent, not scoring targets. Keep them for building profiles; exclude them from the "needs a score" population.
- `override_count > 0` → a reviewer changed the amount before accepting. That is not a clean approval. Only clean approvals (`override_count = 0`) count toward precedent. *(I don't think we need to think about it.)*

**Casing trap** (from the dictionary): `item_status` is Title-case (`Accepted`); `report_status` is ALL-CAPS (`ACCEPTED`). Never reuse one filter list on both. We use `item_status`.

### 3.3 Load With Explicit Types

Never let pandas infer.

| Column | Cast | Why |
|---|---|---|
| `bill_number` | string | `int64` drops leading zeros → breaks any bill matching |
| `expense_category_code` | category | grouping key, low cardinality |
| `bill_date`, `submission_date`, `approval_date`, `rejection_date`, `last_overridden_at` | datetime, `errors="coerce"` | bad dates → `NaT`, counted not thrown |
| `employee_id` | int | selected twice in the SQL (item + report) → in the CSV export this surfaces as `employee_id-2`, confirmed identical to `employee_id`; dropped |
