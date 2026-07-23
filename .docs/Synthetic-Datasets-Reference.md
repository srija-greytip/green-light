# Synthetic Datasets Reference

7 CSVs in `data/raw/`

---

**Strict at MBU** — Highly conservative policy. Only claims that follow the employee's historical precedent are approved. Any deviation or unfamiliar claim is automatically rejected, making approvals rare and more meaningful indicators of "in-pattern" spending.

**Regular at SBU** — Balanced policy. Standard, in-pattern claims are approved routinely. Out-of-pattern claims are considered, sometimes rejected, or accepted after further review, reflecting realistic but attentive scrutiny from reviewers.

**Lenient at LBU** — Permissive policy. The majority of claims are approved with minimal regard for whether they match the claimant's history. Approvals are frequent, with little discrimination, so acceptance says little about the validity of a claim.

**Strict at LBU** — Conservative policy at the LBU level, mirroring the strict behavior at MBU. Only claims matching employee precedent are approved; any variation leads to rejection, ensuring approvals are strong signals of conformity.

**Regular at MBU** — Moderately attentive policy at MBU, similar to regular at SBU. In-pattern claims are approved smoothly, while unusual claims undergo genuine review and mixed outcomes, maintaining a careful but not severe approach.

**Lenient at SBU** — Highly permissive approach at SBU. Most claims are approved regardless of their alignment with claimant history, echoing the lenient pattern at LBU, with approvals having low informational value about claim sensibility.

**Regular at MBU, high volume** —  This dataset uses the same policy and headcount tier as the Regular MBU dataset and spans the same 18-month time window as all the other datasets. The increased volume comes entirely from employee behavior, not from a longer timeline. Employees are active across 7–12 expense categories/types instead of 3–5, and they submit claims at approximately twice the frequency. Policy limits are also 2.25× higher than the standard, reflecting a more generous reimbursement policy. This dataset is designed to test the pipeline with significantly richer per-employee historical data while keeping the timeline constant, ensuring that the comparison isolates the effect of higher claim volume rather than longer observation periods.

## 1. Shared structure

| | |
|---|---|
| **Columns** | **45** — down from an earlier 47-column version. `expense_type_name` and `expense_category_name` were removed; `expense_type_id` was added in their place, and a duplicate `employee_id` column present in an earlier export no longer exists. |
| **Employees** | SBU 10 · MBU 25 · LBU 50 · **MBU-highvolume 25** |
| **Categories** | 6 |
| **Expense types** | 15 defined, identified by `expense_type_id` only — see the type table below |
| **Date range** | 2025-01-06 onward · **18 months, identical across all seven** |
| **Reviewer chains** | `Manager` · `Manager > Admin` · `Manager > Manager's Manager > Admin` |

**Type names are not in the data.** The table below is maintained only in the generator script (`scripts/generate_six_datasets.py`, the `TYPE_ID` mapping) for human reference. The CSVs themselves carry only the numeric ID.

| ID | Type | ID | Type | ID | Type |
|---|---|---|---|---|---|
| 1 | Broadband | 6 | Local Cab | 11 | Books |
| 2 | Mobile Postpaid | 7 | Hotel | 12 | Certification |
| 3 | Daily Meal | 8 | Airfare | 13 | Course Fee |
| 4 | Client Lunch | 9 | Two Wheeler | 14 | Consultation |
| 5 | Team Dinner | 10 | Four Wheeler | 15 | Hospitalisation |

**Type coverage is not guaranteed at small BU sizes.** With only 10 employees, random archetype assignment doesn't always touch every type: `regular_sbu` exercises 12 of 15, `lenient_sbu` 14 of 15. MBU, LBU, and the highvolume dataset reliably hit all 15.

---

## 2. Row-level totals

| Dataset | Employees | Rows | Reject rate | Auto-approved | Clean approvals |
|---|---:|---:|---:|---:|---:|
| strict_mbu | 25 | 1,159 | **24.3%** | 31 | 827 |
| regular_sbu | 10 | 520 | **10.0%** | 2 | 450 |
| lenient_lbu | 50 | 2,391 | **1.3%** | 32 | 2,306 |
| strict_lbu | 50 | 2,277 | **24.7%** | 48 | 1,634 |
| regular_mbu | 25 | 1,075 | **10.1%** | 12 | 930 |
| lenient_sbu | 10 | 465 | **1.1%** | 28 | 429 |
| **regular_mbu_highvolume** | **25** | **5,130** | **10.0%** | **179** | **4,296** |

*Clean approvals = approved, human-reviewed, amount not overridden — the only claims that count toward precedent.*

