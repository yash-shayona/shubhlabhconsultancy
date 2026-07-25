# Copyright (c) 2026, Shayona Technology and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime

ALLOCATION_DOCTYPE = "Brokerage Allocation"
STATEMENT_DOCTYPE = "Brokerage Statement"
POLICY_DOCTYPE = "Policy Register"

MONEY_PRECISION = 4
AMOUNT_TOLERANCE = 0.0001


class BrokerageAllocation(Document):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF

        allocated_amount: DF.Currency
        allocated_by: DF.Link | None
        allocated_on: DF.Datetime | None
        allocation_status: DF.Literal["", "Draft", "Allocated", "Reversed", "Cancelled"]
        amended_from: DF.Link | None
        brokerage_statement: DF.Link
        is_reversal: DF.Check
        match_details: DF.SmallText | None
        match_method: DF.Literal["", "Exact Policy & Endorsement", "Exact Policy", "Scored Match", "Manual Match"]
        match_score: DF.Percent
        policy_register: DF.Link
        reverses_allocation: DF.Link | None
    # end: auto-generated types

    """
    One allocation connects:

        Brokerage Statement
                ↓
        Brokerage Allocation
                ↓
        Policy Register

    Allocated Amount is always entered as a positive value.

    For reversal:
    - is_reversal = 1
    - allocated_amount remains positive
    - controller applies it as a negative accounting effect
    """

    def before_insert(self):
        if not self.allocation_status:
            self.allocation_status = "Draft"

    def validate(self):
        self._validate_amount()
        self._validate_linked_documents()
        self._validate_match_score()
        self._validate_reversal()
        self._validate_available_balances()

    def before_submit(self):
        # Concurrent submissions ke against linked balance rows lock honge.
        self._lock_linked_rows()

        # Lock ke baad fresh values par validations repeat karte hain.
        self._validate_linked_documents()
        self._validate_reversal()
        self._validate_available_balances()

        self.allocation_status = "Reversed" if self.is_reversal else "Allocated"

        self.allocated_by = frappe.session.user
        self.allocated_on = now_datetime()

    def on_submit(self):
        recalculate_brokerage_statement(self.brokerage_statement)

        recalculate_policy_register(self.policy_register)

    def on_cancel(self):
        frappe.db.set_value(
            ALLOCATION_DOCTYPE,
            self.name,
            "allocation_status",
            "Cancelled",
            update_modified=False,
        )

        recalculate_brokerage_statement(self.brokerage_statement)

        recalculate_policy_register(self.policy_register)

    # ------------------------------------------------------------------
    # VALIDATIONS
    # ------------------------------------------------------------------

    def _validate_amount(self):
        allocated_amount = flt(
            self.allocated_amount,
            MONEY_PRECISION,
        )

        if allocated_amount <= 0:
            frappe.throw(_("Allocated Amount must be greater than zero."))

        self.allocated_amount = allocated_amount

    def _validate_linked_documents(self):
        statement = _get_statement_values(self.brokerage_statement)

        policy = _get_policy_values(self.policy_register)

        if not statement:
            frappe.throw(_("Brokerage Statement does not exist."))

        if not policy:
            frappe.throw(_("Policy Register does not exist."))

        if statement.docstatus != 1:
            frappe.throw(
                _(
                    "Brokerage Statement {0} must be submitted " "before allocation."
                ).format(self.brokerage_statement)
            )

        if policy.docstatus != 1:
            frappe.throw(
                _("Policy Register {0} must be submitted " "before allocation.").format(
                    self.policy_register
                )
            )

    def _validate_match_score(self):
        if self.match_score in (None, ""):
            return

        match_score = flt(self.match_score)

        if match_score < 0 or match_score > 100:
            frappe.throw(_("Match Score must be between 0 and 100."))

    def _validate_reversal(self):
        if not self.is_reversal:
            if self.reverses_allocation:
                frappe.throw(
                    _(
                        "Reverses Allocation must remain blank "
                        "for a normal allocation."
                    )
                )

            return

        if not self.reverses_allocation:
            frappe.throw(
                _("Reverses Allocation is required for " "a reversal allocation.")
            )

        original = frappe.db.get_value(
            ALLOCATION_DOCTYPE,
            self.reverses_allocation,
            [
                "name",
                "docstatus",
                "is_reversal",
                "policy_register",
                "brokerage_statement",
                "allocated_amount",
            ],
            as_dict=True,
        )

        if not original:
            frappe.throw(_("Original Brokerage Allocation does not exist."))

        if original.docstatus != 1:
            frappe.throw(
                _("Original Brokerage Allocation {0} " "must be submitted.").format(
                    original.name
                )
            )

        if original.is_reversal:
            frappe.throw(
                _(
                    "A reversal allocation cannot reverse "
                    "another reversal allocation."
                )
            )

        if original.policy_register != self.policy_register:
            frappe.throw(
                _(
                    "Reversal must use the same Policy Register "
                    "as the original allocation."
                )
            )

        if original.brokerage_statement == self.brokerage_statement:
            frappe.throw(
                _(
                    "Reversal must use the new negative Brokerage "
                    "Statement, not the original statement."
                )
            )

        current_statement = _get_statement_values(self.brokerage_statement)

        if (
            flt(
                current_statement.brokerage_received,
                MONEY_PRECISION,
            )
            >= 0
        ):
            frappe.throw(
                _(
                    "A reversal allocation must be linked to a "
                    "Brokerage Statement having negative "
                    "Brokerage Received."
                )
            )

        already_reversed = _get_already_reversed_amount(
            original_allocation=original.name,
            exclude_allocation=self.name,
        )

        reversible_amount = flt(
            flt(
                original.allocated_amount,
                MONEY_PRECISION,
            )
            - already_reversed,
            MONEY_PRECISION,
        )

        if reversible_amount <= AMOUNT_TOLERANCE:
            frappe.throw(
                _("Original allocation {0} is already " "fully reversed.").format(
                    original.name
                )
            )

        if (
            flt(
                self.allocated_amount,
                MONEY_PRECISION,
            )
            > reversible_amount + AMOUNT_TOLERANCE
        ):
            frappe.throw(
                _(
                    "Reversal Amount cannot exceed the remaining "
                    "reversible amount of {0}."
                ).format(reversible_amount)
            )

    def _validate_available_balances(self):
        statement = _get_statement_values(self.brokerage_statement)

        policy = _get_policy_values(self.policy_register)

        allocated_amount = flt(
            self.allocated_amount,
            MONEY_PRECISION,
        )

        statement_unallocated = flt(
            statement.unallocated_brokerage,
            MONEY_PRECISION,
        )

        policy_outstanding = flt(
            policy.outstanding_brokerage,
            MONEY_PRECISION,
        )

        if self.is_reversal:
            if statement_unallocated >= -AMOUNT_TOLERANCE:
                frappe.throw(
                    _(
                        "The selected reversal Brokerage Statement "
                        "does not have a negative unallocated balance."
                    )
                )

            available_reversal_amount = abs(statement_unallocated)

            if allocated_amount > available_reversal_amount + AMOUNT_TOLERANCE:
                frappe.throw(
                    _(
                        "Reversal Amount cannot exceed the negative "
                        "statement balance of {0}."
                    ).format(available_reversal_amount)
                )

            # Reversal policy outstanding ko increase karta hai,
            # isliye normal outstanding limit yahan apply nahi hogi.
            return

        if statement_unallocated <= AMOUNT_TOLERANCE:
            frappe.throw(
                _(
                    "Brokerage Statement {0} has no unallocated " "brokerage available."
                ).format(self.brokerage_statement)
            )

        if policy_outstanding <= AMOUNT_TOLERANCE:
            frappe.throw(
                _(
                    "Policy Register {0} has no outstanding " "brokerage available."
                ).format(self.policy_register)
            )

        if allocated_amount > statement_unallocated + AMOUNT_TOLERANCE:
            frappe.throw(
                _(
                    "Allocated Amount cannot exceed the statement "
                    "unallocated balance of {0}."
                ).format(statement_unallocated)
            )

        if allocated_amount > policy_outstanding + AMOUNT_TOLERANCE:
            frappe.throw(
                _(
                    "Allocated Amount cannot exceed the policy "
                    "outstanding balance of {0}."
                ).format(policy_outstanding)
            )

    # ------------------------------------------------------------------
    # CONCURRENCY PROTECTION
    # ------------------------------------------------------------------

    def _lock_linked_rows(self):
        _lock_document_row(
            STATEMENT_DOCTYPE,
            self.brokerage_statement,
        )

        _lock_document_row(
            POLICY_DOCTYPE,
            self.policy_register,
        )

        if self.reverses_allocation:
            _lock_document_row(
                ALLOCATION_DOCTYPE,
                self.reverses_allocation,
            )


