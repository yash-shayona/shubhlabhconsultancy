// Copyright (c) 2026, Shayona Technology and contributors
// For license information, please see license.txt

frappe.ui.form.on("Policy Register Staging", {
    refresh(frm) {
        frm.events._set_insurer_name_query(frm);
    },

    _set_insurer_name_query(frm) {
        frm.set_query("insurer_name", () => {
            return {
                filters: {
                    enabled: 1,
                },
            };
        });
    }
});