| Dataset | Duplicate flagged | Overridden | Blank `bill_number` | Mileage claims | Median amount | Max amount |
|---|---:|---:|---:|---:|---:|---:|
| strict_mbu | 5 | 19 | 348 (30%) | 138 | ₹533 | ₹54,105 |
| regular_sbu | 2 | 16 | 151 (29%) | 61 | ₹505 | ₹26,660 |
| lenient_lbu | 17 | 21 | 729 (30%) | 357 | ₹547 | ₹57,727 |
| strict_lbu | 18 | 33 | 645 (28%) | 329 | ₹546 | ₹70,008 |
| regular_mbu | 6 | 24 | 318 (30%) | 215 | ₹616 | ₹76,168 |
| lenient_sbu | 1 | 3 | 153 (33%) | 53 | ₹631 | ₹55,536 |
| **regular_mbu_highvolume** | **26** | **143** | **1,552 (30%)** | **891** | **₹495** | **₹79,393** |

Reject rate matches `regular_mbu` almost exactly (10.0% vs 10.1%) — same policy function, same behaviour, confirming volume alone didn't change the underlying decision logic. Max amount (₹79,393) is higher than the standard dataset's (₹76,168) mainly because 25 employees claiming far more often draws more often from the Hospitalisation tail — expected, not a defect.

**Auto-approve rate is still not tightly controlled** — thresholds are fixed per category but each dataset uses a different random seed. `auto_approved` remains exclusion-only, never a feature, so this doesn't affect scorer evaluation.

---

## 3. Categories and types

| Code | Category | Types | Chain | Limit/claim (standard) | Limit/claim (highvolume, 2.25×) |
|---|---|---:|---|---:|---:|
| `MEAL` | Meals | 3 | Manager > Admin | ₹10,000 | ₹22,500 |
| `TRVL` | Travel | 3 | Manager > MM > Admin | ₹60,000 | ₹135,000 |
| `FUEL` | Fuel & Mileage | 2 | Manager > Admin | ₹8,000 | ₹18,000 |
| `INT` | Internet & Telecom | 2 | Manager | ₹3,000 | ₹6,750 |
| `LEARN` | Learning & Development | 3 | Manager > Admin | ₹30,000 | ₹67,500 |
| `MED` | Medical | 2 | Manager > MM > Admin | ₹100,000 | ₹225,000 |

*The highvolume column applies only to `regular_mbu_highvolume`. The other six use the standard limit.*

### Rejection rate by category, all seven

| Category | strict_mbu | regular_sbu | lenient_lbu | strict_lbu | regular_mbu | lenient_sbu | highvolume |
|---|---:|---:|---:|---:|---:|---:|---:|
| FUEL | 29.0% | 9.8% | 2.0% | 25.5% | 10.7% | 3.8% | 7.6% |
| INT | 34.2% | 9.1% | 1.4% | 24.6% | 12.2% | 0.0% | 10.4% |
| LEARN | 26.9% | 12.5% | 1.2% | 27.0% | 18.9% | 0.0% | 11.0% |
| MEAL | 24.7% | 8.8% | 0.9% | 24.3% | 8.6% | 0.6% | 10.0% |
| MED | 22.6% | 12.5% | 3.3% | 34.1% | 8.5% | 0.0% | 12.9% |
| TRVL | 18.2% | 27.3% | 1.6% | 22.6% | 9.7% | 1.7% | 11.1% |

Highvolume tracks `regular_mbu` closely in every category, as expected for a same-policy comparison at higher density.

---

## 4. What differs between the datasets

Two variables: **policy** (how sharply rejection tracks deviation) and **company profile** (headcount, and — for highvolume only — claim density per employee, achieved through frequency and category breadth, not duration).

```
P(reject) = base + slope × deviation^exponent
```

| Policy | base | slope | exponent | Effect |
|---|---:|---:|---:|---|
| **lenient** | 0.004 | 0.13 | 3.0 | near-flat — deviation barely matters |
| **regular** | 0.020 | 0.62 | 1.9 | moderate |
| **strict** | 0.030 | 0.95 | 1.25 | steep — even mild deviation is punished |

### What each is for

- **strict_mbu / strict_lbu** — deviation strongly predicts rejection at two company sizes.
- **regular_sbu / regular_mbu** — the realistic middle, at two scales.
- **lenient_lbu / lenient_sbu** — negative controls. The scorer **should be unable to discriminate**; if it appears to, that's a bug or a leak.
- **regular_mbu_highvolume** — same policy and headcount as `regular_mbu`, but far denser per-employee history. Isolates the effect of claim volume from the effect of company size — a question the original six couldn't answer on their own.

---

## 5. Eligibility and the grain finding

### Eligibility

