# Copyright (c) 2026, Shayona Technology and contributors
# For license information, please see license.txt

from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr, flt


class BrokerageSettlement(Document):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF

        allocated_amount: DF.Currency
        amended_from: DF.Link | None
        brokerage_reconciliation: DF.Link
        brokerage_statement: DF.Link | None
        difference_amount: DF.Currency
        match_method: DF.Literal["", "Exact Policy Number", "Formatted Policy Number", "Policy and Customer", "Customer and Dates", "Manual"]
        match_score: DF.Percent
        policy_expected_amount: DF.Currency
        policy_outstanding_before: DF.Currency
        policy_register: DF.Link | None
        remarks: DF.SmallText | None
        reverses_settlement: DF.Link | None
        settlement_date: DF.Date
        settlement_type: DF.Literal["", "Regular", "Write Off", "Adjustment", "Reversal"]
        statement_received_amount: DF.Currency
        statement_unallocated_before: DF.Currency
        write_off_amount: DF.Currency
    # end: auto-generated types

    # This settlement is created by Brokerage Reconciliation and updates both final balances.
    def validate(self):
        self._set_default_values()
        self._load_amount_snapshots()
        self._validate_supported_settlement_type()
        self._validate_linked_documents()
        self._validate_amounts()
        self._set_difference_amount()

    # This keeps Policy Register and Brokerage Statement balances correct after submit.
    def on_submit(self):
        recalculate_policy_register(self.policy_register)

        if self.brokerage_statement:
            recalculate_brokerage_statement(self.brokerage_statement)

    # This recalculates balances again when a settlement is cancelled.
    def on_cancel(self):
        recalculate_policy_register(self.policy_register)

        if self.brokerage_statement:
            recalculate_brokerage_statement(self.brokerage_statement)

    # This gives predictable default values before validation starts.
    def _set_default_values(self):
        if not self.settlement_type:
            self.settlement_type = "Regular"

        self.allocated_amount = flt(self.allocated_amount)
        self.write_off_amount = flt(self.write_off_amount)

    # This stores the current balances before the settlement is submitted.
    def _load_amount_snapshots(self):
        if self.policy_register:
            policy = frappe.get_doc("Policy Register", self.policy_register)
            self.policy_expected_amount = flt(policy.expected_brokerage)
            self.policy_outstanding_before = flt(policy.outstanding_brokerage)

        if self.brokerage_statement:
            statement = frappe.get_doc("Brokerage Statement", self.brokerage_statement)
            self.statement_received_amount = flt(statement.brokerage_received)
            self.statement_unallocated_before = flt(statement.unallocated_brokerage)

    # Phase 1 intentionally supports only normal allocation and write-off.

    # This keeps unsupported settlement types out of the current automatic workflow.
    def _validate_supported_settlement_type(self):
        if self.settlement_type in ("Adjustment", "Reversal"):
            frappe.throw(
                _("{0} settlement is not enabled yet.").format(self.settlement_type)
            )

    # This checks that linked final records are submitted and belong to the reconciliation.
    def _validate_linked_documents(self):
        if not self.brokerage_reconciliation:
            frappe.throw(_("Brokerage Reconciliation is required."))

        reconciliation = frappe.get_doc(
            "Brokerage Reconciliation",
            self.brokerage_reconciliation,
        )

        if not self.policy_register:
            frappe.throw(_("Policy Register is required."))

        policy = frappe.get_doc("Policy Register", self.policy_register)

        if policy.docstatus != 1:
            frappe.throw(_("Policy Register must be submitted."))

        if self.settlement_type == "Regular" and not self.brokerage_statement:
            frappe.throw(_("Brokerage Statement is required for Regular settlement."))

        if self.brokerage_statement:
            statement = frappe.get_doc("Brokerage Statement", self.brokerage_statement)

            if statement.docstatus != 1:
                frappe.throw(_("Brokerage Statement must be submitted."))

            if statement.insurer_name != reconciliation.insurer_name:
                frappe.throw(
                    _("Brokerage Statement insurer does not match the reconciliation.")
                )

        if not _policy_matches_reconciliation_insurer(
            policy.insurer_name,
            reconciliation.insurer_name,
        ):
            frappe.throw(
                _("Policy Register insurer does not match the reconciliation.")
            )

    # This protects against over-allocation and invalid write-off amounts.
    def _validate_amounts(self):
        if self.allocated_amount < 0:
            frappe.throw(_("Allocated Amount cannot be negative."))

        if self.write_off_amount < 0:
            frappe.throw(_("Write-off Amount cannot be negative."))

        if self.settlement_type == "Regular":
            if self.allocated_amount <= 0:
                frappe.throw(_("Allocated Amount must be greater than zero."))

            if self.allocated_amount > self.statement_unallocated_before:
                frappe.throw(
                    _("Allocated Amount cannot exceed Statement Unallocated Before.")
                )

        if self.settlement_type == "Write Off":
            if self.allocated_amount:
                frappe.throw(_("Allocated Amount must be zero for Write Off."))

            if self.write_off_amount <= 0:
                frappe.throw(_("Write-off Amount must be greater than zero."))

        total_policy_effect = self.allocated_amount + self.write_off_amount

        if total_policy_effect > self.policy_outstanding_before:
            frappe.throw(
                _(
                    "Allocated Amount plus Write-off Amount cannot exceed "
                    "Policy Outstanding Before."
                )
            )

        if self.write_off_amount and not cstr(self.remarks).strip():
            frappe.throw(_("Remarks are required when Write-off Amount is entered."))

    # This shows the remaining policy difference after this settlement.
    def _set_difference_amount(self):
        self.difference_amount = (
            flt(self.policy_outstanding_before)
            - flt(self.allocated_amount)
            - flt(self.write_off_amount)
        )


