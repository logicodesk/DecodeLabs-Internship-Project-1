/**
 * script.js — Frontend Chat Logic with Streaming, Markdown, Voice, Auth, Sidebar
 */

let sessionId = window.SESSION_ID || crypto.randomUUID();
let isLoading = false;
let authToken = localStorage.getItem('chat_token');

// DOM References
const chatWindow    = document.getElementById('chatWindow');
const messageInput  = document.getElementById('messageInput');
const sendBtn       = document.getElementById('sendBtn');
const charCount     = document.getElementById('charCount');
const newChatBtn    = document.getElementById('newChatBtn');
const downloadBtn   = document.getElementById('downloadChatBtn');
const voiceBtn      = document.getElementById('voiceBtn');
const personaSelect = document.getElementById('personaSelect');

// Upload DOM
const attachBtn      = document.getElementById('attachBtn');
const fileInput      = document.getElementById('fileInput');
const uploadStatus   = document.getElementById('uploadStatus');
const uploadFileName = document.getElementById('uploadFileName');
const uploadProgressFill = document.getElementById('uploadProgressFill');
const uploadBadge    = document.getElementById('uploadBadge');
const uploadBadgeName = document.getElementById('uploadBadgeName');
const removeUploadBtn = document.getElementById('removeUploadBtn');
const modalOverlay  = document.getElementById('modalOverlay');
const modalConfirm  = document.getElementById('modalConfirm');
const modalCancel   = document.getElementById('modalCancel');
const welcomeScreen = document.getElementById('welcomeScreen');

// Auth DOM
const authModal     = document.getElementById('authModal');
const authUsername  = document.getElementById('authUsername');
const authPassword  = document.getElementById('authPassword');
const loginBtn      = document.getElementById('loginBtn');
const registerBtn   = document.getElementById('registerBtn');
const authError     = document.getElementById('authError');
const loggedInUser  = document.getElementById('loggedInUser');
const sessionList   = document.getElementById('sessionList');
const logoutBtn     = document.getElementById('logoutBtn');

const MAX_CHARS = 2000;

// Speech Recognition setup
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;
if (SpeechRecognition) {
  recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = false;
  
  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    messageInput.value += (messageInput.value ? ' ' : '') + transcript;
    updateCharCount();
    autoResize();
    voiceBtn.classList.remove('active');
  };
  recognition.onerror = () => voiceBtn.classList.remove('active');
  recognition.onend = () => voiceBtn.classList.remove('active');
} else {
  voiceBtn.style.display = 'none';
}

