"""
chatbot.py — Core Chatbot Engine (Database, RAG, Web Search, Images)
"""

import os
import json
import urllib.parse
from openai import OpenAI, AuthenticationError, RateLimitError, APIConnectionError, APITimeoutError
from dotenv import load_dotenv

try:
    from duckduckgo_search import DDGS
    _ddgs_available = True
except ImportError:
    _ddgs_available = False

from database import SessionLocal
from models import ChatSession, Message
import rag

load_dotenv(override=True)


def create_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found. Please add it to your .env file.")

    base_url = os.getenv("OPENAI_BASE_URL")
    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    return OpenAI(api_key=api_key)

DEFAULT_SYSTEM_PROMPT = """You are a helpful, friendly, and knowledgeable AI assistant.
You have a warm personality and you are always polite.
You remember everything that has been said in this conversation.
If you don't know something, say so honestly rather than guessing.

IMAGE GENERATION:
If the user asks you to generate, draw, or create an image, you MUST respond with a markdown image linked to Pollinations.ai.
Format: ![Image Description](https://image.pollinations.ai/prompt/[URL_ENCODED_PROMPT]?width=1024&height=1024&nologo=true)
Example: If the user says "draw a cat in space", you reply:
Here is your image:
![A cat in space](https://image.pollinations.ai/prompt/a%20cat%20in%20space?width=1024&height=1024&nologo=true)

DOCUMENT KNOWLEDGE:
If context from a document is provided, use it to answer the question. 
"""

def search_web(query: str) -> str:
    """Search the web using DuckDuckGo."""
    if not _ddgs_available:
        return "Web search is not available yet (dependencies still installing)."
    try:
        results = DDGS().text(query, max_results=3)
        if not results:
            return "No results found."
        formatted_results = "\n\n".join([f"Title: {r['title']}\nSnippet: {r['body']}\nURL: {r['href']}" for r in results])
        return formatted_results
    except Exception as e:
        return f"Search failed: {str(e)}"

tools = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for current events, news, or real-time information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query."
                    }
                },
                "required": ["query"]
            }
        }
    }
]

def get_session_history_db(db, session_id: str, system_prompt: str = None) -> list[dict]:
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

    if not session:
        session = ChatSession(id=session_id)
        db.add(session)
        db.commit()
        sys_msg = Message(session_id=session_id, role="system", content=prompt)
        db.add(sys_msg)
        db.commit()

    messages = db.query(Message).filter(Message.session_id == session_id).order_by(Message.id).all()
    if messages and messages[0].role == "system" and messages[0].content != prompt:
        messages[0].content = prompt
        db.commit()

    return [{"role": msg.role, "content": msg.content} for msg in messages]

def add_message_db(db, session_id: str, role: str, content: str):
    msg = Message(session_id=session_id, role=role, content=content)
    db.add(msg)
    db.commit()

def clear_session_db(db, session_id: str):
    db.query(Message).filter(Message.session_id == session_id).delete()
    db.query(ChatSession).filter(ChatSession.id == session_id).delete()
    db.commit()

def get_history(session_id: str):
    with SessionLocal() as db:
        messages = db.query(Message).filter(Message.session_id == session_id).order_by(Message.id).all()
        return [{"role": msg.role, "content": msg.content} for msg in messages if msg.role != "system"]

def chat_stream(session_id: str, user_message: str, persona: str = None):
    user_message = user_message.strip()
    if not user_message:
        yield "Error: Message cannot be empty."
        return

    with SessionLocal() as db:
        history = get_session_history_db(db, session_id, system_prompt=persona)
        
        # RAG Context Injection
        context = rag.query_index(session_id, user_message)
        final_user_message = user_message
        if context:
            final_user_message = f"DOCUMENT CONTEXT:\n{context}\n\nUSER QUESTION: {user_message}"

        add_message_db(db, session_id, "user", user_message)  # Store original message
        
        # We append the augmented message for the LLM to read
        history.append({"role": "user", "content": final_user_message})

        try:
            client = create_client()
            
            # Call model directly with streaming
            response = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "grok-3-mini"),
                messages=history,
                temperature=0.7,
                max_tokens=2048,
                timeout=30.0,
                stream=True,
            )
            
            full_reply = ""
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    text = chunk.choices[0].delta.content
                    full_reply += text
                    yield text
            add_message_db(db, session_id, "assistant", full_reply)


        except Exception as e:
            last_msg = db.query(Message).filter(Message.session_id == session_id).order_by(Message.id.desc()).first()
            if last_msg:
                db.delete(last_msg)
            db.commit()
            yield f"Error: Unexpected error - {str(e)}"