# This recalculates one Policy Register from submitted settlements.
def recalculate_policy_register(policy_register_name: str | None):
    if not policy_register_name:
        return

    policy = frappe.get_doc("Policy Register", policy_register_name)

    totals = frappe.db.get_all(
        "Brokerage Settlement",
        filters={
            "policy_register": policy_register_name,
            "docstatus": 1,
        },
        fields=[
            {"SUM": "allocated_amount", "as": "allocated"},
            {"SUM": "write_off_amount", "as": "written_off"},
        ],
    )[0]

    settled_brokerage = flt(totals.allocated)
    written_off_brokerage = flt(totals.written_off)
    expected_brokerage = flt(policy.expected_brokerage)
    outstanding_brokerage = (
        expected_brokerage - settled_brokerage - written_off_brokerage
    )

    frappe.db.set_value(
        "Policy Register",
        policy_register_name,
        {
            "settled_brokerage": settled_brokerage,
            "written_off_brokerage": written_off_brokerage,
            "has_write_off": 1 if written_off_brokerage else 0,
            "outstanding_brokerage": outstanding_brokerage,
            "reconciliation_status": _get_policy_reconciliation_status(
                expected_brokerage,
                settled_brokerage,
                written_off_brokerage,
                outstanding_brokerage,
            ),
        },
        update_modified=False,
    )


# This recalculates one Brokerage Statement from submitted settlements.
def recalculate_brokerage_statement(brokerage_statement_name: str | None):
    if not brokerage_statement_name:
        return

    statement = frappe.get_doc("Brokerage Statement", brokerage_statement_name)

    totals = frappe.db.get_all(
        "Brokerage Settlement",
        filters={
            "brokerage_statement": brokerage_statement_name,
            "docstatus": 1,
        },
        fields=[
            {"SUM": "allocated_amount", "as": "allocated"},
        ],
    )[0]

    allocated_brokerage = flt(totals.allocated)
    brokerage_received = flt(statement.brokerage_received)
    unallocated_brokerage = brokerage_received - allocated_brokerage

    frappe.db.set_value(
        "Brokerage Statement",
        brokerage_statement_name,
        {
            "allocated_brokerage": allocated_brokerage,
            "unallocated_brokerage": unallocated_brokerage,
            "reconciliation_status": _get_statement_reconciliation_status(
                brokerage_received,
                allocated_brokerage,
                unallocated_brokerage,
            ),
        },
        update_modified=False,
    )


# This decides the Policy Register status from current calculated balances.
def _get_policy_reconciliation_status(
    expected_brokerage: float,
    settled_brokerage: float,
    written_off_brokerage: float,
    outstanding_brokerage: float,
) -> str:
    if outstanding_brokerage <= 0:
        return "Fully Settled"

    if settled_brokerage or written_off_brokerage:
        return "Partially Settled"

    return "Pending"


# This decides the Brokerage Statement status from current calculated balances.
def _get_statement_reconciliation_status(
    brokerage_received: float,
    allocated_brokerage: float,
    unallocated_brokerage: float,
) -> str:
    if unallocated_brokerage == 0:
        return "Fully Allocated"

    if allocated_brokerage:
        return "Partially Allocated"

    return "Unallocated"


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


# This makes policy/company comparison ignore spaces, case and punctuation.
def _normalize_value(value) -> str:
    return re.sub(r"[^A-Z0-9]", "", cstr(value).upper().strip())
