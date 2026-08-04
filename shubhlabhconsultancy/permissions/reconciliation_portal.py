from __future__ import annotations

import frappe
from frappe import _

# This keeps the website tool access identical to the existing Desk Page access.
BROKERAGE_RECONCILIATION_TOOL_ALLOWED_ROLES = frozenset({"System Manager"})

# These fields are safe to return to the page when it restores one of the user's runs.
RECONCILIATION_STATUS_FIELDS = [
    "name",
    "status",
    "docstatus",
    "insurer_name",
    "statement_month",
    "reconciliation_date",
    "last_matching_started_on",
    "last_matching_completed_on",
    "statements_checked",
    "settlements_submitted",
    "unmatched_statements",
    "failed_records",
    "creation",
]


# This verifies that the logged-in user may open or call the reconciliation website tool.
def require_brokerage_reconciliation_tool_access(user: str | None = None):
    user = user or frappe.session.user

    if user == "Guest":
        frappe.throw(_("Please login to continue."), frappe.PermissionError)

    # Administrator is always allowed to use this controlled financial tool.
    if user == "Administrator":
        return

    user_roles = set(frappe.get_roles(user))

    if user_roles & BROKERAGE_RECONCILIATION_TOOL_ALLOWED_ROLES:
        return

    frappe.throw(
        _("You do not have permission to access Brokerage Reconciliation Tool."),
        frappe.PermissionError,
    )


# This returns only active insurers for the website dropdown.
@frappe.whitelist()
def get_enabled_insurers():
    require_brokerage_reconciliation_tool_access()

    return frappe.get_list(
        "Insurer",
        filters={"enabled": 1},
        fields=["name", "insurer_name", "short_name"],
        order_by="insurer_name asc",
        limit_page_length=500,
    )


# This restores the latest reconciliation started by the current user after a refresh.
@frappe.whitelist()
def get_reconciliation_status(reconciliation_name: str | None = None):
    user = frappe.session.user
    require_brokerage_reconciliation_tool_access(user)

    # Limiting by owner keeps this website page focused on the current user's own runs.
    filters = {"owner": user}

    if reconciliation_name:
        filters["name"] = reconciliation_name

    reconciliation_rows = frappe.get_list(
        "Brokerage Reconciliation",
        filters=filters,
        fields=RECONCILIATION_STATUS_FIELDS,
        order_by="creation desc",
        limit_page_length=1,
    )

    reconciliation = reconciliation_rows[0] if reconciliation_rows else None

    if not reconciliation:
        return {"reconciliation": None}

    # Matching is the only active processing status in the current backend workflow.
    is_processing = reconciliation.status == "Matching"

    # A completed timestamp distinguishes a completed zero-settlement run from a new Draft.
    is_finished = bool(reconciliation.last_matching_completed_on)

    return {
        "reconciliation": reconciliation,
        "is_processing": is_processing,
        "is_finished": is_finished,
    }
