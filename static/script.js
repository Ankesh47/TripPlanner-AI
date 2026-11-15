let currentThreadId = localStorage.getItem("travel_thread_id") || null;
let latestAnswerMarkdown = "";

function setPrompt(text) {
    const input = document.getElementById("userInput");
    input.value = text;
    input.focus();
}

function setLoading(isLoading, message = "Agents collaborating — analyzing flights, hotels, weather & budget…") {
    const sendBtn = document.getElementById("sendBtn");
    const btnText = document.getElementById("btnText");
    const btnLoader = document.getElementById("btnLoader");
    const btnArrow = document.getElementById("btnArrow");
    const progress = document.getElementById("progressBar");
    const progressText = document.getElementById("progressText");

    if (sendBtn) sendBtn.disabled = isLoading;

    if (isLoading) {
        if (btnText) btnText.classList.add("hidden");
        if (btnArrow) btnArrow.classList.add("hidden");
        if (btnLoader) btnLoader.classList.remove("hidden");
        if (progress) progress.classList.remove("hidden");
        if (progressText) progressText.textContent = message;
    } else {
        if (btnText) btnText.classList.remove("hidden");
        if (btnArrow) btnArrow.classList.remove("hidden");
        if (btnLoader) btnLoader.classList.add("hidden");
        if (progress) progress.classList.add("hidden");
    }
}

function showError(message) {
    const errorBox = document.getElementById("errorBox");
    errorBox.textContent = message;
    errorBox.classList.remove("hidden");
}

function hideError() {
    const errorBox = document.getElementById("errorBox");
    errorBox.classList.add("hidden");
    errorBox.textContent = "";

    const guardrailBox = document.getElementById("guardrailBox");
    if (guardrailBox) guardrailBox.classList.add("hidden");
}

function showGuardrailFiltered(reason) {
    const guardrailBox = document.getElementById("guardrailBox");
    const guardrailReason = document.getElementById("guardrailReason");
    if (guardrailBox && guardrailReason) {
        guardrailReason.textContent = reason || "The travel request was filtered by input guardrails.";
        guardrailBox.classList.remove("hidden");
    }
}

