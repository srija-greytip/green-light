# Synthetic Datasets Reference

Three CSVs in `data/synthetic/`

> **What these can and cannot show.** The rejection rates below are ones *I authored* — they validate that the pipeline and scorer behave correctly on known patterns. They are **not** evidence about real-world approval behaviour, and no threshold recommendation should ever be drawn from them.

> **Correction note.** An earlier version of this document's grain-finding section (§5) used a methodology that pooled claims across *all employees* rather than testing one employee's own profile — which isn't what the real scorer computes. That section has been rebuilt using the correct per-employee methodology. The finding survives, but is smaller and more specific than first stated. See §5 for the full account.

---

**Strict at MBU** — Highly conservative policy. Only claims that follow the employee's historical precedent are approved. Any deviation or unfamiliar claim is automatically rejected, making approvals rare and more meaningful indicators of "in-pattern" spending.

**Regular at SBU** — Balanced policy. Standard, in-pattern claims are approved routinely. Out-of-pattern claims are considered, sometimes rejected, or accepted after further review, reflecting realistic but attentive scrutiny from reviewers.

**Lenient at LBU** — Permissive policy. The majority of claims are approved with minimal regard for whether they match the claimant's history. Approvals are frequent, with little discrimination, so acceptance says little about the validity of a claim.

**Strict at LBU** — Conservative policy at the LBU level, mirroring the strict behavior at MBU. Only claims matching employee precedent are approved; any variation leads to rejection, ensuring approvals are strong signals of conformity.

**Regular at MBU** — Moderately attentive policy at MBU, similar to regular at SBU. In-pattern claims are approved smoothly, while unusual claims undergo genuine review and mixed outcomes, maintaining a careful but not severe approach.

**Lenient at SBU** — Highly permissive approach at SBU. Most claims are approved regardless of their alignment with claimant history, echoing the lenient pattern at LBU, with approvals having low informational value about claim sensibility.

**Regular at MBU, high volume** — Same policy and headcount tier as Regular MBU, but a deliberately dense stress case: 75 employees (above even LBU), a 5-year window instead of 18 months, and 7–12 active categories per employee instead of 3–5. Built to test the pipeline under much deeper per-employee history than any normal-sized company would realistically produce.

---

## 1. Shared structure

| | |
|---|---|
| **Columns** | **47** (exact match to the slimmed extraction query) |
| **Employees** | SBU 10 · MBU 25 · LBU 50 · **MBU-highvolume 75** |
| **Categories** | 6 |
| **Expense types** | 15 defined — see coverage note below |
| **Date range** | 2025-01-06 onward · 18 months (six datasets) / **5 years (highvolume)** |
| **Reviewer chains** | `Manager` · `Manager > Admin` · `Manager > Manager's Manager > Admin` |

**Type coverage is not guaranteed at small BU sizes.** With only 10 employees, random archetype assignment doesn't always touch every type: `regular_sbu` exercises 12 of 15 types, `lenient_sbu` 14 of 15. MBU, LBU, and the highvolume dataset reliably hit all 15.

---

## 2. Row-level totals

| Dataset | Employees | Rows | Accepted | Paid | Rejected | Reject rate | Auto-approved | Clean approvals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| strict_mbu | 25 | 1,159 | 502 | 375 | 282 | **24.3%** | 31 | 827 |
| regular_sbu | 10 | 520 | 244 | 224 | 52 | **10.0%** | 2 | 450 |
| lenient_lbu | 50 | 2,391 | 1,313 | 1,046 | 32 | **1.3%** | 32 | 2,306 |
| strict_lbu | 50 | 2,277 | 949 | 766 | 562 | **24.7%** | 48 | 1,634 |
| regular_mbu | 25 | 1,075 | 543 | 423 | 109 | **10.1%** | 12 | 930 |
| lenient_sbu | 10 | 465 | 276 | 184 | 5 | **1.1%** | 28 | 429 |
| **regular_mbu_highvolume** | **75** | **25,789** | 13,070 | 10,235 | 2,484 | **9.6%** | 417 | 22,099 |

*Clean approvals = approved, human-reviewed, amount not overridden — the only claims that count toward precedent.*

