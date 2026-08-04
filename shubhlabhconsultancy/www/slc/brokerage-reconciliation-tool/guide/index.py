import frappe

from shubhlabhconsultancy.permissions.reconciliation_portal import (
    require_brokerage_reconciliation_tool_access,
)

# This is the fixed protected route used by the tool-page guidance link.
BROKERAGE_RECONCILIATION_GUIDE_ROUTE = "/slc/brokerage-reconciliation-tool/guide"


# This protects the guide with the same login and role checks as the financial tool.
def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = (
            f"/login?redirect-to={BROKERAGE_RECONCILIATION_GUIDE_ROUTE}"
        )
        raise frappe.Redirect

    require_brokerage_reconciliation_tool_access()

    context.no_cache = 1
    context.show_sidebar = 0
    context.no_header = 1
    context.no_breadcrumbs = 1
    context.full_width = 1
    context.title = "Brokerage Reconciliation Guide"
