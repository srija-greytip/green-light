### Working SQL to extract data
```sql
### SQL
SELECT
    -- Item identity
    eri.id                               AS item_pk,
    eri.item_id,
    eri.expense_report_id                AS report_pk,
	eri.employee_id,
    er.report_id,
    er.employee_id,
	
    -- Claim category
    et.name                              AS expense_type_name,
    ec.name                              AS expense_category_name,
    ec.code                              AS expense_category_code,
    -- Claim amounts
    eri.bill_number,
    eri.bill_date,
    eri.bill_amount,
    eri.tax_amount,
    eri.amount_before_tax,
    eri.bill_currency_id,
    eri.payout_currency_id,
    eri.exchange_rate,
    eri.payout_amount,
    eri.overridden_amount,
    eri.overridden_tax_amount,
    eri.overridden_reason,
    (eri.attachment_id IS NOT NULL)      AS has_attachment,
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
    (CASE
        WHEN type_currency_limit.entry IS NOT NULL THEN 'TYPE_CURRENCY_MATCHED'
        WHEN category_currency_limit.entry IS NOT NULL THEN 'CATEGORY_CURRENCY_MATCHED'
        WHEN type_limit.action IS NOT NULL THEN 'TYPE_FLAT_FALLBACK'
        WHEN category_limit.action IS NOT NULL THEN 'CATEGORY_FLAT_FALLBACK'
    END)                                                                 AS limit_scope,
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
    eri.remarks                          AS latest_remark,
    jsonb_array_length(coalesce(eri.remarks_history, '[]'::jsonb))     AS remark_count,
    eri.remarks_history -> -1 ->> 'workflowAction'                     AS last_workflow_action,
    (eri.remarks_history -> -1 ->> 'reviewLevel')::int                 AS last_review_level,
    (eri.remarks_history -> -1 ->> 'timestamp')::timestamp             AS last_remark_at,
    (eri.remarks_history -> 0 ->> 'timestamp')::timestamp              AS first_remark_at,
    er.remarks                           AS report_level_remark,
    -- Workflow engine step history, flattened to the LATEST step + a count
    step_count.cnt                          AS workflow_step_count,
    latest_step.step_id                     AS latest_workflow_step_id,
    latest_step.action_id                   AS latest_workflow_action_id,
    latest_step.status                      AS latest_step_status,
    latest_step.start_date                  AS latest_step_start_date,
    latest_step.due_date                    AS latest_step_due_date,
    latest_step.finish_date                 AS latest_step_finish_date,
    (latest_step.finish_date - latest_step.due_date) AS latest_step_finish_minus_due,
    latest_step.owner_id                    AS latest_step_owner_raw_id,
    (CASE WHEN latest_step.owner_id >= 0 THEN 'EMPLOYEE' WHEN latest_step.owner_id < 0 THEN 'SYSTEM_USER' END) AS latest_step_owner_type,
    owner_emp.employeeno                    AS latest_step_owner_employee_no,
    (CASE WHEN latest_step.owner_id < 0 THEN abs(latest_step.owner_id) END) AS latest_step_owner_auth_user_id, -- TODO: confirm GtAuthUser table/join
    latest_step.caller_id                   AS latest_step_caller_raw_id,
    (CASE WHEN latest_step.caller_id >= 0 THEN 'EMPLOYEE' WHEN latest_step.caller_id < 0 THEN 'SYSTEM_USER' END) AS latest_step_caller_type,
    caller_emp.employeeno                   AS latest_step_caller_employee_no,
    (CASE WHEN latest_step.caller_id < 0 THEN abs(latest_step.caller_id) END) AS latest_step_caller_auth_user_id, -- TODO: confirm GtAuthUser table/join
    latest_step_remark.remarks              AS latest_step_remark_text,
    -- Duplicate / override signals
    jsonb_array_length(coalesce(eri.duplicates, '[]'::jsonb)) > 0      AS is_duplicate_flagged,
    jsonb_array_length(coalesce(eri.duplicates, '[]'::jsonb))          AS duplicate_match_count,
    jsonb_array_length(coalesce(eri.override_info, '[]'::jsonb))       AS override_count,
    eri.override_info -> -1 ->> 'overrideReason'                       AS last_override_reason,
    (eri.override_info -> -1 ->> 'overriddenAt')::timestamp            AS last_overridden_at,
    -- Timestamps
    eri.created_on                       AS item_created_on,
    eri.updated_on                       AS item_updated_on,
    er.submission_date
FROM expense_report_item eri
JOIN expense_report er         ON er.id = eri.expense_report_id
LEFT JOIN expense_type et      ON et.id = eri.expense_type_id
LEFT JOIN expense_category ec  ON ec.id = et.expense_category_id
LEFT JOIN policies pol      ON (eri.rule_info ->> 'policyId') ~ '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
                             AND pol.id = (eri.rule_info ->> 'policyId')::uuid
LEFT JOIN policy_rules pr   ON (eri.rule_info ->> 'ruleId') ~ '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
                             AND pr.id = (eri.rule_info ->> 'ruleId')::uuid
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
LEFT JOIN LATERAL (
    SELECT hs.id, hs.step_id, hs.action_id, hs.status,
           hs.start_date, hs.due_date, hs.finish_date,
           CASE WHEN hs.owner  ~ '^-?[0-9]+$' THEN hs.owner::int  END AS owner_id,
           CASE WHEN hs.caller ~ '^-?[0-9]+$' THEN hs.caller::int END AS caller_id
    FROM os_historystep hs
    WHERE hs.entry_id = er.workflow_entry_id
    ORDER BY hs.id DESC
    LIMIT 1
) latest_step ON true
LEFT JOIN LATERAL (
    SELECT count(*) AS cnt
    FROM os_historystep hs2
    WHERE hs2.entry_id = er.workflow_entry_id
) step_count ON true
LEFT JOIN tblemployee owner_emp  ON latest_step.owner_id  >= 0 AND owner_emp.cid  = latest_step.owner_id
LEFT JOIN tblemployee caller_emp ON latest_step.caller_id >= 0 AND caller_emp.cid = latest_step.caller_id
LEFT JOIN workflow_info wi ON wi.entry_id = er.workflow_entry_id
LEFT JOIN LATERAL (
    SELECT wr.remarks, wr.user_name
    FROM workflow_remarks wr
    WHERE wr.workflow_info_id = wi.id
      AND wr.history_step_cid = latest_step.id
    LIMIT 1
) latest_step_remark ON true
WHERE reviewer_chain.level_count > 0
  AND eri.status IN ('Accepted', 'Paid', 'Rejected')
ORDER BY eri.created_on DESC;
```


