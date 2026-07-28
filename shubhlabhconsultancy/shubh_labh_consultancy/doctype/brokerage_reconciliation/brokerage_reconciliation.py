# Copyright (c) 2026, Shayona Technology and contributors
# For license information, please see license.txt

from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr, flt, getdate, today

MONTH_NUMBER_BY_NAME = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}

MONTH_NAME_BY_NUMBER = {
    month_number: month_name for month_name, month_number in MONTH_NUMBER_BY_NAME.items()
}


class BrokerageReconciliation(Document):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF

        amended_from: DF.Link | None
        amount_tolerance: DF.Currency
        failed_records: DF.Int
        include_earlier_business: DF.Check
        insurer_name: DF.Link
        last_matching_completed_on: DF.Datetime | None
        last_matching_started_on: DF.Datetime | None
        reconciliation_date: DF.Date
        remarks: DF.SmallText | None
        settlements_submitted: DF.Int
        statement_month: DF.Date
        statements_checked: DF.Int
        status: DF.Literal[
            "",
            "Draft",
            "Matching",
            "Review Required",
            "Ready to Submit",
            "Completed",
            "Cancelled",
        ]
        unmatched_statements: DF.Int
    # end: auto-generated types

    # This keeps the reconciliation document in a predictable starting state.
    def validate(self):
        if not self.status:
            self.status = "Draft"

        self._set_statement_month_start_date()

        if flt(self.amount_tolerance) < 0:
            frappe.throw(_("Amount Tolerance cannot be negative."))

    # This stores Statement Month as the first date of the selected month.
    def _set_statement_month_start_date(self):
        statement_month = _get_month_start_date_from_fields(
            record=self,
            month_fieldname="statement_month_select",
            year_fieldname="statement_year",
            date_fieldname="statement_month",
            label="Statement Month",
            required=True,
        )

        if not statement_month:
            return

        self.statement_month = statement_month
        self.statement_month_select = MONTH_NAME_BY_NUMBER[statement_month.month]
        self.statement_year = statement_month.year

    # This confirms the reconciliation after automatic settlements are already submitted.
    def on_submit(self):
        submitted_settlements = frappe.get_all(
            "Brokerage Settlement",
            filters={
                "brokerage_reconciliation": self.name,
                "docstatus": 1,
            },
            pluck="name",
        )

        if not submitted_settlements:
            frappe.throw(_("No submitted Brokerage Settlements were found."))

        self.db_set("status", "Completed", update_modified=False)

    # This cancels submitted settlements when reconciliation is cancelled.
    def on_cancel(self):
        settlement_names = frappe.get_all(
            "Brokerage Settlement",
            filters={
                "brokerage_reconciliation": self.name,
                "docstatus": 1,
            },
            pluck="name",
            order_by="creation desc",
        )

        for settlement_name in settlement_names:
            settlement = frappe.get_doc("Brokerage Settlement", settlement_name)
            settlement.flags.ignore_permissions = True
            settlement.cancel()

        self.db_set("status", "Cancelled", update_modified=False)


# This queues matching so large reconciliations do not block the browser request.
@frappe.whitelist()
def enqueue_generate_matches(reconciliation_name: str):
    reconciliation = frappe.get_doc("Brokerage Reconciliation", reconciliation_name)

    _validate_generate_match_permissions(reconciliation)
    _validate_reconciliation_can_generate(reconciliation)
    _delete_existing_draft_settlements(reconciliation.name)

    frappe.db.set_value(
        "Brokerage Reconciliation",
        reconciliation.name,
        "status",
        "Matching",
        update_modified=False,
    )

    requested_by = frappe.session.user

    frappe.enqueue(
        run_generate_matches,
        queue="long",
        timeout=1500,
        enqueue_after_commit=True,
        reconciliation_name=reconciliation.name,
        requested_by=requested_by,
    )

    return {
        "queued": True,
        "message": _("Reconciliation matching has started in the background."),
    }


