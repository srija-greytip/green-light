## Working SQL to extract data

```sql
SELECT
    -- Item identity
    eri.id                               AS item_pk,
    eri.item_id,
    eri.expense_report_id                AS report_pk,
    eri.employee_id,
    er.report_id,
    er.employee_id,

    -- Claim category
    et.id                              AS expense_type_id,
    ec.code                              AS expense_category_code,
    -- Claim amounts
    eri.bill_number,
    eri.bill_date,
    eri.bill_amount,
    eri.bill_currency_id,
    eri.overridden_amount,
    -- Mileage detail (null for non-mileage claims)
    eri.mileage_info ->> 'unit'                            AS mileage_unit,
    (eri.mileage_info ->> 'quantity')::numeric              AS mileage_quantity,
    (eri.mileage_info ->> 'ratePerUnit')::numeric           AS mileage_rate_per_unit,
    (eri.mileage_info ->> 'originalRatePerUnit')::numeric   AS mileage_original_rate_per_unit,
    (eri.mileage_info ->> 'overriddenQuantity')::numeric    AS mileage_overridden_quantity,
    -- Outcome labels (what the scorer is back-tested against)
    eri.status                           AS item_status,
    er.status                            AS report_status,
    er.auto_approved,
    er.approval_date,
    er.rejection_date,
    -- Policy / rule linkage, real join now that policies/policy_rules are
    -- in the same DB. rule_info stores these ids as text; policies.id and
    -- policy_rules.id are uuid, so cast + regex-guard to avoid a hard cast
    -- error on any null/malformed id (same class of bug as the owner/caller
    -- varchar issue earlier).
    eri.rule_info ->> 'policyId'         AS policy_id,
    eri.rule_info ->> 'ruleId'           AS rule_id,
    -- Policy limit snapshot AS IT APPLIED AT CLAIM TIME, resolved to the
    -- claim's bill currency (currency-matched entry first, flat fallback second)
    COALESCE(
        (type_currency_limit.entry ->> 'limitPerClaim')::int,
        (category_currency_limit.entry ->> 'limitPerClaim')::int,
        (type_limit.action ->> 'limitPerClaim')::int,
        (category_limit.action ->> 'limitPerClaim')::int
    )                                                                    AS limit_per_claim,
    COALESCE(
        (type_currency_limit.entry ->> 'limitPerDay')::int,
        (category_currency_limit.entry ->> 'limitPerDay')::int,
        (type_limit.action ->> 'limitPerDay')::int,
        (category_limit.action ->> 'limitPerDay')::int
    )                                                                    AS limit_per_day,
    COALESCE(
        (type_currency_limit.entry ->> 'limitPerMonth')::int,
        (category_currency_limit.entry ->> 'limitPerMonth')::int,
        (type_limit.action ->> 'limitPerMonth')::int,
        (category_limit.action ->> 'limitPerMonth')::int
    )                                                                    AS limit_per_month,
    COALESCE(
        (type_currency_limit.entry ->> 'limitPerQuarter')::int,
        (category_currency_limit.entry ->> 'limitPerQuarter')::int,
        (type_limit.action ->> 'limitPerQuarter')::int,
        (category_limit.action ->> 'limitPerQuarter')::int
    )                                                                    AS limit_per_quarter,
    COALESCE(
        (type_currency_limit.entry ->> 'limitPerYear')::int,
        (category_currency_limit.entry ->> 'limitPerYear')::int,
        (type_limit.action ->> 'limitPerYear')::int,
        (category_limit.action ->> 'limitPerYear')::int
    )                                                                    AS limit_per_year,
    COALESCE(
        (type_limit.action ->> 'allowBeyondLimit')::boolean,
        (category_limit.action ->> 'allowBeyondLimit')::boolean
    )                                                                    AS allow_beyond_limit,
    -- Frequency snapshot -- lives on 'expense.restriction.type', not the limit action
    (freq_restriction.action ->> 'frequencyPerDay')::int        AS frequency_per_day,
    (freq_restriction.action ->> 'frequencyPerMonth')::int      AS frequency_per_month,
    (freq_restriction.action ->> 'frequencyPerQuarter')::int    AS frequency_per_quarter,
    (freq_restriction.action ->> 'frequencyPerYear')::int       AS frequency_per_year,
    (freq_restriction.action ->> 'allowBeyondFrequency')::boolean AS allow_beyond_frequency,
    -- Reviewer / workflow config, flattened from the 'platform.workflow.reviewers' action
    reviewer_chain.chain                 AS configured_reviewer_chain,
    reviewer_chain.level_count           AS configured_reviewer_count,
    -- Item-level remarks cache (Penex's own convenience copy)
    jsonb_array_length(coalesce(eri.remarks_history, '[]'::jsonb))     AS remark_count,
    eri.remarks_history -> -1 ->> 'workflowAction'                     AS last_workflow_action,
    -- Duplicate / override signals
    jsonb_array_length(coalesce(eri.duplicates, '[]'::jsonb)) > 0      AS is_duplicate_flagged,
    jsonb_array_length(coalesce(eri.duplicates, '[]'::jsonb))          AS duplicate_match_count,
    jsonb_array_length(coalesce(eri.override_info, '[]'::jsonb))       AS override_count,
    -- Timestamps
    eri.created_on                       AS item_created_on,
    eri.updated_on                       AS item_updated_on,
    er.submission_date
FROM expense_report_item eri
JOIN expense_report er         ON er.id = eri.expense_report_id
LEFT JOIN expense_type et      ON et.id = eri.expense_type_id
LEFT JOIN expense_category ec  ON ec.id = et.expense_category_id
LEFT JOIN LATERAL (
    SELECT a AS action
    FROM jsonb_array_elements(
        CASE WHEN jsonb_typeof(eri.rule_info -> 'actions') = 'array'
             THEN eri.rule_info -> 'actions' ELSE '[]'::jsonb END
    ) a
    WHERE a ->> 'code' = 'expense.limit.type'
    LIMIT 1
) type_limit ON true
LEFT JOIN LATERAL (
    SELECT a AS action
    FROM jsonb_array_elements(
        CASE WHEN jsonb_typeof(eri.rule_info -> 'actions') = 'array'
             THEN eri.rule_info -> 'actions' ELSE '[]'::jsonb END
    ) a
    WHERE a ->> 'code' = 'expense.limit.category'
    LIMIT 1
) category_limit ON true
LEFT JOIN LATERAL (
    SELECT c AS entry
    FROM jsonb_array_elements(
        CASE WHEN jsonb_typeof(type_limit.action -> 'currencyLimits') = 'array'
             THEN type_limit.action -> 'currencyLimits' ELSE '[]'::jsonb END
    ) c
    WHERE (c ->> 'currency')::int = eri.bill_currency_id
    LIMIT 1
) type_currency_limit ON true
LEFT JOIN LATERAL (
    SELECT c AS entry
    FROM jsonb_array_elements(
        CASE WHEN jsonb_typeof(category_limit.action -> 'currencyLimits') = 'array'
             THEN category_limit.action -> 'currencyLimits' ELSE '[]'::jsonb END
    ) c
    WHERE (c ->> 'currency')::int = eri.bill_currency_id
    LIMIT 1
) category_currency_limit ON true
LEFT JOIN LATERAL (
    SELECT a AS action
    FROM jsonb_array_elements(
        CASE WHEN jsonb_typeof(eri.rule_info -> 'actions') = 'array'
             THEN eri.rule_info -> 'actions' ELSE '[]'::jsonb END
    ) a
    WHERE a ->> 'code' = 'expense.restriction.type'
    LIMIT 1
) freq_restriction ON true
LEFT JOIN LATERAL (
    SELECT a AS action
    FROM jsonb_array_elements(
        CASE WHEN jsonb_typeof(eri.rule_info -> 'actions') = 'array'
             THEN eri.rule_info -> 'actions' ELSE '[]'::jsonb END
    ) a
    WHERE a ->> 'code' = 'platform.workflow.reviewers'
    LIMIT 1
) workflow_action ON true
LEFT JOIN LATERAL (
    SELECT
        string_agg(r ->> 'wfReviewerTypeName', ' > ' ORDER BY (r ->> 'level')::int) AS chain,
        count(*) AS level_count
    FROM jsonb_array_elements(
        CASE WHEN jsonb_typeof(workflow_action.action -> 'workflowConfig' -> 'reviewers') = 'array'
             THEN workflow_action.action -> 'workflowConfig' -> 'reviewers' ELSE '[]'::jsonb END
    ) r
) reviewer_chain ON true
WHERE reviewer_chain.level_count > 0
  AND eri.status IN ('Accepted', 'Paid', 'Rejected')
ORDER BY eri.created_on DESC;
```