| Dataset | Duplicate flagged | Overridden | Blank `bill_number` | Mileage claims | Median amount | Max amount |
|---|---:|---:|---:|---:|---:|---:|
| strict_mbu | 5 | 19 | 348 (30%) | 138 | ₹533 | ₹54,105 |
| regular_sbu | 2 | 16 | 151 (29%) | 61 | ₹505 | ₹26,660 |
| lenient_lbu | 17 | 21 | 729 (30%) | 357 | ₹547 | ₹57,727 |
| strict_lbu | 18 | 33 | 645 (28%) | 329 | ₹546 | ₹70,008 |
| regular_mbu | 6 | 24 | 318 (30%) | 215 | ₹616 | ₹76,168 |
| lenient_sbu | 1 | 3 | 153 (33%) | 53 | ₹631 | ₹55,536 |
| **regular_mbu_highvolume** | **177** | **789** | **7,579 (29%)** | **4,152** | **₹632** | **₹173,646** |

**Auto-approve rate is not tightly controlled (0.4%–6.0%)** — thresholds are fixed per category but each dataset uses a different random seed, so how many per-employee centres happen to fall under threshold varies by chance. Documented and accepted as a known artifact: `auto_approved` is only ever used as an exclusion filter, never a computed feature, so this doesn't affect scorer evaluation. The highvolume dataset sits at 1.6% — consistent with the others.

The highvolume dataset's max amount (₹173,646) exceeds every other dataset's by 2–6×, purely because 75 employees × 5 years generates far more draws from the Hospitalisation tail (₹20,000–₹60,000 base range) — expected at this scale, not a defect.

---

## 3. Categories and types

| Code | Category | Types | Chain | Limit/claim |
|---|---|---:|---|---:|
| `MEAL` | Meals | 3 | Manager > Admin | ₹10,000 |
| `TRVL` | Travel | 3 | Manager > MM > Admin | ₹60,000 |
| `FUEL` | Fuel & Mileage | 2 | Manager > Admin | ₹8,000 |
| `INT` | Internet & Telecom | 2 | Manager | ₹3,000 |
| `LEARN` | Learning & Development | 3 | Manager > Admin | ₹30,000 |
| `MED` | Medical | 2 | Manager > MM > Admin | ₹100,000 |

### Rejection rate by category, all seven

| Category | strict_mbu | regular_sbu | lenient_lbu | strict_lbu | regular_mbu | lenient_sbu | highvolume |
|---|---:|---:|---:|---:|---:|---:|---:|
| FUEL | 29.0% | 9.8% | 2.0% | 25.5% | 10.7% | 3.8% | 8.8% |
| INT | 34.2% | 9.1% | 1.4% | 24.6% | 12.2% | 0.0% | 10.2% |
| LEARN | 26.9% | 12.5% | 1.2% | 27.0% | 18.9% | 0.0% | 11.7% |
| MEAL | 24.7% | 8.8% | 0.9% | 24.3% | 8.6% | 0.6% | 9.4% |
| MED | 22.6% | 12.5% | 3.3% | 34.1% | 8.5% | 0.0% | 11.8% |
| TRVL | 18.2% | 27.3% | 1.6% | 22.6% | 9.7% | 1.7% | 9.6% |

The highvolume dataset (regular policy, 75 employees) lands close to `regular_mbu`'s per-category rates, as expected — same policy function, just far more draws.

---

## 4. What differs between the datasets

Three variables now, not two: **policy** (how sharply rejection tracks deviation), **company size** (headcount), and — introduced by the highvolume run — **history depth per employee** (duration × active-category breadth), which can vary independently of headcount.

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
- **regular_mbu_highvolume** — same policy as `regular_mbu`, but tests whether the pipeline holds up under deep history: pairs with 100+ claims, employees active in nearly every category, and — as it turns out — the case that let us properly test the grain question (§5).

---

## 5. Eligibility and the grain finding (corrected)

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
| **highvolume** | **641** | **494 (77%)** | **393** | **344 (88%)** |

Eligibility rate holds in a tight 61–77% band across company sizes; the highvolume dataset's much deeper history pushes it to the top of that range, as expected.

### The grain finding — rebuilt on the correct methodology

**What was wrong before:** earlier versions of this test compared *company-wide, all-employees-pooled* type distributions against *company-wide, all-employees-pooled* category distributions. That's not what the scorer computes — `build_profiles()` groups by `(employee_id, category)`, strictly per person. The pooled version was measuring between-employee variance (different people have different centres), which inflated the apparent effect enormously and isn't a grain question at all.

**The corrected test:** for each employee with a genuinely mixed claiming history in a category (a dominant type plus at least one other, both with real depth), compute *their own* type-level profile and *their own* category-level profile (pooling only their own claims across types), then check whether a claim at 2× their personal type-normal is caught at type-level but hidden at category-level.

**Run across all seven datasets, 212 qualifying (employee, category) cases:**