# ----------------------------------------------------------------------
# RECALCULATION: BROKERAGE STATEMENT
# ----------------------------------------------------------------------


def recalculate_brokerage_statement(
    brokerage_statement: str,
):
    statement = _get_statement_values(brokerage_statement)

    if not statement:
        return

    allocations = frappe.get_all(
        ALLOCATION_DOCTYPE,
        filters={
            "brokerage_statement": brokerage_statement,
            "docstatus": 1,
        },
        fields=[
            "allocated_amount",
            "is_reversal",
        ],
    )

    allocated_brokerage = flt(
        sum(_get_signed_allocation_amount(row) for row in allocations),
        MONEY_PRECISION,
    )

    brokerage_received = flt(
        statement.brokerage_received,
        MONEY_PRECISION,
    )

    unallocated_brokerage = flt(
        brokerage_received - allocated_brokerage,
        MONEY_PRECISION,
    )

    reconciliation_status = _get_statement_reconciliation_status(
        brokerage_received=brokerage_received,
        allocated_brokerage=allocated_brokerage,
        unallocated_brokerage=unallocated_brokerage,
        allocations=allocations,
    )

    frappe.db.set_value(
        STATEMENT_DOCTYPE,
        brokerage_statement,
        {
            "allocated_brokerage": allocated_brokerage,
            "unallocated_brokerage": unallocated_brokerage,
            "reconciliation_status": (reconciliation_status),
        },
        update_modified=False,
    )