function renderFullPlan(data) {
    latestAnswerMarkdown = data.answer || "";

    const resultSection = document.getElementById("resultSection");
    const resultBox = document.getElementById("resultBox");
    const threadInfo = document.getElementById("threadInfo");
    const planStatusBadge = document.getElementById("planStatusBadge");
    const approvalCard = document.getElementById("approvalCard");
    const approvalPrompt = document.getElementById("approvalPrompt");
    const metaBar = document.getElementById("metaBar");
    const agentPills = document.getElementById("agentPills");
    const constraintPills = document.getElementById("constraintPills");

    // Markdown rendering
    if (typeof marked !== "undefined") {
        resultBox.innerHTML = marked.parse(latestAnswerMarkdown);
    } else {
        resultBox.innerText = latestAnswerMarkdown;
    }

    // Thread ID
    threadInfo.textContent = `Thread: ${data.thread_id}`;

    // Status Badge & Title
    const resultTitle = document.getElementById("resultTitle");
    if (data.requires_approval) {
        if (resultTitle) resultTitle.textContent = "Draft Itinerary";
        planStatusBadge.className = "plan-badge badge-draft";
        planStatusBadge.textContent = "Draft — Review & Approve";
        approvalCard.classList.remove("hidden");
        if (approvalPrompt && data.approval_request) {
            approvalPrompt.textContent = data.approval_request;
        }
    } else {
        if (resultTitle) resultTitle.textContent = "Finalized Travel Plan";
        planStatusBadge.className = "plan-badge badge-approved";
        planStatusBadge.textContent = "Plan Approved & Finalized";
        approvalCard.classList.add("hidden");
    }

    // Render Selected Agent Badges
    if (agentPills) {
        agentPills.innerHTML = "";
        const agentMap = {
            "flight_agent": "✈️ Flights Agent",
            "hotel_agent": "🏨 Hotels Agent",
            "weather_agent": "⛅ Weather Agent",
            "budget_agent": "💰 Budget Agent",
            "itinerary_agent": "🗺️ Itinerary Agent",
        };
        const agents = data.selected_agents || [];
        if (agents.length > 0) {
            const label = document.createElement("span");
            label.style.fontWeight = "600";
            label.style.color = "var(--text-tertiary)";
            label.style.marginRight = "4px";
            label.textContent = "Active Agents:";
            agentPills.appendChild(label);

            agents.forEach(agentKey => {
                const pill = document.createElement("span");
                pill.className = "pill pill-agent";
                pill.textContent = agentMap[agentKey] || agentKey;
                agentPills.appendChild(pill);
            });
        }
    }

    // Render Extracted Trip Constraints
    if (constraintPills) {
        constraintPills.innerHTML = "";
        const constraints = data.trip_constraints || {};
        const items = [];
        if (constraints.destination) items.push(`📍 ${constraints.destination}`);
        if (constraints.origin) items.push(`🛫 Departs: ${constraints.origin}`);
        if (constraints.duration) items.push(`⏱️ ${constraints.duration}`);
        if (constraints.budget) items.push(`💵 Budget: ${constraints.budget}`);
        if (constraints.travel_style) items.push(`🎒 ${constraints.travel_style}`);

        if (items.length > 0) {
            items.forEach(text => {
                const pill = document.createElement("span");
                pill.className = "pill pill-constraint";
                pill.textContent = text;
                constraintPills.appendChild(pill);
            });
        }
    }

    // Populate Specialist Drawer data
    const flightsBox = document.getElementById("specialistFlights");
    const hotelsBox = document.getElementById("specialistHotels");
    const weatherBox = document.getElementById("specialistWeather");
    const budgetBox = document.getElementById("specialistBudget");

    if (flightsBox) flightsBox.textContent = data.flight_results || "No flight details recorded.";
    if (hotelsBox) hotelsBox.textContent = data.hotel_results || "No hotel details recorded.";
    if (weatherBox) weatherBox.textContent = data.weather_results || "No weather details recorded.";
    if (budgetBox) budgetBox.textContent = data.budget_results || "No budget analysis recorded.";

    resultSection.classList.remove("hidden");

    resultSection.scrollIntoView({
        behavior: "smooth",
        block: "start",
    });
}

async function sendMessage() {
    hideError();

    const input = document.getElementById("userInput");
    const message = input.value.trim();

    if (!message) {
        showError("Please describe your travel request first.");
        return;
    }

    setLoading(true);

    try {
        const response = await fetch("/api/travel", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message: message,
                thread_id: currentThreadId,
            }),
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(data.error || "The travel planner encountered an error.");
        }

        // Check if input guardrail rejected the message
        if (data.guardrail_allowed === false) {
            showGuardrailFiltered(data.guardrail_reason);
            return;
        }

        currentThreadId = data.thread_id;
        localStorage.setItem("travel_thread_id", currentThreadId);

        renderFullPlan(data);

    } catch (error) {
        showError(error.message);
    } finally {
        setLoading(false);
    }
}

async function submitApproval(approved) {
    hideError();

    const feedbackInput = document.getElementById("revisionInput");
    const feedback = feedbackInput ? feedbackInput.value.trim() : "";

    if (!approved && !feedback) {
        showError("Please specify what changes or revisions you would like in the input box before requesting a revision.");
        if (feedbackInput) feedbackInput.focus();
        return;
    }

    const approveBtn = document.getElementById("approveBtn");
    const reviseBtn = document.getElementById("reviseBtn");

    if (approveBtn) approveBtn.disabled = true;
    if (reviseBtn) reviseBtn.disabled = true;

    const actionMessage = approved
        ? "Finalizing and polishing your travel plan..."
        : "Revising itinerary with your feedback...";

    setLoading(true, actionMessage);

    try {
        const response = await fetch("/api/travel/approve", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                thread_id: currentThreadId,
                approved: approved,
                feedback: feedback,
            }),
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(data.error || "Approval request failed.");
        }

        if (feedbackInput) feedbackInput.value = "";

        renderFullPlan(data);

    } catch (error) {
        showError(error.message);
    } finally {
        setLoading(false);
        if (approveBtn) approveBtn.disabled = false;
        if (reviseBtn) reviseBtn.disabled = false;
    }
}

