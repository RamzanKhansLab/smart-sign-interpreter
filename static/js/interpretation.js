const state = {
  connected: false,
  pollTimer: null,
  lastPrediction: null,
};

function setText(id, value) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = value;
}

function setSpeakEnabled(enabled) {
  const btn = document.getElementById("speak");
  if (!btn) return;
  btn.disabled = !enabled;
}

function getChannel(channels, key) {
  if (!channels) return null;
  return channels[key] ?? null;
}

function speak(text) {
  if (!text) return;
  if (!("speechSynthesis" in window)) {
    alert("Text-to-speech is not supported in this browser.");
    return;
  }
  try {
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1;
    utterance.pitch = 1;
    utterance.volume = 1;
    window.speechSynthesis.speak(utterance);
  } catch (e) {
    alert("Failed to play voice.");
  }
}

function updateFromMessage(message) {
  if (!message || !message.data) return;
  const data = message.data;
  const channels = data.channels || {};
  const imu = data.imu || {};

  setText("s1", getChannel(channels, "s1") ?? "-");
  setText("s2", getChannel(channels, "s2") ?? "-");
  setText("s3", getChannel(channels, "s3") ?? "-");
  setText("s4", getChannel(channels, "s4") ?? "-");
  setText("s5", getChannel(channels, "s5") ?? "-");
  setText("timestamp", data.timestamp ?? "-");

  setText("ax", imu.ax ?? "-");
  setText("ay", imu.ay ?? "-");
  setText("az", imu.az ?? "-");
  setText("gx", imu.gx ?? "-");
  setText("gy", imu.gy ?? "-");
  setText("gz", imu.gz ?? "-");

  if (message.prediction !== null && message.prediction !== undefined) {
    const pred = String(message.prediction);
    state.lastPrediction = pred;
    setText("prediction", pred);
    setSpeakEnabled(true);
  } else {
    state.lastPrediction = null;
    setText("prediction", "MODEL NOT LOADED");
    setSpeakEnabled(false);
  }

  setText("raw", JSON.stringify(message, null, 2));
  setText("stream-status", "ACTIVE");
}

function setupWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${protocol}://${window.location.host}/ws/sensor-stream`);

  ws.onopen = () => {
    state.connected = true;
    setText("connection-status", "CONNECTED");
  };

  ws.onclose = () => {
    state.connected = false;
    setText("connection-status", "DISCONNECTED");
    setText("stream-status", "IDLE");
  };

  ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    updateFromMessage(message);
  };

  ws.onerror = () => {
    state.connected = false;
  };

  return ws;
}

async function pollLatestOnce() {
  try {
    const res = await fetch("/api/latest");
    if (!res.ok) return;
    const message = await res.json();
    updateFromMessage(message);
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
  }, 2000);
}

function bindUi() {
  const speakBtn = document.getElementById("speak");
  if (speakBtn) {
    speakBtn.addEventListener("click", () => {
      if (!state.lastPrediction) {
        alert("No prediction to speak yet.");
        return;
      }
      speak(state.lastPrediction);
    });
  }
  setSpeakEnabled(false);
}

document.addEventListener("DOMContentLoaded", () => {
  bindUi();
  setupWebSocket();
  startPolling();
});
