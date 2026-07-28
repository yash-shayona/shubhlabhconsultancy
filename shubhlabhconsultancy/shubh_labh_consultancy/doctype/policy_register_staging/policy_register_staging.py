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

STAGING_DOCTYPE = "Policy Register Staging"
FINAL_DOCTYPE = "Policy Register"

COMMIT_BATCH_SIZE = 50
POSTABLE_VALIDATION_STATUSES = ("Valid",)

# This maps user-facing month selection to the stored first date of that month.
MONTH_NUMBER_BY_NAME = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}

MONTH_NAME_BY_NUMBER = {
    month_number: month_name for month_name, month_number in MONTH_NUMBER_BY_NAME.items()
}

# These actual DocType fields decide Policy Register duplicate fingerprint.
POLICY_REGISTER_FINGERPRINT_FIELDS = (
    "normalized_policy_number",
    "normalized_endorsement_number",
)


BUSINESS_FIELDS = (
    "business_month",
    "financial_year",
    "cno",
    "policy_type",
    "policy_number",
    "endorsement_number",
    "start_date",
    "expiry_date",
    "share_percentage",
    "brokerage_premium",
    "brokerage_percentage",
    "brokerage_amount",
    "tp_premium",
    "tp_brokerage_percentage",
    "tp_brokerage_amount",
    "total_brokerage",
    "total_brokerage_and_reward",
    "business_type",
    "insurer_name",
    "customer_name",
    "campaign_name",
)


