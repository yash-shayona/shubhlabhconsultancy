app_name = "shubhlabhconsultancy"
app_title = "Shubh Labh Consultancy"
app_publisher = "Shayona Technology"
app_description = "Shubh Labh Consultancy has roots in Insurance since almost 4 decades. We believe in providing cutting edge services and low premium costs to our corporate and retail clients. We pride ourselves on our technical knowledge, ethical approach and availability in times of need."
app_email = "info@shayona.biz"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
add_to_apps_screen = [
	{
		"name": "shubhlabhconsultancy",
		"logo": "/assets/shubhlabhconsultancy/images/logo.png",
		"title": "Shubh Labh Consultancy",
		"route": "/shubhlabhconsultancy",
		# "has_permission": "shubhlabhconsultancy.api.permission.has_app_permission"
	}
]

# This hook provides the default desk/login/logo fallback without touching File records.
app_logo_url = "/assets/shubhlabhconsultancy/images/logo.png"

# This hook provides website-level asset branding directly from public files.
website_context = {
    "favicon": "/assets/shubhlabhconsultancy/images/favicon.png",
    "splash_image": "/assets/shubhlabhconsultancy/images/logo.png",
    "banner_image": "/assets/shubhlabhconsultancy/images/logo.png",
}

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/shubhlabhconsultancy/css/shubhlabhconsultancy.css"
# app_include_js = "/assets/shubhlabhconsultancy/js/shubhlabhconsultancy.js"

# include js, css files in header of web template
# web_include_css = "/assets/shubhlabhconsultancy/css/shubhlabhconsultancy.css"
# web_include_js = "/assets/shubhlabhconsultancy/js/shubhlabhconsultancy.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "shubhlabhconsultancy/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "shubhlabhconsultancy/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "shubhlabhconsultancy.utils.jinja_methods",
# 	"filters": "shubhlabhconsultancy.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "shubhlabhconsultancy.install.before_install"
after_install = "shubhlabhconsultancy.setup.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "shubhlabhconsultancy.uninstall.before_uninstall"
after_uninstall = "shubhlabhconsultancy.setup.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "shubhlabhconsultancy.utils.before_app_install"
# after_app_install = "shubhlabhconsultancy.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "shubhlabhconsultancy.utils.before_app_uninstall"
# after_app_uninstall = "shubhlabhconsultancy.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "shubhlabhconsultancy.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "shubhlabhconsultancy.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"shubhlabhconsultancy.tasks.all"
# 	],
# 	"daily": [
# 		"shubhlabhconsultancy.tasks.daily"
# 	],
# 	"hourly": [
# 		"shubhlabhconsultancy.tasks.hourly"
# 	],
# 	"weekly": [
# 		"shubhlabhconsultancy.tasks.weekly"
# 	],
# 	"monthly": [
# 		"shubhlabhconsultancy.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "shubhlabhconsultancy.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "shubhlabhconsultancy.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "shubhlabhconsultancy.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "shubhlabhconsultancy.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["shubhlabhconsultancy.utils.before_request"]
# after_request = ["shubhlabhconsultancy.utils.after_request"]

# Job Events
# ----------
# before_job = ["shubhlabhconsultancy.utils.before_job"]
# after_job = ["shubhlabhconsultancy.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"shubhlabhconsultancy.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
