// Copyright (c) 2026, Shayona Technology and contributors
// For license information, please see license.txt

frappe.ui.form.on("Insurer", {
    refresh(frm) {
        add_enabled_toggle_button(frm);
    },
});

// This adds one button to enable or disable the insurer from the form.
function add_enabled_toggle_button(frm) {
    if (frm.is_new()) {
        return;
    }

    const is_enabled = cint(frm.doc.enabled);
    const label = is_enabled ? __("Disable") : __("Enable");

    frm.add_custom_button(label, () => {
        const next_value = is_enabled ? 0 : 1;

        frm.set_value("enabled", next_value);
        frm.save();
    });
}