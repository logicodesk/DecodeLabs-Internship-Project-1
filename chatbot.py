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
            
            # Step 1: Call model with tools
            response = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "grok-3-mini"),
                messages=history,
                temperature=0.7,
                max_tokens=2048,
                timeout=30.0,
                tools=tools,
                tool_choice="auto",
                stream=False, # We don't stream the first pass because it might be a tool call
            )

            message = response.choices[0].message
            
            # Step 2: Handle Tool Calls (Web Search)
            if message.tool_calls:
                history.append(message.model_dump(exclude_unset=True))
                for tool_call in message.tool_calls:
                    if tool_call.function.name == "search_web":
                        args = json.loads(tool_call.function.arguments)
                        query = args.get("query")
                        yield f"*Searching the web for: '{query}'...*\n\n"
                        search_result = search_web(query)
                        history.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_call.function.name,
                            "content": search_result
                        })
                
                # Step 3: Second call with tool results (Streaming)
                second_response = client.chat.completions.create(
                    model=os.getenv("OPENAI_MODEL", "grok-3-mini"),
                    messages=history,
                    stream=True,
                )
                
                full_reply = ""
                for chunk in second_response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        text = chunk.choices[0].delta.content
                        full_reply += text
                        yield text
                add_message_db(db, session_id, "assistant", full_reply)

            else:
                # No tool calls, just stream normally
                # Since we already ran a non-stream query, we can just yield the content, 
                # but to be truly streaming, we should have used stream=True first and detected tools.
                # OpenAI Python SDK can stream tool calls, but it's complex. Let's just yield the non-streamed text for simplicity when it's not a tool call.
                # Actually, to preserve the streaming feel, let's yield it in chunks.
                full_reply = message.content
                chunk_size = 10
                for i in range(0, len(full_reply), chunk_size):
                    yield full_reply[i:i+chunk_size]
                add_message_db(db, session_id, "assistant", full_reply)

        except Exception as e:
            db.query(Message).filter(Message.session_id == session_id).order_by(Message.id.desc()).limit(1).delete()
            db.commit()
            yield f"Error: Unexpected error - {str(e)}"
