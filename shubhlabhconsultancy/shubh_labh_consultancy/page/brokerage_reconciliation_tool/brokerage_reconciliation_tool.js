// Copyright (c) 2026, Shayona Technology and contributors
// For license information, please see license.txt

frappe.pages["brokerage-reconciliation-tool"].on_page_load = function (wrapper) {
	const tool = new BrokerageReconciliationTool(wrapper);
	tool.make();
};

class BrokerageReconciliationTool {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.current_reconciliation = null;
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Brokerage Reconciliation Tool"),
			single_column: true,
		});
	}

	make() {
		this.make_body();
		this.add_fields();
		this.add_actions();
		this.register_realtime();
	}

	add_fields() {
		this.insurer = this.make_field(
			{
				fieldname: "insurer_name",
				label: __("Insurer"),
				fieldtype: "Link",
				options: "Insurer",
				reqd: 1,
				get_query: () => ({
					filters: {
						enabled: 1,
					},
				}),
			},
			this.$left_column
		);

		this.statement_month = this.make_field(
			{
				fieldname: "statement_month_select",
				label: __("Statement Month"),
				fieldtype: "Select",
				options: Object.keys(MONTH_NUMBER_BY_NAME).join("\n"),
				reqd: 1,
			},
			this.$left_column
		);

		this.statement_year = this.make_field(
			{
				fieldname: "statement_year",
				label: __("Year"),
				fieldtype: "Int",
				default: new Date().getFullYear(),
				reqd: 1,
			},
			this.$left_column
		);

		this.reconciliation_date = this.make_field(
			{
				fieldname: "reconciliation_date",
				label: __("Reconciliation Date"),
				fieldtype: "Date",
				default: frappe.datetime.get_today(),
				reqd: 1,
			},
			this.$right_column
		);

		this.write_off_limit = this.make_field(
			{
				fieldname: "amount_tolerance",
				label: __("Write-off Limit"),
				fieldtype: "Currency",
				default: 0,
			},
			this.$right_column
		);

		this.include_earlier_business = this.make_field(
			{
				fieldname: "include_earlier_business",
				label: __("Include Earlier Business"),
				fieldtype: "Check",
				default: 1,
			},
			this.$right_column
		);
	}

	make_field(df, $parent) {
		const $field = $('<div class="brokerage-tool-field"></div>').appendTo($parent);
		const control = frappe.ui.form.make_control({
			df,
			parent: $field,
			only_input: false,
		});

		control.refresh();

		if (df.default !== undefined) {
			control.set_input(df.default);
		}

		$field.find(".form-group").css("margin-bottom", "0");
		$field.find(".control-input-wrapper").css("max-width", "100%");
		$field.find("input, select").css("width", "100%");

		return control;
	}

	add_actions() {
		$(`<button class="btn btn-primary btn-sm">${__("Generate Matches")}</button>`)
			.appendTo(this.$actions)
			.on("click", () => {
				this.confirm_and_start("match");
			});

		$(`<button class="btn btn-default btn-sm">${__("Generate Write-offs")}</button>`)
			.appendTo(this.$actions)
			.on("click", () => {
				this.confirm_and_start("write_off");
			});

		$(`<button class="btn btn-default btn-sm">${__("View Reconciliation")}</button>`)
			.appendTo(this.$actions)
			.on("click", () => {
				if (!this.current_reconciliation) {
					frappe.msgprint(__("No reconciliation has been started from this page yet."));
					return;
				}

				frappe.set_route("Form", "Brokerage Reconciliation", this.current_reconciliation);
			});

		$(`<button class="btn btn-default btn-sm">${__("View Settlements")}</button>`)
			.appendTo(this.$actions)
			.on("click", () => {
				if (!this.current_reconciliation) {
					frappe.msgprint(__("No reconciliation has been started from this page yet."));
					return;
				}

				frappe.set_route("List", "Brokerage Settlement", {
					brokerage_reconciliation: this.current_reconciliation,
				});
			});
	}

	make_body() {
		this.$body = $(`
			<div class="brokerage-reconciliation-tool">
				<div class="brokerage-tool-section">
					<div class="brokerage-tool-grid">
						<div class="brokerage-tool-column brokerage-tool-left"></div>
						<div class="brokerage-tool-column brokerage-tool-right"></div>
					</div>
					<div class="brokerage-tool-actions"></div>
				</div>
				<div class="tool-summary"></div>
			</div>
		`).appendTo(this.page.body);

		this.$left_column = this.$body.find(".brokerage-tool-left");
		this.$right_column = this.$body.find(".brokerage-tool-right");
		this.$actions = this.$body.find(".brokerage-tool-actions");
		this.$summary = this.$body.find(".tool-summary");

		this.$body.css({
			width: "min(900px, calc(100% - 32px))",
			margin: "0 auto",
		});

		this.$body.find(".brokerage-tool-section").css({
			"border-top": "1px solid var(--border-color)",
			"border-bottom": "1px solid var(--border-color)",
			padding: "18px 0",
			"margin-top": "12px",
		});

		this.$body.find(".brokerage-tool-grid").css({
			display: "grid",
			"grid-template-columns": "repeat(auto-fit, minmax(280px, 1fr))",
			gap: "30px",
			"align-items": "start",
		});

		this.$body.find(".brokerage-tool-column").css({
			display: "grid",
			gap: "16px",
		});

		this.$actions.css({
			display: "flex",
			gap: "8px",
			"flex-wrap": "wrap",
			"margin-top": "18px",
		});

		this.$summary.css({
			"margin-top": "20px",
		});
	}

	confirm_and_start(action) {
		const message =
			action === "write_off"
				? __("This will create write-off settlements for eligible policy balances. Continue?")
				: __("This will create regular settlements for matched statement rows. Continue?");

		frappe.confirm(message, () => {
			this.start(action);
		});
	}

	start(action) {
		const values = this.get_values();

		if (!values) {
			return;
		}

		if (action === "write_off" && flt(values.amount_tolerance) <= 0) {
			frappe.msgprint(__("Write-off Limit must be greater than zero."));
			return;
		}

		frappe.call({
			method:
				"shubhlabhconsultancy.shubh_labh_consultancy.page.brokerage_reconciliation_tool.brokerage_reconciliation_tool.start_reconciliation",
			args: {
				action,
				...values,
			},
			freeze: true,
			freeze_message:
				action === "write_off"
					? __("Starting write-off processing...")
					: __("Starting reconciliation matching..."),
			callback: (response) => {
				if (response.exc) {
					return;
				}

				const result = response.message || {};
				this.current_reconciliation = result.reconciliation_name;
				this.show_started(result, action);
			},
		});
	}

	get_values() {
		const values = {
			insurer_name: this.insurer.get_value(),
			statement_month_select: this.statement_month.get_value(),
			statement_year: this.statement_year.get_value(),
			include_earlier_business: this.include_earlier_business.get_value() ? 1 : 0,
			amount_tolerance: this.write_off_limit.get_value() || 0,
			reconciliation_date: this.reconciliation_date.get_value(),
		};

		if (!values.insurer_name) {
			frappe.msgprint(__("Insurer is required."));
			return null;
		}

		if (!values.statement_month_select) {
			frappe.msgprint(__("Statement Month is required."));
			return null;
		}

		if (!cint(values.statement_year)) {
			frappe.msgprint(__("Year is required."));
			return null;
		}

		if (!values.reconciliation_date) {
			frappe.msgprint(__("Reconciliation Date is required."));
			return null;
		}

		return values;
	}

	show_started(result, action) {
		const title =
			action === "write_off"
				? __("Write-off Processing Started")
				: __("Matching Started");

		this.$summary.html(`
			<div class="alert alert-info" style="margin-bottom: 0;">
				<div><strong>${title}</strong></div>
				<div>${result.message || __("Background job has been queued.")}</div>
				<div style="margin-top: 8px;">
					<a class="reconciliation-link">${__("Open Reconciliation")} ${
			result.reconciliation_name || ""
		}</a>
				</div>
			</div>
		`);

		this.$summary.find(".reconciliation-link").on("click", () => {
			frappe.set_route("Form", "Brokerage Reconciliation", result.reconciliation_name);
		});
	}

	register_realtime() {
		window.brokerage_reconciliation_tool_current = this;

		if (window.brokerage_reconciliation_tool_listener_registered) {
			return;
		}

		window.brokerage_reconciliation_tool_listener_registered = true;

		frappe.realtime.on("brokerage_reconciliation_job_complete", (data) => {
			const tool = window.brokerage_reconciliation_tool_current;

			if (!tool) {
				return;
			}

			if (!data || !data.reconciliation_name) {
				return;
			}

			if (tool.current_reconciliation && data.reconciliation_name !== tool.current_reconciliation) {
				return;
			}

			tool.current_reconciliation = data.reconciliation_name;
			tool.show_completed(data);
		});
	}

	show_completed(data) {
		const is_write_off = data.action === "write_off";
		const title = is_write_off
			? __("Write-off Processing Completed")
			: __("Reconciliation Matching Completed");
		const checked_label = is_write_off ? __("Policies Checked") : __("Statements Checked");
		const created_label = is_write_off
			? __("Write-off Settlements Submitted")
			: __("Settlements Submitted");
		const unmatched_label = is_write_off ? __("Skipped Policies") : __("Unmatched Statements");
		const checked_count = data.total_records || data.total_statements || 0;

		this.$summary.html(`
			<div class="alert ${data.failed ? "alert-warning" : "alert-success"}" style="margin-bottom: 0;">
				<div><strong>${title}</strong></div>
				<div style="margin-top: 8px;">
					<div>${checked_label}: <strong>${checked_count}</strong></div>
					<div>${created_label}: <strong>${data.created || 0}</strong></div>
					<div>${unmatched_label}: <strong>${data.unmatched || 0}</strong></div>
					<div>${__("Failed")}: <strong>${data.failed || 0}</strong></div>
				</div>
				<div style="margin-top: 12px;">
					<button class="btn btn-xs btn-default open-reconciliation">${__("Open Reconciliation")}</button>
					<button class="btn btn-xs btn-default open-settlements">${__("Open Settlements")}</button>
				</div>
			</div>
		`);

		this.$summary.find(".open-reconciliation").on("click", () => {
			frappe.set_route("Form", "Brokerage Reconciliation", data.reconciliation_name);
		});

		this.$summary.find(".open-settlements").on("click", () => {
			frappe.set_route("List", "Brokerage Settlement", {
				brokerage_reconciliation: data.reconciliation_name,
			});
		});
	}
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