def _get_statement_reconciliation_status(
    brokerage_received: float,
    allocated_brokerage: float,
    unallocated_brokerage: float,
    allocations: list,
) -> str:
    has_reversal = any(row.is_reversal for row in allocations)

    if brokerage_received < -AMOUNT_TOLERANCE or has_reversal:
        return "Reversed"

    if not allocations or abs(allocated_brokerage) <= AMOUNT_TOLERANCE:
        return "Unallocated"

    if abs(unallocated_brokerage) <= AMOUNT_TOLERANCE:
        return "Fully Allocated"

    if unallocated_brokerage > AMOUNT_TOLERANCE:
        return "Partially Allocated"

    return "Disputed"


# ----------------------------------------------------------------------
# RECALCULATION: POLICY REGISTER
# ----------------------------------------------------------------------


def recalculate_policy_register(
    policy_register: str,
):
    policy = _get_policy_values(policy_register)

    if not policy:
        return

    allocations = frappe.get_all(
        ALLOCATION_DOCTYPE,
        filters={
            "policy_register": policy_register,
            "docstatus": 1,
        },
        fields=[
            "allocated_amount",
            "is_reversal",
        ],
    )

    settled_brokerage = flt(
        sum(_get_signed_allocation_amount(row) for row in allocations),
        MONEY_PRECISION,
    )

    expected_brokerage = flt(
        policy.expected_brokerage,
        MONEY_PRECISION,
    )

    # Current simplified Brokerage Allocation DocType me
    # Write-off Amount field nahi hai, isliye existing value preserve hogi.
    written_off_brokerage = flt(
        policy.written_off_brokerage,
        MONEY_PRECISION,
    )

    outstanding_brokerage = flt(
        expected_brokerage - settled_brokerage - written_off_brokerage,
        MONEY_PRECISION,
    )

    reconciliation_status = _get_policy_reconciliation_status(
        settled_brokerage=settled_brokerage,
        written_off_brokerage=written_off_brokerage,
        outstanding_brokerage=outstanding_brokerage,
        allocations=allocations,
    )

    frappe.db.set_value(
        POLICY_DOCTYPE,
        policy_register,
        {
            "settled_brokerage": settled_brokerage,
            "outstanding_brokerage": (outstanding_brokerage),
            "reconciliation_status": (reconciliation_status),
        },
        update_modified=False,
    )


