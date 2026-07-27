# Copyright (c) 2026, Shayona Technology and contributors
# For license information, please see license.txt

from __future__ import annotations

import hashlib
import re
from decimal import Decimal, InvalidOperation

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr, flt, getdate, now_datetime

STAGING_DOCTYPE = "Brokerage Statement Staging"
FINAL_DOCTYPE = "Brokerage Statement"

COMMIT_BATCH_SIZE = 50

# Abhi sirf completely valid rows post hongi.
# Warning approval flow future phase me add kar sakte hain.
POSTABLE_VALIDATION_STATUSES = ("Valid",)


BUSINESS_FIELDS = (
    "statement_month",
    "insurer_name",
    "policy_number",
    "customer_name",
    "start_date",
    "expiry_date",
    "brokerage_received",
)


class BrokerageStatementStaging(Document):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF

        brokerage_received: DF.Currency
        customer_name: DF.Data | None
        expiry_date: DF.Date | None
        has_warning: DF.Check
        ignore_reason: DF.SmallText | None
        ignore_record: DF.Check
        insurer_name: DF.Link | None
        is_duplicate: DF.Check
        normalized_customer_name: DF.Data | None
        normalized_insurer_name: DF.Data | None
        normalized_policy_number: DF.Data | None
        policy_number: DF.Data | None
        posted_brokerage_statement: DF.Link | None
        processed_by: DF.Link | None
        processed_on: DF.Datetime | None
        processing_status: DF.Literal["", "Not Processed", "Ready", "Processing", "Processed", "Ignored", "Failed"]
        record_fingerprint: DF.Data | None
        start_date: DF.Date | None
        statement_month: DF.Date | None
        validation_messages: DF.SmallText | None
        validation_status: DF.Literal["", "Pending", "Valid", "Warning", "Invalid"]
    # end: auto-generated types

    """
    Business validation Insert/Save ke time run nahi hoti.

    Normal document lifecycle sirf:

    1. Initial status set karta hai.
    2. Business field edit hone par validation reset karta hai.
    3. Posted record ke business fields edit hone se rokta hai.
    4. Processing record edit hone se rokta hai.
    5. Ignore Record handling karta hai.
    """

    def before_insert(self):
        if not self.validation_status:
            self.validation_status = "Pending"

        if not self.processing_status:
            self.processing_status = "Not Processed"

        self.has_warning = 0
        self.is_duplicate = 0

    def validate(self):
        old_doc = None

        if not self.is_new():
            old_doc = self.get_doc_before_save()

        business_data_changed = self._business_data_changed(old_doc)

        if old_doc and business_data_changed:
            if old_doc.posted_brokerage_statement:
                frappe.throw(
                    _(
                        "This staging record is already posted to Brokerage "
                        "Statement {0}. Its business data cannot be changed."
                    ).format(old_doc.posted_brokerage_statement)
                )

            if old_doc.processing_status == "Processing":
                frappe.throw(
                    _(
                        "This record is currently being processed. "
                        "Please wait for the background job to complete."
                    )
                )

            self._reset_validation_status()

        if self.ignore_record:
            if not cstr(self.ignore_reason).strip():
                frappe.throw(_("Ignore Reason is required."))

            if not self.posted_brokerage_statement:
                self.processing_status = "Ignored"

        elif old_doc and old_doc.ignore_record and not self.ignore_record:
            self._reset_validation_status()

    def _business_data_changed(self, old_doc):
        if not old_doc:
            return False

        return any(
            old_doc.get(fieldname) != self.get(fieldname)
            for fieldname in BUSINESS_FIELDS
        )

    def _reset_validation_status(self):
        self.validation_status = "Pending"
        self.processing_status = "Not Processed"
        self.validation_messages = ""

        self.has_warning = 0
        self.is_duplicate = 0

        self.normalized_policy_number = ""
        self.normalized_insurer_name = ""
        self.normalized_customer_name = ""
        self.record_fingerprint = ""


# -------------------------------------------------------------------------
# LIST BUTTON ENTRY METHODS
# -------------------------------------------------------------------------


@frappe.whitelist()
def enqueue_pending_validation():
    """
    List header ke Validate button se call hoga.

    Checkbox selection required nahi hai.

    Eligible records:
    - Ignore nahi kiya gaya.
    - Already posted nahi hai.
    - Currently Processing nahi hai.
    - Already Processed nahi hai.
    """

    _check_validation_permission()

    record_names = _get_validation_candidates()

    if not record_names:
        return {
            "queued": False,
            "count": 0,
            "message": _("No pending Brokerage Statement Staging records were found."),
        }

    _mark_records_as_processing(record_names)

    requested_by = frappe.session.user

    frappe.enqueue(
        run_pending_validation,
        queue="long",
        timeout=1500,
        enqueue_after_commit=True,
        record_names=record_names,
        requested_by=requested_by,
    )

    return {
        "queued": True,
        "count": len(record_names),
        "message": _(
            "Validation has started in the background for {0} record(s)."
        ).format(len(record_names)),
    }


