# Copyright (c) 2026, Shayona Technology and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BrokerageStatement(Document):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF

        allocated_brokerage: DF.Currency
        amended_from: DF.Link | None
        brokerage_received: DF.Currency
        customer_name: DF.Data | None
        expiry_date: DF.Date | None
        insurer_name: DF.Link | None
        policy_number: DF.Data | None
        reconciliation_status: DF.Literal["", "Unallocated", "Partially Allocated", "Fully Allocated", "On Account", "Disputed", "Reversed"]
        source_data_import: DF.Link | None
        source_staging: DF.Link
        start_date: DF.Date | None
        statement_month: DF.Date | None
        unallocated_brokerage: DF.Currency
    # end: auto-generated types

    def on_trash(self):
        staging_records = frappe.get_all(
            "Brokerage Statement Staging",
            filters={
                "posted_brokerage_statement": self.name,
            },
            pluck="name",
        )

        for staging_name in staging_records:
            frappe.db.set_value(
                "Brokerage Statement Staging",
                staging_name,
                {
                    # Remove final document reference
                    "posted_brokerage_statement": None,
                    # Send the staging row back for validation
                    "validation_status": "Pending",
                    "processing_status": "Not Processed",
                    # Clear old processing audit
                    "processed_by": None,
                    "processed_on": None,
                    # Clear previous validation result
                    "validation_messages": "",
                    "has_warning": 0,
                    "is_duplicate": 0,
                    # Clear generated validation values
                    "normalized_policy_number": "",
                    "normalized_company_name": "",
                    "normalized_customer_name": "",
                    "record_fingerprint": "",
                },
                update_modified=False,
            )
