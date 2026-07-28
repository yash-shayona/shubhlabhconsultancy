// Copyright (c) 2026, Shayona Technology and contributors
// For license information, please see license.txt

frappe.ui.form.on("Brokerage Reconciliation", {
	refresh(frm) {
		add_reconciliation_actions(frm);
		register_reconciliation_realtime(frm);
		set_insurer_name_query(frm);
		sync_statement_month_fields(frm);
	},

	statement_month_select(frm) {
		set_statement_month_date(frm);
	},

	statement_year(frm) {
		set_statement_month_date(frm);
	},

	statement_month(frm) {
		sync_statement_month_fields(frm);
	},
});

function add_reconciliation_actions(frm) {
	if (frm.is_new()) {
		return;
	}

	frm.add_custom_button(__("View Settlements"), () => {
		frappe.set_route("List", "Brokerage Settlement", {
			brokerage_reconciliation: frm.doc.name,
		});
	});

	if (frm.doc.docstatus !== 0) {
		return;
	}

	frm.add_custom_button(__("Generate Matches"), () => {
		frappe.confirm(
			__(
				"This will replace existing draft settlements for this reconciliation. Continue?"
			),
			() => {
				enqueue_reconciliation_matching(frm);
			}
		);
	}).addClass("btn-primary");

	frm.add_custom_button(__("Generate Write-offs"), () => {
		frappe.confirm(
			__(
				"This will close eligible policy balances without allocating statement amounts. Continue?"
			),
			() => {
				enqueue_reconciliation_write_offs(frm);
			}
		);
	});
}

function enqueue_reconciliation_matching(frm) {
	frappe.call({
		method:
			"shubhlabhconsultancy.shubh_labh_consultancy.doctype.brokerage_reconciliation.brokerage_reconciliation.enqueue_generate_matches",
		args: {
			reconciliation_name: frm.doc.name,
		},
		freeze: true,
		freeze_message: __("Starting reconciliation matching..."),
		callback(response) {
			if (response.exc) {
				return;
			}

			const result = response.message || {};

			frappe.msgprint({
				title: __("Matching Started"),
				indicator: result.queued ? "blue" : "orange",
				message: result.message || __("No eligible records were found."),
			});

			frm.reload_doc();
		},
	});
}

function enqueue_reconciliation_write_offs(frm) {
	frappe.call({
		method:
			"shubhlabhconsultancy.shubh_labh_consultancy.doctype.brokerage_reconciliation.brokerage_reconciliation.enqueue_generate_write_offs",
		args: {
			reconciliation_name: frm.doc.name,
		},
		freeze: true,
		freeze_message: __("Starting write-off processing..."),
		callback(response) {
			if (response.exc) {
				return;
			}

			const result = response.message || {};

			frappe.msgprint({
				title: __("Write-off Processing Started"),
				indicator: result.queued ? "blue" : "orange",
				message: result.message || __("No eligible records were found."),
			});

			frm.reload_doc();
		},
	});
}

function register_reconciliation_realtime(frm) {
	if (window.brokerage_reconciliation_listener_registered) {
		return;
	}

	window.brokerage_reconciliation_listener_registered = true;

	frappe.realtime.on("brokerage_reconciliation_job_complete", (data) => {
		if (!data || data.reconciliation_name !== frm.doc.name) {
			return;
		}

		const is_write_off = data.action === "write_off";
		const title = is_write_off
			? __("Write-off Processing Completed")
			: __("Reconciliation Matching Completed");
		const checked_label = is_write_off
			? __("Policies Checked")
			: __("Statements Checked");
		const created_label = is_write_off
			? __("Write-off Settlements Submitted")
			: __("Settlements Submitted");
		const unmatched_label = is_write_off
			? __("Skipped Policies")
			: __("Unmatched Statements");
		const checked_count = data.total_records || data.total_statements || 0;
		const created_count = data.created || 0;
		const unmatched_count = data.unmatched || 0;
		const failed_count = data.failed || 0;

		frappe.msgprint({
			title,
			indicator: data.failed ? "orange" : "green",
			message: `
				<div>
					<p><b>${checked_label}:</b> ${checked_count}</p>
					<p><b>${created_label}:</b> ${created_count}</p>
					<p><b>${unmatched_label}:</b> ${unmatched_count}</p>
					<p><b>${__("Failed")}:</b> ${failed_count}</p>
				</div>
			`,
		});

		frm.reload_doc();
	});
}

function set_insurer_name_query(frm) {
	frm.set_query("insurer_name", () => {
		return {
			filters: {
				enabled: 1,
			},
		};
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

// This sets the internal Statement Month Date to the first date of the selected month.
function set_statement_month_date(frm) {
	const month_name = frm.doc.statement_month_select;
	const year = cint(frm.doc.statement_year);

	if (!month_name && !year) {
		return;
	}

	if (month_name && !year) {
		frm.set_value("statement_year", new Date().getFullYear());
		return;
	}

	if (!month_name || !year) {
		return;
	}

	const month_number = MONTH_NUMBER_BY_NAME[month_name];

	if (!month_number) {
		return;
	}

	const statement_month = `${year}-${String(month_number).padStart(2, "0")}-01`;

	if (frm.doc.statement_month !== statement_month) {
		frm.set_value("statement_month", statement_month);
	}
}

// This fills Month and Year from the internal Statement Month Date.
function sync_statement_month_fields(frm) {
	if (!frm.doc.statement_month) {
		if (!frm.doc.statement_year) {
			frm.set_value("statement_year", new Date().getFullYear());
		}

		return;
	}

	const date_object = frappe.datetime.str_to_obj(frm.doc.statement_month);
	const month_name = MONTH_NAME_BY_NUMBER[date_object.getMonth() + 1];
	const year = date_object.getFullYear();

	if (month_name && frm.doc.statement_month_select !== month_name) {
		frm.set_value("statement_month_select", month_name);
	}

	if (frm.doc.statement_year !== year) {
		frm.set_value("statement_year", year);
	}
}
