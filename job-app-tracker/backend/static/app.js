const form = document.querySelector("#analysis-form");
const analyzeButton = document.querySelector("#analyze-button");
const saveButton = document.querySelector("#save-button");
const refreshButton = document.querySelector("#refresh-button");
const statusMessage = document.querySelector("#status-message");
const analysisOutput = document.querySelector("#analysis-output");
const resultTitle = document.querySelector("#result-title");
const scoreBadge = document.querySelector("#score-badge");
const savedList = document.querySelector("#saved-list");
const weightsTotal = document.querySelector("#weights-total");
const analysisLoader = document.querySelector("#analysis-loader");
const tabButtons = document.querySelectorAll("[data-tab]");
const tabPanels = document.querySelectorAll(".tab-panel");
const tabTargetButtons = document.querySelectorAll("[data-tab-target]");

const scoreLabels = {
  required_skills: "Required skills",
  experience_relevance: "Experience",
  responsibilities_match: "Responsibilities",
  tools_match: "Tools",
  seniority_match: "Seniority",
  education_domain_match: "Education/domain",
};

const weightKeys = Object.keys(scoreLabels);

let currentResult = null;
let isAnalyzing = false;

function setStatus(message, type = "") {
  statusMessage.textContent = message;
  statusMessage.className = `status-message${type ? ` is-${type}` : ""}`;
}

function switchTab(tabName) {
  tabButtons.forEach((button) => {
    const isActive = button.dataset.tab === tabName;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-selected", String(isActive));
  });

  tabPanels.forEach((panel) => {
    panel.classList.toggle("is-active", panel.id === `${tabName}-tab`);
  });
}

function setLoading(active) {
  isAnalyzing = active;
  analysisLoader.classList.toggle("is-hidden", !active);
  analyzeButton.textContent = active ? "Analyzing..." : "Analyze resume";
  updateWeightTotal();
}

function renderList(elementId, items) {
  const element = document.querySelector(elementId);
  element.innerHTML = "";

  if (!items || items.length === 0) {
    const empty = document.createElement("li");
    empty.textContent = "None found.";
    element.appendChild(empty);
    return;
  }

  items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    element.appendChild(li);
  });
}

function renderChips(elementId, items) {
  const element = document.querySelector(elementId);
  element.innerHTML = "";

  if (!items || items.length === 0) {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = "None";
    element.appendChild(chip);
    return;
  }

  items.forEach((item) => {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = item;
    element.appendChild(chip);
  });
}

function getScoringWeights() {
  return Object.fromEntries(
    weightKeys.map((key) => {
      const input = form.elements[key];
      return [key, Number.parseInt(input.value || "0", 10)];
    }),
  );
}

function scoringWeightTotal() {
  return Object.values(getScoringWeights()).reduce((total, value) => total + value, 0);
}

function updateWeightTotal() {
  const total = scoringWeightTotal();
  weightsTotal.textContent = total;
  weightsTotal.classList.toggle("is-invalid", total !== 100);
  analyzeButton.disabled = total !== 100 || isAnalyzing;
}

function renderScoreBreakdown(result) {
  const element = document.querySelector("#score-breakdown");
  element.innerHTML = "";

  weightKeys.forEach((key) => {
    const row = document.createElement("div");
    row.className = "breakdown-row";

    const label = document.createElement("span");
    label.textContent = scoreLabels[key];

    const value = document.createElement("strong");
    value.textContent = `${result.score_breakdown[key]} / ${result.scoring_weights[key]}`;

    const meter = document.createElement("div");
    meter.className = "breakdown-meter";

    const fill = document.createElement("span");
    const weight = result.scoring_weights[key] || 1;
    fill.style.width = `${Math.min((result.score_breakdown[key] / weight) * 100, 100)}%`;
    meter.appendChild(fill);

    row.append(label, value, meter);
    element.appendChild(row);
  });
}

function renderAnalysis(result) {
  const candidateName = result.candidate_name || "Candidate";
  resultTitle.textContent = candidateName;
  scoreBadge.textContent = `${result.fit_score}%`;
  scoreBadge.classList.remove("is-empty");
  document.querySelector("#fit-score").textContent = `${result.fit_score}/100 · ${result.fit_level}`;
  document.querySelector("#recommendation").textContent = result.recommendation;

  renderScoreBreakdown(result);
  renderChips("#matched-keywords", result.matched_keywords);
  renderChips("#missing-keywords", result.missing_keywords);
  renderList("#strengths", result.strengths);
  renderList("#concerns", result.concerns);
  renderList("#summary-bullets", result.summary_bullets);

  analysisOutput.classList.remove("is-hidden");
}

