// This centralizes the website and existing reconciliation API method names.
const BROKERAGE_PORTAL_METHODS = {
    get_enabled_insurers:
        "shubhlabhconsultancy.permissions.reconciliation_portal.get_enabled_insurers",
    get_reconciliation_status:
        "shubhlabhconsultancy.permissions.reconciliation_portal.get_reconciliation_status",
    start_reconciliation:
        "shubhlabhconsultancy.shubh_labh_consultancy.page.brokerage_reconciliation_tool.brokerage_reconciliation_tool.start_reconciliation",
};

// This keeps month labels consistent with the existing reconciliation DocType.
const BROKERAGE_MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
];

// This controls how often the page falls back to the saved server status.
const RECONCILIATION_STATUS_POLL_INTERVAL_MS = 5000;

// This remembers the current run in memory and persists its name in the URL/browser.
const brokeragePortalState = {
    currentReconciliation: null,
    pollTimer: null,
    hasLiveProgress: false,
};

// This collects all page elements once so event handlers stay simple.
const brokerageElements = {
    insurer: document.getElementById("insurer-name"),
    month: document.getElementById("statement-month"),
    year: document.getElementById("statement-year"),
    reconciliationDate: document.getElementById("reconciliation-date"),
    tolerance: document.getElementById("amount-tolerance"),
    includeEarlierBusiness: document.getElementById("include-earlier-business"),
    actionButtons: document.querySelectorAll("[data-action]"),
    statusBadge: document.getElementById("run-status-badge"),
    emptyState: document.getElementById("run-empty-state"),
    result: document.getElementById("run-result"),
    resultTitle: document.getElementById("run-result-title"),
    resultMessage: document.getElementById("run-result-message"),
    progressCard: document.getElementById("reconciliation-progress"),
    progressPhase: document.getElementById("progress-phase"),
    progressPercentage: document.getElementById("progress-percentage"),
    progressTrack: document.getElementById("progress-track"),
    progressBar: document.getElementById("progress-bar"),
    progressCount: document.getElementById("progress-count"),
    checkedLabel: document.getElementById("checked-label"),
    createdLabel: document.getElementById("created-label"),
    unmatchedLabel: document.getElementById("unmatched-label"),
    recordsChecked: document.getElementById("records-checked"),
    recordsCreated: document.getElementById("records-created"),
    recordsUnmatched: document.getElementById("records-unmatched"),
    recordsFailed: document.getElementById("records-failed"),
    reconciliationLink: document.getElementById("open-reconciliation-link"),
    settlementsLink: document.getElementById("open-settlements-link"),
};

// This calls a whitelisted backend method and returns only its message payload.
async function callBrokeragePortal(methodName, args = {}) {
    const method = BROKERAGE_PORTAL_METHODS[methodName];

    if (!method) {
        throw new Error(`Brokerage portal method is not configured: ${methodName}`);
    }

    const response = await frappe.call({
        method,
        args,
    });

    return response.message;
}

// This converts the local browser date into Frappe's YYYY-MM-DD Date field format.
function getTodayDate() {
    const today = new Date();
    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, "0");
    const day = String(today.getDate()).padStart(2, "0");

    return `${year}-${month}-${day}`;
}

// This uses Frappe's standard modal so an error is visible at the clicked action.
function showFrappeMessage(message, title = "Brokerage Reconciliation", indicator = "red") {
    frappe.msgprint({
        title,
        indicator,
        message: frappe.utils.escape_html(message),
    });
}

// This extracts the most useful Frappe message from an API failure.
function getErrorMessage(error, fallback = "Something went wrong. Please try again.") {
    const serverMessages =
        error?._server_messages || error?.responseJSON?._server_messages;

    if (!serverMessages) {
        return error?.message || fallback;
    }

    try {
        const parsedMessages = JSON.parse(serverMessages);
        const firstMessage = parsedMessages?.[0]
            ? JSON.parse(parsedMessages[0])
            : null;

        if (typeof firstMessage === "string") {
            return firstMessage;
        }

        return firstMessage?.message || fallback;
    } catch (parseError) {
        return fallback;
    }
}

// This changes both action buttons together to prevent duplicate job requests.
function setActionButtonsProcessing(isProcessing) {
    brokerageElements.actionButtons.forEach((button) => {
        button.disabled = isProcessing;
    });
}

// This updates the status badge using controlled page state classes.
function setRunStatus(label, status) {
    brokerageElements.statusBadge.textContent = label;
    brokerageElements.statusBadge.className = `slc-run-badge is-${status}`;
}

