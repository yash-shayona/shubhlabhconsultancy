import frappe

from shubhlabhconsultancy.permissions.reconciliation_portal import (
    require_brokerage_reconciliation_tool_access,
)

# This is the fixed website route used for login redirect and browser refresh.
BROKERAGE_RECONCILIATION_TOOL_ROUTE = "/slc/brokerage-reconciliation-tool"


# This protects the route and configures it as a clean full-width application page.
def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = (
            f"/login?redirect-to={BROKERAGE_RECONCILIATION_TOOL_ROUTE}"
        )
        raise frappe.Redirect

    # This blocks users outside the current System Manager access model.
    require_brokerage_reconciliation_tool_access()

    context.no_cache = 1
    context.show_sidebar = 0
    context.no_header = 1
    context.no_breadcrumbs = 1
    context.full_width = 1
    context.title = "Brokerage Reconciliation Tool"