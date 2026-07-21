import frappe

APP_NAME = "Shubh Labh Consultancy"
CRM_APP_NAME = "Frappe CRM"


# This updates Website Settings text branding that hooks do not control.
def apply_website_settings():
    website_settings = frappe.get_single("Website Settings")
    website_settings.app_name = APP_NAME
    website_settings.save(ignore_permissions=True)


# This resets Website Settings text branding back to the default Frappe value.
def reset_website_settings():
    website_settings = frappe.get_single("Website Settings")
    website_settings.app_name = "Frappe"
    website_settings.save(ignore_permissions=True)


# This sets the Desktop page navbar logo used in the top-left corner.
def apply_navbar_settings():
    navbar = frappe.get_single("Navbar Settings")
    navbar.app_logo = "/assets/shubhlabhconsultancy/images/logo.png"
    navbar.save(ignore_permissions=True)


# This clears the Desktop page navbar logo so Frappe can use its default fallback again.
def reset_navbar_settings():
    navbar = frappe.get_single("Navbar Settings")
    navbar.app_logo = ""
    navbar.save(ignore_permissions=True)


# This updates CRM branding only if CRM is installed on the site.
def apply_fcrm_settings():
    if not frappe.db.exists("DocType", "FCRM Settings"):
        return

    fcrm_settings = frappe.get_single("FCRM Settings")
    fcrm_settings.brand_name = APP_NAME
    fcrm_settings.brand_logo = "/assets/shubhlabhconsultancy/images/logo.png"
    fcrm_settings.favicon = "/assets/shubhlabhconsultancy/images/favicon.png"
    fcrm_settings.save(ignore_permissions=True)


# This resets CRM branding only if CRM is installed on the site.
def reset_fcrm_settings():
    if not frappe.db.exists("DocType", "FCRM Settings"):
        return

    fcrm_settings = frappe.get_single("FCRM Settings")
    fcrm_settings.brand_name = CRM_APP_NAME
    fcrm_settings.brand_logo = ""
    fcrm_settings.favicon = ""
    fcrm_settings.save(ignore_permissions=True)


# This is the main install-time branding entry point.
def setup_branding():
    apply_website_settings()
    apply_navbar_settings()
    # apply_fcrm_settings()
    frappe.db.commit()
    print("Branding setup completed successfully.")


# This is the main uninstall-time cleanup entry point.
def cleanup_branding():
    reset_website_settings()
    reset_navbar_settings()
    # reset_fcrm_settings()
    print("Branding cleanup completed successfully.")
