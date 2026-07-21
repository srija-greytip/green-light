# **Synthetic Data Generation Strategy**

**Status:** for review. **Format:** flat CSVs matching the extraction query's 80 columns exactly. Drop-in replacement for `data/raw/expense_claims.csv`

---

## **0\. What synthetic data can and cannot prove**

Stating this up front because it bounds every claim we can make from these datasets.

**Cannot:** produce a threshold table for finance. We author the ground truth, so any leakage figure only measures how well the scorer recovers rules we wrote. Circular by construction.

**Can:** prove the pipeline runs end to end; prove the scorer behaves correctly on *known* archetypes (does an erratic claimant's band actually widen? does a drifter get caught?); prove guardrails fire on planted duplicates and cold starts.

That's **mechanism testing** — it needs coverage of cases, not statistical power. Sizing follows from that.

---

## **1\. Sizing**

|  | Per dataset |
| ----- | ----- |
| Employees | 25 |
| Categories | 6 (≈2 expense types each) |
| Duration | 18 months |
| Active categories per employee | 2–3 |
| **Expected claim items** | **\~1,200–1,500** |

**Why 25 and not 5:** at 5 employees you get \~10 (employee, category) pairs and each archetype appears once. If the drifter case misbehaves you can't tell whether it's the archetype or that one generated employee. At 25 you get 4–5 pairs per archetype, so a failure is visibly a *pattern* failure.

**Why not 200:** past \~30 employees you add rows without adding cases, and lose the ability to eyeball the file when something looks wrong.

**Plus a fixture set:** 3 employees, 2 categories, \~30 claims, hand-verifiable. For `pytest` — unit tests shouldn't load 1,500 rows.

---

## **2\. Categories and types**

**Schema confirms a two-level hierarchy** — `expense_category (1) ──< expense_type (many) ──< expense_report_item (many)`, via `eri.expense_type_id → et.id` and `et.expense_category_id → ec.id`. Verified three ways: the SQL joins, the dictionary (*"Client Lunch" under "Meals"*), and the real export (`LEARN` contained both `Certificates` and `Books v2`; `DM` contained `Mobile/wifi`, `petrol`, and `Food`).

**This makes profile grain an open question, not a settled one** — see §8.

Categories chosen so that some are deliberately homogeneous and some deliberately not, which is what lets us measure the grain decision rather than assume it.

| Code | Category | Types | Amount range | Grain sensitivity |
| ----- | ----- | ----- | ----- | ----- |
| `INT` | Internet & Telecom | Broadband, Mobile Postpaid | ₹600–1,500 | **Low** — types are similar; category-level profiling should be adequate |
| `MEAL` | Meals | Daily Meal, Client Lunch, Team Dinner | ₹150–8,000 | **High** |
| `FUEL` | Fuel & Mileage | Two Wheeler, Four Wheeler | ₹200–3,000 | Medium — different rates; exercises the mileage branch |
| `TRVL` | Travel | Local Cab, Airfare, Hotel | ₹250–25,000 | **Very high** — the key grain test |
| `LEARN` | Learning & Development | Books, Certification, Course Fee | ₹500–20,000 | Medium, rare |
| `MED` | Medical | Consultation, Hospitalisation | ₹500–60,000 | **High** — the abstention case |

**Why `TRVL` and `MED` matter most:** if profiles are built at category level, someone who only ever claims `Local Cab` at ₹300 has a Travel band wide enough to swallow a first-ever ₹18,000 `Airfare` — it wouldn't look anomalous, and would auto-approve. At type level the airfare has zero precedent and correctly abstains. Same structure as the hospital-bill problem. These two categories make that failure mode **observable rather than hypothetical**.

---

## **3\. Archetypes**

Assigned per **(employee, category) pair**, not per employee — a person can be steady in Internet and erratic in Travel. More realistic, and gives more archetype instances from the same 25 people.

| Archetype | Generation rule | What it must prove |
| ----- | ----- | ----- |
| **Steady recurrer** | `amount = centre ± 3% noise`, fixed monthly gap | scores high, auto-approves. The core case. |
| **Erratic legitimate** | `amount ~ wide distribution`, irregular gaps | `cv` widens the band so they aren't falsely flagged |
| **Drifter** | `centre(t) = base × (1 + 0.04t) ± noise` | does the scorer over-react to slow legitimate growth? |
| **Rare claimer** | 1–2 claims total in the category | eligibility gate routes to manual regardless of amount |
| **New joiner** | first claims appear in final 3 months | cold-start handling |
| **Duplicate submitter** | re-submits same `bill_number` \+ `bill_period` | `is_duplicate_flagged` guardrail fires |
| **Override-prone** | amount routinely corrected downward by reviewer | `override_count > 0` excluded from clean precedent |

**Allocation across 25 employees** (\~75–90 (employee, type) pairs): steady ≈ 28, erratic ≈ 15, drifter ≈ 10, rare ≈ 14, new joiner ≈ 6, plus duplicate and override behaviour injected into \~6 existing pairs rather than dedicated employees.

Archetypes are assigned per **(employee, expense\_type)** — finer than category, so that a person can be a steady `Local Cab` claimant *and* a rare `Airfare` claimant within the same Travel category. That combination is precisely what the grain test needs.

---

## **4\. Column generation — by group**

All 80 columns, grouped by how they're produced.

### **4.1 Identity**

`item_pk` sequential int · `item_id` \= `{categoryCode}-{seq}` · `report_pk` sequential · `report_id` \= `EXP-{n}` · `employee_id` \+ `employee_id-2` (kept duplicated, per instruction, to match the real export)

Multi-item reports: \~20% of reports carry 2–4 items, so the per-item vs per-report label distinction stays exercised.

### **4.2 Category and type**

`expense_type_name` is the claim's actual type (§2) · `expense_category_name` and `expense_category_code` are its **parent**, resolved through the hierarchy — never assigned independently, so the `type → category` relationship stays internally consistent exactly as `et.expense_category_id → ec.id` enforces it in the real schema. Names kept (not replaced with ids) per instruction.

Amount distributions are defined **per type, not per category** — that's what makes the grain question measurable.

### **4.3 Amounts**

`bill_amount` from the archetype's distribution · `tax_amount` ≈ 5–18% where applicable · `amount_before_tax` \= bill − tax · `bill_currency_id` mostly 1 (INR), \~8% foreign · `payout_currency_id` \= 1 · `exchange_rate` \= 1 when matched, real-ish rate when not, **and deliberately 0 on \~1% to exercise the `forex_invalid` guardrail** · `payout_amount` \= (overridden or bill) × rate · `overridden_*` populated only for override-prone pairs · `has_attachment` mostly true, false on some small claims · `bill_number` realistic mixed formats (`INV-4471`, `4471`, blank \~30%) — **blanks matter**, they're why we rely on `is_duplicate_flagged` rather than bill matching

### **4.4 Mileage — `FUEL` only**

`mileage_unit` KM · `mileage_quantity` \~ archetype · `mileage_rate_per_unit` policy rate · `mileage_original_rate_per_unit` differs only where a rate override happened · `mileage_overridden_quantity` rare. `bill_amount` \= qty × rate. Null for all other categories.

### **4.5 Outcome**

`item_status` ∈ {Accepted, Paid, Rejected} from the decision function (§5) · `report_status` ALL-CAPS equivalent (deliberately preserving the casing mismatch) · `approval_date` / `rejection_date` mutually exclusive · **`auto_approved` generated but set only where amount \< category threshold**, so the column is available if wanted and ignorable if not

### **4.6 Policy, limits, frequency**

`policy_id` / `rule_id` stable uuids per category · limits per category held constant across the dataset · `limit_scope` mostly `TYPE_CURRENCY_MATCHED`, some `*_FLAT_FALLBACK` · frequency caps per category · `allow_beyond_limit` / `_frequency` mostly true

### **4.7 Reviewer config**

`configured_reviewer_chain` per category — mix of `Manager`, `Manager > Admin`, `Manager > Manager's Manager > Admin` · `configured_reviewer_count` its length (always ≥ 1, matching the query's filter)

### **4.8 Remarks & workflow trail**

Generated **consistently with the outcome**, not independently — a Rejected claim gets `last_workflow_action = REJECT`, a populated `last_review_level`, and a rejection remark; an Accepted one gets ACCEPT/FORWARD. `workflow_step_count` scales with chain length. `latest_step_owner_type` / `_caller_type` mix EMPLOYEE and SYSTEM\_USER (system for routing, employee for decisions). `latest_step_finish_minus_due` centred near zero, skewed later in the Lenient variant.

### **4.9 Duplicate / override**

`is_duplicate_flagged` \+ `duplicate_match_count` set on planted duplicates only · `override_count`, `last_override_reason`, `last_overridden_at` on override-prone pairs

### **4.10 Timestamps**

`item_created_on` → `submission_date` → decision date, always ordered. `submit_lag` per archetype (steady \= 2–5 days, erratic \= up to 40).

---

## **5\. The three datasets**

Same archetype machinery, **different outcome-decision function**. Each claim gets an internal `fit` value (how well it matches its own archetype's band, rhythm, and precedent); the variants differ in how steeply approval probability falls as fit degrades.

|  | Regular | Strict | Lenient |
| ----- | ----- | ----- | ----- |
| In-pattern approve rate | \~92% | \~97% | \~99% |
| Out-of-pattern approve rate | \~50% | \~10% | \~90% |
| Slope of P(approve) vs fit | moderate | steep | near-flat |
| Overrides | occasional | rare — rejects instead | rare — approves as-is |
| Reviewer SLA lag | mixed | tight | loose |

**The key property:** the difference is expressed as *how tightly `item_status` correlates with `amount_z` / `rhythm_z`* — not as three unrelated random distributions. Otherwise the datasets would look different superficially without actually stress-testing the scorer's calibration.

**What each should demonstrate:**

* **Strict** — the scorer's fit signal is genuinely predictive; high separation  
* **Lenient** — approval carries almost no information; the scorer should be *unable* to discriminate, and if it appears to, we've got a bug or leakage  
* **Regular** — the realistic middle, and the one the threshold sweep is demonstrated on

---

## **6\. Build order**

1. Employees \+ archetype assignment per (employee, category)  
2. Category / policy config (limits, chains, thresholds) — held constant  
3. Claim sequences walked forward in time per pair  
4. Outcome decision per claim (variant-specific)  
5. Workflow trail generated to match each outcome  
6. Duplicate / override / invalid-forex injection at known positions  
7. Assemble to the 80-column layout, write CSV

Step 6 is **test-fixture engineering, not randomness** — we record exactly which `item_id`s carry planted defects, so the guardrail tests assert against a known list.

---

## **7\. Feature coverage check**

| Feature | Supported |
| ----- | ----- |
| Profile (`n_prior_approved`, `centre`, `spread`, `cv`, `median_gap_days`) | ✅ |
| `amount_z`, `rhythm_z`, `submit_lag_z` | ✅ |
| `pct_of_claim_limit` / `_month_limit` | ✅ (limits generated per claim) |
| `is_duplicate_flagged` guardrail | ✅ planted |
| `forex_invalid` guardrail | ✅ planted (\~1%) |
| Cold-start / eligibility gate | ✅ via rare \+ new-joiner archetypes |
| Employee-category & company-category approval rates | ✅ derivable post-hoc |
| Seasonality / monthly trend | ✅ injected into TRVL and FOOD |
| **Peer / role comparison** | ❌ **not possible** — `tblemployee` exposes only `cid` and `employeeno`. No role, grade, department, or location exists in this schema. Confirms the earlier decision to exclude peer features. |

---

## **8\. Open items before generation**

1. **`n_prior_approved` and auto-approved claims** — profile should include them (avoids the upward bias); label must exclude them. Whether they count toward the *eligibility* threshold is still a product call: "we've seen this person claim this repeatedly" vs "a human has vouched for them at least N times." Both defensible.

2. **`src/profiles.py` needs the corresponding fix** — currently builds profiles from `is_clean_approval` only, which excludes auto-approved claims and biases `centre` upward.

3. **Coverage denominator** — with the two rules OR'd, coverage must be measured against claims that *fail* the amount rule (today's manual queue), not all claims.

4. **Profile grain — type or category?** The schema supports both, and so does the policy engine (`limit_scope` returns `TYPE_*` or `CATEGORY_*` depending on how limits were configured). Earlier plans said "profile at category level to avoid fragmentation" — **that was premature.** Category-level risks blending semantically different types (`Local Cab` with `Airfare`), producing a band wide enough to auto-approve a genuinely novel claim. Type-level is cleaner but thins precedent and worsens cold start.

    **Recommendation:** make it `PROFILE_GRAIN = "type" | "category"` in `config.py` — a one-line change in `build_profiles` — and measure both on the generated data. §2's category design makes the difference visible.

5. Confirm the 6 categories / 15 types in §2, or swap in ones closer to what production actually uses.

