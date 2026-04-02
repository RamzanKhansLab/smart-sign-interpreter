const state = {
  capturing: false,
  timer: null,
  buffer: [],
  lastMessage: null,
  labels: [],
};

function setText(id, value) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = value;
}

function getChannel(channels, key) {
  if (!channels) return null;
  return channels[key] ?? null;
}

function updatePreview(message) {
  if (!message || !message.data) return;
  state.lastMessage = message;

  const data = message.data;
  const channels = data.channels || {};

  setText("s1", getChannel(channels, "s1") ?? "-");
  setText("s2", getChannel(channels, "s2") ?? "-");
  setText("s3", getChannel(channels, "s3") ?? "-");
  setText("s4", getChannel(channels, "s4") ?? "-");
  setText("s5", getChannel(channels, "s5") ?? "-");
  setText("timestamp", data.timestamp ?? "-");

  setText("raw", JSON.stringify(message, null, 2));
}

function showNoData() {
  setText(
    "raw",
    "No sensor data yet. POST to /api/sensor-data or use the demo button on Home."
  );
}

function setCapturing(isCapturing) {
  state.capturing = isCapturing;
  setText("capture-status", isCapturing ? "RUNNING" : "STOPPED");
}

function setBufferCount() {
  setText("buffer-count", String(state.buffer.length));
}

async function fetchLatest() {
  const res = await fetch("/api/latest");
  if (res.status === 404) return { __no_data: true };
  if (!res.ok) return null;
  return await res.json();
}

async function tick() {
  try {
    const message = await fetchLatest();
    if (!message) return;
    if (message.__no_data) {
      showNoData();
      return;
    }
    updatePreview(message);
    if (state.capturing && message.data) {
      state.buffer.push(message.data);
      setBufferCount();
    }
  } catch (e) {
    // ignore
  }
}

function startCapture() {
  if (state.timer) return;
  setCapturing(true);
  state.timer = setInterval(tick, 2000);
  tick();
}

function stopCapture() {
  setCapturing(false);
  if (state.timer) {
    clearInterval(state.timer);
    state.timer = null;
  }
}

function clearBuffer() {
  state.buffer = [];
  setBufferCount();
}

function getLabel() {
  const label = document.getElementById("gesture-label").value.trim();
  return label;
}

async function refreshStats() {
  const res = await fetch("/api/dataset/stats");
  const data = await res.json();
  setText("dataset-stats", JSON.stringify(data, null, 2));
  updateLabelSelect(data.by_label || {});
  return data;
}

function updateLabelSelect(byLabel) {
  const select = document.getElementById("edit-label");
  if (!select) return;

  const labels = Object.keys(byLabel);
  labels.sort((a, b) => a.localeCompare(b));
  state.labels = labels;

  const previous = select.value;
  select.innerHTML = "";

  const allOpt = document.createElement("option");
  allOpt.value = "__all__";
  allOpt.textContent = "(all labels)";
  select.appendChild(allOpt);

  for (const label of labels) {
    const opt = document.createElement("option");
    opt.value = label;
    const count = byLabel[label];
    const display = label === "" ? "(empty label)" : label;
    opt.textContent = `${display} (${count})`;
    select.appendChild(opt);
  }

  if (previous && [...select.options].some((o) => o.value === previous)) {
    select.value = previous;
  } else {
    select.value = "__all__";
  }
}

async function refreshModelStatus() {
  const res = await fetch("/api/model/status");
  const data = await res.json();
  setText("model-loaded", data.model_loaded ? "YES" : "NO");
}

async function readErrorMessage(res) {
  try {
    const data = await res.json();
    if (data && data.detail) return data.detail;
    return JSON.stringify(data);
  } catch (e) {
    try {
      return await res.text();
    } catch (e2) {
      return "Request failed";
    }
  }
}

async function saveBuffer() {
  const label = getLabel();
  if (!label) {
    alert("Enter a gesture label (placeholder does not count)");
    return;
  }
  if (state.buffer.length === 0) {
    alert("Buffer is empty. Click START and wait for samples.");
    return;
  }

  const res = await fetch("/api/dataset/save-batch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ label, samples: state.buffer }),
  });

  if (!res.ok) {
    const msg = await readErrorMessage(res);
    alert(msg || "Save failed");
    return;
  }

  const out = await res.json();
  alert(`Saved ${out.saved} samples for label '${label}'`);
  clearBuffer();
  await refreshStats();
}