class PolicyRegisterStaging(Document):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF

        brokerage_amount: DF.Currency
        brokerage_percentage: DF.Percent
        brokerage_premium: DF.Currency
        business_month: DF.Date | None
        business_type: DF.Literal["", "New", "Renewal"]
        campaign_name: DF.Data | None
        cno: DF.Int
        customer_name: DF.Data | None
        endorsement_number: DF.Data | None
        expiry_date: DF.Date | None
        financial_year: DF.Data | None
        has_warning: DF.Check
        ignore_reason: DF.SmallText | None
        ignore_record: DF.Check
        insurer_name: DF.Link | None
        is_duplicate: DF.Check
        normalized_customer_name: DF.Data | None
        normalized_endorsement_number: DF.Data | None
        normalized_insurer_name: DF.Data | None
        normalized_policy_number: DF.Data | None
        policy_number: DF.Data | None
        policy_type: DF.Data | None
        posted_policy_register: DF.Link | None
        processed_by: DF.Link | None
        processed_on: DF.Datetime | None
        processing_status: DF.Literal[
            "", "Not Processed", "Ready", "Processing", "Processed", "Ignored", "Failed"
        ]
        record_fingerprint: DF.Data | None
        share_percentage: DF.Percent
        start_date: DF.Date | None
        total_brokerage: DF.Currency
        total_brokerage_and_reward: DF.Currency
        tp_brokerage_amount: DF.Currency
        tp_brokerage_percentage: DF.Percent
        tp_premium: DF.Currency
        validation_messages: DF.SmallText | None
        validation_status: DF.Literal["", "Pending", "Valid", "Warning", "Invalid"]
    # end: auto-generated types

    """
    Business validation intentionally does not run on Insert/Save.

    Normal save lifecycle only handles:
    1. Initial statuses.
    2. Resetting validation after business fields are edited.
    3. Preventing edits after final posting.
    4. Ignore Record handling.
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
            if old_doc.posted_policy_register:
                frappe.throw(
                    _(
                        "This staging record is already posted to Policy Register {0}. "
                        "Its business data cannot be changed."
                    ).format(old_doc.posted_policy_register)
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

            if not self.posted_policy_register:
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
        self.normalized_endorsement_number = ""
        self.normalized_insurer_name = ""
        self.normalized_customer_name = ""
        self.record_fingerprint = ""


# -------------------------------------------------------------------------
# BUTTON ENTRY METHODS
# -------------------------------------------------------------------------


@frappe.whitelist()
def enqueue_pending_validation():
    """
    Called by the list header button.

    No checkbox selection is required.
    Finds every outstanding staging row that:
    - is not ignored,
    - is not already posted,
    - is not already processing,
    - is not already processed.
    """

    _check_validation_permission()

    record_names = _get_validation_candidates()

    if not record_names:
        return {
            "queued": False,
            "count": 0,
            "message": _("No pending Policy Register Staging records were found."),
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
    Called by the list header button.

    No checkbox selection is required.
    Finds every staging row that is:
    - Valid,
    - Ready,
    - not ignored,
    - not already linked to a final Policy Register.
    """

    _check_posting_permission()

    record_names = _get_posting_candidates()

    if not record_names:
        return {
            "queued": False,
            "count": 0,
            "message": _(
                "No validated and ready staging records were found for posting."
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
        "message": _("Posting has started in the background for {0} record(s).").format(
            len(record_names)
        ),
    }


# -------------------------------------------------------------------------
# BACKGROUND JOB: VALIDATION
# -------------------------------------------------------------------------


def run_pending_validation(record_names: list[str], requested_by: str):
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
        savepoint = f"prs_validate_{index}"
        frappe.db.savepoint(savepoint)

        try:
            staging = frappe.get_doc(STAGING_DOCTYPE, record_name)

            if staging.ignore_record:
                frappe.db.set_value(
                    STAGING_DOCTYPE,
                    record_name,
                    {"processing_status": "Ignored"},
                    update_modified=False,
                )

                summary["ignored"] += 1
                continue

            if staging.posted_policy_register:
                frappe.db.set_value(
                    STAGING_DOCTYPE,
                    record_name,
                    {"processing_status": "Processed"},
                    update_modified=False,
                )

                summary["already_processed"] += 1
                continue

            existing_final = frappe.db.get_value(
                FINAL_DOCTYPE,
                {"source_staging": staging.name},
                ["name", "docstatus"],
                as_dict=True,
            )

            if existing_final and existing_final.docstatus == 1:
                frappe.db.set_value(
                    STAGING_DOCTYPE,
                    record_name,
                    {
                        "posted_policy_register": existing_final.name,
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
                title=f"Policy Register Staging validation failed: {record_name}",
                message=frappe.get_traceback(),
            )

            summary["failed"] += 1

        if index % COMMIT_BATCH_SIZE == 0:
            frappe.db.commit()

    frappe.db.commit()

    frappe.publish_realtime(
        "policy_register_staging_job_complete",
        summary,
        user=requested_by,
    )


# -------------------------------------------------------------------------
# BACKGROUND JOB: POSTING
# -------------------------------------------------------------------------


def run_valid_posting(record_names: list[str], requested_by: str):
    """
    Posts records already decided as Valid + Ready by the validation job.

    No business validation is repeated here. Only technical safety guards are
    retained to prevent ignored/already-posted rows from creating duplicates.
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
        savepoint = f"prs_post_{index}"
        frappe.db.savepoint(savepoint)

        try:
            staging = frappe.get_doc(STAGING_DOCTYPE, record_name)

            if staging.ignore_record:
                frappe.db.set_value(
                    STAGING_DOCTYPE,
                    staging.name,
                    {"processing_status": "Ignored"},
                    update_modified=False,
                )

                summary["not_eligible"] += 1
                continue

            if staging.posted_policy_register:
                frappe.db.set_value(
                    STAGING_DOCTYPE,
                    staging.name,
                    {"processing_status": "Processed"},
                    update_modified=False,
                )

                summary["already_processed"] += 1
                continue

            existing_final = frappe.db.get_value(
                FINAL_DOCTYPE,
                {"source_staging": staging.name},
                ["name", "docstatus"],
                as_dict=True,
            )

            if existing_final:
                if existing_final.docstatus == 1:
                    frappe.db.set_value(
                        STAGING_DOCTYPE,
                        staging.name,
                        {
                            "posted_policy_register": existing_final.name,
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
                        "A draft Policy Register {0} already exists for this "
                        "staging record."
                    ).format(existing_final.name)
                )

            policy_register = _create_policy_register(
                staging=staging,
                requested_by=requested_by,
            )

            frappe.db.set_value(
                STAGING_DOCTYPE,
                staging.name,
                {
                    "posted_policy_register": policy_register.name,
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
                for message in (staging_messages, posting_error)
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
                title=f"Policy Register posting failed: {record_name}",
                message=frappe.get_traceback(),
            )

            summary["failed"] += 1

        if index % COMMIT_BATCH_SIZE == 0:
            frappe.db.commit()

    frappe.db.commit()

    frappe.publish_realtime(
        "policy_register_staging_job_complete",
        summary,
        user=requested_by,
    )


# -------------------------------------------------------------------------
# PHASE 1 VALIDATION LOGIC
# -------------------------------------------------------------------------


def _get_validation_result(staging: Document) -> dict:
    """
    Phase 1 validation rules only.

    Rules intentionally not included here:
    - CNO value/range validation
    - Policy period sequence validation
    - Share Percentage validation
    - Brokerage/financial calculation validation
    - Zero/negative amount warnings
    - Business Type allowed-value validation
    - Duplicate staging/final validation
    """

    errors: list[str] = []
    warnings: list[str] = []

    policy_type = cstr(staging.policy_type).strip()
    policy_number = cstr(staging.policy_number).strip()
    endorsement_number = cstr(staging.endorsement_number).strip()
    insurer_name = cstr(staging.insurer_name).strip()
    customer_name = cstr(staging.customer_name).strip()
    business_type = cstr(staging.business_type).strip()
    business_month = _get_month_start_date_from_fields(
        record=staging,
        month_fieldname="business_month_select",
        year_fieldname="business_year",
        date_fieldname="business_month",
        label="Business Month",
        errors=errors,
        required=False,
    )

    # Policy Type: required and numeric digits are not allowed.
    # Spaces and common punctuation remain allowed for practical names.
    if not policy_type:
        errors.append(_("Policy Type is missing."))
    # elif re.search(r"\d", policy_type):
    #     errors.append(_("Policy Type must not contain numeric digits."))

    # Policy Number: required and literal numeric zero is not accepted.
    if _is_blank_or_zero(policy_number):
        errors.append(_("Policy Number is required and cannot be zero."))

    # Endorsement Number has no format rule, but a meaningful value is required
    # because Phase 1 fingerprint is Policy Number + Endorsement Number.
    if _is_blank_or_zero(endorsement_number):
        warnings.append(
            _(
                "Endorsement Number is required and cannot be zero because "
                "it is used to generate the record fingerprint."
            )
        )

    # Date fields are not mandatory in Phase 1. If supplied, they must be dates.
    _validate_optional_date(staging.start_date, "Start Date", errors)
    _validate_optional_date(staging.expiry_date, "Expiry Date", errors)

    required_text_fields = {
        "Insurer Name": insurer_name,
        "Customer Name": customer_name,
        "Business Type": business_type,
    }

    for label, value in required_text_fields.items():
        if not value:
            errors.append(_("{0} is missing.").format(label))

    normalized_policy_number = _normalize_value(policy_number)
    normalized_endorsement_number = _normalize_value(endorsement_number)
    normalized_insurer_name = _normalize_value(insurer_name)
    normalized_customer_name = _normalize_value(customer_name)

    if business_month:
        staging.business_month = business_month
        staging.business_month_select = MONTH_NAME_BY_NUMBER[business_month.month]
        staging.business_year = business_month.year

    # These values are set on the in-memory document so fingerprint helper can read by fieldname.
    staging.normalized_policy_number = normalized_policy_number
    staging.normalized_endorsement_number = normalized_endorsement_number
    staging.normalized_insurer_name = normalized_insurer_name
    staging.normalized_customer_name = normalized_customer_name

    record_fingerprint = ""

    # This keeps the existing rule: normalized policy number + normalized endorsement number.
    if (
        not _is_blank_or_zero(policy_number)
        and not _is_blank_or_zero(endorsement_number)
        and normalized_policy_number
        and normalized_endorsement_number
    ):
        record_fingerprint = _make_record_fingerprint(
            staging,
            POLICY_REGISTER_FINGERPRINT_FIELDS,
        )

    # This blocks duplicate staging/final policy rows before posting.
    duplicate_message = _get_duplicate_fingerprint_message(
        staging=staging,
        record_fingerprint=record_fingerprint,
        final_doctype=FINAL_DOCTYPE,
    )

    if duplicate_message:
        errors.append(duplicate_message)

    if errors:
        validation_status = "Invalid"
        processing_status = "Not Processed"
    elif warnings:
        validation_status = "Warning"
        processing_status = "Ready"
    else:
        validation_status = "Valid"
        processing_status = "Ready"

    validation_messages = [_("ERROR: {0}").format(message) for message in errors] + [
        _("WARNING: {0}").format(message) for message in warnings
    ]

    return {
        "business_month": business_month,
        "business_month_select": staging.business_month_select,
        "business_year": staging.business_year,
        "normalized_policy_number": normalized_policy_number,
        "normalized_endorsement_number": normalized_endorsement_number,
        "normalized_insurer_name": normalized_insurer_name,
        "normalized_customer_name": normalized_customer_name,
        "record_fingerprint": record_fingerprint,
        "validation_status": validation_status,
        "validation_messages": "\n".join(validation_messages),
        "processing_status": processing_status,
        "has_warning": 1 if warnings else 0,
        "is_duplicate": 1 if duplicate_message else 0,
    }


# -------------------------------------------------------------------------
# FINAL POLICY REGISTER CREATION
# -------------------------------------------------------------------------


def _create_policy_register(
    staging: Document,
    requested_by: str,
) -> Document:
    source_data_import = _get_source_data_import(staging)
    expected_brokerage = _get_expected_brokerage_from_staging(staging)

    policy_register = frappe.get_doc(
        {
            "doctype": FINAL_DOCTYPE,
            "business_month": staging.business_month,
            "financial_year": staging.financial_year,
            "cno": staging.cno,
            "policy_type": staging.policy_type,
            "policy_number": staging.policy_number,
            "endorsement_number": staging.endorsement_number,
            "start_date": staging.start_date,
            "expiry_date": staging.expiry_date,
            "share_percentage": staging.share_percentage,
            "brokerage_premium": staging.brokerage_premium,
            "brokerage_percentage": staging.brokerage_percentage,
            "brokerage_amount": staging.brokerage_amount,
            "tp_premium": staging.tp_premium,
            "tp_brokerage_percentage": staging.tp_brokerage_percentage,
            "tp_brokerage_amount": staging.tp_brokerage_amount,
            "total_brokerage": staging.total_brokerage,
            "total_brokerage_and_reward": staging.total_brokerage_and_reward,
            "business_type": staging.business_type,
            "insurer_name": staging.insurer_name,
            "customer_name": staging.customer_name,
            "campaign_name": staging.campaign_name,
            "source_staging": staging.name,
            "source_data_import": source_data_import,
            "normalized_policy_number": staging.normalized_policy_number,
            "normalized_endorsement_number": staging.normalized_endorsement_number,
            "normalized_insurer_name": staging.normalized_insurer_name,
            "normalized_customer_name": staging.normalized_customer_name,
            "record_fingerprint": staging.record_fingerprint,
            "expected_brokerage": expected_brokerage,
            "settled_brokerage": 0,
            "written_off_brokerage": 0,
            "outstanding_brokerage": expected_brokerage,
            "reconciliation_status": "Pending",
        }
    )

    # Permission is checked before the background job is queued.
    policy_register.flags.ignore_permissions = True

    policy_register.insert()
    policy_register.submit()

    return policy_register


# This decides the receivable amount for Policy Register from staging totals.
def _get_expected_brokerage_from_staging(staging: Document) -> float:
    total_brokerage_and_reward = flt(staging.total_brokerage_and_reward)

    if total_brokerage_and_reward:
        return total_brokerage_and_reward

    return flt(staging.total_brokerage)


# -------------------------------------------------------------------------
# QUERY HELPERS
# -------------------------------------------------------------------------


def _get_validation_candidates() -> list[str]:
    return frappe.get_all(
        STAGING_DOCTYPE,
        filters=[
            ["posted_policy_register", "is", "not set"],
            ["ignore_record", "=", 0],
            [
                "processing_status",
                "not in",
                ["Processed", "Processing", "Ignored"],
            ],
        ],
        pluck="name",
        order_by="creation asc",
    )


def _get_posting_candidates() -> list[str]:
    return frappe.get_all(
        STAGING_DOCTYPE,
        filters=[
            ["posted_policy_register", "is", "not set"],
            ["ignore_record", "=", 0],
            [
                "validation_status",
                "in",
                list(POSTABLE_VALIDATION_STATUSES),
            ],
            ["processing_status", "=", "Ready"],
        ],
        pluck="name",
        order_by="creation asc",
    )


def _mark_records_as_processing(record_names: list[str]):
    for record_name in record_names:
        frappe.db.set_value(
            STAGING_DOCTYPE,
            record_name,
            "processing_status",
            "Processing",
            update_modified=False,
        )


def _get_source_data_import(staging: Document) -> str | None:
    logs = frappe.get_all(
        "Data Import Log",
        filters={
            "docname": staging.name,
            "success": 1,
            "creation": [">=", staging.creation],
        },
        fields=["data_import"],
        order_by="creation desc",
        limit_page_length=1,
    )

    return logs[0].data_import if logs else None


# -------------------------------------------------------------------------
# NORMALIZATION / FINGERPRINT HELPERS
# -------------------------------------------------------------------------


def _normalize_value(value) -> str:
    return re.sub(
        r"[^A-Z0-9]",
        "",
        cstr(value).upper().strip(),
    )


# This creates fingerprint from configured fieldnames by reading values from the document.
def _make_record_fingerprint(
    record: Document, fingerprint_fields: tuple[str, ...]
) -> str:
    raw_value = "|".join(
        cstr(record.get(fieldname)) for fieldname in fingerprint_fields
    )

    return hashlib.sha256(raw_value.encode("utf-8")).hexdigest()


# This checks whether the same fingerprint already exists in staging or final records.
def _get_duplicate_fingerprint_message(
    staging: Document,
    record_fingerprint: str,
    final_doctype: str,
) -> str:
    if not record_fingerprint:
        return ""

    final_duplicate = frappe.db.get_value(
        final_doctype,
        {
            "record_fingerprint": record_fingerprint,
            "docstatus": ["<", 2],
        },
        "name",
    )

    if final_duplicate:
        return _("Duplicate record already posted as {0} {1}.").format(
            final_doctype,
            final_duplicate,
        )

    staging_duplicate = frappe.db.get_value(
        STAGING_DOCTYPE,
        {
            "record_fingerprint": record_fingerprint,
            "name": ["!=", staging.name],
            "ignore_record": 0,
            "validation_status": ["!=", "Invalid"],
        },
        "name",
    )

    if staging_duplicate:
        return _("Duplicate staging record found: {0}.").format(staging_duplicate)

    return ""


# -------------------------------------------------------------------------
# GENERAL HELPERS
# -------------------------------------------------------------------------


def _is_blank_or_zero(value) -> bool:
    """
    Returns True for blank values and values representing numeric zero.

    Examples treated as invalid:
    - None
    - ""
    - "   "
    - 0
    - "0"
    - "0.00"

    Alphanumeric values such as "0A", "POL-0" or "00/1" are not treated as
    numeric zero and therefore remain valid identifiers.
    """

    text_value = cstr(value).strip()

    if not text_value:
        return True

    numeric_candidate = text_value.replace(",", "")

    try:
        return Decimal(numeric_candidate) == 0
    except InvalidOperation:
        return False


def _validate_optional_date(value, label: str, errors: list[str]):
    if value in (None, ""):
        return

    # A raw number is not accepted as a date value by this validation rule.
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        errors.append(_("{0} must contain a valid date.").format(label))
        return

    try:
        getdate(value)
    except Exception:
        errors.append(_("{0} must contain a valid date.").format(label))


# This returns the first date of a month from Month/Year fields or an existing Date field.
def _get_month_start_date_from_fields(
    record: Document,
    month_fieldname: str,
    year_fieldname: str,
    date_fieldname: str,
    label: str,
    errors: list[str],
    required: bool,
):
    month_name = cstr(record.get(month_fieldname)).strip()
    year = record.get(year_fieldname)

    if month_name or year:
        if not month_name or not year:
            errors.append(_("{0} and Year are required together.").format(label))
            return None

        month_number = MONTH_NUMBER_BY_NAME.get(month_name)

        if not month_number:
            errors.append(_("{0} is invalid.").format(label))
            return None

        try:
            year = int(year)
        except (TypeError, ValueError):
            errors.append(_("{0} Year must contain a valid year.").format(label))
            return None

        return getdate(f"{year}-{month_number:02d}-01")

    date_value = record.get(date_fieldname)

    if date_value in (None, ""):
        if required:
            errors.append(_("{0} is missing.").format(label))

        return None

    try:
        date_value = getdate(date_value)
    except Exception:
        errors.append(_("{0} must contain a valid date.").format(label))
        return None

    return date_value.replace(day=1)


def _check_validation_permission():
    if not frappe.has_permission(
        STAGING_DOCTYPE,
        ptype="write",
    ):
        frappe.throw(
            _("You do not have permission to validate staging records."),
            frappe.PermissionError,
        )


def _check_posting_permission():
    if not frappe.has_permission(
        STAGING_DOCTYPE,
        ptype="write",
    ):
        frappe.throw(
            _("You do not have permission to update staging records."),
            frappe.PermissionError,
        )

    if not frappe.has_permission(
        FINAL_DOCTYPE,
        ptype="create",
    ):
        frappe.throw(
            _("You do not have permission to create Policy Register records."),
            frappe.PermissionError,
        )

    if not frappe.has_permission(
        FINAL_DOCTYPE,
        ptype="submit",
    ):
        frappe.throw(
            _("You do not have permission to submit Policy Register records."),
            frappe.PermissionError,
        )