function toggleSpecialistDrawer() {
    const drawer = document.getElementById("specialistDrawer");
    const toggle = document.querySelector(".drawer-toggle");
    const toggleText = document.getElementById("drawerToggleText");

    if (!drawer) return;

    const isHidden = drawer.classList.contains("hidden");
    if (isHidden) {
        drawer.classList.remove("hidden");
        if (toggle) toggle.classList.add("open");
        if (toggleText) toggleText.textContent = "Hide Specialist Agent Findings";
    } else {
        drawer.classList.add("hidden");
        if (toggle) toggle.classList.remove("open");
        if (toggleText) toggleText.textContent = "Show Specialist Agent Findings (Flights, Hotels, Weather, Budget)";
    }
}

function switchTab(targetTabId) {
    const tabs = ["flightsTab", "hotelsTab", "weatherTab", "budgetTab"];
    tabs.forEach(tabId => {
        const el = document.getElementById(tabId);
        if (el) el.classList.add("hidden");
    });

    const targetEl = document.getElementById(targetTabId);
    if (targetEl) targetEl.classList.remove("hidden");

    // Update active tab buttons
    const buttons = document.querySelectorAll(".tabs-nav .tab-btn");
    buttons.forEach(btn => btn.classList.remove("active"));

    const clickedBtn = Array.from(buttons).find(b =>
        b.getAttribute("onclick") && b.getAttribute("onclick").includes(targetTabId)
    );
    if (clickedBtn) clickedBtn.classList.add("active");
}

function copyResult() {
    const resultBox = document.getElementById("resultBox");
    const text = resultBox ? resultBox.innerText : "";
    if (!text) return;

    navigator.clipboard.writeText(text)
        .then(() => {
            const label = document.querySelector(".copy-label");
            if (label) {
                const prev = label.textContent;
                label.textContent = "Copied!";
                setTimeout(() => { label.textContent = prev; }, 1400);
            }
        })
        .catch(() => showError("Could not copy result."));
}

function downloadPDF() {
    const pdfContent = document.getElementById("pdfContent");

    if (!latestAnswerMarkdown || !pdfContent) {
        showError("No travel plan available to download.");
        return;
    }

    const downloadBtn = document.querySelector(".btn-accent");
    if (downloadBtn) {
        downloadBtn.disabled = true;
        const oldHTML = downloadBtn.innerHTML;
        downloadBtn.textContent = "Preparing…";

        const options = {
            margin: 0.6,
            filename: "ai-travel-plan.pdf",
            image: { type: "jpeg", quality: 0.98 },
            html2canvas: { scale: 2, useCORS: true, backgroundColor: "#ffffff" },
            jsPDF: { unit: "in", format: "a4", orientation: "portrait" },
            pagebreak: { mode: ["avoid-all", "css", "legacy"] },
        };

        html2pdf()
            .set(options)
            .from(pdfContent)
            .save()
            .then(() => {
                downloadBtn.innerHTML = oldHTML;
                downloadBtn.disabled = false;
            })
            .catch(() => {
                downloadBtn.innerHTML = oldHTML;
                downloadBtn.disabled = false;
                showError("Could not download PDF.");
            });
    }
}

document.addEventListener("keydown", function (event) {
    if (event.ctrlKey && event.key === "Enter") {
        sendMessage();
    }
});
