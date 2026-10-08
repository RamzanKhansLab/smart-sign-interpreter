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
  rowsLoaded: false,
  statsPending: false,
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
  if (state.statsPending) return;
  state.statsPending = true;
  try {
    const res = await fetch("/api/dataset/stats", { cache: "no-store" });
    if (!res.ok) throw new Error(await readErrorMessage(res));
    const data = await res.json();
    renderStats(data);
    if (state.rowsLoaded) await loadRows();
    return data;
  } catch (error) {
    setText("dataset-stats", `Refresh failed: ${error.message}`);
    setText("dataset-rows", "Refresh failed. Click LOAD ROWS to retry.");
    updateLabelSelect({});
    return null;
  } finally {
    state.statsPending = false;
  }
}

function updateLabelSelect(byLabel) {
  const select = document.getElementById("edit-label");
  if (!select) return;

  const labels = Object.keys(byLabel);
  labels.sort((a, b) => a.localeCompare(b));
  state.labels = labels;

  const previous = select.value;
  const hadSelection = select.selectedIndex > 0;
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

  const index = [...select.options].findIndex((o, i) => i > 0 && o.value === previous);
  select.selectedIndex = hadSelection && index > 0 ? index : 0;
}

async function refreshModelStatus() {
  const res = await fetch("/api/model/status");
  if (!res.ok) throw new Error(await readErrorMessage(res));
  const data = await res.json();
  setText("model-loaded", data.model_loaded ? "YES" : "NO");
}

async function readErrorMessage(res) {
  try {
    const data = await res.json();
    if (Array.isArray(data.detail)) return data.detail.map((item) => item.msg).join("; ");
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
    if (state.rowsLoaded) await loadRows();
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
    `Retrained (${data.metrics.model_type}). Accuracy=${data.metrics.accuracy.toFixed(3)} Samples=${data.metrics.samples}\n${data.metrics.evaluation_label}\n${data.metrics.warning || "View Model Performance for the full report and confusion matrix."}`
  );
}

function selectedEditLabel() {
  const sel = document.getElementById("edit-label");
  if (!sel) return null;
  const value = sel.value;
  if (sel.selectedIndex <= 0) return null;
  return value;
}

async function loadRows() {
  const label = selectedEditLabel();
  const url = new URL("/api/dataset/rows", window.location.origin);
  url.searchParams.set("limit", "50");
  url.searchParams.set("offset", "0");
  if (label !== null) url.searchParams.set("label", label);

  const res = await fetch(url.toString(), { cache: "no-store" });
  if (!res.ok) {
    const msg = await readErrorMessage(res);
    alert(msg || "Failed to load rows");
    return;
  }
  const data = await res.json();
  state.rowsLoaded = true;
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
  renderStats(out.stats);
  const select = document.getElementById("edit-label");
  select.selectedIndex = [...select.options].findIndex((option, index) => index > 0 && option.value === toLabel);
  await loadRows();
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
  renderStats(out.stats);
  await loadRows();
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
  renderStats(out.stats);
  await loadRows();
}

async function clearDataset() {
  if (!confirm("Clear the entire active dataset (Google Sheets when configured, plus the local CSV)?")) return;
  const res = await fetch("/api/dataset/clear", { method: "POST" });
  if (!res.ok) {
    const msg = await readErrorMessage(res);
    alert(msg || "Clear failed");
    return;
  }
  const out = await res.json();
  alert("Dataset cleared");
  clearBuffer();
  setText("dataset-rows", "Click LOAD ROWS");
  renderStats(out.stats);
  state.rowsLoaded = false;
}

function bindUi() {
  const actions = {
    start: startCapture, stop: stopCapture, save: saveBuffer, clear: clearBuffer,
    "refresh-stats": refreshStats, "model-reset": resetModel, "model-retrain": retrainModel,
    "rows-load": loadRows, "label-rename": renameSelectedLabel,
    "label-delete": deleteSelectedLabel, "delete-empty": deleteEmptyLabels,
    "dataset-clear": clearDataset,
  };
  for (const [id, action] of Object.entries(actions)) {
    const button = document.getElementById(id);
    button.addEventListener("click", async () => {
      if (button.disabled) return;
      const modelAction = id === "model-retrain" || id === "model-reset";
      const buttons = modelAction ? [document.getElementById("model-reset"), document.getElementById("model-retrain")] : [button];
      buttons.forEach((item) => { item.disabled = true; });
      const original = button.textContent;
      if (id === "model-retrain") button.textContent = "TRAINING...";
      try {
        await action();
      } catch (error) {
        alert(`Request failed: ${error.message}. Please retry.`);
      } finally {
        buttons.forEach((item) => { item.disabled = false; });
        button.textContent = original;
      }
    });
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  bindUi();
  setCapturing(false);
  setBufferCount();
  setSavePending(false);
  setupWebSocket();
  startPolling();
  await Promise.allSettled([refreshStats(), refreshModelStatus(), pollLatestOnce()]);
});