| | |
|---|---|
| Cases where category-level fully masks the type-level anomaly | **32 of 212 (15.1%)** |
| Median spread inflation (category vs. type) | **1.16×** — mild in the typical case |
| Maximum spread inflation observed | **338×** — severe in the extreme case |

**The effect is not uniform — it depends almost entirely on how balanced an employee's claims are across types within the category:**

| Share of category claims in the *non-dominant* type | Average spread inflation |
|---|---:|
| ≤10% | 1.03× |
| 10–20% | 1.10× |
| 20–30% | 1.55× |
| 30–40% | 1.91× |
| 40–50% | 3.71× |
| >50% (no single type dominates) | **113.6×** |

**When one type clearly dominates an employee's category usage (>70% of their claims), masking is mild and often negligible** — this matches the earlier corrected Consultation/Hospitalisation check, which found only 1.0–1.8× inflation. **When an employee's usage is genuinely split between two types, masking can be severe, and in some cases inverts the sign of the anomaly entirely** (the probe claim looks *below* their category-normal, not just unremarkable).

### Two real examples, both from `regular_mbu_highvolume`

**Employee 1037, Fuel & Mileage — Two Wheeler (52 claims) / Four Wheeler (52 claims), a near-exact 50/50 split.**
Their own Two Wheeler normal is ₹668. A claim at ₹1,335 (2× normal) is a 20-sigma anomaly against their own Two Wheeler history — but their pooled Fuel profile (mixing in the much larger Four Wheeler amounts) has a centre of ₹1,399. The ₹1,335 probe lands almost exactly *on* that pooled centre: **z = -0.1. Completely invisible.**

**Employee 1002, Learning & Development — Books (13), Certification (10), Course Fee (8), roughly even three-way split.**
Their own Books normal is ₹715. A claim at ₹1,430 is a 20-sigma anomaly against their own Books history. Their pooled L&D profile — dragged upward by Certification and Course Fee, both far pricier — has a centre of ₹9,751. The probe now looks *below average* for the category: **z = -0.7.**

### Revised recommendation

`PROFILE_GRAIN = "type"` is still the right default, but on narrower grounds than first claimed: **the risk isn't universal, it's concentrated in the ~36% of employees whose category usage is genuinely mixed across types rather than dominated by one.** For that group, category-level pooling can hide a real, large deviation — occasionally inverting it. For the majority with a dominant type, grain choice barely matters. Given type-level costs almost nothing (a small reduction in eligible-pair count, per §5 above) and directly protects the mixed-usage minority, it remains the better default — just not because "grain always matters," because it doesn't for most employees.

---

## 6. Planted defects

`data/six_datasets/planted_{policy}_{bu}.json` lists the exact `item_id`s carrying each defect:

| Dataset | Duplicates | Overrides |
|---|---:|---:|
| strict_mbu | 5 | 19 |
| regular_sbu | 2 | 16 |
| lenient_lbu | 17 | 21 |
| strict_lbu | 18 | 33 |
| regular_mbu | 6 | 24 |
| lenient_sbu | 1 | 3 |
| **highvolume** | **177** | **789** |

Both scale roughly with row count, as expected — the highvolume dataset has ~24× the rows of `regular_mbu` and ~30× the duplicates, ~33× the overrides.

---

## 7. Known limitations

1. **Rejection rates are authored, not observed.** No calibration conclusion can come from these.
2. **Archetype labels are not in the CSV.** Generator-internal, so nothing can accidentally train on them. Re-derivable from `scripts/generate_six_datasets.py` for diagnosis.
3. **`MED` is thin at small BU sizes**, most severely at SBU. Deliberate — it's the rare one-off case — but too thin for per-category threshold tuning below MBU scale. The highvolume dataset largely fixes this (743 MED claims vs. 29 in the original `regular_mbu`).
4. **SBU doesn't guarantee full type coverage** (§1) — a real property of small companies, not a generation bug.
5. **Auto-approval rate is uncontrolled across datasets** (§2) — accepted as harmless since the column is exclusion-only, never a feature.
6. **Peer/role features remain impossible** — no role, grade, department or location exists in the source schema, so none is generated.
7. **The `z@type = 20.0` value recurring throughout §5 is not a coincidence** — it's the spread floor (`SPREAD_FLOOR_PCT = 0.05` in `config.py`) engaging for employees whose natural type-level spread is tighter than 5% of their centre. This is expected behaviour (it's what prevents divide-by-zero for very steady claimants), not an artifact of the grain test specifically — but worth knowing so the repeated exact value doesn't look like a bug when read out of context.