function savedCard(record) {
  const card = document.createElement("article");
  card.className = "saved-card";

  const header = document.createElement("div");
  header.className = "saved-card-header";

  const titleGroup = document.createElement("div");
  const title = document.createElement("h3");
  title.textContent = record.candidate_name || record.resume_filename || "Candidate";
  const meta = document.createElement("p");
  const created = new Date(record.created_at).toLocaleString();
  meta.textContent = `${record.fit_level} · ${record.recommendation} · ${created}`;
  titleGroup.append(title, meta);

  const score = document.createElement("div");
  score.className = "saved-score";
  score.textContent = `${record.fit_score}%`;

  header.append(titleGroup, score);

  const missing = document.createElement("p");
  const missingText = record.missing_keywords?.slice(0, 5).join(", ") || "None";
  missing.textContent = `Missing: ${missingText}`;

  card.append(header, missing);
  return card;
}

async function loadSavedAnalyses() {
  savedList.textContent = "Loading saved analyses...";
  try {
    const response = await fetch("/resume/analyses");
    if (!response.ok) {
      throw new Error(await response.text());
    }

    const records = await response.json();
    savedList.innerHTML = "";

    if (records.length === 0) {
      savedList.textContent = "No saved resume analyses yet.";
      return;
    }

    records.forEach((record) => savedList.appendChild(savedCard(record)));
  } catch (error) {
    savedList.textContent = `Could not load saved analyses: ${error.message}`;
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  switchTab("analyzer");

  const scoringWeights = getScoringWeights();
  if (scoringWeightTotal() !== 100) {
    setStatus("Score weights must total 100 before analysis.", "error");
    return;
  }

  currentResult = null;
  saveButton.disabled = true;
  setLoading(true);
  setStatus("Analyzing resume...");

  const data = new FormData(form);
  data.append("scoring_weights", JSON.stringify(scoringWeights));

  try {
    const response = await fetch("/resume/analyze-upload", {
      method: "POST",
      body: data,
    });

    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.detail || "Analysis failed");
    }

    currentResult = {
      candidate_name: data.get("candidate_name") || result.candidate_name,
      job_description: data.get("job_description"),
      resume_filename: data.get("resume_file")?.name,
      resume_text: result.resume_text,
      analysis: {
        candidate_name: result.candidate_name,
        fit_score: result.fit_score,
        fit_level: result.fit_level,
        scoring_weights: result.scoring_weights,
        score_breakdown: result.score_breakdown,
        recommendation: result.recommendation,
        matched_keywords: result.matched_keywords,
        missing_keywords: result.missing_keywords,
        strengths: result.strengths,
        concerns: result.concerns,
        summary_bullets: result.summary_bullets,
      },
    };

    renderAnalysis(result);
    setStatus("Analysis complete.", "success");
    saveButton.disabled = false;
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setLoading(false);
  }
});

saveButton.addEventListener("click", async () => {
  if (!currentResult) return;

  saveButton.disabled = true;
  setStatus("Saving analysis...");

  try {
    const response = await fetch("/resume/analyses", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(currentResult),
    });

    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.detail || "Save failed");
    }

    setStatus("Analysis saved to the database.", "success");
    await loadSavedAnalyses();
    switchTab("analyzer");
    document.querySelector("#analyzer-tab").scrollIntoView({ behavior: "smooth" });
  } catch (error) {
    setStatus(error.message, "error");
    saveButton.disabled = false;
  }
});

tabButtons.forEach((button) => {
  button.addEventListener("click", () => switchTab(button.dataset.tab));
});
tabTargetButtons.forEach((button) => {
  button.addEventListener("click", () => switchTab(button.dataset.tabTarget));
});
refreshButton.addEventListener("click", loadSavedAnalyses);
weightKeys.forEach((key) => form.elements[key].addEventListener("input", updateWeightTotal));

updateWeightTotal();
loadSavedAnalyses();