### Column Reference
Data dictionary for the extraction query built for Srija's research spike. Grain: **one row per expense_report_item** (one claim line item), filtered to item_status IN ('Accepted', 'Paid', 'Rejected') and configured_reviewer_count > 0 (claims that actually went through at least one configured reviewer level).

Every column below is traced to its source table/column or JSONB path in the penex (and polly) repos - not assumed.

## Item identity

| **Column**  | **Source**                                                         | **What it is**                                                                                                                                                                                                                                                                             |
| ----------- | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| item_pk     | expense_report_item.id                                             | Internal numeric primary key of the claim line item.                                                                                                                                                                                                                                       |
| report_pk   | expense_report_item.expense_report_id                              | FK to the parent expense report's internal id.                                                                                                                                                                                                                                             |
| employee_id | expense_report_item.employee_id **and** expense_report.employee_id | The claimant. **Both are selected in this query (once via the item, once via the report) and share the same underlying column name** - if loaded into pandas the second one will auto-suffix to employee_id.1. They should always be identical; drop one if that duplication is a problem. |
| report_id   | expense_report.report_id                                           | Human-readable report ID, format EXP-{id}.                                                                                                                                                                                                                                                 |

## Claim category

| **Column**            | **Source**                                                   | **What it is**                                                   |
| --------------------- | ------------------------------------------------------------ | ---------------------------------------------------------------- |
| expense_category_id   | expense_category.id                                            |                                     |
| expense_type_id       | expense_type.id                                                 | ---                                                              |

## Claim amounts

| **Column**            | **Source**                                | **What it is**                                                                                                                        |
| --------------------- | ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| bill_number           | expense_report_item.bill_number           | Receipt/bill number as entered by the claimant.                                                                                       |
| bill_date             | expense_report_item.bill_date             | Date on the receipt.                                                                                                                  |
| bill_amount           | expense_report_item.bill_amount           | Original claimed amount, in the bill's own currency.                                                                                  |
| bill_currency_id      | expense_report_item.bill_currency_id      | Currency the expense was actually incurred in.                                                                                        |
| overridden_amount     | expense_report_item.overridden_amount     | If a reviewer manually changed the claimed amount, the new value. Null if never overridden.                                           |

## Mileage detail (null for non-mileage claims)

