// Copyright (c) 2026, Shayona Technology and contributors
// For license information, please see license.txt

frappe.ui.form.on("Brokerage Statement Staging", {
	refresh(frm) {
		frm.events._set_insurer_name_query(frm);
		frm.events._sync_statement_month_fields(frm);
		add_brokerage_statement_staging_actions(frm);
		register_brokerage_statement_staging_form_realtime();
	},

	statement_month_select(frm) {
		frm.events._set_statement_month_date(frm);
	},

	statement_year(frm) {
		frm.events._set_statement_month_date(frm);
	},

	statement_month(frm) {
		frm.events._sync_statement_month_fields(frm);
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

	_set_statement_month_date(frm) {
		set_month_start_date(
			frm,
			"statement_month_select",
			"statement_year",
			"statement_month"
		);
	},

	_sync_statement_month_fields(frm) {
		sync_month_fields_from_date(
			frm,
			"statement_month",
			"statement_month_select",
			"statement_year"
		);
	},
});

const BROKERAGE_STATEMENT_STAGING_METHODS = {
	validate:
		"shubhlabhconsultancy.shubh_labh_consultancy.doctype.brokerage_statement_staging.brokerage_statement_staging.enqueue_pending_validation",
	post:
		"shubhlabhconsultancy.shubh_labh_consultancy.doctype.brokerage_statement_staging.brokerage_statement_staging.enqueue_valid_posting",
};

// This mirrors the current server eligibility only to decide whether to show the Post button.
const POSTABLE_BROKERAGE_STATEMENT_VALIDATION_STATUSES = ["Valid"];

// This adds actions that queue validation or posting for only the open staging record.
function add_brokerage_statement_staging_actions(frm) {
	if (frm.is_new() || !is_brokerage_statement_staging_actionable(frm.doc)) {
		return;
	}

	frm.add_custom_button(__("Validate This Record"), () => {
		queue_brokerage_statement_staging_action({
			frm,
			method: BROKERAGE_STATEMENT_STAGING_METHODS.validate,
			freeze_message: __("Starting validation for this record..."),
			title: __("Validation Started"),
		});
	});

	if (!is_brokerage_statement_staging_postable(frm.doc)) {
		return;
	}

	frm.add_custom_button(__("Post This Record"), () => {
		frappe.confirm(
			__(
				"This will create and submit the final Brokerage Statement for this staging record. Continue?"
			),
			() => {
				queue_brokerage_statement_staging_action({
					frm,
					method: BROKERAGE_STATEMENT_STAGING_METHODS.post,
					freeze_message: __("Starting posting for this record..."),
					title: __("Posting Started"),
				});
			}
		);
	}).addClass("btn-primary");
}

// This checks whether the current row can still be validated or posted.
function is_brokerage_statement_staging_actionable(doc) {
	return (
		!cint(doc.ignore_record) &&
		!doc.posted_brokerage_statement &&
		doc.processing_status !== "Processing" &&
		doc.processing_status !== "Processed" &&
		doc.processing_status !== "Ignored"
	);
}

// This checks whether the current row has passed validation and is ready for posting.
function is_brokerage_statement_staging_postable(doc) {
	return (
		is_brokerage_statement_staging_actionable(doc) &&
		POSTABLE_BROKERAGE_STATEMENT_VALIDATION_STATUSES.includes(doc.validation_status) &&
		doc.processing_status === "Ready"
	);
}

// This queues one staging record through the existing background processing methods.
function queue_brokerage_statement_staging_action({
	frm,
	method,
	freeze_message,
	title,
}) {
	frappe.call({
		method,
		args: {
			staging_name: frm.doc.name,
		},
		freeze: true,
		freeze_message,
		callback(response) {
			if (response.exc) {
				return;
			}

			const result = response.message || {};

			frappe.msgprint({
				title,
				indicator: result.queued ? "blue" : "orange",
				message: result.message || __("This record is not eligible for processing."),
			});

			frm.reload_doc();
		},
	});
}

// This reloads the open form when its own background validation or posting completes.
function register_brokerage_statement_staging_form_realtime() {
	if (window.brokerage_statement_staging_form_listener_registered) {
		return;
	}

	window.brokerage_statement_staging_form_listener_registered = true;

	frappe.realtime.on("brokerage_statement_staging_job_complete", (data) => {
		const frm = cur_frm;

		if (
			!frm ||
			frm.doctype !== "Brokerage Statement Staging" ||
			!Array.isArray(data?.record_names) ||
			!data.record_names.includes(frm.doc.name)
		) {
			return;
		}

		frappe.show_alert({
			message:
				data.action === "posting"
					? __("Posting completed for this record.")
					: __("Validation completed for this record."),
			indicator: data.failed > 0 ? "orange" : "green",
		});

		frm.reload_doc();
	});
}

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