# This background job creates and submits settlement suggestions.
def run_generate_matches(reconciliation_name: str, requested_by: str):
    summary = {
        "action": "matching",
        "reconciliation_name": reconciliation_name,
        "total_statements": 0,
        "created": 0,
        "unmatched": 0,
        "failed": 0,
    }

    savepoint = "brokerage_reconciliation_matching"
    frappe.db.savepoint(savepoint)

    try:
        reconciliation = frappe.get_doc("Brokerage Reconciliation", reconciliation_name)

        frappe.db.set_value(
            "Brokerage Reconciliation",
            reconciliation.name,
            {
                "last_matching_started_on": frappe.utils.now(),
                "statements_checked": 0,
                "settlements_submitted": 0,
                "unmatched_statements": 0,
                "failed_records": 0,
            },
            update_modified=False,
        )

        match_summary = _generate_match_suggestions(reconciliation)
        summary.update(match_summary)

        final_status = "Completed" if summary["created"] else "Draft"

        frappe.db.set_value(
            "Brokerage Reconciliation",
            reconciliation.name,
            {
                "status": final_status,
                "last_matching_completed_on": frappe.utils.now(),
                "statements_checked": summary["total_statements"],
                "settlements_submitted": summary["created"],
                "unmatched_statements": summary["unmatched"],
                "failed_records": summary["failed"],
            },
            update_modified=False,
        )

        if summary["created"]:
            _submit_reconciliation_after_matching(reconciliation.name)

    except Exception:
        frappe.db.rollback(save_point=savepoint)

        frappe.db.set_value(
            "Brokerage Reconciliation",
            reconciliation_name,
            {
                "status": "Draft",
                "last_matching_completed_on": frappe.utils.now(),
                "failed_records": 1,
            },
            update_modified=False,
        )

        frappe.log_error(
            title=f"Brokerage Reconciliation matching failed: {reconciliation_name}",
            message=frappe.get_traceback(),
        )

        summary["failed"] = 1

    frappe.db.commit()

    frappe.publish_realtime(
        "brokerage_reconciliation_job_complete",
        summary,
        user=requested_by,
    )


# This submits the reconciliation document after its settlements are already submitted.
def _submit_reconciliation_after_matching(reconciliation_name: str):
    reconciliation = frappe.get_doc("Brokerage Reconciliation", reconciliation_name)

    if reconciliation.docstatus != 0:
        return

    reconciliation.flags.ignore_permissions = True
    reconciliation.submit()


# This runs all matching methods and creates draft settlement suggestions.
def _generate_match_suggestions(reconciliation: Document) -> dict:
    statements = _get_available_statements(reconciliation)
    policies_by_policy_number = _get_available_policies_by_policy_number(reconciliation)

    summary = {
        "total_statements": len(statements),
        "created": 0,
        "unmatched": 0,
    }

    for statement in statements:
        statement_remaining = flt(statement.unallocated_brokerage)
        match_result = _find_statement_match(statement, policies_by_policy_number)

        if not match_result:
            summary["unmatched"] += 1
            continue

        created_for_statement = 0

        for policy in match_result["policies"]:
            if statement_remaining <= 0:
                break

            policy_remaining = flt(policy.outstanding_brokerage)

            if policy_remaining <= 0:
                continue

            settlement_amounts = _get_suggested_settlement_amounts(
                reconciliation=reconciliation,
                policy_remaining=policy_remaining,
                statement_remaining=statement_remaining,
            )

            _create_draft_settlement(
                reconciliation=reconciliation,
                policy=policy,
                statement=statement,
                allocated_amount=settlement_amounts["allocated_amount"],
                write_off_amount=settlement_amounts["write_off_amount"],
                remarks=settlement_amounts["remarks"],
                match_method=match_result["match_method"],
                match_score=match_result["match_score"],
            )

            summary["created"] += 1
            created_for_statement += 1
            statement_remaining -= settlement_amounts["allocated_amount"]
            policy.outstanding_brokerage = (
                policy_remaining
                - settlement_amounts["allocated_amount"]
                - settlement_amounts["write_off_amount"]
            )

        if not created_for_statement:
            summary["unmatched"] += 1

    return summary


