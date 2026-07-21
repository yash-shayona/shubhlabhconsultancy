import frappe
from ..services.branding_setup_service import cleanup_branding


def after_uninstall():
    cleanup_branding()

    frappe.db.commit()
