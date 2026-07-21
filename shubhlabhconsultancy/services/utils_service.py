import os
import json

import frappe
from frappe.utils.file_manager import get_content_hash, save_file, save_url

def load_json(filepath):
    # try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    # except FileNotFoundError:
        # frappe.throw("File not found.")


# ---------------------------------------------------------
# 🔹 Common File Upload Helper
# ---------------------------------------------------------
def attach_file(file_path, doctype, docname, filename, is_private=1, attached_to_field=None):
    """Attach a file to a document and return the file URL."""

    if not os.path.exists(file_path):
        return None

    with open(file_path, "rb") as f:
        file_content = f.read()

    content_hash = get_content_hash(file_content)
    existing_files = frappe.get_all(
        "File",
        filters={"content_hash": content_hash, "is_private": is_private},
        fields=["file_url", "file_name"],
        order_by="creation asc",
    )

    existing_file = next((row for row in existing_files if row.file_name == filename), None)
    if not existing_file and existing_files:
        existing_file = existing_files[0]

    if existing_file:
        if doctype and docname:
            file_link_exists = frappe.db.exists(
                "File",
                {
                    "file_url": existing_file.file_url,
                    "attached_to_doctype": doctype,
                    "attached_to_name": docname,
                    "attached_to_field": attached_to_field,
                },
            )
            if not file_link_exists:
                save_url(
                    existing_file.file_url,
                    existing_file.file_name,
                    doctype,
                    docname,
                    "Home/Attachments",
                    is_private,
                    df=attached_to_field,
                )
        return existing_file.file_url

    file_doc = save_file(
        fname=filename,
        content=file_content,
        dt=doctype,
        dn=docname,
        folder="Home/Attachments",
        is_private=is_private,
        df=attached_to_field,
    )

    return file_doc.file_url

def success(message="Success", data=None, status_code=200):
    frappe.local.response["http_status_code"] = status_code

    return {
        "success": True,
        "message": message,
        "data": data or {}
    }

def error(message="Something went wrong", status_code=400, errors=None):
    frappe.local.response["http_status_code"] = status_code

    return {
        "success": False,
        "message": message,
        "errors": errors or []
    }

def validation(message="Validation failed", errors=None):
    frappe.local.response["http_status_code"] = 422

    return {
        "success": False,
        "message": message,
        "errors": errors or []
    }

def not_found(message="Resource not found"):
    frappe.local.response["http_status_code"] = 404

    return {
        "success": False,
        "message": message
    }

def server_error(message="Internal server error"):
    frappe.local.response["http_status_code"] = 500

    return {
        "success": False,
        "message": message
    }