# This suggests allocation and small write-off amounts from the reconciliation tolerance.
def _get_suggested_settlement_amounts(
    reconciliation: Document,
    policy_remaining: float,
    statement_remaining: float,
) -> dict:
    allocated_amount = min(policy_remaining, statement_remaining)
    write_off_amount = 0
    remarks = ""

    policy_balance_after_allocation = policy_remaining - allocated_amount
    amount_tolerance = flt(reconciliation.amount_tolerance)

    # This closes small policy differences when they are within the configured tolerance.
    if (
        allocated_amount > 0
        and policy_balance_after_allocation > 0
        and amount_tolerance > 0
        and policy_balance_after_allocation <= amount_tolerance
    ):
        write_off_amount = policy_balance_after_allocation
        remarks = _("Auto write-off within amount tolerance.")

    return {
        "allocated_amount": allocated_amount,
        "write_off_amount": write_off_amount,
        "remarks": remarks,
    }


# This checks matching methods one by one and returns the first valid match.
def _find_statement_match(statement, policies_by_policy_number: dict) -> dict | None:
    for matching_method in _get_matching_methods():
        match_result = matching_method(statement, policies_by_policy_number)

        if match_result:
            return match_result

    return None


# This keeps the matching order in one place for future methods.
def _get_matching_methods() -> tuple:
    return (_match_exact_policy_number,)


# This matches statement and policy using exact normalized policy number.
def _match_exact_policy_number(
    statement, policies_by_policy_number: dict
) -> dict | None:
    normalized_statement_policy = _normalize_value(statement.policy_number)

    if not normalized_statement_policy:
        return None

    matching_policies = policies_by_policy_number.get(normalized_statement_policy, [])

    if not matching_policies:
        return None

    return {
        "policies": matching_policies,
        "match_method": "Exact Policy Number",
        "match_score": 100,
    }


# This creates one settlement and submits it so balances update immediately.
def _create_draft_settlement(
    reconciliation: Document,
    policy,
    statement,
    allocated_amount: float,
    write_off_amount: float = 0,
    remarks: str = "",
    match_method: str = "Exact Policy Number",
    match_score: float = 100,
):
    settlement = frappe.get_doc(
        {
            "doctype": "Brokerage Settlement",
            "brokerage_reconciliation": reconciliation.name,
            "settlement_date": reconciliation.reconciliation_date or today(),
            "settlement_type": "Regular",
            "policy_register": policy.name,
            "brokerage_statement": statement.name,
            "allocated_amount": allocated_amount,
            "write_off_amount": write_off_amount,
            "match_method": match_method,
            "match_score": match_score,
            "remarks": remarks,
        }
    )

    settlement.flags.ignore_permissions = True
    settlement.insert()
    settlement.submit()

    return settlement


# This loads submitted Brokerage Statements with unallocated brokerage.
def _get_available_statements(reconciliation: Document) -> list:
    return frappe.get_all(
        "Brokerage Statement",
        filters={
            "docstatus": 1,
            "insurer_name": reconciliation.insurer_name,
            "statement_month": reconciliation.statement_month,
            "unallocated_brokerage": [">", 0],
        },
        fields=[
            "name",
            "policy_number",
            "insurer_name",
            "customer_name",
            "start_date",
            "expiry_date",
            "brokerage_received",
            "unallocated_brokerage",
        ],
        order_by="creation asc",
    )


# This loads submitted Policy Registers and groups them by normalized policy number.
def _get_available_policies_by_policy_number(
    reconciliation: Document,
) -> dict[str, list]:
    filters = {
        "docstatus": 1,
        "outstanding_brokerage": [">", 0],
    }

    if reconciliation.include_earlier_business:
        filters["business_month"] = ["<=", reconciliation.statement_month]
    else:
        filters["business_month"] = reconciliation.statement_month

    policies = frappe.get_all(
        "Policy Register",
        filters=filters,
        fields=[
            "name",
            "policy_number",
            "insurer_name",
            "customer_name",
            "start_date",
            "expiry_date",
            "business_month",
            "expected_brokerage",
            "outstanding_brokerage",
        ],
        order_by="business_month asc, creation asc",
    )

    policies_by_policy_number: dict[str, list] = {}

    for policy in policies:
        if not _policy_matches_reconciliation_insurer(
            policy.insurer_name,
            reconciliation.insurer_name,
        ):
            continue

        normalized_policy_number = _normalize_value(policy.policy_number)

        if not normalized_policy_number:
            continue

        policies_by_policy_number.setdefault(normalized_policy_number, []).append(
            policy
        )

    return policies_by_policy_number