Pairs with ≥3 clean approvals (the `MIN_PRIOR_APPROVALS` gate — tunable, not fixed):

| Dataset | Type-level pairs | Eligible | Category-level pairs | Eligible |
|---|---:|---:|---:|---:|
| strict_mbu | 87 | 56 (64%) | 70 | 52 (74%) |
| regular_sbu | 39 | 28 (72%) | 30 | 21 (70%) |
| lenient_lbu | 192 | 124 (65%) | 160 | 113 (71%) |
| strict_lbu | 162 | 104 (64%) | 134 | 98 (73%) |
| regular_mbu | 96 | 65 (68%) | 82 | 61 (74%) |
| lenient_sbu | 38 | 23 (61%) | 30 | 21 (70%) |
| **highvolume** | **194** | **156 (80%)** | **129** | **116 (90%)** |

Highvolume's density pushes eligibility to the top of the range, as expected — same 25 employees as `regular_mbu`, but far more history per pair.

### The grain finding

**Correct methodology:** for each employee with a genuinely mixed claiming history in a category (a dominant type plus at least one other, both with real depth), compute *their own* type-level profile and *their own* category-level profile, then check whether a claim at 2× their personal type-normal is caught at type-level but hidden at category-level. This is **per-employee**, matching exactly what `build_profiles()` computes — not a company-wide pooled comparison, which was an earlier, incorrect version of this test.

**Across 212 qualifying (employee, category) cases, all seven datasets:**

| | |
|---|---|
| Cases where category-level fully masks the type-level anomaly | **32 of 212 (15.1%)** |
| Median spread inflation (category vs. type) | **1.16×** — mild in the typical case |
| Maximum spread inflation observed | **338×** — severe in the extreme case |

**Severity depends almost entirely on how balanced an employee's claims are across types:**

| Share of category claims in the *non-dominant* type | Average spread inflation |
|---|---:|
| ≤10% | 1.03× |
| 10–20% | 1.10× |
| 20–30% | 1.55× |
| 30–40% | 1.91× |
| 40–50% | 3.71× |
| >50% (no single type dominates) | **113.6×** |

Two real examples, both from `regular_mbu_highvolume`:

**Employee 1037, Fuel & Mileage — Two Wheeler / Four Wheeler, near-exact 50/50 split.** A claim at 2× their own Two Wheeler normal is a 20-sigma anomaly against their own history — and lands at **z = -0.1** against their pooled Fuel profile. Completely invisible.

**Employee 1002, Learning & Development — Books / Certification / Course Fee, roughly even split.** Same 20-sigma anomaly against their Books history comes out at **z = -0.7** pooled — the anomaly inverts, looking *below* their category normal rather than merely unremarkable.

### Recommendation — now fixed, not just default

`PROFILE_GRAIN` is set permanently to `"type"`. This is no longer a tunable default under review — mixed-usage employees (roughly a third of those tested) are the ones this protects, and the cost of type-level grain (a modest reduction in eligible-pair count) is worth paying unconditionally.

---

## 6. Planted defects

`data/raw/planted_{name}.json` lists the exact `item_id`s carrying each defect:

| Dataset | Duplicates | Overrides |
|---|---:|---:|
| strict_mbu | 5 | 19 |
| regular_sbu | 2 | 16 |
| lenient_lbu | 17 | 21 |
| strict_lbu | 18 | 33 |
| regular_mbu | 6 | 24 |
| lenient_sbu | 1 | 3 |
| **highvolume** | **26** | **143** |

Both scale with row count relative to `regular_mbu`, as expected for a same-policy, same-headcount comparison at higher density.

---

## 7. Known limitations

1. **Rejection rates are authored, not observed.** No calibration conclusion can come from these.
2. **Archetype labels are not in the CSV.** Generator-internal, so nothing can accidentally train on them. Re-derivable from `scripts/generate_six_datasets.py` for diagnosis.
3. **`MED` is thin at small BU sizes**, most severely at SBU. Deliberate — it's the rare one-off case — but too thin for per-category threshold tuning below MBU scale. The highvolume dataset improves this materially (124 MED claims vs. 47 in standard `regular_mbu`), though less dramatically than the earlier 5-year version did.
4. **SBU doesn't guarantee full type coverage** (§1) — a real property of small companies, not a generation bug.
5. **Auto-approval rate is uncontrolled across datasets** (§2) — accepted as harmless since the column is exclusion-only, never a feature.
6. **Peer/role features remain impossible** — no role, grade, department or location exists in the source schema, so none is generated.
7. **Type names exist only in the generator script**, not in any dataset. Any report or table that shows a type by name (including this document) is using the fixed lookup in §1 — the same mapping across all seven files, but not something computable from the CSVs themselves.
