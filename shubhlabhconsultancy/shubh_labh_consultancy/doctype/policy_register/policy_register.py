# Copyright (c) 2026, Shayona Technology and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PolicyRegister(Document):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF

        amended_from: DF.Link | None
        brokerage_amount: DF.Currency
        brokerage_percentage: DF.Percent
        brokerage_premium: DF.Currency
        business_month: DF.Date | None
        business_type: DF.Literal["", "New", "Renewal"]
        campaign_name: DF.Data | None
        cno: DF.Int
        customer_name: DF.Data | None
        endorsement_number: DF.Data | None
        expected_brokerage: DF.Currency
        expiry_date: DF.Date | None
        financial_year: DF.Data | None
        insurer_name: DF.Link | None
        outstanding_brokerage: DF.Currency
        policy_number: DF.Data | None
        policy_type: DF.Data | None
        reconciliation_status: DF.Literal["", "Pending", "Partially Settled", "Fully Settled", "Written Off", "Excess Received", "Disputed", "Reversed"]
        settled_brokerage: DF.Currency
        share_percentage: DF.Percent
        source_data_import: DF.Link | None
        source_staging: DF.Link
        start_date: DF.Date | None
        total_brokerage: DF.Currency
        total_brokerage_and_reward: DF.Currency
        tp_brokerage_amount: DF.Currency
        tp_brokerage_percentage: DF.Percent
        tp_premium: DF.Currency
        written_off_brokerage: DF.Currency
    # end: auto-generated types

    def on_trash(self):
        staging_records = frappe.get_all(
            "Policy Register Staging",
            filters={
                "posted_policy_register": self.name,
            },
            pluck="name",
        )

        for staging_name in staging_records:
            frappe.db.set_value(
                "Policy Register Staging",
                staging_name,
                {
                    # Remove final document reference
                    "posted_policy_register": None,
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
                    "normalized_endorsement_number": "",
                    "normalized_insurer_name": "",
                    "normalized_customer_name": "",
                    "record_fingerprint": "",
                },
                update_modified=False,
            )
