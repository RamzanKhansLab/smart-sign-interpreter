const state = {
  connected: false,
  pollTimer: null,
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
    setText("prediction", message.prediction);
  } else {
    setText("prediction", "MODEL NOT LOADED");
  }

  setText("raw", JSON.stringify(message, null, 2));
  setText("stream-status", "ACTIVE");
}

function showNoData(reason) {
  setText("stream-status", "NO DATA");
  setText(
    "raw",
    reason ||
      "No sensor data yet. POST to /api/sensor-data or use the demo button on Home."
  );
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

  // Keep some proxies from closing an idle socket.
  const pingTimer = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) {
      try {
        ws.send("ping");
      } catch (e) {
        // ignore
      }
    }
  }, 15000);

  ws.addEventListener("close", () => clearInterval(pingTimer));

  return ws;
}

async function pollLatestOnce() {
  try {
    const res = await fetch("/api/latest");
    if (res.status === 404) {
      showNoData();
      return;
    }
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

document.addEventListener("DOMContentLoaded", () => {
  setupWebSocket();
  startPolling();
  pollLatestOnce();
});