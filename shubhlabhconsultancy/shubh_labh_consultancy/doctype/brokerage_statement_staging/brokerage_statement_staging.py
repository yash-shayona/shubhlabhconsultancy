# Copyright (c) 2026, Shayona Technology and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class BrokerageStatementStaging(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		brokerage_received: DF.Currency
		company_name: DF.Data | None
		customer_name: DF.Data | None
		expiry_date: DF.Date | None
		has_warning: DF.Check
		ignore_reason: DF.SmallText | None
		ignore_record: DF.Check
		is_duplicate: DF.Check
		normalized_company_name: DF.Data | None
		normalized_customer_name: DF.Data | None
		normalized_policy_number: DF.Data | None
		policy_number: DF.Data | None
		posted_brokerage_statement: DF.Link | None
		processed_by: DF.Link | None
		processed_on: DF.Datetime | None
		processing_status: DF.Literal["", "Not Processed", "Ready", "Processing", "Processed", "Ignored", "Failed"]
		record_fingerprint: DF.Data | None
		start_date: DF.Date | None
		statement_month: DF.Date | None
		validation_messages: DF.SmallText | None
		validation_status: DF.Literal["", "Pending", "Valid", "Warning", "Invalid"]
	# end: auto-generated types

	pass
