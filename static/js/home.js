function setText(id, value) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = value;
}

async function sendDemoPacket() {
  setText("demo-output", "Sending...");
  try {
    const res = await fetch("/api/demo/publish", { method: "POST" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      setText("demo-output", data.detail || `Failed: HTTP ${res.status}`);
      return;
    }
    setText("demo-output", JSON.stringify(data, null, 2));
  } catch (e) {
    setText("demo-output", "Network error sending demo packet");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("send-demo");
  if (btn) btn.addEventListener("click", sendDemoPacket);
});