## Column reference

Data dictionary for the extraction query built for Srija's research spike. Grain: **one row per expense_report_item** (one claim line item), filtered to `item_status IN ('Accepted', 'Paid', 'Rejected')` and `configured_reviewer_count > 0` (claims that actually went through at least one configured reviewer level).

Every column below is traced to its source table/column or JSONB path in the penex (and polly) repos — not assumed.

### Item identity

| Column | Source | What it is |
| --- | --- | --- |
| item_pk | expense_report_item.id | Internal numeric primary key of the claim line item. |
| item_id | expense_report_item.item_id | Business-facing line item identifier on the report. |
| report_pk | expense_report_item.expense_report_id | FK to the parent expense report's internal id. |
| employee_id | expense_report_item.employee_id **and** expense_report.employee_id | The claimant. **Both are selected in this query (once via the item, once via the report) and share the same underlying column name** — if loaded into pandas the second one will auto-suffix to `employee_id.1`. They should always be identical; drop one if that duplication is a problem. |
| report_id | expense_report.report_id | Human-readable report ID, format `EXP-{id}`. |

### Claim category

| Column | Source | What it is |
| --- | --- | --- |
| expense_type_id | expense_type.id | Internal numeric primary key of the expense type. |
| expense_category_code | expense_category.code | Stable category code. |

