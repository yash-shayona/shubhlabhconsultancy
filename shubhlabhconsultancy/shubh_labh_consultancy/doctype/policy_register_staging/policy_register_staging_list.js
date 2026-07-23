const POLICY_REGISTER_STAGING_METHODS = {
	validate:
		"shubhlabhconsultancy.shubh_labh_consultancy.doctype.policy_register_staging.policy_register_staging.enqueue_pending_validation",

	post:
		"shubhlabhconsultancy.shubh_labh_consultancy.doctype.policy_register_staging.policy_register_staging.enqueue_valid_posting",
};


frappe.listview_settings["Policy Register Staging"] = {
	add_fields: [
		"validation_status",
		"processing_status",
		"has_warning",
		"is_duplicate",
		"posted_policy_register",
	],

	onload(listview) {
		add_policy_register_staging_buttons(listview);
		register_policy_register_staging_realtime(listview);
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


function add_policy_register_staging_buttons(listview) {
	const validate_label = __("Validate Pending Records");
	const post_label = __("Post Valid Records");

	listview.page.add_inner_button(
		validate_label,
		() => {
			frappe.confirm(
				__(
					"Validate all staging records that are not ignored, processing, processed, or already posted?"
				),
				() => {
					run_policy_register_staging_action({
						listview,
						method:
							POLICY_REGISTER_STAGING_METHODS.validate,
						freeze_message:
							__("Starting staging validation..."),
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
					"Create and submit Policy Register documents for all Valid and Ready staging records?"
				),
				() => {
					run_policy_register_staging_action({
						listview,
						method:
							POLICY_REGISTER_STAGING_METHODS.post,
						freeze_message:
							__("Starting Policy Register posting..."),
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


function run_policy_register_staging_action({
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
				indicator: result.queued ? "blue" : "orange",
				message:
					result.message ||
					__("No eligible records were found."),
			});

			listview.refresh();
		},
	});
}


function register_policy_register_staging_realtime(listview) {
	/*
	 * onload multiple times run ho sakta hai.
	 * Is flag se duplicate realtime listener register nahi hoga.
	 */
	if (window.policy_register_staging_listener_registered) {
		return;
	}

	window.policy_register_staging_listener_registered = true;

	frappe.realtime.on(
		"policy_register_staging_job_complete",
		(data) => {
			if (!data) {
				return;
			}

			if (data.action === "validation") {
				frappe.msgprint({
					title: __("Staging Validation Completed"),
					indicator:
						data.failed > 0 ? "orange" : "green",
					message: `
						<div>
							<p><b>${__("Total")}:</b> ${data.total || 0}</p>
							<p><b>${__("Valid")}:</b> ${data.valid || 0}</p>
							<p><b>${__("Warning")}:</b> ${data.warning || 0}</p>
							<p><b>${__("Invalid")}:</b> ${data.invalid || 0}</p>
							<p><b>${__("Ignored")}:</b> ${data.ignored || 0}</p>
							<p><b>${__("Failed")}:</b> ${data.failed || 0}</p>
						</div>
					`,
				});
			}

			if (data.action === "posting") {
				frappe.msgprint({
					title: __("Policy Register Posting Completed"),
					indicator:
						data.failed > 0 ? "orange" : "green",
					message: `
						<div>
							<p><b>${__("Total")}:</b> ${data.total || 0}</p>
							<p><b>${__("Posted")}:</b> ${data.posted || 0}</p>
							<p><b>${__("Already Processed")}:</b> ${data.already_processed || 0}</p>
							<p><b>${__("Not Eligible")}:</b> ${data.not_eligible || 0}</p>
							<p><b>${__("Failed")}:</b> ${data.failed || 0}</p>
						</div>
					`,
				});
			}

			listview.refresh();
		}
	);
}