@frappe.whitelist()
def enqueue_valid_posting():
    """
    List header ke Post button se call hoga.

    Eligible records:
    - Validation Status = Valid
    - Processing Status = Ready
    - Ignore nahi kiya gaya.
    - Already final document se linked nahi hai.
    """

    _check_posting_permission()

    record_names = _get_posting_candidates()

    if not record_names:
        return {
            "queued": False,
            "count": 0,
            "message": _(
                "No validated and ready Brokerage Statement Staging "
                "records were found for posting."
            ),
        }

    _mark_records_as_processing(record_names)

    requested_by = frappe.session.user

    frappe.enqueue(
        run_valid_posting,
        queue="long",
        timeout=1500,
        enqueue_after_commit=True,
        record_names=record_names,
        requested_by=requested_by,
    )

    return {
        "queued": True,
        "count": len(record_names),
        "message": _(
            "Brokerage Statement posting has started in the background "
            "for {0} record(s)."
        ).format(len(record_names)),
    }


# -------------------------------------------------------------------------
# BACKGROUND JOB: VALIDATION
# -------------------------------------------------------------------------


def run_pending_validation(
    record_names: list[str],
    requested_by: str,
):
    summary = {
        "action": "validation",
        "total": len(record_names),
        "valid": 0,
        "warning": 0,
        "invalid": 0,
        "ignored": 0,
        "already_processed": 0,
        "failed": 0,
    }

    for index, record_name in enumerate(record_names, start=1):
        savepoint = f"bss_validate_{index}"

        frappe.db.savepoint(savepoint)

        try:
            staging = frappe.get_doc(
                STAGING_DOCTYPE,
                record_name,
            )

            # Job queue hone ke baad user ne record Ignore kar diya.
            if staging.ignore_record:
                frappe.db.set_value(
                    STAGING_DOCTYPE,
                    record_name,
                    {
                        "processing_status": "Ignored",
                    },
                    update_modified=False,
                )

                summary["ignored"] += 1
                continue

            # Staging record already final document se linked hai.
            if staging.posted_brokerage_statement:
                frappe.db.set_value(
                    STAGING_DOCTYPE,
                    record_name,
                    {
                        "processing_status": "Processed",
                    },
                    update_modified=False,
                )

                summary["already_processed"] += 1
                continue

            # Link missing ho sakta hai, lekin final document already exist kare.
            existing_final = frappe.db.get_value(
                FINAL_DOCTYPE,
                {
                    "source_staging": staging.name,
                },
                [
                    "name",
                    "docstatus",
                ],
                as_dict=True,
            )

            if existing_final and existing_final.docstatus == 1:
                frappe.db.set_value(
                    STAGING_DOCTYPE,
                    record_name,
                    {
                        "posted_brokerage_statement": existing_final.name,
                        "processing_status": "Processed",
                    },
                    update_modified=False,
                )

                summary["already_processed"] += 1
                continue

            result = _get_validation_result(staging)

            frappe.db.set_value(
                STAGING_DOCTYPE,
                record_name,
                result,
                update_modified=False,
            )

            status_key = cstr(result["validation_status"]).lower()

            if status_key in summary:
                summary[status_key] += 1

        except Exception as exc:
            frappe.db.rollback(save_point=savepoint)

            error_message = _("Unexpected validation error: {0}").format(cstr(exc))

            frappe.db.set_value(
                STAGING_DOCTYPE,
                record_name,
                {
                    "validation_status": "Invalid",
                    "processing_status": "Failed",
                    "validation_messages": error_message,
                    "has_warning": 0,
                    "is_duplicate": 0,
                },
                update_modified=False,
            )

            frappe.log_error(
                title=(
                    "Brokerage Statement Staging validation failed: " f"{record_name}"
                ),
                message=frappe.get_traceback(),
            )

            summary["failed"] += 1

        if index % COMMIT_BATCH_SIZE == 0:
            frappe.db.commit()

    frappe.db.commit()

    frappe.publish_realtime(
        "brokerage_statement_staging_job_complete",
        summary,
        user=requested_by,
    )


# -------------------------------------------------------------------------
# BACKGROUND JOB: POSTING
# -------------------------------------------------------------------------


