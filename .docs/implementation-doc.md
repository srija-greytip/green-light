# EC-1062 — Implementation Plan

## 1. Environment and Repo

| Item | Detail |
|---|---|
| Python | 3.11 |
| Env | venv + requirements.txt (Docker is also an option) |
| Notebooks | Jupyter Lab. Use for data exploration only. |
| Version control | Git |

### Libraries — and Where We Use Each One

| Library | Purpose | Section |
|---|---|---|
| pandas | Extraction, cleaning, profiling, feature building | §3, §4, §5 |
| numpy | np.where, percentiles, NaN handling | §4, §5 |
| ydata-profiling | One-line data-quality HTML report | §3.4 |
| matplotlib | Static plots for the report | §3.4, §7 |
| scikit-learn | LogisticRegression, CalibratedClassifierCV, metrics | §6, §7 |
| LightGBM | Coverage-ceiling benchmark | §7 |
| SHAP | LightGBM attributions | §7 |
| pytest | Tests. Leakage tests are the priority. | §5 |
| google-generativeai | Gemini, comparison arm | §8 |
| pyarrow | Parquet I/O between stages | §3 |

Each stage writes Parquet files to `data/`. We can re-run any stage without redoing the stage before it.

### Repo Structure

```
ec1062/
  data/          notebooks/     src/
  tests/         reports/       requirements.txt
```

`src/` holds importable, tested code. Notebooks import from `src/`. Notebooks must not redefine logic that lives in `src/`.

---

## 2. Pipeline

```
SQL extract → load & type → profile → clean → outlier policy
    → build profiles → featurise (point-in-time) → score → evaluate
```

---

## 3. Extraction and Cleaning

### 3.1 What We Pull

To be confirmed with Vinay Parida. We will update §3.2 and §3.3 later.

### 3.2 Collapsing Workflow Steps Into One Label

A claim has many workflow rows. We need one outcome per claim.

Rejection ends the chain. Approved means every level agreed. Rejected means the first reviewer who objected said no. We model this first objection, not the full chain.

### 3.3 Load With Explicit Types

Do not let pandas guess column types.

- If pandas infers `bill_number` as `int64`, it drops leading zeros. This breaks duplicate detection. We load `bill_number` as a string instead.
- We parse dates with `errors="coerce"`. This turns a bad date into `NaT` instead of stopping the program. We then count how many dates failed, instead of finding out later.

### 3.4 Profile the Raw Data

```python
from ydata_profiling import ProfileReport
ProfileReport(df, minimal=True).to_file("reports/raw_profile.html")
```

We look at the data before we change it.

**What we check, and the cost of a bad result:**

| Check | Cost if the result is bad |
|---|---|
| `bill_number` null rate | Duplicate detection stops working |
| `bill_date` null rate | The `submit_lag` feature stops working |
| Category cardinality | Free-text categories block per-category thresholds |
| Amount distribution | May reveal currency or unit mismatches |
| Claims per employee | If most employees have under 3 claims, almost nothing is eligible to score |

We list every candidate feature and its weight.

---

## 4. Outliers — Why We Do Not Remove Them

An outlier can be a low-weight feature. We do not drop outliers.

Standard exploratory analysis removes outliers. Here, that removal would destroy the feature we need. An unusual claim is exactly the signal we want to detect. A ₹9,000 food claim from someone who always claims ₹800 is not noise. It is the signal.

**Rule: we never remove outliers from the dataset.**

### Outliers Must Not Damage the Profile

There is a real risk here. Take an employee, Ravi, with claim history `[800, 800, 820, 9000, 800]`.

```
mean = 2,244    std = 3,668
```

This profile is now wrong. Every future claim looks normal against a mean of ₹2,244 and a spread of ₹3,668. One unusual claim breaks Ravi's tolerance band for good.

### Our Policy Has Two Separate Rules

| Situation | Rule |
|---|---|
| The claim we are scoring right now | We never clip it and never drop it. We score it as it is. |
| A claim's contribution to the profile statistics | We use robust statistics. One extreme value must not distort the result. |