| **Column**                     | **Source**                                  | **What it is**                                              |
| ------------------------------ | ------------------------------------------- | ----------------------------------------------------------- |
| mileage_unit                   | expense_report_item.mileage_info ->> 'unit' | Distance unit (km/miles), from the mileage_info JSONB blob. |
| mileage_quantity               | mileage_info ->> 'quantity'                 | Distance claimed.                                           |
| mileage_rate_per_unit          | mileage_info ->> 'ratePerUnit'              | Rate applied per unit of distance.                          |
| mileage_original_rate_per_unit | mileage_info ->> 'originalRatePerUnit'      | Rate before any override - lets you spot rate manipulation. |
| mileage_overridden_quantity    | mileage_info ->> 'overriddenQuantity'       | Distance value if a reviewer overrode it.                   |

## Outcome labels (what the scorer is back-tested against)

| **Column**     | **Source**                    | **What it is**                                                                                                                                                                                                                                                                                                       |
| -------------- | ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| item_status    | expense_report_item.status    | Item-level workflow outcome, stored **title case** ("Accepted", "Rejected", "Forwarded", "Withdrawn", "Underway", "Paid", ...) - confirmed via item.setStatus(ExpenseReportStatus.X.getValue()) calls in Accept.java/Reject.java/Forward.java/AutoApprove.java. This query filters to Accepted, Paid, Rejected only. |
| ---            | ---                           | ---                                                                                                                                                                                                                                                                                                                  |
| report_status  | expense_report.status         | Report-level status. **Different casing from item_status**: this column is @Enumerated(EnumType.STRING), so Hibernate persists the enum _name_, not its label - stored ALL CAPS ("ACCEPTED", "PAID", etc). Don't reuse the same filter list on this column without upper-casing it.                                  |
| ---            | ---                           | ---                                                                                                                                                                                                                                                                                                                  |
| auto_approved  | expense_report.auto_approved  | Whether the whole report was auto-approved by workflow rules rather than a human reviewer - directly relevant to EC-1062 since this is the existing precedent for what you're building.                                                                                                                              |
| ---            | ---                           | ---                                                                                                                                                                                                                                                                                                                  |
| approval_date  | expense_report.approval_date  | When the report was approved.                                                                                                                                                                                                                                                                                        |
| ---            | ---                           | ---                                                                                                                                                                                                                                                                                                                  |
| rejection_date | expense_report.rejection_date | When the report was rejected.                                                                                                                                                                                                                                                                                        |
| ---            | ---                           | ---                                                                                                                                                                                                                                                                                                                  |

## Policy / rule linkage

