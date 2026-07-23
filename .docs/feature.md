# Feature Documentation

## 1. Amount vs Type Medium
- **1.1** Is 2000 very high for books?

## 2. Amount vs My Own History
- **2.1** Is this claim very high for current employee?

## 3. Frequency Data
- **3.1** Is this a sudden spike?

## 4. Submission Date Delta
- **4.1** Is the user submitting date deviated from the history?

## 5. Duplicate Bill
- **5.1** Give high score when you see the same pattern

---

## Future Features

> **Note:** Once we integrate the attachment data we can do this

### 100. Vendor Parity
- **100.1** Is this vendor different from past history?


# Feature Documentation

Every feature must answer one specific question. If a feature cannot be written as a single question, it does not belong in this document.

---

## Scored Features

These feed the model. Each contributes a weighted signal — none of them can force a decision on its own.

## 1. Amount vs Type Median
- **1.1** Is this amount high compared to what everyone claims for this type, company-wide? -->one way to think
- **Caution:** this is a population-level comparison, not personal. It must only ever *lower* a score, never raise one. A claim with no personal history must not score well just because the amount is typical for other people. Using this to raise a score recreates the exact risk we ruled out earlier — a model that learns "this type is usually fine" and auto-approves a genuinely novel claim.
- **1.2** Is this amount high compared to what the persons history. -->other way
## 2. Amount vs My Own History
- **2.1** Is this amount high for this specific employee, in this specific type?
- This is the core feature. It is the one the whole score is built around.

## 3. Frequency Delta
- **3.1** Is this a sudden spike — a claim after a long gap of no activity in this type?

## 4. Submission Date Delta
- **4.1** Does the gap between the bill date and the submission date differ from this employee's usual gap?

## 5. Percent of Policy Limit
- **5.1** How close is this amount to the category's configured limit?
- Not the same question as Feature 2. An amount can be normal for the employee and still sit right under the policy ceiling — that pattern is worth surfacing on its own.

## 6. Tenure in This Type
- **6.1** How long has this employee been claiming this exact type?
- This does not judge the claim. It judges how much we should trust the profile the claim is being judged against. A one-month-old profile and a two-year-old profile should not carry equal weight, even if both currently show 3 prior approvals.

## 7. Mileage Rate Consistency *(mileage claims only)* -->should be handeled separately.
- **7.1** Does the claimed rate per unit match this employee's usual rate for this type?
- The schema stores `mileage_original_rate_per_unit` specifically to catch rate manipulation. This feature uses that field directly.

---

## Guardrails(we can say, but during scoring itself we will keep these in find).

These are hard caps, not scored features. A guardrail is checked before scoring runs. If one fires, it sets the score directly and no weighted feature can override it.

## G1. Duplicate Bill
- **G1.1** Is this bill number, or a near-identical one, already claimed by this employee in the same billing period — or by a different employee at all?
- **If yes: score is capped at 0.** *(Corrected from the original draft, which had this backwards — a duplicate must never score highly, regardless of how well it otherwise matches the employee's pattern.)*

## G2. Insufficient History
- **G2.1** Does this employee have fewer than the minimum required prior approvals in this exact type?
- If yes, the claim is not eligible to be scored at all. It goes to manual review by default, not because it looks suspicious, but because there is nothing to judge it against.

## G3. Prior Rejection
- **G3.1** Has this employee ever had a claim rejected in this exact type before?
- If yes, cap the score. A clean recent streak should not erase an earlier rejection.

## G4. Absolute Ceiling
- **G4.1** Does the amount exceed a fixed absolute limit, regardless of how well it fits the employee's pattern?
- Protects against a claim that is perfectly "normal" for someone whose normal happens to be very large — a scenario a purely relative feature cannot catch on its own.

---

## Future Features

> **Note:** these need attachment data integration before they can be built.

## 100. Vendor Parity
- **100.1** Is this vendor different from the employee's past history for this type?

## 101. Receipt-Amount Match *(new candidate, same dependency)*
- **101.1** Does the amount on the receipt image match the amount the employee typed in?
- Flagged as a strong candidate once OCR/attachment data lands — a mismatch is either an honest typo or an inflated claim, and either way a human should see it before the receipt data is trusted for anything else.

---

## Open Question for Discussion

Feature 1 and Feature G4 both compare a claim against something other than the employee's own history — one against the company average, one against a fixed ceiling. Worth confirming with the team: should **any** non-personal comparison ever be allowed to *raise* a score, or should the rule be absolute — personal history raises, everything else can only lower or cap? Recommend the absolute version, but flagging it as a decision to confirm rather than assuming it.
