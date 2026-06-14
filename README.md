# AI Chatbot with Session Memory 🤖

A production-quality conversational AI chatbot built with **FastAPI**, **OpenAI GPT**, and a modern **glassmorphism UI**. The chatbot remembers your entire conversation within a session.

---

## ✨ Features

| Feature | Details |
|---|---|
| 💬 **Session Memory** | Full conversation history sent with every request |
| 🧠 **Context Awareness** | AI remembers names, facts, preferences from earlier in the chat |
| 🎨 **Modern UI** | Dark glassmorphism design with smooth animations |
| 📱 **Responsive** | Works on mobile, tablet, and desktop |
| ⚡ **Fast Backend** | Async FastAPI + Uvicorn |
| 🔒 **Secure** | API key loaded from `.env`, never exposed to frontend |
| 🛡️ **Error Handling** | Graceful handling of auth, rate-limit, and network errors |
| 🗑️ **New Chat** | Clear session and start fresh anytime |

---

## 📁 Project Structure

```
AI Chatbot DecodeLabs/
│
├── app.py              ← FastAPI server (routes, request handling)
├── chatbot.py          ← Core engine (memory, OpenAI calls)
├── requirements.txt    ← Python dependencies
├── .env.example        ← Template — copy to .env and fill in your key
├── .gitignore          ← Protects secrets from being committed
│
├── static/
│   ├── style.css       ← All styling (glassmorphism, animations)
│   └── script.js       ← Frontend logic (fetch, rendering, events)
│
└── templates/
    └── index.html      ← Main chat UI (Jinja2 template)
```

---

## 🚀 Quick Start

### Step 1 — Clone / Navigate to project

```powershell
cd "AI Chatbot DecodeLabs"
```

### Step 2 — Create a virtual environment

```powershell
python -m venv venv
venv\Scripts\activate
```

### Step 3 — Install dependencies

```powershell
pip install -r requirements.txt
```

### Step 4 — Set up your API key

```powershell
copy .env.example .env
```

Open `.env` in any text editor and replace the placeholder:

```env
OPENAI_API_KEY=sk-proj-your-real-key-here
OPENAI_MODEL=gpt-4o-mini
```

> 🔑 Get your API key at [platform.openai.com/api-keys](https://platform.openai.com/api-keys)

### Step 5 — Run the server

```powershell
uvicorn app:app --reload
```

### Step 6 — Open the chatbot

Open your browser and go to: **[http://localhost:8001](http://localhost:8001)**

---

## 🧠 How Session Memory Works

Every time you send a message, the **entire conversation history** is sent to the OpenAI API — not just your latest message. This is what makes the chatbot "remember":

```
User:      My name is Alex
AI:        Nice to meet you, Alex!

User:      What is my name?
AI:        Your name is Alex.        ← AI knows because it saw the earlier exchange
```

**Memory data structure:**
```python
history = [
    {"role": "system",    "content": "You are a helpful AI assistant..."},
    {"role": "user",      "content": "My name is Alex"},
    {"role": "assistant", "content": "Nice to meet you, Alex!"},
    {"role": "user",      "content": "What is my name?"},
]
# ↑ This full list is sent on every API call
```

**Where it lives:** `chatbot.py` — the `_sessions` dictionary maps each `session_id` to its message list. Sessions are isolated per browser tab (each tab gets a unique UUID from the server).

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Serves the chat UI |
| `POST` | `/chat` | Send a message, get a reply |
| `POST` | `/clear` | Clear session history |
| `GET` | `/history/{session_id}` | View raw conversation history |
| `GET` | `/health` | Health check |

**Example `/chat` request:**
```json
POST /chat
{
  "message": "Hello!",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Example response:**
```json
{
  "reply": "Hello! How can I help you today?",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## ⚙️ Configuration

Edit `.env` to change behaviour:

```env
OPENAI_API_KEY=sk-proj-...      # Required
OPENAI_MODEL=gpt-4o-mini        # Model to use
HOST=127.0.0.1                  # Server host
PORT=8001                       # Server port
```

**Available models:**
| Model | Speed | Cost | Best For |
|-------|-------|------|----------|
| `gpt-4o-mini` | ⚡ Fast | 💰 Cheap | Development, testing |
| `gpt-4o` | Fast | $$ | Production |
| `gpt-4-turbo` | Medium | $$$ | Complex tasks |

---

## 🛠️ Error Handling

| Error | Cause | User Message |
|-------|-------|--------------|
| `401` | Invalid API key | "Invalid OpenAI API key. Check your .env file." |
| `429` | Rate limit hit | "Rate limit reached. Please wait and try again." |
| `503` | No internet | "Could not connect to OpenAI. Check your connection." |
| `504` | Timeout | "Request timed out. Please try again." |
| `400` | Empty message | "Message cannot be empty." |

---

## 🏗️ Architecture

```
Browser (HTML + CSS + JS)
        │
        │  HTTP POST /chat  {message, session_id}
        ▼
FastAPI Server (app.py)
        │
        │  chatbot.chat(session_id, message)
        ▼
Chatbot Engine (chatbot.py)
        │  ┌───────────────────────────────────┐
        │  │  _sessions[session_id] = [        │
        │  │    {role: system, content: ...},  │
        │  │    {role: user, content: ...},    │
        │  │    {role: assistant, content:...} │
        │  │  ]                                │
        │  └───────────────────────────────────┘
        │
        │  Full history → OpenAI API
        ▼
OpenAI GPT Model
        │
        │  AI reply
        ▼
Chatbot Engine → stores reply in history
        │
        ▼
FastAPI → JSON response → Browser renders bubble
```

---

## 📝 License

MIT — free for personal and commercial use.
