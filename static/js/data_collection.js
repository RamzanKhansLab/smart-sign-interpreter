const CAPTURE_INTERVAL_MS = 2000;
const FALLBACK_POLL_INTERVAL_MS = 1000;
const WS_RECONNECT_DELAY_MS = 1000;

const state = {
  capturing: false,
  captureTimer: null,
  pollTimer: null,
  ws: null,
  connected: false,
  buffer: [],
  lastMessage: null,
  latestData: null,
  latestFingerprint: null,
  lastBufferedFingerprint: null,
  labels: [],
  savePending: false,
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

function cloneJson(value) {
  return JSON.parse(JSON.stringify(value));
}

function buildSampleFingerprint(data) {
  if (!data) return null;
  return JSON.stringify({
    timestamp: data.timestamp ?? null,
    channels: data.channels || {},
    imu: data.imu || {},
  });
}

function renderStats(data) {
  if (!data) return;
  setText("dataset-stats", JSON.stringify(data, null, 2));
  updateLabelSelect(data.by_label || {});
}

function updatePreview(message) {
  if (!message || !message.data) return;
  state.lastMessage = message;
  state.latestData = cloneJson(message.data);
  state.latestFingerprint = buildSampleFingerprint(message.data);

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
  state.lastMessage = null;
  state.latestData = null;
  state.latestFingerprint = null;
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

function setSavePending(isPending) {
  state.savePending = isPending;
  const button = document.getElementById("save");
  if (!button) return;
  button.disabled = isPending;
  button.textContent = isPending ? "SAVING..." : "SAVE";
}

async function fetchLatest() {
  const res = await fetch("/api/latest");
  if (res.status === 404) return { __no_data: true };
  if (!res.ok) return null;
  return await res.json();
}

async function pollLatestOnce() {
  try {
    const message = await fetchLatest();
    if (!message) return;
    if (message.__no_data) {
      showNoData();
      return;
    }
    updatePreview(message);
  } catch (e) {
    // ignore
  }
}

function startPolling() {
  if (state.pollTimer) return;
  state.pollTimer = setInterval(() => {
    if (!state.connected) {
      pollLatestOnce();
    }
  }, FALLBACK_POLL_INTERVAL_MS);
}

function scheduleReconnect(previousSocket) {
  window.setTimeout(() => {
    if (state.ws === previousSocket && !state.connected) {
      setupWebSocket();
    }
  }, WS_RECONNECT_DELAY_MS);
}

function setupWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${protocol}://${window.location.host}/ws/sensor-stream`);
  state.ws = ws;

  ws.onopen = () => {
    state.connected = true;
  };

  ws.onclose = () => {
    state.connected = false;
    scheduleReconnect(ws);
  };

  ws.onerror = () => {
    state.connected = false;
  };

  ws.onmessage = (event) => {
    try {
      const message = JSON.parse(event.data);
      updatePreview(message);
    } catch (e) {
      // ignore malformed websocket messages
    }
  };
}

function bufferLatestSample() {
  if (!state.latestData || !state.latestFingerprint) return;
  if (state.latestFingerprint === state.lastBufferedFingerprint) return;

  state.buffer.push(cloneJson(state.latestData));
  state.lastBufferedFingerprint = state.latestFingerprint;
  setBufferCount();
}

function startCapture() {
  if (state.captureTimer) return;
  setCapturing(true);
  bufferLatestSample();
  state.captureTimer = setInterval(bufferLatestSample, CAPTURE_INTERVAL_MS);
}

function stopCapture() {
  setCapturing(false);
  if (state.captureTimer) {
    clearInterval(state.captureTimer);
    state.captureTimer = null;
  }
}

function clearBuffer() {
  state.buffer = [];
  state.lastBufferedFingerprint = null;
  setBufferCount();
}

function getLabel() {
  return document.getElementById("gesture-label").value.trim();
}

async function refreshStats() {
  const res = await fetch("/api/dataset/stats");
  if (!res.ok) {
    setText("dataset-stats", "Failed to load dataset statistics.");
    return null;
  }

  const data = await res.json();
  renderStats(data);
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
  if (state.savePending) return;

  const label = getLabel();
  if (!label) {
    alert("Enter a gesture label (placeholder does not count)");
    return;
  }
  if (state.buffer.length === 0) {
    alert("Buffer is empty. Click START and wait for fresh samples.");
    return;
  }

  if (state.capturing) {
    stopCapture();
  }

  const samplesToSave = state.buffer.map(cloneJson);
  setSavePending(true);
  try {
    const res = await fetch("/api/dataset/save-batch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ label, samples: samplesToSave }),
    });

    if (!res.ok) {
      const msg = await readErrorMessage(res);
      alert(msg || "Save failed");
      return;
    }

    const out = await res.json();
    alert(`Saved ${out.saved} samples for label '${label}'`);
    state.buffer = state.buffer.slice(samplesToSave.length);
    if (state.buffer.length === 0) {
      state.lastBufferedFingerprint = null;
    }
    setBufferCount();

    if (out.stats) {
      renderStats(out.stats);
    } else {
      await refreshStats();
    }
  } finally {
    setSavePending(false);
  }
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
  clearBuffer();
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
  setSavePending(false);
  setupWebSocket();
  startPolling();
  await refreshStats();
  await refreshModelStatus();
  await pollLatestOnce();
});