// This fills static month and date defaults before the user starts a run.
function setDefaultFormValues() {
    const today = new Date();

    BROKERAGE_MONTHS.forEach((monthName) => {
        const option = document.createElement("option");
        option.value = monthName;
        option.textContent = monthName;
        brokerageElements.month.appendChild(option);
    });

    brokerageElements.month.value = BROKERAGE_MONTHS[today.getMonth()];
    brokerageElements.year.value = today.getFullYear();
    brokerageElements.reconciliationDate.value = getTodayDate();
}

// This loads enabled Insurer master records through the protected server endpoint.
async function loadEnabledInsurers() {
    try {
        const insurers = await callBrokeragePortal("get_enabled_insurers");

        brokerageElements.insurer.innerHTML = "";
        brokerageElements.insurer.appendChild(new Option("Select an insurer", ""));

        (insurers || []).forEach((insurer) => {
            const label = insurer.insurer_name || insurer.short_name || insurer.name;
            brokerageElements.insurer.appendChild(new Option(label, insurer.name));
        });

        brokerageElements.insurer.disabled = false;

        if (!insurers?.length) {
            showFrappeMessage(
                "No enabled Insurer records were found.",
                "No enabled insurers",
                "orange"
            );
        }
    } catch (error) {
        brokerageElements.insurer.innerHTML = "";
        brokerageElements.insurer.appendChild(
            new Option("Unable to load insurers", "")
        );

        showFrappeMessage(getErrorMessage(error), "Unable to load insurers");
    }
}

// This validates browser inputs before sending a reconciliation request to Frappe.
function getFormValues() {
    const values = {
        insurer_name: brokerageElements.insurer.value,
        statement_month_select: brokerageElements.month.value,
        statement_year: Number(brokerageElements.year.value),
        reconciliation_date: brokerageElements.reconciliationDate.value,
        include_earlier_business: brokerageElements.includeEarlierBusiness.checked ? 1 : 0,
        amount_tolerance: Number(brokerageElements.tolerance.value || 0),
    };

    if (!values.insurer_name) {
        showFrappeMessage("Please select an insurer.", "Required input");
        return null;
    }

    if (!values.statement_month_select) {
        showFrappeMessage("Please select a statement month.", "Required input");
        return null;
    }

    if (!Number.isInteger(values.statement_year) || values.statement_year < 2000) {
        showFrappeMessage("Please enter a valid statement year.", "Required input");
        return null;
    }

    if (!values.reconciliation_date) {
        showFrappeMessage("Please select a reconciliation date.", "Required input");
        return null;
    }

    if (values.amount_tolerance < 0) {
        showFrappeMessage("Write-off Limit cannot be negative.", "Invalid write-off limit");
        return null;
    }

    return values;
}

// This returns the reconciliation name saved in the route before the browser-local fallback.
function getSavedReconciliationName() {
    const routeName = new URLSearchParams(window.location.search).get("reconciliation");

    if (routeName) {
        return routeName;
    }

    try {
        return window.localStorage.getItem("slc_brokerage_reconciliation_name");
    } catch (storageError) {
        return null;
    }
}

// This persists the current reconciliation so browser refresh and a copied URL keep its status.
function saveCurrentReconciliation(reconciliationName) {
    if (!reconciliationName) {
        return;
    }

    brokeragePortalState.currentReconciliation = reconciliationName;

    const routeUrl = new URL(window.location.href);
    routeUrl.searchParams.set("reconciliation", reconciliationName);
    window.history.replaceState({}, "", routeUrl);

    try {
        window.localStorage.setItem("slc_brokerage_reconciliation_name", reconciliationName);
    } catch (storageError) {
        // The URL remains the refresh-safe fallback when local storage is unavailable.
    }
}

// This removes an unavailable saved run so the page can safely fall back to the user's latest run.
function clearSavedReconciliation() {
    brokeragePortalState.currentReconciliation = null;

    const routeUrl = new URL(window.location.href);
    routeUrl.searchParams.delete("reconciliation");
    window.history.replaceState({}, "", routeUrl);

    try {
        window.localStorage.removeItem("slc_brokerage_reconciliation_name");
    } catch (storageError) {
        // No action is needed when local storage is unavailable.
    }
}

