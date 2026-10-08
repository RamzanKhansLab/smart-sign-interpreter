let runs = [];
let activeRunId = null;
let refreshing = false;

const element = (id) => document.getElementById(id);
const percent = (value) => Number.isFinite(value) ? `${(value * 100).toFixed(2)}%` : "Unknown";
const date = (value) => value ? new Date(value).toLocaleString() : "Unknown";

function cell(tag, value) {
  const node = document.createElement(tag);
  node.textContent = value;
  if (tag === "th") node.scope = "col";
  return node;
}

function renderRun() {
  const run = runs.find((item) => item.run_id === element("training-run").value);
  element("evaluation").hidden = !run;
  if (!run) return;
  for (const key of ["accuracy", "precision", "recall", "f1"]) {
    element(`metric-${key}`).textContent = percent(run[key]);
  }
  element("metric-weighted-f1").textContent = percent(run.weighted_f1);
  const details = element("evaluation-details");
  details.replaceChildren();
  const entries = [
    ["Model", run.model_type],
    ["In use", run.run_id === activeRunId ? "YES" : "NO (historical result)"],
    [run.evaluation_kind === "current_dataset" ? "Model file modified" : "Trained", date(run.trained_at)],
    ["Evaluation", run.evaluation_label],
    ["Data source", run.dataset_source],
    ["Usable samples", run.samples],
    ["Training samples", run.train_samples ?? "Unknown"],
    ["Held-out test samples", run.test_samples ?? "Unknown"],
    ["Evaluated samples", run.evaluation_samples],
    ["Classes", run.classes.length],
    ["Features", run.feature_count ?? "Unknown"],
  ];
  if (run.random_state !== undefined) entries.push(["Random seed", run.random_state]);
  if (run.training_seconds !== undefined) entries.push(["Training time", `${run.training_seconds.toFixed(3)} s`]);
  if (run.evaluated_at) entries.push(["Evaluated", date(run.evaluated_at)]);
  for (const [label, value] of entries) {
    const item = document.createElement("li");
    item.textContent = `${label}: ${value}`;
    details.appendChild(item);
  }
  element("evaluation-warning").textContent = run.warning || "Evaluation uses a stratified test split excluded from model fitting. Nearby samples from the same recording may be correlated; use separate recording sessions for stronger validation.";
  const body = element("classification-rows");
  body.replaceChildren();
  for (const row of run.per_class) {
    const tr = document.createElement("tr");
    for (const value of [row.label, percent(row.precision), percent(row.recall), percent(row["f1-score"]), row.support]) {
      tr.appendChild(cell("td", value));
    }
    body.appendChild(tr);
  }
  const matrixTable = element("matrix-table");
  const header = document.createElement("tr");
  header.appendChild(cell("th", "True / Predicted"));
  for (const label of run.classes) header.appendChild(cell("th", label));
  matrixTable.tHead.replaceChildren(header);
  matrixTable.tBodies[0].replaceChildren();
  run.confusion_matrix.forEach((counts, index) => {
    const row = document.createElement("tr");
    const label = cell("th", run.classes[index]);
    label.scope = "row";
    row.appendChild(label);
    for (const count of counts) row.appendChild(cell("td", count));
    matrixTable.tBodies[0].appendChild(row);
  });
  const url = `/api/model/confusion-matrix/${encodeURIComponent(run.run_id)}.png?v=${Date.now()}`;
  const img = element("confusion-matrix");
  img.hidden = true;
  element("matrix-status").textContent = "Loading Matplotlib plot...";
  img.onload = () => { img.hidden = false; element("matrix-status").textContent = ""; };
  img.onerror = () => { img.hidden = true; element("matrix-status").textContent = "Could not load the plot. Refresh to retry; matrix counts are shown below."; };
  img.src = url;
  element("download-matrix").href = url;
}

async function refreshMetrics() {
  if (refreshing) return;
  refreshing = true;
  const button = element("refresh-metrics");
  button.disabled = true;
  button.textContent = "REFRESHING...";
  try {
    const response = await fetch("/api/model/metrics", { cache: "no-store" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Could not load model performance.");
    const select = element("training-run");
    const previous = select.value;
    const followedActive = !previous || previous === activeRunId;
    runs = data.runs;
    activeRunId = data.active_run_id;
    select.replaceChildren();
    for (const run of runs) {
      const option = document.createElement("option");
      option.value = run.run_id;
      option.textContent = `${run.model_type} — ${date(run.trained_at)} — ${run.evaluation_label}${run.run_id === activeRunId ? " (active)" : ""}`;
      select.appendChild(option);
    }
    select.disabled = runs.length === 0;
    select.value = followedActive && activeRunId ? activeRunId :
      runs.some((run) => run.run_id === previous) ? previous : activeRunId || runs[0]?.run_id || "";
    element("metrics-status").textContent = [
      data.model_loaded ? "Model loaded." : "No active model. Retrain from Data Collection to enable predictions.",
      data.message || "",
      runs.length ? `${runs.length} saved/evaluated run(s). Updated ${date(data.refreshed_at)}.` : "No evaluation results yet.",
    ].filter(Boolean).join(" ");
    renderRun();
  } catch (error) {
    element("metrics-status").textContent = `Refresh failed: ${error.message}. Any displayed results are from the previous refresh.`;
  } finally {
    refreshing = false;
    button.disabled = false;
    button.textContent = "REFRESH";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  element("refresh-metrics").addEventListener("click", refreshMetrics);
  element("training-run").addEventListener("change", renderRun);
  window.addEventListener("focus", refreshMetrics);
  refreshMetrics();
});
