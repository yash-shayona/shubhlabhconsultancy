// This opens Insurer list with enabled insurers by default.
frappe.listview_settings["Insurer"] = {
    onload(listview) {
        listview.filter_area.add([
            ["Insurer", "enabled", "=", 1],
        ]);
    },
};