function currentTime() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function escapeHTML(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function formatAIText(text) {
  if (typeof marked !== 'undefined' && typeof DOMPurify !== 'undefined') {
    return DOMPurify.sanitize(marked.parse(text));
  }
  return escapeHTML(text).replace(/\n/g, '<br>');
}

function scrollToBottom() {
  chatWindow.scrollTo({ top: chatWindow.scrollHeight, behavior: 'smooth' });
}

function hideWelcome() {
  if (welcomeScreen) welcomeScreen.style.display = 'none';
}

// ── Auth Flow ────────────────────────────────────────────────────────────

function showAuthError(msg) {
  authError.textContent = msg;
  authError.style.display = 'block';
}

async function handleLogin() {
  const username = authUsername.value.trim();
  const password = authPassword.value;
  if (!username || !password) return showAuthError("Enter username and password");

  const formData = new URLSearchParams();
  formData.append('username', username);
  formData.append('password', password);

  try {
    const res = await fetch('/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Login failed");
    
    authToken = data.access_token;
    localStorage.setItem('chat_token', authToken);
    authModal.classList.remove('active');
    initApp();
  } catch (err) {
    showAuthError(err.message);
  }
}

async function handleRegister() {
  const username = authUsername.value.trim();
  const password = authPassword.value;
  if (!username || !password) return showAuthError("Enter username and password");

  try {
    const res = await fetch('/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Registration failed");
    
    // Automatically log in after registration
    await handleLogin();
  } catch (err) {
    showAuthError(err.message);
  }
}

function handleLogout() {
  localStorage.removeItem('chat_token');
  authToken = null;
  authModal.classList.add('active');
  chatWindow.innerHTML = '';
  sessionList.innerHTML = '';
  sessionId = crypto.randomUUID();
}

loginBtn.addEventListener('click', handleLogin);
registerBtn.addEventListener('click', handleRegister);
logoutBtn.addEventListener('click', handleLogout);

// ── Sidebar & Sessions ───────────────────────────────────────────────────

async function fetchSessions() {
  try {
    const res = await fetch('/sessions', {
      headers: { 'Authorization': `Bearer ${authToken}` }
    });
    if (!res.ok) {
      if (res.status === 401) handleLogout();
      return;
    }
    const sessions = await res.json();
    sessionList.innerHTML = '';
    
    sessions.forEach(s => {
      const div = document.createElement('div');
      div.className = 'session-item';
      div.textContent = s.title;
      div.onclick = () => loadSession(s.id);
      sessionList.appendChild(div);
    });
  } catch(e) { console.error(e); }
}

async function loadSession(id) {
  try {
    const res = await fetch(`/history/${id}`, {
      headers: { 'Authorization': `Bearer ${authToken}` }
    });
    if (!res.ok) return;
    const data = await res.json();
    
    sessionId = id;
    chatWindow.innerHTML = '';
    
    if (data.history.length === 0) {
      chatWindow.appendChild(createWelcomeScreen());
    } else {
      data.history.forEach(msg => {
        if (msg.role === 'user') appendUserMessage(msg.content);
        else if (msg.role === 'assistant') {
          const b = createAIMessageBubble();
          b.appendText(msg.content);
        }
      });
      scrollToBottom();
    }
  } catch(e) { console.error(e); }
}

// ── Messages ─────────────────────────────────────────────────────────────

function appendUserMessage(text) {
  const row = document.createElement('div');
  row.className = 'message-row user';
  row.innerHTML = `
    <div class="avatar user-avatar" aria-hidden="true">👤</div>
    <div class="bubble-group">
      <div class="bubble" role="log" aria-label="Your message">${escapeHTML(text)}</div>
      <span class="message-time">${currentTime()}</span>
    </div>
  `;
  chatWindow.appendChild(row);
  scrollToBottom();
}

function createAIMessageBubble() {
  const row = document.createElement('div');
  row.className = 'message-row ai';
  row.innerHTML = `
    <div class="avatar ai-avatar" aria-hidden="true">🤖</div>
    <div class="bubble-group">
      <div class="bubble" role="log" aria-label="AI response"></div>
      <div class="message-footer">
        <span class="message-time">${currentTime()}</span>
        <button class="copy-btn" title="Copy to clipboard">📋 Copy</button>
        <button class="speak-btn" title="Read aloud">🔊 Read</button>
      </div>
    </div>
  `;
  chatWindow.appendChild(row);
  
  const bubble = row.querySelector('.bubble');
  const copyBtn = row.querySelector('.copy-btn');
  const speakBtn = row.querySelector('.speak-btn');
  let rawContent = "";
  
  copyBtn.addEventListener('click', () => {
    navigator.clipboard.writeText(rawContent).then(() => {
      copyBtn.textContent = '✅ Copied!';
      setTimeout(() => copyBtn.textContent = '📋 Copy', 2000);
    });
  });

  speakBtn.addEventListener('click', () => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(bubble.innerText);
      window.speechSynthesis.speak(utterance);
    }
  });

  return { row, bubble, appendText: (text) => {
    rawContent += text;
    bubble.innerHTML = formatAIText(rawContent);
  }};
}

function showTypingIndicator() {
  const row = document.createElement('div');
  row.className = 'typing-row';
  row.id = 'typingIndicator';
  row.innerHTML = `
    <div class="avatar ai-avatar" aria-hidden="true">🤖</div>
    <div class="typing-bubble" aria-label="AI is typing" role="status">
      <div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>
    </div>
  `;
  chatWindow.appendChild(row);
  scrollToBottom();
  return row;
}

function removeTypingIndicator() {
  const el = document.getElementById('typingIndicator');
  if (el) el.remove();
}

function showError(message) {
  const toast = document.createElement('div');
  toast.className = 'error-toast';
  toast.innerHTML = `<span class="error-icon">⚠️</span><span>${escapeHTML(message)}</span>`;
  chatWindow.appendChild(toast);
  scrollToBottom();
  setTimeout(() => toast.remove(), 8000);
}

// ── Streaming Send Flow ──────────────────────────────────────────────────
async function sendMessage() {
  const text = messageInput.value.trim();
  const persona = personaSelect.value;

  if (!text || isLoading) return;
  if (text.length > MAX_CHARS) return showError(`Message too long.`);

  isLoading = true;
  sendBtn.disabled = true;
  messageInput.disabled = true;
  messageInput.value = '';
  updateCharCount();
  resetTextareaHeight();
  hideWelcome();

  appendUserMessage(text);
  const typingEl = showTypingIndicator();

  try {
    const response = await fetch('/chat', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`
      },
      body: JSON.stringify({ message: text, session_id: sessionId, persona: persona }),
    });

    removeTypingIndicator();

    if (!response.ok) {
      if (response.status === 401) return handleLogout();
      const errData = await response.json().catch(() => ({}));
      return showError(errData.detail || `Server error`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    const aiBubble = createAIMessageBubble();

    let done = false;
    let buffer = "";

    while (!done) {
      const { value, done: readerDone } = await reader.read();
      done = readerDone;
      if (value) {
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop(); 
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.replace('data: ', '');
            try {
              const data = JSON.parse(dataStr);
              if (data.session_id) sessionId = data.session_id;
              if (data.error) showError(data.error);
              else if (data.chunk) {
                aiBubble.appendText(data.chunk);
                scrollToBottom();
              }
            } catch (e) { }
          }
        }
      }
    }
    
    // Refresh sidebar after a new message so the new session shows up
    fetchSessions();
  } catch (err) {
    removeTypingIndicator();
    showError('Network error. Please check your connection.');
  } finally {
    isLoading = false;
    sendBtn.disabled = false;
    messageInput.disabled = false;
    messageInput.focus();
  }
}

// ── Helpers ──────────────────────────────────────────────────────────────
function updateCharCount() {
  const len = messageInput.value.length;
  charCount.textContent = `${len} / ${MAX_CHARS}`;
  charCount.className = 'char-count';
  if (len > MAX_CHARS * 0.9) charCount.classList.add('danger');
  else if (len > MAX_CHARS * 0.7) charCount.classList.add('warning');
}

function resetTextareaHeight() { messageInput.style.height = 'auto'; }
function autoResize() {
  messageInput.style.height = 'auto';
  messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
}

function openClearModal() { modalOverlay.classList.add('active'); }
function closeClearModal() { modalOverlay.classList.remove('active'); }

async function clearConversation() {
  closeClearModal();
  try {
    await fetch('/clear', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`
      },
      body: JSON.stringify({ session_id: sessionId }),
    });
  } catch (e) { }
  sessionId = crypto.randomUUID();
  chatWindow.innerHTML = '';
  chatWindow.appendChild(createWelcomeScreen());
}