We use median and MAD (median absolute deviation) instead of mean and standard deviation. One ₹9,000 claim barely moves the median or the MAD. Ravi's band stays tight, which is correct. His next ₹850 claim still scores well.

**We use outlier counts for the report only.** We use them to answer "how common are unusual claims?" in the exploration report. We never use them to filter data.

### Tests

- `test_future_claims_do_not_affect_past_features`. If this test fails, every number in the report is wrong. This test runs on every commit.
- **Split:** We train on months 1 to N. We test on month N+1 onward.

---

## 6. Profiles, Features, Scorers

### Profile — We Can Add More Fields Later

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

`cv` is the most important feature in the profile. It tells the difference between Ravi, who always claims ₹800, and Priya, whose claims range from ₹600 to ₹1,400. `cv` lets the tolerance band adjust for each person.

### Feature Vector — Still to Be Decided

| Feature | Definition |
|---|---|
| `n_prior_approved` | from the profile |
| `amount_z` | `(amount - centre) / spread` |
| `cv` | from the profile |
| `pct_of_policy_limit` | `amount / policy_limit` |
| `rhythm_z` | `(days_since_last - median_gap) / median_gap` |
| `submit_lag_days` | `submitted_at - bill_date` |
| `submit_lag_z` | deviation from the employee's own usual lag |
| `months_claiming` | tenure in this category |
| `bill_number_missing` | boolean |

We can also compare the category-specific approval rate against the global approval rate. This helps us tell an individual's normal pattern apart from general company behaviour.

### Guardrails — Inside the Scorer, Checked First

A guardrail is a threshold. It does not use weights.

A weighted penalty can be outvoted. A -30 point penalty can still lose to a strong pattern and let a duplicate claim through. A guardrail is a hard cap. It cannot be outvoted.

```python
def apply_guardrails(claim, profile) -> int | None:
    if profile.n_prior_approved < MIN_PRIOR:   return 0      # not eligible
    if profile.months_claiming  < MIN_TENURE:  return 0
    if duplicate_same_period(claim):           return 0
    if claimed_by_other_employee(claim):       return 0
    if profile.prior_rejection:                return CAP_REJECTED   # 40
    if claim.amount > ABS_CEILING:              return CAP_LARGE      # 40
    return None      # no guardrail applies — send to the scorer


def duplicate_same_period(claim) -> bool:
    return exists(bill_number == claim.bill_number
                  and bill_period == claim.bill_period)   # period, not just the number
```

### Three Scorers

```python
def score(claim: Claim, profile: Profile) -> tuple[int, list[str]]
```

| Module | Band |
|---|---|
| `rule.py` | fixed band, ±20% of the centre |
| `stddev.py` | band scaled by the employee's own MAD |
| `learned.py` | logistic regression |

```python
# rule.py --> pseudocode
in_band = abs(amount - centre) <= 0.20 * centre  # amount falls in a fixed range
score   = 90 if (n_prior >= 3 and in_band) else 30

# stddev.py
# ...

# learned.py --> pseudocode
model = CalibratedClassifierCV(
    LogisticRegression(random_state=42),
    method="isotonic",
)
```

Calibration turns the output into a real probability. A score of 70 means: 70% of similar past claims were approved without change. This meaning stays stable even when we update the model. We keep the feature count near 8. Every coefficient must be explainable to a finance admin.

### Reasons — Template Text, Still to Be Finalised

```python
TEMPLATES = {
  "n_prior_approved": "Approved {n} times before in {category}, always ₹{lo}–₹{hi}.",
  "amount_z":         "This claim is ₹{amt} — {k:.1f}× their usual variation.",
  "submit_lag_z":     "Submitted {d} days after the bill; they usually submit within {u}.",
}
```

Each reason comes directly from the numbers and weights that produced the score. A guardrail hit skips the templates. It shows a fixed message instead: `"Duplicate: bill 4471 already claimed for June 2026."`

---

## 7. Evaluation

