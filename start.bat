@echo off
echo Starting AI Chatbot Server...
call venv\Scripts\activate
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8001
pause