def run_valid_posting(
    record_names: list[str],
    requested_by: str,
):
    """
    Valid + Ready staging records ko Brokerage Statement me post karta hai.

    Business validation yahan repeat nahi hoti. Technical guards retain kiye
    gaye hain taaki ignored ya already-posted row duplicate final document
    create na kare.
    """

    summary = {
        "action": "posting",
        "total": len(record_names),
        "posted": 0,
        "already_processed": 0,
        "not_eligible": 0,
        "failed": 0,
    }

    for index, record_name in enumerate(record_names, start=1):
        savepoint = f"bss_post_{index}"

        frappe.db.savepoint(savepoint)

        try:
            staging = frappe.get_doc(
                STAGING_DOCTYPE,
                record_name,
            )

            if staging.ignore_record:
                frappe.db.set_value(
                    STAGING_DOCTYPE,
                    staging.name,
                    {
                        "processing_status": "Ignored",
                    },
                    update_modified=False,
                )

                summary["not_eligible"] += 1
                continue

            if staging.posted_brokerage_statement:
                frappe.db.set_value(
                    STAGING_DOCTYPE,
                    staging.name,
                    {
                        "processing_status": "Processed",
                    },
                    update_modified=False,
                )

                summary["already_processed"] += 1
                continue

            # Processing ke beech status manually change hua ho to guard.
            if (
                staging.validation_status not in POSTABLE_VALIDATION_STATUSES
                or staging.processing_status != "Processing"
            ):
                frappe.db.set_value(
                    STAGING_DOCTYPE,
                    staging.name,
                    {
                        "processing_status": "Not Processed",
                    },
                    update_modified=False,
                )

                summary["not_eligible"] += 1
                continue

            existing_final = frappe.db.get_value(
                FINAL_DOCTYPE,
                {
                    "source_staging": staging.name,
                },
                [
                    "name",
                    "docstatus",
                ],
                as_dict=True,
            )

            if existing_final:
                if existing_final.docstatus == 1:
                    frappe.db.set_value(
                        STAGING_DOCTYPE,
                        staging.name,
                        {
                            "posted_brokerage_statement": (existing_final.name),
                            "processing_status": "Processed",
                            "processed_by": requested_by,
                            "processed_on": now_datetime(),
                        },
                        update_modified=False,
                    )

                    summary["already_processed"] += 1
                    continue

                frappe.throw(
                    _(
                        "A non-submitted Brokerage Statement {0} already "
                        "exists for this staging record."
                    ).format(existing_final.name)
                )

            brokerage_statement = _create_brokerage_statement(
                staging=staging,
            )

            frappe.db.set_value(
                STAGING_DOCTYPE,
                staging.name,
                {
                    "posted_brokerage_statement": (brokerage_statement.name),
                    "processing_status": "Processed",
                    "processed_by": requested_by,
                    "processed_on": now_datetime(),
                },
                update_modified=False,
            )

            summary["posted"] += 1

        except Exception as exc:
            frappe.db.rollback(save_point=savepoint)

            staging_messages = frappe.db.get_value(
                STAGING_DOCTYPE,
                record_name,
                "validation_messages",
            )

            posting_error = _("Posting failed: {0}").format(cstr(exc))

            combined_message = "\n".join(
                message
                for message in (
                    staging_messages,
                    posting_error,
                )
                if cstr(message).strip()
            )

            frappe.db.set_value(
                STAGING_DOCTYPE,
                record_name,
                {
                    "processing_status": "Failed",
                    "validation_messages": combined_message,
                },
                update_modified=False,
            )

            frappe.log_error(
                title=("Brokerage Statement posting failed: " f"{record_name}"),
                message=frappe.get_traceback(),
            )

            summary["failed"] += 1

        if index % COMMIT_BATCH_SIZE == 0:
            frappe.db.commit()

    frappe.db.commit()

    frappe.publish_realtime(
        "brokerage_statement_staging_job_complete",
        summary,
        user=requested_by,
    )


# -------------------------------------------------------------------------
# PHASE 1 VALIDATION LOGIC
# -------------------------------------------------------------------------


