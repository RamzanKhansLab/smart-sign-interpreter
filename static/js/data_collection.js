const state = {
  capturing: false,
  timer: null,
  buffer: [],
  lastMessage: null,
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

function setCapturing(isCapturing) {
  state.capturing = isCapturing;
  setText("capture-status", isCapturing ? "RUNNING" : "STOPPED");
}

function setBufferCount() {
  setText("buffer-count", String(state.buffer.length));
}

async function fetchLatest() {
  const res = await fetch("/api/latest");
  if (!res.ok) return null;
  return await res.json();
}

async function tick() {
  try {
    const message = await fetchLatest();
    if (!message) return;
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
}

async function refreshModelStatus() {
  const res = await fetch("/api/model/status");
  const data = await res.json();
  setText("model-loaded", data.model_loaded ? "YES" : "NO");
}

async function saveBuffer() {
  const label = getLabel();
  if (!label) {
    alert("Enter a gesture label");
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
    const err = await res.json().catch(() => ({}));
    alert(err.detail || "Save failed");
    return;
  }

  const out = await res.json();
  alert(`Saved ${out.saved} samples for label '${label}'`);
  clearBuffer();
  refreshStats();
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

function bindUi() {
  document.getElementById("start").addEventListener("click", startCapture);
  document.getElementById("stop").addEventListener("click", stopCapture);
  document.getElementById("save").addEventListener("click", saveBuffer);
  document.getElementById("clear").addEventListener("click", clearBuffer);

  document
    .getElementById("refresh-stats")
    .addEventListener("click", refreshStats);

  document
    .getElementById("model-reset")
    .addEventListener("click", resetModel);

  document
    .getElementById("model-retrain")
    .addEventListener("click", retrainModel);
}

document.addEventListener("DOMContentLoaded", () => {
  bindUi();
  setCapturing(false);
  setBufferCount();
  refreshStats();
  refreshModelStatus();
  tick();
});
