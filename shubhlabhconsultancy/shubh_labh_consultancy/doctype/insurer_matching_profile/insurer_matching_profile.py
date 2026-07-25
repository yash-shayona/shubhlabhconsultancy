# Copyright (c) 2026, Shayona Technology and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class InsurerMatchingProfile(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		company_name: DF.Data
		customer_name_score: DF.Int
		date_score: DF.Int
		enabled: DF.Check
		endorsement_score: DF.Int
		exact_match_threshold: DF.Percent
		match_customer_name: DF.Check
		match_endorsement_reference: DF.Check
		match_expiry_date: DF.Check
		match_policy_number: DF.Check
		match_policy_type__product: DF.Check
		match_start_date: DF.Check
		policy_number_score: DF.Int
		policy_type_score: DF.Int
		suggested_match_threshold: DF.Percent
	# end: auto-generated types

	pass