def _get_validation_result(
    staging: Document,
) -> dict:
    """
    Minimal Phase-1 validation.

    Included:
    - Statement Month required and valid.
    - Policy Number required and cannot be numeric zero.
    - Company Name required.
    - Optional Start Date and Expiry Date validation.
    - Expiry Date cannot be earlier than Start Date.
    - Brokerage Received must contain a numeric value.

    Intentionally not included yet:
    - Customer Name warning.
    - Zero or negative brokerage warning.
    - Duplicate detection.
    - Policy Register matching.
    - Company / insurer matching.
    - Customer similarity.
    - Multiple Policy Register match warning.
    """

    errors: list[str] = []

    policy_number = cstr(staging.policy_number).strip()

    insurer_name = cstr(staging.insurer_name).strip()

    customer_name = cstr(staging.customer_name).strip()

    statement_month = _get_valid_date(
        value=staging.statement_month,
        label="Statement Month",
        errors=errors,
        required=True,
    )

    start_date = _get_valid_date(
        value=staging.start_date,
        label="Start Date",
        errors=errors,
        required=False,
    )

    expiry_date = _get_valid_date(
        value=staging.expiry_date,
        label="Expiry Date",
        errors=errors,
        required=False,
    )

    if _is_blank_or_zero(policy_number):
        errors.append(_("Policy Number is required and cannot be zero."))

    if not insurer_name:
        errors.append(_("Insurer Name is missing."))

    if start_date and expiry_date and expiry_date < start_date:
        errors.append(_("Expiry Date is earlier than Start Date."))

    brokerage_received = _get_decimal_value(
        value=staging.brokerage_received,
        label="Brokerage Received",
        errors=errors,
    )

    normalized_policy_number = _normalize_value(policy_number)

    normalized_insurer_name = _normalize_value(insurer_name)

    normalized_customer_name = _normalize_value(customer_name)

    record_fingerprint = ""

    if normalized_policy_number and normalized_insurer_name:
        record_fingerprint = _make_record_fingerprint(
            statement_month=statement_month,
            normalized_policy_number=(normalized_policy_number),
            normalized_insurer_name=(normalized_insurer_name),
            normalized_customer_name=(normalized_customer_name),
            start_date=start_date,
            expiry_date=expiry_date,
            brokerage_received=brokerage_received,
        )

    if errors:
        validation_status = "Invalid"
        processing_status = "Not Processed"
    else:
        validation_status = "Valid"
        processing_status = "Ready"

    validation_messages = [_("ERROR: {0}").format(message) for message in errors]

    return {
        "normalized_policy_number": (normalized_policy_number),
        "normalized_insurer_name": (normalized_insurer_name),
        "normalized_customer_name": (normalized_customer_name),
        "record_fingerprint": record_fingerprint,
        "validation_status": validation_status,
        "processing_status": processing_status,
        "validation_messages": "\n".join(validation_messages),
        "has_warning": 0,
        "is_duplicate": 0,
    }


# -------------------------------------------------------------------------
# FINAL BROKERAGE STATEMENT CREATION
# -------------------------------------------------------------------------


def _create_brokerage_statement(
    staging: Document,
) -> Document:
    source_data_import = _get_source_data_import(staging.name)

    brokerage_received = flt(staging.brokerage_received)

    brokerage_statement = frappe.get_doc(
        {
            "doctype": FINAL_DOCTYPE,
            "statement_month": (staging.statement_month),
            "insurer_name": staging.insurer_name,
            "policy_number": staging.policy_number,
            "customer_name": staging.customer_name,
            "start_date": staging.start_date,
            "expiry_date": staging.expiry_date,
            "brokerage_received": brokerage_received,
            "allocated_brokerage": 0,
            "unallocated_brokerage": (brokerage_received),
            "reconciliation_status": "Unallocated",
            "source_staging": staging.name,
            "source_data_import": source_data_import,
        }
    )

    # Permission already enqueue method me check ho chuki hai.
    brokerage_statement.flags.ignore_permissions = True

    brokerage_statement.insert()
    brokerage_statement.submit()

    return brokerage_statement


# -------------------------------------------------------------------------
# QUERY HELPERS
# -------------------------------------------------------------------------


def _get_validation_candidates() -> list[str]:
    return frappe.get_all(
        STAGING_DOCTYPE,
        filters=[
            [
                "posted_brokerage_statement",
                "is",
                "not set",
            ],
            [
                "ignore_record",
                "=",
                0,
            ],
            [
                "processing_status",
                "not in",
                [
                    "Processed",
                    "Processing",
                    "Ignored",
                ],
            ],
        ],
        pluck="name",
        order_by="creation asc",
    )


def _get_posting_candidates() -> list[str]:
    return frappe.get_all(
        STAGING_DOCTYPE,
        filters=[
            [
                "posted_brokerage_statement",
                "is",
                "not set",
            ],
            [
                "ignore_record",
                "=",
                0,
            ],
            [
                "validation_status",
                "in",
                list(POSTABLE_VALIDATION_STATUSES),
            ],
            [
                "processing_status",
                "=",
                "Ready",
            ],
        ],
        pluck="name",
        order_by="creation asc",
    )