function createWelcomeScreen() {
  const div = document.createElement('div');
  div.className = 'welcome-screen';
  div.id = 'welcomeScreen';
  div.innerHTML = `
    <div class="welcome-avatar">🤖</div>
    <h2>Hello! I'm your AI Assistant</h2>
    <p>I remember everything you tell me during our conversation. Ask me anything!</p>
    <div class="starter-chips">
      <button class="chip" onclick="useChip(this)">✍️ Write a poem for me</button>
      <button class="chip" onclick="useChip(this)">💡 Explain quantum computing</button>
      <button class="chip" onclick="useChip(this)">🔢 Solve a math problem</button>
      <button class="chip" onclick="useChip(this)">🌍 Recommend a travel destination</button>
    </div>
  `;
  return div;
}

function useChip(btn) {
  const raw = btn.textContent.trim();
  const text = raw.replace(/^[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]\s*/u, '').trim();
  messageInput.value = text;
  updateCharCount();
  autoResize();
  sendMessage();
}

function downloadChat() {
  const elements = chatWindow.querySelectorAll('.message-row');
  if (elements.length === 0) return alert('No chat to download!');
  
  let content = "# Chat History\n\n";
  elements.forEach(el => {
    const isUser = el.classList.contains('user');
    const bubble = el.querySelector('.bubble');
    const text = isUser ? bubble.innerText : bubble.innerText;
    content += `### ${isUser ? 'You' : 'AI Assistant'}\n${text}\n\n---\n\n`;
  });
  
  const blob = new Blob([content], { type: 'text/markdown' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `chat_history_${new Date().toISOString().split('T')[0]}.md`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── File Upload ──────────────────────────────────────────────────────────
async function uploadFile(file) {
  if (!authToken) return showError('Please log in first.');
  if (!file) return;

  const maxSize = 10 * 1024 * 1024; // 10MB
  if (file.size > maxSize) return showError('File too large. Max 10MB.');

  const allowed = ['.pdf', '.txt', '.md', '.csv'];
  const ext = '.' + file.name.split('.').pop().toLowerCase();
  if (!allowed.includes(ext)) return showError('Unsupported file type. Use PDF, TXT, MD, or CSV.');

  // Show upload progress
  uploadStatus.style.display = 'block';
  uploadFileName.textContent = `Processing: ${file.name}`;
  uploadProgressFill.style.width = '20%';
  uploadBadge.style.display = 'none';

  const formData = new FormData();
  formData.append('file', file);
  formData.append('session_id', sessionId);

  try {
    // Simulate progress steps
    uploadProgressFill.style.width = '50%';

    const res = await fetch('/upload', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${authToken}` },
      body: formData,
    });

    uploadProgressFill.style.width = '90%';

    if (!res.ok) {
      if (res.status === 401) return handleLogout();
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || 'Upload failed');
    }

    uploadProgressFill.style.width = '100%';

    // Hide progress, show success badge
    setTimeout(() => {
      uploadStatus.style.display = 'none';
      uploadProgressFill.style.width = '0%';
      uploadBadge.style.display = 'flex';
      uploadBadgeName.textContent = `${file.name} — Ready for Q&A`;
    }, 500);

    // Add a system message to the chat
    hideWelcome();
    const row = document.createElement('div');
    row.className = 'message-row ai';
    row.innerHTML = `
      <div class="avatar ai-avatar" aria-hidden="true">🤖</div>
      <div class="bubble-group">
        <div class="bubble" style="background: rgba(16,185,129,0.08); border-color: rgba(16,185,129,0.25);">
          📄 <strong>${escapeHTML(file.name)}</strong> has been processed! You can now ask questions about this document.
        </div>
        <span class="message-time">${currentTime()}</span>
      </div>
    `;
    chatWindow.appendChild(row);
    scrollToBottom();

  } catch (err) {
    uploadStatus.style.display = 'none';
    uploadProgressFill.style.width = '0%';
    showError(`Upload failed: ${err.message}`);
  }

  // Reset file input for re-upload
  fileInput.value = '';
}

// ── Listeners ────────────────────────────────────────────────────────────
sendBtn.addEventListener('click', sendMessage);
messageInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});
messageInput.addEventListener('input', () => { updateCharCount(); autoResize(); });
newChatBtn.addEventListener('click', openClearModal);
downloadBtn.addEventListener('click', downloadChat);
voiceBtn.addEventListener('click', () => {
  if (recognition) {
    voiceBtn.classList.add('active');
    recognition.start();
  }
});

// File Upload Listeners
if (attachBtn) {
  attachBtn.addEventListener('click', () => fileInput.click());
}
if (fileInput) {
  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) uploadFile(e.target.files[0]);
  });
}
if (removeUploadBtn) {
  removeUploadBtn.addEventListener('click', () => {
    uploadBadge.style.display = 'none';
  });
}

modalConfirm.addEventListener('click', clearConversation);
modalCancel.addEventListener('click', closeClearModal);
modalOverlay.addEventListener('click', (e) => { if (e.target === modalOverlay) closeClearModal(); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeClearModal(); });

// ── Initialization ───────────────────────────────────────────────────────
async function initApp() {
  if (!authToken) {
    authModal.classList.add('active');
    return;
  }
  
  // Verify token
  try {
    const res = await fetch('/me', { headers: { 'Authorization': `Bearer ${authToken}` } });
    if (!res.ok) throw new Error("Invalid token");
    const data = await res.json();
    loggedInUser.textContent = `Logged in as: ${data.username}`;
    authModal.classList.remove('active');
    
    // Load sidebar sessions
    fetchSessions();
    chatWindow.appendChild(createWelcomeScreen());
  } catch(e) {
    handleLogout();
  }
}

window.addEventListener('DOMContentLoaded', () => {
  initApp();
  messageInput.focus();
  updateCharCount();
});
