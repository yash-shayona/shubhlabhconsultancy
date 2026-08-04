# Copyright (c) 2026, Shayona Technology and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt, nowdate

from shubhlabhconsultancy.shubh_labh_consultancy.doctype.brokerage_reconciliation.brokerage_reconciliation import (
    MONTH_NUMBER_BY_NAME,
    enqueue_generate_matches,
    enqueue_generate_write_offs,
)

from shubhlabhconsultancy.permissions.reconciliation_portal import (
    require_brokerage_reconciliation_tool_access,
)


# This creates one reconciliation audit document and starts the selected tool action.
@frappe.whitelist()
def start_reconciliation(
    action: str,
    insurer_name: str,
    statement_month_select: str,
    statement_year: int,
    reconciliation_date: str | None = None,
    include_earlier_business: int = 1,
    amount_tolerance: float = 0,
):
    # This keeps the Desk action and website action under the same role restriction.
    require_brokerage_reconciliation_tool_access()
    
    if action not in ("match", "write_off"):
        frappe.throw(_("Invalid reconciliation action."))

    reconciliation = _create_reconciliation_document(
        insurer_name=insurer_name,
        statement_month_select=statement_month_select,
        statement_year=statement_year,
        reconciliation_date=reconciliation_date,
        include_earlier_business=include_earlier_business,
        amount_tolerance=amount_tolerance,
    )

    if action == "write_off":
        queue_result = enqueue_generate_write_offs(reconciliation.name)
    else:
        queue_result = enqueue_generate_matches(reconciliation.name)

    return {
        "reconciliation_name": reconciliation.name,
        "queued": queue_result.get("queued"),
        "message": queue_result.get("message"),
    }


# This stores the page inputs in the normal Brokerage Reconciliation DocType.
def _create_reconciliation_document(
    insurer_name: str,
    statement_month_select: str,
    statement_year: int,
    reconciliation_date: str | None,
    include_earlier_business: int,
    amount_tolerance: float,
):
    statement_month = _get_statement_month_date(
        statement_month_select=statement_month_select,
        statement_year=statement_year,
    )

    reconciliation = frappe.get_doc(
        {
            "doctype": "Brokerage Reconciliation",
            "insurer_name": insurer_name,
            "statement_month_select": statement_month_select,
            "statement_year": cint(statement_year),
            "statement_month": statement_month,
            "reconciliation_date": reconciliation_date or nowdate(),
            "include_earlier_business": cint(include_earlier_business),
            "amount_tolerance": flt(amount_tolerance),
            "status": "Draft",
        }
    )

    reconciliation.insert()

    return reconciliation


# This converts Month and Year page inputs into the first date of that month.
def _get_statement_month_date(statement_month_select: str, statement_year: int) -> str:
    if not statement_month_select:
        frappe.throw(_("Statement Month is required."))

    if not cint(statement_year):
        frappe.throw(_("Statement Year is required."))

    month_number = MONTH_NUMBER_BY_NAME.get(statement_month_select)

    if not month_number:
        frappe.throw(_("Invalid Statement Month."))

    return f"{cint(statement_year)}-{month_number:02d}-01"