# This prevents duplicate generated draft settlements before a fresh matching run.
def _delete_existing_draft_settlements(reconciliation_name: str):
    submitted_settlements = frappe.get_all(
        "Brokerage Settlement",
        filters={
            "brokerage_reconciliation": reconciliation_name,
            "docstatus": 1,
        },
        pluck="name",
    )

    if submitted_settlements:
        frappe.throw(
            _(
                "This reconciliation already has submitted settlements. "
                "Cancel the reconciliation before generating matches again."
            )
        )

    draft_settlements = frappe.get_all(
        "Brokerage Settlement",
        filters={
            "brokerage_reconciliation": reconciliation_name,
            "docstatus": 0,
        },
        pluck="name",
    )

    for settlement_name in draft_settlements:
        frappe.delete_doc(
            "Brokerage Settlement",
            settlement_name,
            ignore_permissions=True,
        )


# This checks basic state before matching is generated.
def _validate_reconciliation_can_generate(reconciliation: Document):
    if reconciliation.docstatus != 0:
        frappe.throw(_("Matches can be generated only for a draft reconciliation."))

    if not reconciliation.insurer_name:
        frappe.throw(_("Insurer Name is required."))

    if not reconciliation.statement_month:
        frappe.throw(_("Statement Month is required."))


# This checks user permissions before automatic settlement records are created and submitted.
def _validate_generate_match_permissions(reconciliation: Document):
    if not frappe.has_permission(
        "Brokerage Reconciliation", ptype="write", doc=reconciliation
    ):
        frappe.throw(
            _("You do not have permission to update this Brokerage Reconciliation."),
            frappe.PermissionError,
        )

    if not frappe.has_permission("Brokerage Settlement", ptype="create"):
        frappe.throw(
            _("You do not have permission to create Brokerage Settlement records."),
            frappe.PermissionError,
        )

    if not frappe.has_permission("Brokerage Settlement", ptype="submit"):
        frappe.throw(
            _("You do not have permission to submit Brokerage Settlement records."),
            frappe.PermissionError,
        )


# This matches raw Policy Register insurer text with the selected Insurer master.
def _policy_matches_reconciliation_insurer(
    policy_insurer_name: str | None,
    reconciliation_insurer: str | None,
) -> bool:
    if not reconciliation_insurer:
        return False

    insurer_values = frappe.db.get_value(
        "Insurer",
        reconciliation_insurer,
        ["name", "insurer_name", "short_name", "insurer_code"],
        as_dict=True,
    )

    allowed_values = {
        _normalize_value(value)
        for value in (insurer_values or {}).values()
        if cstr(value).strip()
    }

    return _normalize_value(policy_insurer_name) in allowed_values


# This returns the first date of a month from Month/Year fields or an existing Date field.
def _get_month_start_date_from_fields(
    record: Document,
    month_fieldname: str,
    year_fieldname: str,
    date_fieldname: str,
    label: str,
    required: bool,
):
    month_name = cstr(record.get(month_fieldname)).strip()
    year = record.get(year_fieldname)

    if month_name or year:
        if not month_name or not year:
            frappe.throw(_("{0} and Year are required together.").format(label))

        month_number = MONTH_NUMBER_BY_NAME.get(month_name)

        if not month_number:
            frappe.throw(_("{0} is invalid.").format(label))

        try:
            year = int(year)
        except (TypeError, ValueError):
            frappe.throw(_("{0} Year must contain a valid year.").format(label))

        return getdate(f"{year}-{month_number:02d}-01")

    date_value = record.get(date_fieldname)

    if date_value in (None, ""):
        if required:
            frappe.throw(_("{0} is required.").format(label))

        return None

    try:
        date_value = getdate(date_value)
    except Exception:
        frappe.throw(_("{0} must contain a valid date.").format(label))

    return date_value.replace(day=1)


# This makes policy/company comparison ignore spaces, case and punctuation.
def _normalize_value(value) -> str:
    return re.sub(r"[^A-Z0-9]", "", cstr(value).upper().strip())
