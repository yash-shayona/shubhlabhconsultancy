# Copyright (c) 2026, Shayona Technology and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class Insurer(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		enabled: DF.Check
		insurer_code: DF.Data
		insurer_name: DF.Data
		short_name: DF.Data | None
	# end: auto-generated types

	pass
