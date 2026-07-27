// Copyright (c) 2026, Shayona Technology and contributors
// For license information, please see license.txt

frappe.ui.form.on("Brokerage Reconciliation", {
	refresh(frm) {
		add_reconciliation_actions(frm);
		register_reconciliation_realtime(frm);
		set_insurer_name_query(frm);
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

function register_reconciliation_realtime(frm) {
	if (window.brokerage_reconciliation_listener_registered) {
		return;
	}

	window.brokerage_reconciliation_listener_registered = true;

	frappe.realtime.on("brokerage_reconciliation_job_complete", (data) => {
		if (!data || data.reconciliation_name !== frm.doc.name) {
			return;
		}

		frappe.msgprint({
			title: __("Reconciliation Matching Completed"),
			indicator: data.failed ? "orange" : "green",
			message: `
				<div>
					<p><b>${__("Statements Checked")}:</b> ${data.total_statements || 0}</p>
					<p><b>${__("Draft Settlements Created")}:</b> ${data.created || 0}</p>
					<p><b>${__("Unmatched Statements")}:</b> ${data.unmatched || 0}</p>
					<p><b>${__("Failed")}:</b> ${data.failed || 0}</p>
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