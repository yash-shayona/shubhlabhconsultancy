// Copyright (c) 2026, Shayona Technology and contributors
// For license information, please see license.txt

frappe.ui.form.on("Policy Register Staging", {
	refresh(frm) {
		frm.events._set_insurer_name_query(frm);
		frm.events._sync_business_month_fields(frm);
	},

	business_month_select(frm) {
		frm.events._set_business_month_date(frm);
	},

	business_year(frm) {
		frm.events._set_business_month_date(frm);
	},

	business_month(frm) {
		frm.events._sync_business_month_fields(frm);
	},

	_set_insurer_name_query(frm) {
		frm.set_query("insurer_name", () => {
			return {
				filters: {
					enabled: 1,
				},
			};
		});
	},

	_set_business_month_date(frm) {
		set_month_start_date(
			frm,
			"business_month_select",
			"business_year",
			"business_month"
		);
	},

	_sync_business_month_fields(frm) {
		sync_month_fields_from_date(
			frm,
			"business_month",
			"business_month_select",
			"business_year"
		);
	},
});

const MONTH_NUMBER_BY_NAME = {
	January: 1,
	February: 2,
	March: 3,
	April: 4,
	May: 5,
	June: 6,
	July: 7,
	August: 8,
	September: 9,
	October: 10,
	November: 11,
	December: 12,
};

const MONTH_NAME_BY_NUMBER = Object.fromEntries(
	Object.entries(MONTH_NUMBER_BY_NAME).map(([month_name, month_number]) => [
		month_number,
		month_name,
	])
);

// This sets the internal Date field to the first date of the selected month.
function set_month_start_date(frm, month_fieldname, year_fieldname, date_fieldname) {
	const month_name = frm.doc[month_fieldname];
	const year = cint(frm.doc[year_fieldname]);

	if (!month_name && !year) {
		return;
	}

	if (month_name && !year) {
		frm.set_value(year_fieldname, new Date().getFullYear());
		return;
	}

	if (!month_name || !year) {
		return;
	}

	const month_number = MONTH_NUMBER_BY_NAME[month_name];

	if (!month_number) {
		return;
	}

	const month_start_date = `${year}-${String(month_number).padStart(2, "0")}-01`;

	if (frm.doc[date_fieldname] !== month_start_date) {
		frm.set_value(date_fieldname, month_start_date);
	}
}

// This fills Month and Year from an existing Date value.
function sync_month_fields_from_date(frm, date_fieldname, month_fieldname, year_fieldname) {
	const date_value = frm.doc[date_fieldname];

	if (!date_value) {
		if (!frm.doc[year_fieldname]) {
			frm.set_value(year_fieldname, new Date().getFullYear());
		}

		return;
	}

	const date_object = frappe.datetime.str_to_obj(date_value);
	const month_name = MONTH_NAME_BY_NUMBER[date_object.getMonth() + 1];
	const year = date_object.getFullYear();

	if (month_name && frm.doc[month_fieldname] !== month_name) {
		frm.set_value(month_fieldname, month_name);
	}

	if (frm.doc[year_fieldname] !== year) {
		frm.set_value(year_fieldname, year);
	}
}