**We do not optimise for accuracy.**

A hospital bill was approved once. A model that scores it 92 is accurate — but this is exactly the claim we do not want auto-approved. A more accurate model here would be a worse product.

| Metric | Definition |
|---|---|
| Coverage | `n_auto_approved / n_manual_queue` |
| Leakage (count) | share of auto-approved claims a human would have rejected |
| Leakage (value) | same measure, weighted by rupee amount |
| Abstention | of claims with no prior history, the share we correctly leave alone. A high value is good here, even though it costs accuracy. |

### Threshold Sweep

This table answers the question "60 or 70?". It shows the cost of each choice, so the team can pick the risk level it wants.

We compute bootstrap confidence intervals on leakage. If rejections are rare, a leakage number rests on very few claims. Finance may read a precise number as a promise. A confidence interval shows the real uncertainty.

- **Bootstrap:** a method that resamples the data, with replacement, many times, to show how stable a result is.
- **CI (Confidence Interval):** a range of values, instead of one single number.

### LightGBM — Coverage Ceiling

This answers one question: how much more of the queue could a stronger model handle, at the same leakage rate?

```python
LGBMClassifier(random_state=42, n_estimators=200)
# → CalibratedClassifierCV → same threshold sweep
```

This step is not required.

---

## 8. LLM Comparison

Run this after every step above is complete and working.

We use Gemini. We request structured JSON output. We send one claim per call. The prompt carries the claim plus that employee's history — as much history as fits in the prompt.

1. **Determinism.** Run 100 claims through the model, 10 times each. Count how many scores change. This test is cheap. Run it first.
2. **Calibration.** Group the model's scores into buckets. Check: were claims scored near 70 actually approved about 70% of the time?
3. **Corpus blindness.** Add duplicate-bill cases to the test set. A prompt holds one employee's history. It cannot hold 40,000 claims across the company. We expect failures to cluster here.
4. **Head-to-head.** Run the same threshold sweep. Build the same table and chart as the other scorers.

We report the numbers either way, even if they do not support our expectation.

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

## 10. End-to-End Walkthrough (Input to Output)

*This shows the full flow once the data arrives.*

### Stage 1 — Extraction

Train and test split: 80-20 or 70-30. The right split depends on data volume.

**Input:** SQL or CSV extract (claims plus workflow data).
**Libraries:** pandas, pyarrow, ydata-profiling, matplotlib.
**Output:** one clean claims table, plus a data-quality report.

```python
load claims.csv and workflow.csv          # pandas.read_csv / read_parquet
cast types explicitly                      # bill_number → string, dates → datetime
join workflow → one label per claim        # see §3.2
ProfileReport(df).to_file(...)             # ydata-profiling → raw_profile.html
plot amount + claims-per-employee dists    # matplotlib
save → data/claims_clean.parquet
```

**Deliverables:**
- A category breakdown: which categories exist, and the claim volume in each.
- A description of a normal employee: median claims, median amount, typical rhythm. We test this across every category.

### Stage 2 — Profiles

**Input:** `claims_clean.parquet`.
**Libraries:** pandas, numpy.
**Output:** one Profile per (employee, category) pair.
**Key idea:** a profile is a query result, not a model. It is a plain aggregation of that person's own past claims.

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

**Input:** each claim, joined to its employee's profile.
**Libraries:** pandas, numpy.
**Output:** one feature row per claim.
**Note:** this runs in the same pass as profile building. For each claim, we look up the profile and compute the deltas.

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
- A discussion of the features and their weights. We do this once the data is available.
- The final feature table.

### Stage 4 — Scoring

**Input:** the feature table.
**Libraries:** scikit-learn (LogisticRegression, CalibratedClassifierCV).
**Output:** a score from 0 to 100, plus reasons, for each claim.

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

**Input:** the scored test set, split by time from the training set.
**Libraries:** scikit-learn (metrics), matplotlib, numpy (bootstrap).
**Output:** the threshold table. This table answers "60 or 70?".