def _mark_records_as_processing(
    record_names: list[str],
):
    for record_name in record_names:
        frappe.db.set_value(
            STAGING_DOCTYPE,
            record_name,
            "processing_status",
            "Processing",
            update_modified=False,
        )


def _get_source_data_import(
    staging_name: str,
) -> str | None:
    logs = frappe.get_all(
        "Data Import Log",
        filters={
            "docname": staging_name,
            "success": 1,
        },
        fields=[
            "data_import",
        ],
        order_by="creation desc",
        limit_page_length=1,
    )

    return logs[0].data_import if logs else None


# -------------------------------------------------------------------------
# NORMALIZATION / FINGERPRINT HELPERS
# -------------------------------------------------------------------------


def _normalize_value(value) -> str:
    """
    Spaces, slash, dash and other punctuation remove karke
    uppercase alphanumeric matching value return karta hai.

    Example:
    POL-123 / A -> POL123A
    """

    return re.sub(
        r"[^A-Z0-9]",
        "",
        cstr(value).upper().strip(),
    )


def _make_record_fingerprint(
    statement_month,
    normalized_policy_number: str,
    normalized_insurer_name: str,
    normalized_customer_name: str,
    start_date,
    expiry_date,
    brokerage_received: Decimal | None,
) -> str:
    normalized_amount = ""

    if brokerage_received is not None:
        normalized_amount = format(
            brokerage_received.normalize(),
            "f",
        )

    raw_value = "|".join(
        (
            cstr(statement_month),
            normalized_policy_number,
            normalized_insurer_name,
            normalized_customer_name,
            cstr(start_date),
            cstr(expiry_date),
            normalized_amount,
        )
    )

    return hashlib.sha256(raw_value.encode("utf-8")).hexdigest()


# -------------------------------------------------------------------------
# GENERAL VALIDATION HELPERS
# -------------------------------------------------------------------------


def _is_blank_or_zero(value) -> bool:
    """
    Blank aur literal numeric zero values ko invalid maanta hai.

    Invalid:
    - None
    - ""
    - " "
    - 0
    - "0"
    - "0.00"

    Valid identifiers:
    - "0A"
    - "POL-0"
    - "00/1"
    """

    text_value = cstr(value).strip()

    if not text_value:
        return True

    numeric_candidate = text_value.replace(
        ",",
        "",
    )

    try:
        return Decimal(numeric_candidate) == Decimal("0")

    except InvalidOperation:
        return False


def _get_valid_date(
    value,
    label: str,
    errors: list[str],
    required: bool,
):
    if value in (None, ""):
        if required:
            errors.append(_("{0} is missing.").format(label))

        return None

    # Numeric Excel serial value ko direct valid date nahi maana jayega.
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        errors.append(_("{0} must contain a valid date.").format(label))

        return None

    try:
        return getdate(value)

    except Exception:
        errors.append(_("{0} must contain a valid date.").format(label))

        return None


def _get_decimal_value(
    value,
    label: str,
    errors: list[str],
) -> Decimal | None:
    """
    Brokerage Received numeric hai ya nahi check karta hai.

    Blank Currency value ko zero maana gaya hai because DocType field ka
    default bhi zero hai. Zero/negative warning future phase me add hogi.
    """

    text_value = cstr(value).strip()

    if not text_value:
        return Decimal("0")

    numeric_candidate = text_value.replace(
        ",",
        "",
    )

    try:
        return Decimal(numeric_candidate)

    except InvalidOperation:
        errors.append(_("{0} must contain a numeric value.").format(label))

        return None


# -------------------------------------------------------------------------
# PERMISSION HELPERS
# -------------------------------------------------------------------------


def _check_validation_permission():
    if not frappe.has_permission(
        STAGING_DOCTYPE,
        ptype="write",
    ):
        frappe.throw(
            _(
                "You do not have permission to validate "
                "Brokerage Statement Staging records."
            ),
            frappe.PermissionError,
        )


def _check_posting_permission():
    if not frappe.has_permission(
        STAGING_DOCTYPE,
        ptype="write",
    ):
        frappe.throw(
            _(
                "You do not have permission to update "
                "Brokerage Statement Staging records."
            ),
            frappe.PermissionError,
        )

    if not frappe.has_permission(
        FINAL_DOCTYPE,
        ptype="create",
    ):
        frappe.throw(
            _("You do not have permission to create " "Brokerage Statement records."),
            frappe.PermissionError,
        )

    if not frappe.has_permission(
        FINAL_DOCTYPE,
        ptype="submit",
    ):
        frappe.throw(
            _("You do not have permission to submit " "Brokerage Statement records."),
            frappe.PermissionError,
        )
