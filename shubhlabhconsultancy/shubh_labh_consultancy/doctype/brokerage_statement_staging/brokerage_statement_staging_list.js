const BROKERAGE_STATEMENT_STAGING_METHODS = {
	validate:
		"shubhlabhconsultancy.shubh_labh_consultancy.doctype.brokerage_statement_staging.brokerage_statement_staging.enqueue_pending_validation",

	post:
		"shubhlabhconsultancy.shubh_labh_consultancy.doctype.brokerage_statement_staging.brokerage_statement_staging.enqueue_valid_posting",
};


frappe.listview_settings["Brokerage Statement Staging"] = {
	add_fields: [
		"validation_status",
		"processing_status",
		"has_warning",
		"is_duplicate",
		"posted_brokerage_statement",
	],

	onload(listview) {
		add_brokerage_statement_staging_buttons(listview);
		register_brokerage_statement_staging_realtime(listview);
	},

	get_indicator(doc) {
		if (doc.processing_status === "Processed") {
			return [
				__("Processed"),
				"green",
				"processing_status,=,Processed",
			];
		}

		if (doc.processing_status === "Processing") {
			return [
				__("Processing"),
				"blue",
				"processing_status,=,Processing",
			];
		}

		if (doc.processing_status === "Failed") {
			return [
				__("Failed"),
				"red",
				"processing_status,=,Failed",
			];
		}

		if (doc.processing_status === "Ignored") {
			return [
				__("Ignored"),
				"gray",
				"processing_status,=,Ignored",
			];
		}

		if (doc.validation_status === "Invalid") {
			return [
				__("Invalid"),
				"red",
				"validation_status,=,Invalid",
			];
		}

		if (doc.validation_status === "Warning") {
			return [
				__("Warning"),
				"orange",
				"validation_status,=,Warning",
			];
		}

		if (doc.validation_status === "Valid") {
			return [
				__("Valid"),
				"green",
				"validation_status,=,Valid",
			];
		}

		return [
			__("Pending"),
			"gray",
			"validation_status,=,Pending",
		];
	},
};


function add_brokerage_statement_staging_buttons(listview) {
	const validate_label = __("Validate Pending Records");
	const post_label = __("Post Valid Records");

	listview.page.add_inner_button(
		validate_label,
		() => {
			frappe.confirm(
				__(
					"Validate all Brokerage Statement Staging records " +
					"that are not ignored, processing, processed, or " +
					"already posted?"
				),
				() => {
					run_brokerage_statement_staging_action({
						listview,
						method:
							BROKERAGE_STATEMENT_STAGING_METHODS
								.validate,
						freeze_message:
							__(
								"Starting Brokerage Statement " +
								"Staging validation..."
							),
						title:
							__("Validation Started"),
					});
				}
			);
		}
	);

	listview.page.add_inner_button(
		post_label,
		() => {
			frappe.confirm(
				__(
					"Create and submit Brokerage Statement documents " +
					"for all Valid and Ready staging records?"
				),
				() => {
					run_brokerage_statement_staging_action({
						listview,
						method:
							BROKERAGE_STATEMENT_STAGING_METHODS
								.post,
						freeze_message:
							__(
								"Starting Brokerage Statement " +
								"posting..."
							),
						title:
							__("Posting Started"),
					});
				}
			);
		}
	);

	listview.page.change_inner_button_type(
		post_label,
		null,
		"primary"
	);
}


function run_brokerage_statement_staging_action({
	listview,
	method,
	freeze_message,
	title,
}) {
	frappe.call({
		method,
		freeze: true,
		freeze_message,

		callback(response) {
			if (response.exc) {
				return;
			}

			const result = response.message || {};

			frappe.msgprint({
				title,
				indicator:
					result.queued
						? "blue"
						: "orange",
				message:
					result.message ||
					__("No eligible records were found."),
			});

			listview.refresh();
		},
	});
}


function register_brokerage_statement_staging_realtime(
	listview
) {
	/*
	 * List View ka onload multiple times run ho sakta hai.
	 * Is flag se duplicate realtime listener register nahi hoga.
	 */
	if (
		window
			.brokerage_statement_staging_listener_registered
	) {
		return;
	}

	window
		.brokerage_statement_staging_listener_registered = true;

	frappe.realtime.on(
		"brokerage_statement_staging_job_complete",
		(data) => {
			if (!data) {
				return;
			}

			if (data.action === "validation") {
				frappe.msgprint({
					title:
						__(
							"Brokerage Statement Staging " +
							"Validation Completed"
						),
					indicator:
						data.failed > 0
							? "orange"
							: "green",
					message: `
						<div>
							<p>
								<b>${__("Total")}:</b>
								${data.total || 0}
							</p>

							<p>
								<b>${__("Valid")}:</b>
								${data.valid || 0}
							</p>

							<p>
								<b>${__("Warning")}:</b>
								${data.warning || 0}
							</p>

							<p>
								<b>${__("Invalid")}:</b>
								${data.invalid || 0}
							</p>

							<p>
								<b>${__("Ignored")}:</b>
								${data.ignored || 0}
							</p>

							<p>
								<b>
									${__("Already Processed")}:
								</b>
								${data.already_processed || 0}
							</p>

							<p>
								<b>${__("Failed")}:</b>
								${data.failed || 0}
							</p>
						</div>
					`,
				});
			}

			if (data.action === "posting") {
				frappe.msgprint({
					title:
						__(
							"Brokerage Statement Posting " +
							"Completed"
						),
					indicator:
						data.failed > 0
							? "orange"
							: "green",
					message: `
						<div>
							<p>
								<b>${__("Total")}:</b>
								${data.total || 0}
							</p>

							<p>
								<b>${__("Posted")}:</b>
								${data.posted || 0}
							</p>

							<p>
								<b>
									${__("Already Processed")}:
								</b>
								${data.already_processed || 0}
							</p>

							<p>
								<b>${__("Not Eligible")}:</b>
								${data.not_eligible || 0}
							</p>

							<p>
								<b>${__("Failed")}:</b>
								${data.failed || 0}
							</p>
						</div>
					`,
				});
			}

			listview.refresh();
		}
	);
}