```python
for scorer in [rule, stddev, learned]:
  for category, for threshold 0..100:
      coverage, leakage_count, leakage_value
bootstrap CIs on leakage                         # numpy resampling
→ reports/threshold_table.csv + curves
```

### Later — Separate Tasks

- **LLM benchmarking.** We use Gemini, once the stages above run end-to-end.
- **Attachment reading.** Gemini reads bills through an S3 API. This is an enhancement only. Test-environment bills are mock data, not real bills.

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

## ACTUAL IMPLEMENTATION

All work below uses seven synthetic datasets.

6 datasets form a grid. Three approval strictness levels — strict, regular, lenient — cross with three company sizes: SBU (10 employees), MBU (25 employees), LBU (50 employees).

The seventh dataset, `regular_mbu_highvolume`, is a stress test. It has 25 employees, an 18-month history like the other six, but a higher claim volume per employee. This tests the pipeline under much deeper per-employee history than a normal-sized company produces.

All seven datasets share one 45-column schema. This schema matches the real extraction query and data dictionary, with two changes: it removes `expense_category_name` and `expense_type_name`, and it adds `expense_type_id`.

### Stage 1 — Extraction and Preparation

#### 1.1 Source

SQL query and the data dictionary. The grain is one row per claim item. Every row has a final outcome. Every claim passed through at least one reviewer level.

#### 1.2 The Label — Already Present on Each Row

`item_status` gives the outcome for each item. We do not need to collapse multiple rows into one label.

| Label | Source | Meaning |
|---|---|---|
| Positive | `item_status ∈ {Accepted, Paid}` | approved. `Paid` always follows `Accepted`. We treat them as the same outcome. |
| Negative | `item_status = Rejected` | rejected |

The schema forces two refinements:

- `auto_approved = TRUE` means the system approved the report by rule, with no human reviewer. These claims count as history for the profile. They do not count as a scoring target, because no reviewer judged them.
- `override_count > 0` means a reviewer changed the amount before accepting the claim. This is not a clean approval. Only claims with `override_count = 0` count toward the employee's history.

**Casing trap.** The data dictionary flags this directly. `item_status` uses title case, for example `Accepted`. `report_status` uses all capitals, for example `ACCEPTED`. We must not apply one filter list to both columns. We use `item_status` throughout.

#### 1.3 Load With Explicit Types

| Column | Cast | Reason |
|---|---|---|
| `bill_number` | string | If pandas infers `int64`, it drops leading zeros. This breaks bill matching. |
| `expense_category_code` | category | This is a grouping key with low cardinality. |
| `bill_date`, `submission_date`, `approval_date`, `rejection_date`, `item_created_on`, `item_updated_on` | datetime, `errors="coerce"` | A bad date becomes `NaT` instead of stopping the program. We then count how many dates failed. |
| `expense_type_id` | integer (Int64) | This is the new type identifier. It replaces the removed `expense_type_name` column. |


#### 1.4 Derived Fields

We compute five extra fields once per dataset, beyond the label:

```python
df["submit_lag_days"] = (df["submission_date"] - df["bill_date"]).dt.days
df["bill_period"] = df["bill_date"].dt.to_period("M")
df["is_mileage"] = df["mileage_quantity"].notna()
df["is_clean_approval"] = (
    df["is_approved"]
    & (df["auto_approved"] != True)
    & (df["override_count"].fillna(0) == 0)
)
```

We also add `is_rejected` as an explicit column, alongside `is_approved`. We do not leave rejection as an implied opposite of approval. We add one check:

```python
assert (df["is_approved"] | df["is_rejected"]).all(), \
    "found item_status values outside {Accepted, Paid, Rejected}"
```

This check confirms that every row has one of the three expected outcomes. If the check fails, an unexpected value has entered the data, and we must find it before we trust any label downstream.

#### 1.5 Structural Checks

We added two checks once the seven-dataset structure existed. The original plan did not include them.