async function resetModel() {
  const res = await fetch("/api/model/reset", { method: "POST" });
  if (!res.ok) {
    alert("Model reset failed");
    return;
  }
  await refreshModelStatus();
  alert("Model reset (deleted). Retrain to enable predictions.");
}

async function retrainModel() {
  const modelType = document.getElementById("model-type").value.trim() || "knn";
  const res = await fetch("/api/model/retrain", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model_type: modelType }),
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    alert(data.detail || "Retrain failed");
    return;
  }

  await refreshModelStatus();
  alert(
    `Retrained (${data.metrics.model_type}). Accuracy=${data.metrics.accuracy.toFixed(3)} Samples=${data.metrics.samples}`
  );
}

function selectedEditLabel() {
  const sel = document.getElementById("edit-label");
  if (!sel) return null;
  const value = sel.value;
  if (value === "__all__") return null;
  return value;
}

async function loadRows() {
  const label = selectedEditLabel();
  const url = new URL("/api/dataset/rows", window.location.origin);
  url.searchParams.set("limit", "50");
  url.searchParams.set("offset", "0");
  if (label !== null) url.searchParams.set("label", label);

  const res = await fetch(url.toString());
  if (!res.ok) {
    const msg = await readErrorMessage(res);
    alert(msg || "Failed to load rows");
    return;
  }
  const data = await res.json();
  setText("dataset-rows", JSON.stringify(data, null, 2));
}

async function renameSelectedLabel() {
  const fromLabel = selectedEditLabel();
  const toLabel = document.getElementById("rename-to").value.trim();

  if (fromLabel === null) {
    alert("Select a specific label to rename");
    return;
  }
  if (!toLabel) {
    alert("Enter the new label name");
    return;
  }

  const res = await fetch("/api/dataset/rename-label", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ from_label: fromLabel, to_label: toLabel }),
  });

  if (!res.ok) {
    const msg = await readErrorMessage(res);
    alert(msg || "Rename failed");
    return;
  }

  const out = await res.json();
  alert(`Renamed: updated ${out.updated} rows`);
  document.getElementById("rename-to").value = "";
  await refreshStats();
}

async function deleteSelectedLabel() {
  const label = selectedEditLabel();
  if (label === null) {
    alert("Select a specific label to delete");
    return;
  }
  if (!confirm(`Delete ALL rows with label '${label}'?`)) return;

  const res = await fetch("/api/dataset/delete-label", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ label }),
  });

  if (!res.ok) {
    const msg = await readErrorMessage(res);
    alert(msg || "Delete failed");
    return;
  }

  const out = await res.json();
  alert(`Deleted ${out.deleted} rows`);
  await refreshStats();
}

async function deleteEmptyLabels() {
  const res = await fetch("/api/dataset/delete-empty-labels", { method: "POST" });
  if (!res.ok) {
    const msg = await readErrorMessage(res);
    alert(msg || "Delete empty labels failed");
    return;
  }
  const out = await res.json();
  alert(`Deleted ${out.deleted} rows with empty label`);
  await refreshStats();
}

async function clearDataset() {
  if (!confirm("Clear the entire dataset CSV?")) return;
  const res = await fetch("/api/dataset/clear", { method: "POST" });
  if (!res.ok) {
    const msg = await readErrorMessage(res);
    alert(msg || "Clear failed");
    return;
  }
  alert("Dataset cleared");
  setText("dataset-rows", "Click LOAD ROWS");
  await refreshStats();
}

function bindUi() {
  document.getElementById("start").addEventListener("click", startCapture);
  document.getElementById("stop").addEventListener("click", stopCapture);
  document.getElementById("save").addEventListener("click", saveBuffer);
  document.getElementById("clear").addEventListener("click", clearBuffer);

  document
    .getElementById("refresh-stats")
    .addEventListener("click", refreshStats);

  document.getElementById("model-reset").addEventListener("click", resetModel);

  document
    .getElementById("model-retrain")
    .addEventListener("click", retrainModel);

  document.getElementById("rows-load").addEventListener("click", loadRows);
  document
    .getElementById("label-rename")
    .addEventListener("click", renameSelectedLabel);
  document
    .getElementById("label-delete")
    .addEventListener("click", deleteSelectedLabel);
  document
    .getElementById("delete-empty")
    .addEventListener("click", deleteEmptyLabels);
  document
    .getElementById("dataset-clear")
    .addEventListener("click", clearDataset);
}

document.addEventListener("DOMContentLoaded", async () => {
  bindUi();
  setCapturing(false);
  setBufferCount();
  await refreshStats();
  await refreshModelStatus();
  tick();
});
