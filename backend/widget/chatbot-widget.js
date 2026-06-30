/**
 * EmbedAI — Embeddable Widget
 *
 * Usage: Paste this before </body> on your site:
 * <script src="https://YOUR_API/widget.js" data-id="CHATBOT_ID"></script>
 *
 * Config is fetched dynamically from the backend on every load.
 * Changing settings in the EmbedAI dashboard updates all embedded widgets automatically.
 * Zero dependencies. Works on any website.
 */

(function () {
  "use strict";

  // ── Bootstrap — read only what we MUST have from the script tag ──────────
  const script = document.currentScript;
  const CHATBOT_ID =
    script?.getAttribute("data-chatbot-id") ||
    script?.getAttribute("data-id") ||
    "";
  const API_BASE =
    script?.getAttribute("data-api-url") ||
    script?.src.replace(/\/widget\.js.*$/, "") ||
    "http://localhost:8000";

  if (!CHATBOT_ID) {
    console.error("[EmbedAI Widget] Missing data-id attribute on script tag.");
    return;
  }

  const MAX_MESSAGE_LENGTH = 1000;

  // ── State ─────────────────────────────────────────────────────────────────
  let isOpen = false;
  let visitorId = localStorage.getItem("chatbot_visitor_id") || null;
  let messages = [];
  let isStreaming = false;

  // ── Fetch config from backend, then boot the widget ───────────────────────
  async function init() {
    // Defaults (used if the API call fails)
    let PRIMARY_COLOR = "#6366f1";
    let POSITION      = "right";
    let HEADER_TEXT   = "AI Assistant";
    let WELCOME_MSG   = "Hi there! How can I help you today?";

    try {
      const res = await fetch(
        `${API_BASE}/api/chatbots/${CHATBOT_ID}/widget-config`,
        { cache: "no-store" }   // always get the latest settings
      );
      if (res.ok) {
        const cfg = await res.json();
        PRIMARY_COLOR = cfg.color    || PRIMARY_COLOR;
        POSITION      = cfg.position || POSITION;
        HEADER_TEXT   = cfg.header   || HEADER_TEXT;
        WELCOME_MSG   = cfg.welcome  || WELCOME_MSG;
      }
    } catch (e) {
      console.warn("[EmbedAI Widget] Could not fetch config, using defaults.", e);
    }

    // Hand off to the synchronous builder with fully-resolved config
    buildWidget(PRIMARY_COLOR, POSITION, HEADER_TEXT, WELCOME_MSG);
  }

  // ── Build & mount widget after config is resolved ─────────────────────────
  function buildWidget(PRIMARY_COLOR, POSITION, HEADER_TEXT, WELCOME_MSG) {

    // ── Inject Styles ───────────────────────────────────────────────────────
    const style = document.createElement("style");
    style.textContent = `
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

      #cb-widget-container * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      }

      /* ── Chat Bubble ──────────────────────────── */
      #cb-bubble {
        position: fixed;
        bottom: 24px;
        ${POSITION}: 24px;
        width: 60px;
        height: 60px;
        border-radius: 50%;
        background: ${PRIMARY_COLOR};
        color: white;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 24px rgba(0,0,0,0.25);
        z-index: 999998;
        transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1),
                    box-shadow 0.3s ease;
        animation: cb-bounce-in 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
      }

      #cb-bubble:hover {
        transform: scale(1.1);
        box-shadow: 0 6px 32px rgba(0,0,0,0.35);
      }

      #cb-bubble svg {
        width: 28px;
        height: 28px;
        transition: transform 0.3s ease;
      }

      #cb-bubble.cb-open svg.cb-chat-icon  { display: none; }
      #cb-bubble.cb-open svg.cb-close-icon { display: block; }
      #cb-bubble:not(.cb-open) svg.cb-chat-icon  { display: block; }
      #cb-bubble:not(.cb-open) svg.cb-close-icon { display: none; }

      @keyframes cb-bounce-in {
        0%   { transform: scale(0); opacity: 0; }
        100% { transform: scale(1); opacity: 1; }
      }

      /* ── Chat Window ──────────────────────────── */
      #cb-window {
        position: fixed;
        bottom: 100px;
        ${POSITION}: 24px;
        width: 380px;
        height: 520px;
        border-radius: 16px;
        background: #ffffff;
        box-shadow: 0 12px 48px rgba(0,0,0,0.15), 0 0 0 1px rgba(0,0,0,0.05);
        z-index: 999999;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        opacity: 0;
        transform: translateY(20px) scale(0.95);
        pointer-events: none;
        transition: opacity 0.3s ease, transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
      }

      #cb-window.cb-visible {
        opacity: 1;
        transform: translateY(0) scale(1);
        pointer-events: all;
      }

      /* ── Header ───────────────────────────────── */
      #cb-header {
        background: ${PRIMARY_COLOR};
        padding: 18px 20px;
        display: flex;
        align-items: center;
        gap: 12px;
        flex-shrink: 0;
      }

      #cb-header-avatar {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        background: rgba(255,255,255,0.2);
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
      }

      #cb-header-avatar svg {
        width: 20px;
        height: 20px;
        color: white;
      }

      #cb-header-info { flex: 1; }

      #cb-header-title {
        color: white;
        font-weight: 600;
        font-size: 15px;
        line-height: 1.3;
      }

      #cb-header-subtitle {
        color: rgba(255,255,255,0.75);
        font-size: 12px;
        line-height: 1.3;
      }

      /* ── Messages ──────────────────────────────── */
      #cb-messages {
        flex: 1;
        overflow-y: auto;
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 12px;
        background: #f8f9fb;
      }

      #cb-messages::-webkit-scrollbar { width: 4px; }
      #cb-messages::-webkit-scrollbar-thumb {
        background: #d1d5db;
        border-radius: 4px;
      }

      .cb-msg {
        max-width: 85%;
        padding: 10px 14px;
        border-radius: 16px;
        font-size: 14px;
        line-height: 1.5;
        word-wrap: break-word;
        animation: cb-fade-in 0.3s ease;
      }

      @keyframes cb-fade-in {
        0%   { opacity: 0; transform: translateY(6px); }
        100% { opacity: 1; transform: translateY(0); }
      }

      .cb-msg-user {
        align-self: flex-end;
        background: ${PRIMARY_COLOR};
        color: white;
        border-bottom-right-radius: 4px;
      }

      .cb-msg-assistant {
        align-self: flex-start;
        background: white;
        color: #1f2937;
        border-bottom-left-radius: 4px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
      }

      .cb-msg-welcome {
        align-self: center;
        background: transparent;
        color: #6b7280;
        font-size: 13px;
        text-align: center;
        padding: 8px;
      }

      /* ── Typing indicator ─────────────────────── */
      .cb-typing {
        display: flex;
        gap: 4px;
        padding: 12px 16px;
        align-self: flex-start;
        background: white;
        border-radius: 16px;
        border-bottom-left-radius: 4px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
      }

      .cb-typing-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #9ca3af;
        animation: cb-typing-bounce 1.4s infinite;
      }

      .cb-typing-dot:nth-child(2) { animation-delay: 0.2s; }
      .cb-typing-dot:nth-child(3) { animation-delay: 0.4s; }

      @keyframes cb-typing-bounce {
        0%, 60%, 100% { transform: translateY(0); }
        30%           { transform: translateY(-6px); }
      }

      /* ── Input ─────────────────────────────────── */
      #cb-input-area {
        padding: 12px 16px;
        border-top: 1px solid #e5e7eb;
        display: flex;
        gap: 8px;
        align-items: center;
        background: white;
        flex-shrink: 0;
      }

      #cb-input {
        flex: 1;
        border: 1px solid #e5e7eb;
        border-radius: 24px;
        padding: 10px 16px;
        font-size: 14px;
        outline: none;
        transition: border-color 0.2s;
        font-family: 'Inter', sans-serif;
        background: #f9fafb;
      }

      #cb-input:focus {
        border-color: ${PRIMARY_COLOR};
        background: white;
      }

      #cb-input::placeholder { color: #9ca3af; }

      #cb-send-btn {
        width: 38px;
        height: 38px;
        border-radius: 50%;
        border: none;
        background: ${PRIMARY_COLOR};
        color: white;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: opacity 0.2s, transform 0.2s;
        flex-shrink: 0;
      }

      #cb-send-btn:hover   { transform: scale(1.05); }
      #cb-send-btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
        transform: none;
      }

      #cb-send-btn svg { width: 18px; height: 18px; }

      /* ── Powered By ───────────────────────────── */
      #cb-powered {
        text-align: center;
        padding: 6px;
        font-size: 11px;
        color: #9ca3af;
        background: white;
        border-top: 1px solid #f3f4f6;
      }

      #cb-powered a {
        color: #6b7280;
        text-decoration: none;
        font-weight: 500;
      }

      /* ── Mobile ────────────────────────────────── */
      @media (max-width: 440px) {
        #cb-window {
          width: calc(100vw - 16px);
          height: calc(100vh - 140px);
          ${POSITION}: 8px;
          bottom: 90px;
          border-radius: 12px;
        }
      }
    `;
    document.head.appendChild(style);

    // ── Build DOM ───────────────────────────────────────────────────────────
    const container = document.createElement("div");
    container.id = "cb-widget-container";

    container.innerHTML = `
      <!-- Chat Bubble -->
      <div id="cb-bubble">
        <svg class="cb-chat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
        </svg>
        <svg class="cb-close-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      </div>

      <!-- Chat Window -->
      <div id="cb-window">
        <div id="cb-header">
          <div id="cb-header-avatar">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 2a7 7 0 0 1 7 7c0 3-2 5.5-4 7l-3 3.5L9 16c-2-1.5-4-4-4-7a7 7 0 0 1 7-7z"></path>
              <circle cx="12" cy="9" r="2"></circle>
            </svg>
          </div>
          <div id="cb-header-info">
            <div id="cb-header-title">${HEADER_TEXT}</div>
            <div id="cb-header-subtitle">Ask me anything about this site</div>
          </div>
        </div>

        <div id="cb-messages">
          <div class="cb-msg cb-msg-welcome">${WELCOME_MSG}</div>
        </div>

        <div id="cb-input-area">
          <input type="text" id="cb-input" placeholder="Ask something..." autocomplete="off" maxlength="1000" />
          <button id="cb-send-btn" title="Send">
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"></path>
            </svg>
          </button>
        </div>

        <div id="cb-powered">
          Powered by <a href="https://getembedai.vercel.app" target="_blank" rel="noopener">EmbedAI</a>
        </div>
      </div>
    `;

    document.body.appendChild(container);

    // ── Element refs ────────────────────────────────────────────────────────
    const bubble     = document.getElementById("cb-bubble");
    const window_    = document.getElementById("cb-window");
    const messagesEl = document.getElementById("cb-messages");
    const input      = document.getElementById("cb-input");
    const sendBtn    = document.getElementById("cb-send-btn");

    // ── Toggle ──────────────────────────────────────────────────────────────
    bubble.addEventListener("click", () => {
      isOpen = !isOpen;
      bubble.classList.toggle("cb-open", isOpen);
      window_.classList.toggle("cb-visible", isOpen);
      if (isOpen) setTimeout(() => input.focus(), 300);
    });

    // ── Send Message ────────────────────────────────────────────────────────
    function sendMessage() {
      const text = input.value.trim();
      if (!text || isStreaming) return;
      if (text.length > MAX_MESSAGE_LENGTH) {
        addMessage("assistant", `Message is too long (max ${MAX_MESSAGE_LENGTH} characters).`);
        return;
      }
      addMessage("user", text);
      input.value = "";
      isStreaming = true;
      sendBtn.disabled = true;
      showTyping();
      fetchStreamingResponse(text);
    }

    sendBtn.addEventListener("click", sendMessage);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    // ── UI helpers ──────────────────────────────────────────────────────────
    function addMessage(role, content) {
      messages.push({ role, content });
      const msgEl = document.createElement("div");
      msgEl.className = `cb-msg cb-msg-${role}`;
      msgEl.textContent = content;
      messagesEl.appendChild(msgEl);
      scrollToBottom();
      return msgEl;
    }

    function showTyping() {
      const el = document.createElement("div");
      el.className = "cb-typing";
      el.id = "cb-typing";
      el.innerHTML = `
        <div class="cb-typing-dot"></div>
        <div class="cb-typing-dot"></div>
        <div class="cb-typing-dot"></div>
      `;
      messagesEl.appendChild(el);
      scrollToBottom();
    }

    function removeTyping() {
      const el = document.getElementById("cb-typing");
      if (el) el.remove();
    }

    function scrollToBottom() {
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function formatErrorDetail(detail) {
      if (!detail) return null;
      if (typeof detail === "string") return detail;
      if (Array.isArray(detail)) return detail.map((d) => d.msg || String(d)).join(", ");
      return String(detail);
    }

    // ── Streaming API Call ──────────────────────────────────────────────────
    async function fetchStreamingResponse(question) {
      try {
        const response = await fetch(`${API_BASE}/api/chat/${CHATBOT_ID}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: question, visitor_id: visitorId }),
        });

        if (!response.ok) {
          const err = await response.json().catch(() => ({}));
          throw new Error(formatErrorDetail(err.detail) || `Server error (${response.status})`);
        }

        const newVisitorId = response.headers.get("X-Visitor-Id");
        if (newVisitorId) {
          visitorId = newVisitorId;
          localStorage.setItem("chatbot_visitor_id", visitorId);
        }

        removeTyping();
        const msgEl = document.createElement("div");
        msgEl.className = "cb-msg cb-msg-assistant";
        messagesEl.appendChild(msgEl);

        const reader  = response.body.getReader();
        const decoder = new TextDecoder();
        let fullText  = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          fullText += decoder.decode(value, { stream: true });
          msgEl.textContent = fullText;
          scrollToBottom();
        }

        messages.push({ role: "assistant", content: fullText });
      } catch (err) {
        removeTyping();
        addMessage(
          "assistant",
          err instanceof Error ? err.message : "Sorry, something went wrong. Please try again."
        );
        console.error("[EmbedAI Widget]", err);
      } finally {
        isStreaming    = false;
        sendBtn.disabled = false;
        input.focus();
      }
    }

  } // end buildWidget()

  // ── Kick off ───────────────────────────────────────────────────────────────
  init();

})();