**Multi-item report safety.** For every dataset, we check whether any report contains items with different outcomes — some accepted, some rejected, inside the same report. We confirmed this is real across all seven datasets. Each dataset has 90 to 120 or more reports with mixed outcomes. This confirms that per-item labelling is safe. A rejection on one item does not spread to the other items in the same report.

**Eligibility at two grains, side by side.** We compute eligible pairs at the type level and at the category level, in the same check. We do not compute the category level alone, because our profile grain is `type`, not `category`. Reporting only the category number would validate the wrong grain.

```python
pairs_type = clean.groupby(
    ["employee_id", "expense_category_code", "expense_type_id"], observed=True
).size()
pairs_cat = clean.groupby(
    ["employee_id", "expense_category_code"], observed=True
).size()
```

We do not rebuild a category-name or type-name lookup table for these reports. The current schema removes both name columns to keep the data free of names. Reports show the code and the numeric type ID only.

#### 1.6 Data Profiling — `ydata-profiling`

We run this step after casting (§3.3) and after adding the derived fields (§1.4). This way, the report covers the complete data, not the raw strings.

```python
from ydata_profiling import ProfileReport

profile = ProfileReport(
    combined, minimal=True,
    title="EC-1062 Synthetic Claims — All Seven Datasets"
)
profile.to_file("reports/synthetic_all_seven_profile.html")
```

We produce one combined report, tagged by dataset, plus one dedicated report for `regular_mbu_highvolume`, given its size:

```python
ProfileReport(FINAL["regular_mbu_highvolume"], minimal=True,
              title="regular_mbu_highvolume").to_file(
    "reports/regular_mbu_highvolume_profile.html")
```

**What this step does, and what it does not do.** `ydata-profiling` builds a browsable HTML report: null rates, cardinality, distribution shapes, and per-column summaries. A person uses this report to catch an obvious problem — a column that is mostly empty, or a category with unexpected dominance — before we build anything on top of the data.

This report is not the source of any specific finding in this project. Every number reported elsewhere — the eligibility rates in §3.5, the mixed-outcome report counts, the grain-masking analysis — comes from targeted pandas code, written to answer one specific question. None of it comes from reading values out of the profiling report. The profiling report gives a fast, general first look. It does not replace the targeted checks, and we did not use it to produce them.

#### 1.7 Save

We cast, derive, check, and profile each of the seven datasets. We then save each one to its own Parquet file:

```
data/interim/claims_strict_mbu_typed.parquet
data/interim/claims_regular_sbu_typed.parquet
...
data/interim/claims_regular_mbu_highvolume_typed.parquet
```

**We never merge these into one file.** `employee_id` restarts at 1000 in every dataset. Each dataset represents a separate synthetic company. We build one combined, tagged frame, but only for cross-dataset comparison and for the single profiling report above. We never use this combined frame as input to any grouping or profile logic, because `employee_id` alone is not a unique key across it.

#### Stage 2 — Profile Building

We built and ran the profile-building code, `src/profiles.py`, against all seven datasets. We verified the output.

**Profile grain is fixed at `type`.** The config setting `PROFILE_GRAIN` must always read `"type"`. It must never read `"category"`. A category groups several expense types together, and those types can have very different typical amounts. Grouping at the category level can hide a real deviation behind a larger, unrelated type in the same category. We tested this directly and confirmed the effect. See the grain finding in the dataset reference document for the full evidence.

**Profiles save to one file per dataset,** in `data/interim/profiles/`, following the same rule as §3.7. We never merge profiles across datasets.

Each profile row holds:

- `n_prior_approved` — a count, taken only from clean approvals for this exact employee, category, and type.
- `centre`, `spread`, `cv` — computed with median and MAD, per §4 above.
- `median_gap_days` — the employee's usual rhythm for this type.
- `months_claiming` — tenure in this type.
- `prior_rejection` — a boolean. This checks the employee's full history, including rejected claims, not just the clean approvals used for the other statistics.

`MIN_PRIOR_APPROVALS = 3` applies at the same grain as the profile: one employee, one category, one type. A claim in a new type does not benefit from the employee's history in a different type, even inside the same category.