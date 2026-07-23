# Copyright (c) 2026, Shayona Technology and contributors
# For license information, please see license.txt

# import frappe
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
		company_name: DF.Data | None
		customer_name: DF.Data | None
		expiry_date: DF.Date | None
		policy_number: DF.Data | None
		reconciliation_status: DF.Literal["", "Unallocated", "Partially Allocated", "Fully Allocated", "On Account", "Disputed", "Reversed"]
		source_data_import: DF.Link | None
		source_staging: DF.Link
		start_date: DF.Date | None
		statement_month: DF.Date | None
		unallocated_brokerage: DF.Currency
	# end: auto-generated types

	pass