// This fills the Desk audit links after a reconciliation record has been created.
function setDeskLinks(reconciliationName) {
    if (!reconciliationName) {
        brokerageElements.reconciliationLink.href = "#";
        brokerageElements.settlementsLink.href = "#";
        return;
    }

    const encodedName = encodeURIComponent(reconciliationName);

    brokerageElements.reconciliationLink.href =
        `/app/brokerage-reconciliation/${encodedName}`;

    brokerageElements.settlementsLink.href =
        `/app/brokerage-settlement?brokerage_reconciliation=${encodedName}`;
}

// This stops server-status polling once the job has finished or the page is unloading.
function stopStatusPolling() {
    if (!brokeragePortalState.pollTimer) {
        return;
    }

    window.clearInterval(brokeragePortalState.pollTimer);
    brokeragePortalState.pollTimer = null;
}

// This starts one polling timer only while a reconciliation is actively Matching.
function startStatusPolling() {
    if (brokeragePortalState.pollTimer) {
        return;
    }

    brokeragePortalState.pollTimer = window.setInterval(() => {
        loadReconciliationStatus({ showError: false });
    }, RECONCILIATION_STATUS_POLL_INTERVAL_MS);
}

// This formats a saved Frappe datetime only for a concise user-facing status message.
function formatStatusDate(value) {
    if (!value) {
        return "";
    }

    const date = new Date(String(value).replace(" ", "T"));

    if (Number.isNaN(date.getTime())) {
        return String(value);
    }

    return date.toLocaleString("en-IN", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

// This shows a moving loader while the worker is queued or the first progress event has not arrived.
function showWaitingProgress(message = "Waiting for the background job to start…") {
    brokeragePortalState.hasLiveProgress = false;
    brokerageElements.progressCard.classList.remove("hidden");
    brokerageElements.progressCard.classList.add("is-indeterminate");
    brokerageElements.progressPhase.textContent = "Preparing reconciliation";
    brokerageElements.progressPercentage.textContent = "…";
    brokerageElements.progressTrack.setAttribute("aria-valuenow", "0");
    brokerageElements.progressBar.style.width = "0%";
    brokerageElements.progressCount.textContent = message;
}

// This renders the counts sent directly from the running server job without waiting for final commit.
function showLiveProgress(data) {
    const total = Number(data.total || 0);
    const processed = Number(data.processed || 0);
    const percentage = Math.max(0, Math.min(Number(data.progress_percent || 0), 100));
    const isWriteOff = data.action === "write_off";

    brokeragePortalState.hasLiveProgress = true;
    brokerageElements.emptyState.classList.add("hidden");
    brokerageElements.result.classList.remove("hidden");
    brokerageElements.progressCard.classList.remove("hidden", "is-indeterminate");
    brokerageElements.progressPhase.textContent = data.phase || "Processing reconciliation";
    brokerageElements.progressPercentage.textContent = `${percentage}%`;
    brokerageElements.progressTrack.setAttribute("aria-valuenow", String(percentage));
    brokerageElements.progressBar.style.width = `${percentage}%`;

    brokerageElements.checkedLabel.textContent = isWriteOff
        ? "Policies Checked"
        : "Statements Checked";
    brokerageElements.createdLabel.textContent = isWriteOff
        ? "Write-off Settlements"
        : "Settlements Submitted";
    brokerageElements.unmatchedLabel.textContent = isWriteOff
        ? "Skipped Policies"
        : "Unmatched Statements";

    brokerageElements.recordsChecked.textContent = processed;
    brokerageElements.recordsCreated.textContent = data.created || 0;
    brokerageElements.recordsUnmatched.textContent = data.unmatched || 0;
    brokerageElements.recordsFailed.textContent = data.failed || 0;
    brokerageElements.progressCount.textContent = total
        ? `${processed} of ${total} records processed.`
        : "Preparing eligible records for reconciliation.";

    brokerageElements.resultTitle.textContent = isWriteOff
        ? "Write-off processing is running"
        : "Reconciliation matching is running";
    brokerageElements.resultMessage.textContent = "Live progress is being received from the background worker.";
    setRunStatus("Processing", "processing");
}

// This removes the loader only after a completed, failed, or idle reconciliation result is displayed.
function hideProgress() {
    brokeragePortalState.hasLiveProgress = false;
    brokerageElements.progressCard.classList.add("hidden");
    brokerageElements.progressCard.classList.remove("is-indeterminate");
}

// This renders the saved server status, which works even when Socket.IO was disconnected.
function showSavedStatus(statusResult) {
    const reconciliation = statusResult?.reconciliation;

    if (!reconciliation) {
        return;
    }

    saveCurrentReconciliation(reconciliation.name);
    brokerageElements.emptyState.classList.add("hidden");
    brokerageElements.result.classList.remove("hidden");

    brokerageElements.checkedLabel.textContent = "Records Checked";
    brokerageElements.createdLabel.textContent = "Settlements Submitted";
    brokerageElements.unmatchedLabel.textContent = "Not Settled";
    brokerageElements.recordsChecked.textContent = reconciliation.statements_checked || 0;
    brokerageElements.recordsCreated.textContent = reconciliation.settlements_submitted || 0;
    brokerageElements.recordsUnmatched.textContent = reconciliation.unmatched_statements || 0;
    brokerageElements.recordsFailed.textContent = reconciliation.failed_records || 0;
    setDeskLinks(reconciliation.name);

    if (statusResult.is_processing) {
        brokerageElements.resultTitle.textContent = "Reconciliation is processing";
        brokerageElements.resultMessage.textContent = reconciliation.last_matching_started_on
            ? `Started ${formatStatusDate(reconciliation.last_matching_started_on)}. This page checks the saved status automatically every 5 seconds.`
            : "The background job is queued or starting. This page checks the saved status automatically every 5 seconds.";
        setRunStatus("Processing", "processing");
        setActionButtonsProcessing(true);

        if (!brokeragePortalState.hasLiveProgress) {
            showWaitingProgress("The saved job status is Processing. Waiting for live worker updates…");
        }

        startStatusPolling();
        return;
    }

    stopStatusPolling();
    setActionButtonsProcessing(false);
    hideProgress();

    if (reconciliation.failed_records) {
        brokerageElements.resultTitle.textContent = "Reconciliation needs review";
        brokerageElements.resultMessage.textContent = "The last run recorded a failure. Open the audit record before starting another run.";
        setRunStatus("Review required", "warning");
        return;
    }

    if (statusResult.is_finished) {
        brokerageElements.resultTitle.textContent = "Reconciliation completed";
        brokerageElements.resultMessage.textContent = reconciliation.settlements_submitted
            ? "The saved reconciliation results are shown below."
            : "The run completed, but no eligible settlements were created.";
        setRunStatus("Completed", "complete");
        return;
    }

    brokerageElements.resultTitle.textContent = "Reconciliation is ready";
    brokerageElements.resultMessage.textContent = "This saved reconciliation has not started processing yet.";
    setRunStatus("Ready", "idle");
}

// This loads either the URL-selected run or the current user's latest reconciliation from Frappe.
async function loadReconciliationStatus({ showError = false } = {}) {
    const savedName = brokeragePortalState.currentReconciliation || getSavedReconciliationName();

    try {
        const statusResult = await callBrokeragePortal("get_reconciliation_status", {
            reconciliation_name: savedName || undefined,
        });

        if (statusResult?.reconciliation) {
            showSavedStatus(statusResult);
            return;
        }

        if (savedName) {
            clearSavedReconciliation();
        }

        stopStatusPolling();
        setActionButtonsProcessing(false);
        setRunStatus("Ready", "idle");
    } catch (error) {
        if (showError) {
            showFrappeMessage(getErrorMessage(error), "Unable to load reconciliation status");
        }
    }
}

// This prepares the right-side status card immediately after a job is queued.
function showQueuedResult(result, action) {
    saveCurrentReconciliation(result.reconciliation_name);
    brokeragePortalState.hasLiveProgress = false;
    brokerageElements.emptyState.classList.add("hidden");
    brokerageElements.result.classList.remove("hidden");

    const isWriteOff = action === "write_off";

    brokerageElements.resultTitle.textContent = isWriteOff
        ? "Write-off processing started"
        : "Reconciliation matching started";

    brokerageElements.resultMessage.textContent =
        result.message || "The background job has been queued.";

    brokerageElements.checkedLabel.textContent = isWriteOff
        ? "Policies Checked"
        : "Statements Checked";

    brokerageElements.createdLabel.textContent = isWriteOff
        ? "Write-off Settlements"
        : "Settlements Submitted";

    brokerageElements.unmatchedLabel.textContent = isWriteOff
        ? "Skipped Policies"
        : "Unmatched Statements";

    brokerageElements.recordsChecked.textContent = "—";
    brokerageElements.recordsCreated.textContent = "—";
    brokerageElements.recordsUnmatched.textContent = "—";
    brokerageElements.recordsFailed.textContent = "—";

    setRunStatus("Processing", "processing");
    setDeskLinks(result.reconciliation_name);
    showWaitingProgress("The job has been queued. Waiting for the worker to start…");
    startStatusPolling();
}

// This renders the final summary published by the existing background job.
function showCompletedResult(data) {
    const isWriteOff = data.action === "write_off";
    const checkedCount = data.total_records || data.total_statements || 0;

    saveCurrentReconciliation(data.reconciliation_name);
    brokerageElements.emptyState.classList.add("hidden");
    brokerageElements.result.classList.remove("hidden");

    brokerageElements.resultTitle.textContent = isWriteOff
        ? "Write-off processing completed"
        : "Reconciliation matching completed";

    brokerageElements.resultMessage.textContent = data.failed
        ? "The run completed with failures. Review the audit record before taking another action."
        : "The reconciliation run completed successfully.";

    brokerageElements.checkedLabel.textContent = isWriteOff
        ? "Policies Checked"
        : "Statements Checked";

    brokerageElements.createdLabel.textContent = isWriteOff
        ? "Write-off Settlements"
        : "Settlements Submitted";

    brokerageElements.unmatchedLabel.textContent = isWriteOff
        ? "Skipped Policies"
        : "Unmatched Statements";

    brokerageElements.recordsChecked.textContent = checkedCount;
    brokerageElements.recordsCreated.textContent = data.created || 0;
    brokerageElements.recordsUnmatched.textContent = data.unmatched || 0;
    brokerageElements.recordsFailed.textContent = data.failed || 0;

    setDeskLinks(data.reconciliation_name);
    stopStatusPolling();
    hideProgress();
    setRunStatus(data.failed ? "Review required" : "Completed", data.failed ? "warning" : "complete");
    setActionButtonsProcessing(false);
}

// This confirms the action, validates fields, and starts the existing backend workflow.
async function startReconciliation(action) {
    try {
        const values = getFormValues();

        if (!values) {
            return;
        }

        if (action === "write_off" && values.amount_tolerance <= 0) {
            showFrappeMessage(
                "Write-off Limit must be greater than zero for Generate Write-offs.",
                "Invalid write-off limit"
            );
            return;
        }

        const confirmationMessage = action === "write_off"
            ? "This will create eligible write-off settlements. Do you want to continue?"
            : "This will create regular settlements for matched statement rows. Do you want to continue?";

        if (!window.confirm(confirmationMessage)) {
            return;
        }

        setActionButtonsProcessing(true);
        setRunStatus("Starting", "processing");

        const result = await callBrokeragePortal("start_reconciliation", {
            action,
            ...values,
        });

        showQueuedResult(result || {}, action);
    } catch (error) {
        setActionButtonsProcessing(false);
        setRunStatus("Ready", "idle");
        showFrappeMessage(getErrorMessage(error), "Unable to start reconciliation");
    }
}

// This binds the two financial action buttons to their matching backend actions.
function bindPageEvents() {
    brokerageElements.actionButtons.forEach((button) => {
        button.addEventListener("click", () => {
            startReconciliation(button.dataset.action);
        });
    });
}

// This subscribes only after Frappe's website bundle has initialized its standard Socket.IO client.
function registerRealtimeListener() {
    frappe.ready(() => {
        frappe.realtime.on("brokerage_reconciliation_job_progress", (data) => {
            if (!data?.reconciliation_name) {
                return;
            }

            if (
                brokeragePortalState.currentReconciliation &&
                data.reconciliation_name !== brokeragePortalState.currentReconciliation
            ) {
                return;
            }

            saveCurrentReconciliation(data.reconciliation_name);
            showLiveProgress(data);
        });

        frappe.realtime.on("brokerage_reconciliation_job_complete", (data) => {
            if (!data?.reconciliation_name) {
                return;
            }

            if (
                brokeragePortalState.currentReconciliation &&
                data.reconciliation_name !== brokeragePortalState.currentReconciliation
            ) {
                return;
            }

            showCompletedResult(data);
        });
    });
}

// This prevents a background interval from continuing after the user leaves the page.
function registerPageCleanup() {
    window.addEventListener("beforeunload", stopStatusPolling);
}

// This initializes the form, protected insurer list, realtime listener, and saved-status fallback.
document.addEventListener("DOMContentLoaded", async () => {
    setDefaultFormValues();
    bindPageEvents();
    registerRealtimeListener();
    registerPageCleanup();

    await Promise.all([
        loadEnabledInsurers(),
        loadReconciliationStatus({ showError: true }),
    ]);
});