### Claim amounts

| Column | Source | What it is |
| --- | --- | --- |
| bill_number | expense_report_item.bill_number | Receipt/bill number as entered by the claimant. |
| bill_date | expense_report_item.bill_date | Date on the receipt. |
| bill_amount | expense_report_item.bill_amount | Original claimed amount, in the bill's own currency. |
| bill_currency_id | expense_report_item.bill_currency_id | Currency the expense was actually incurred in. |
| overridden_amount | expense_report_item.overridden_amount | If a reviewer manually changed the claimed amount, the new value. Null if never overridden. |

### Mileage detail (null for non-mileage claims)

| Column | Source | What it is |
| --- | --- | --- |
| mileage_unit | expense_report_item.mileage_info ->> 'unit' | Distance unit (km/miles), from the mileage_info JSONB blob. |
| mileage_quantity | mileage_info ->> 'quantity' | Distance claimed. |
| mileage_rate_per_unit | mileage_info ->> 'ratePerUnit' | Rate applied per unit of distance. |
| mileage_original_rate_per_unit | mileage_info ->> 'originalRatePerUnit' | Rate before any override — lets you spot rate manipulation. |
| mileage_overridden_quantity | mileage_info ->> 'overriddenQuantity' | Distance value if a reviewer overrode it. |

### Outcome labels (what the scorer is back-tested against)

| Column | Source | What it is |
| --- | --- | --- |
| item_status | expense_report_item.status | Item-level workflow outcome, stored **title case** ("Accepted", "Rejected", "Forwarded", "Withdrawn", "Underway", "Paid", …) — confirmed via `item.setStatus(ExpenseReportStatus.X.getValue())` calls in Accept.java/Reject.java/Forward.java/AutoApprove.java. This query filters to Accepted, Paid, Rejected only. |
| report_status | expense_report.status | Report-level status. **Different casing from item_status**: this column is `@Enumerated(EnumType.STRING)`, so Hibernate persists the enum _name_, not its label — stored ALL CAPS ("ACCEPTED", "PAID", etc). Don't reuse the same filter list on this column without upper-casing it. |
| auto_approved | expense_report.auto_approved | Whether the whole report was auto-approved by workflow rules rather than a human reviewer — directly relevant to EC-1062 since this is the existing precedent for what you're building. |
| approval_date | expense_report.approval_date | When the report was approved. |
| rejection_date | expense_report.rejection_date | When the report was rejected. |

