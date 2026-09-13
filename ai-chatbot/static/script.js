const logEl = document.getElementById("log");
const emptyEl = document.getElementById("empty");
const form = document.getElementById("composerForm");
const input = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const logoutBtn = document.getElementById("logoutBtn");

let conversationId = null;

if (logoutBtn) {
  logoutBtn.addEventListener("click", async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    window.location.href = "/login";
  });
}

input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 140) + "px";
});

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    form.requestSubmit();
  }
});

function appendMessage(role, text) {
  if (logEl.contains(emptyEl)) logEl.removeChild(emptyEl);
  const row = document.createElement("div");
  row.className = "row " + role;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  row.appendChild(bubble);
  logEl.appendChild(row);
  logEl.scrollTop = logEl.scrollHeight;
  return row;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;

  input.value = "";
  input.style.height = "auto";
  sendBtn.disabled = true;

  appendMessage("user", text);
  const thinkingRow = appendMessage("assistant thinking", "Soch raha hoon…");
  thinkingRow.classList.add("thinking");

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, conversation_id: conversationId }),
    });

    if (res.status === 401) {
      window.location.href = "/login";
      return;
    }

    const data = await res.json();
    thinkingRow.remove();

    if (!res.ok) {
      appendMessage("assistant", data.error || "Kuch gadbad ho gayi. Dobara try karo.");
      return;
    }

    conversationId = data.conversation_id;
    appendMessage("assistant", data.response);
  } catch (err) {
    thinkingRow.remove();
    appendMessage("assistant", "Server tak nahi pahunch paya. Dobara try karo.");
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
});