| **Column** | **Source**                                   | **What it is**                                                                                                                                     |
| ---------- | -------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| policy_id  | expense_report_item.rule_info ->> 'policyId' | The Polly policy id that governed this claim, as a text string (not a normal FK column - it's inside the rule_info JSONB blob, see RuleInfo.java). |
| ---        | ---                                          | ---                                                                                                                                                |
| rule_id    | rule_info ->> 'ruleId'                       | The specific rule within that policy that fired for this claim.                                                                                    |
| ---        | ---                                          | ---                                                                                                                                                |

policies/policy_rules (Polly's tables, confirmed same DB) are joined elsewhere in the query for names, but those name/module/status columns were trimmed out of this particular version - only the raw ids are in the current column set.

## Policy limit snapshot (as it applied at claim time, resolved to the claim's own bill currency)

Limits can be configured **either per expense type or per category** (never both the same way - confirmed via ExpenseRulesService.populateUsageFields), and are **currency-specific** (Action.currencyLimits, a list keyed by currency id - see CurrencyEntitlement.java). Each column below picks, in order: the currency-matched type-level limit, then currency-matched category-level, then the flat (unresolved) type-level value, then flat category-level - limit_scope tells you which one actually fired.

| **Column**         | **What it is**                                                                                                                                                                                                                                       |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| limit_per_claim    | Max amount allowed for a single claim under this policy/currency.                                                                                                                                                                                    |
| limit_per_day      | Max cumulative amount allowed per day.                                                                                                                                                                                                               |
| limit_per_month    | Max cumulative amount allowed per month.                                                                                                                                                                                                             |
| limit_per_quarter  | Max cumulative amount allowed per quarter.                                                                                                                                                                                                           |
| limit_per_year     | Max cumulative amount allowed per year.                                                                                                                                                                                                              |
| allow_beyond_limit | Whether exceeding the limit is even permitted (with justification) vs. hard-blocked. Has no per-currency variant - always comes from the flat field. |

## Frequency snapshot

Lives on a **different action entirely** (expense.restriction.type) from the limit fields above - confirmed via ExpenseRulesServiceTest.

| **Column**                                       | **What it is**                                                                     |
| ------------------------------------------------ | ---------------------------------------------------------------------------------- |
| frequency_per_day / \_month / \_quarter / \_year | Max number of claims (count, not amount) allowed in that period under this policy. |
| allow_beyond_frequency                           | Whether exceeding the frequency cap is permitted.                                  |

## Reviewer / workflow configuration

Flattened from the platform.workflow.reviewers action's workflowConfig object (WorkflowConfig.java).

| **Column**                | **What it is**                                                                                                                                                                        |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| configured_reviewer_chain | The reviewer levels configured for this policy, collapsed into one id ordered by user id, e.g. "12 > 234 > 123". Built from the reviewers array's wfReviewerTypeName field. |
| configured_reviewer_count | How many reviewer levels are configured. This query filters to > 0, i.e. excludes claims with no reviewer chain configured at all (fully automatic policies with nothing to review).  |

## Item-level remarks (Penex's own convenience cache - see caveat below)

| **Column**           | **Source**                           | **What it is**                                                             |
| -------------------- | ------------------------------------ | -------------------------------------------------------------------------- |
| remark_count         | jsonb_array_length(remarks_history)  | How many remarks exist in the item's own history array.                    |
| last_workflow_action | remarks_history\[-1\].workflowAction | Action tied to the latest remark: ACCEPT / FORWARD / REJECT / AUTO_REJECT. |
| ---                  | ---                                  | ---                                                                        |
| last_review_level    | remarks_history\[-1\].reviewLevel    | Which reviewer level made the latest remark.                               |
| ---                  | ---                                  | ---                                                                        |
| last_remark_at       | remarks_history\[-1\].timestamp      | Timestamp of the latest remark.                                            |
| ---                  | ---                                  | ---                                                                        |
| first_remark_at      | remarks_history\[0\].timestamp       | Timestamp of the first remark (start of the review thread).                |
| ---                  | ---                                  | ---                                                                        |
| ---                  | ---                                  | ---                                                                        |

**Caveat**: remarks_history is Penex's own app-level echo (ExpenseReportItem.addRemarkToHistory()), not the canonical audit trail - see next section.

## Workflow engine step history (canonical source, flattened to the latest step)

Pulled from the actual workflow engine's tables (com.greythr.boot.workflow, package com.greytip.oswf), which is compiled directly into Penex and shares its database - **not** a separate service. Joined via expense_report.workflow_entry_id = os_historystep.entry_id. Because this query keeps one row per claim, only the **most recent** step surfaces here (ordered by os_historystep.id DESC); the full step-by-step sequence needs a separate one-row-per-step query.

| **Column**                                                          | **Source**                                             | **What it is**                                                                                                                                                                                           |
| ------------------------------------------------------------------- | ------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| workflow_step_count                                                 | count(\*) over os_historystep for this entry           | Total number of workflow steps this claim has gone through (escalations, forwards, etc).                                                                                                                 |
| ---                                                                 | ---                                                    | ---                                                                                                                                                                                                      |
| latest_workflow_step_id                                             | os_historystep.step_id                                 | Step identifier within the OSWorkflow definition.                                                                                                                                                        |
| ---                                                                 | ---                                                    | ---                                                                                                                                                                                                      |
| latest_workflow_action_id                                           | os_historystep.action_id                               | Numeric action code taken at that step. **Not a global enum** - defined in the expense workflow's OSWorkflow XML descriptor; cross-reference with last_workflow_action above for a human-readable label. |
| ---                                                                 | ---                                                    | ---                                                                                                                                                                                                      |
| latest_step_status                                                  | os_historystep.status                                  | OSWorkflow's own status label for the step (e.g. "Finished").                                                                                                                                            |
| ---                                                                 | ---                                                    | ---                                                                                                                                                                                                      |
| latest_step_start_date                                              | os_historystep.start_date                              | When the step became active.                                                                                                                                                                             |
| ---                                                                 | ---                                                    | ---                                                                                                                                                                                                      |
| latest_step_due_date                                                | os_historystep.due_date                                | When the step was due to be actioned.                                                                                                                                                                    |
| ---                                                                 | ---                                                    | ---                                                                                                                                                                                                      |
| latest_step_finish_date                                             | os_historystep.finish_date                             | When the step was actually actioned.                                                                                                                                                                     |
| ---                                                                 | ---                                                    | ---                                                                                                                                                                                                      |
| latest_step_finish_minus_due                                        | Derived: finish_date - due_date                        | Reviewer SLA lag. Negative = acted early, positive = overdue. Directly useful as a reviewer-behavior feature.                                                                                            |
| ---                                                                 | ---                                                    | ---                                                                                                                                                                                                      |
| latest_step_owner_raw_id                                            | os_historystep.owner, cast from varchar                | Raw id of who owned the step. **Sign-encoded**: >= 0 is an employee id, < 0 is a system/auth user id stored as -id (confirmed in WorkflowManager.getEmployeeLite()).                                     |
| ---                                                                 | ---                                                    | ---                                                                                                                                                                                                      |
| latest_step_owner_type                                              | Derived from the sign above                            | 'EMPLOYEE' or 'SYSTEM_USER'.                                                                                                                                                                             |
| ---                                                                 | ---                                                    | ---                                                                                                                                                                                                      |
| latest_step_owner_employee_no                                       | tblemployee.employeeno (joined when owner id >= 0)     | Employee number of the step owner, if it's a person.                                                                                                                                                     |
| ---                                                                 | ---                                                    | ---                                                                                                                                                                                                      |
| latest_step_owner_auth_user_id                                      | abs(latest_step_owner_raw_id) when negative            | The decoded system/auth user id. **Not yet joined to a name** - the auth-user table's source wasn't available in this workspace to confirm its table name.                                               |
| ---                                                                 | ---                                                    | ---                                                                                                                                                                                                      |
| latest_step_caller_raw_id / \_type / \_employee_no / \_auth_user_id | os_historystep.caller, same encoding                   | Who _invoked_ the step transition (e.g. who forwarded it) - distinct from owner, who _held_ it.                                                                                                          |
| ---                                                                 | ---                                                    | ---                                                                                                                                                                                                      |
| latest_step_remark_text                                             | workflow_remarks.remarks, matched via history_step_cid | The actual remark text tied to this specific step in the canonical workflow tables (as opposed to Penex's own cache above).                                                                              |
| ---                                                                 | ---                                                    | ---                                                                                                                                                                                                      |

## Duplicate / override signals

Anomaly-adjacent features Penex already computes - potentially strong inputs to the scorer directly.

| **Column**            | **Source**                         | **What it is**                                                        |
| --------------------- | ---------------------------------- | --------------------------------------------------------------------- |
| is_duplicate_flagged  | duplicates array non-empty         | Whether the system's own duplicate-bill detection flagged this claim. |
| ---                   | ---                                | ---                                                                   |
| duplicate_match_count | jsonb_array_length(duplicates)     | How many other claims it was flagged as a duplicate of.               |
| ---                   | ---                                | ---                                                                   |
| override_count        | jsonb_array_length(override_info)  | How many times this claim's amount/quantity was manually overridden.  |
| ---                   | ---                                | ---                                                                   |
| last_override_reason  | override_info\[-1\].overrideReason | Reason given for the most recent override.                            |
| ---                   | ---                                | ---                                                                   |
| last_overridden_at    | override_info\[-1\].overriddenAt   | When the most recent override happened.                               |
| ---                   | ---                                | ---                                                                   |

## Timestamps

| **Column**      | **Source**                     | **What it is**                              |
| --------------- | ------------------------------ | ------------------------------------------- |
| item_created_on | expense_report_item.created_on | When the claim line item was first created. |
| ---             | ---                            | ---                                         |
| item_updated_on | expense_report_item.updated_on | Last modification time.                     |
| ---             | ---                            | ---                                         |
| submission_date | expense_report.submission_date | When the parent report was submitted.       |
| ---             | ---                            | ---                                         |

## Filters applied in this version of the query

- configured_reviewer_count > 0 (via reviewer_chain.level_count, since SELECT-list aliases aren't visible in WHERE) - excludes claims under policies with no reviewer chain configured at all.
- item_status IN ('Accepted', 'Paid', 'Rejected') - keeps only claims with a definitive outcome, dropping in-flight states (Applied, Underway, Forwarded, Withdrawn).

## Open items / things to verify against real data before trusting at scale

- latest_step_owner_auth_user_id / latest_step_caller_auth_user_id are decoded but not joined to a name - need the auth-user table name (source not in this workspace) to finish that.
- workflow_remarks.history_step_cid = os_historystep.id is inferred from naming convention, not a documented FK constraint.
- latest_workflow_action_id needs the OSWorkflow XML descriptor to decode into Approve/Reject/Forward labels.
- clean up employee-id2
- remove name of expense type and category and replace id
- auto_approved check where is this coming and remove this 