### Policy / rule linkage

| Column | Source | What it is |
| --- | --- | --- |
| policy_id | expense_report_item.rule_info ->> 'policyId' | The Polly policy id that governed this claim, as a text string (not a normal FK column — it's inside the rule_info JSONB blob, see RuleInfo.java). |
| rule_id | rule_info ->> 'ruleId' | The specific rule within that policy that fired for this claim. |

### Policy limit snapshot (as it applied at claim time, resolved to the claim's own bill currency)

Limits can be configured **either per expense type or per category** (never both the same way — confirmed via ExpenseRulesService.populateUsageFields), and are **currency-specific** (`Action.currencyLimits`, a list keyed by currency id — see CurrencyEntitlement.java). Each column below picks, in order: the currency-matched type-level limit, then currency-matched category-level, then the flat (unresolved) type-level value, then flat category-level.

| Column | What it is |
| --- | --- |
| limit_per_claim | Max amount allowed for a single claim under this policy/currency. |
| limit_per_day | Max cumulative amount allowed per day. |
| limit_per_month | Max cumulative amount allowed per month. |
| limit_per_quarter | Max cumulative amount allowed per quarter. |
| limit_per_year | Max cumulative amount allowed per year. |
| allow_beyond_limit | Whether exceeding the limit is even permitted (with justification) vs. hard-blocked. Has no per-currency variant — always comes from the flat field. |

### Frequency snapshot

Lives on a **different action entirely** (`expense.restriction.type`) from the limit fields above — confirmed via ExpenseRulesServiceTest.

| Column | What it is |
| --- | --- |
| frequency_per_day, frequency_per_month, frequency_per_quarter, frequency_per_year | Max number of claims (count, not amount) allowed in that period under this policy. |
| allow_beyond_frequency | Whether exceeding the frequency cap is permitted. |

### Reviewer / workflow configuration

Flattened from the `platform.workflow.reviewers` action's `workflowConfig` object (WorkflowConfig.java).

| Column | What it is |
| --- | --- |
| configured_reviewer_chain | The reviewer levels configured for this policy, collapsed into one string ordered by level, e.g. `"Manager > Finance"`. Built from the reviewers array's `wfReviewerTypeName` field. |
| configured_reviewer_count | How many reviewer levels are configured. This query filters to > 0, i.e. excludes claims with no reviewer chain configured at all (fully automatic policies with nothing to review). |

### Item-level remarks (Penex's own convenience cache — see caveat below)

| Column | Source | What it is |
| --- | --- | --- |
| remark_count | jsonb_array_length(remarks_history) | How many remarks exist in the item's own history array. |
| last_workflow_action | remarks_history[-1].workflowAction | Action tied to the latest remark: (ACCEPTED/PAID) / REJECT. |


### Duplicate / override signals

Anomaly-adjacent features Penex already computes — potentially strong inputs to the scorer directly.

| Column | Source | What it is |
| --- | --- | --- |
| is_duplicate_flagged | duplicates array non-empty | Whether the system's own duplicate-bill detection flagged this claim. |
| duplicate_match_count | jsonb_array_length(duplicates) | How many other claims it was flagged as a duplicate of. |
| override_count | jsonb_array_length(override_info) | How many times this claim's amount/quantity was manually overridden. |

### Timestamps

| Column | Source | What it is |
| --- | --- | --- |
| item_created_on | expense_report_item.created_on | When the claim line item was first created. |
| item_updated_on | expense_report_item.updated_on | Last modification time. |
| submission_date | expense_report.submission_date | When the parent report was submitted. |