def _get_policy_reconciliation_status(
    settled_brokerage: float,
    written_off_brokerage: float,
    outstanding_brokerage: float,
    allocations: list,
) -> str:
    has_reversal = any(row.is_reversal for row in allocations)

    if outstanding_brokerage < -AMOUNT_TOLERANCE:
        return "Excess Received"

    if abs(outstanding_brokerage) <= AMOUNT_TOLERANCE:
        if written_off_brokerage > AMOUNT_TOLERANCE:
            return "Written Off"

        return "Fully Settled"

    if settled_brokerage > AMOUNT_TOLERANCE:
        return "Partially Settled"

    if written_off_brokerage > AMOUNT_TOLERANCE:
        return "Partially Settled"

    if has_reversal:
        return "Reversed"

    return "Pending"


# ----------------------------------------------------------------------
# DATA HELPERS
# ----------------------------------------------------------------------


def _get_statement_values(
    brokerage_statement: str,
):
    if not brokerage_statement:
        return None

    return frappe.db.get_value(
        STATEMENT_DOCTYPE,
        brokerage_statement,
        [
            "name",
            "docstatus",
            "brokerage_received",
            "allocated_brokerage",
            "unallocated_brokerage",
            "reconciliation_status",
        ],
        as_dict=True,
    )


def _get_policy_values(
    policy_register: str,
):
    if not policy_register:
        return None

    return frappe.db.get_value(
        POLICY_DOCTYPE,
        policy_register,
        [
            "name",
            "docstatus",
            "expected_brokerage",
            "settled_brokerage",
            "written_off_brokerage",
            "outstanding_brokerage",
            "reconciliation_status",
        ],
        as_dict=True,
    )


def _get_signed_allocation_amount(row) -> float:
    allocated_amount = flt(
        row.allocated_amount,
        MONEY_PRECISION,
    )

    if row.is_reversal:
        return -allocated_amount

    return allocated_amount


def _get_already_reversed_amount(
    original_allocation: str,
    exclude_allocation: str | None = None,
) -> float:
    filters = {
        "reverses_allocation": original_allocation,
        "is_reversal": 1,
        "docstatus": 1,
    }

    if exclude_allocation:
        filters["name"] = [
            "!=",
            exclude_allocation,
        ]

    reversal_allocations = frappe.get_all(
        ALLOCATION_DOCTYPE,
        filters=filters,
        pluck="allocated_amount",
    )

    return flt(
        sum(flt(amount, MONEY_PRECISION) for amount in reversal_allocations),
        MONEY_PRECISION,
    )


def _lock_document_row(
    doctype: str,
    document_name: str,
):
    if not document_name:
        return

    frappe.db.sql(
        f"""
        SELECT name
        FROM `tab{doctype}`
        WHERE name = %s
        FOR UPDATE
        """,
        document_name,
    )
