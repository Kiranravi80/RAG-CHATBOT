# AI Database Assistant (Groq + RAG + FAISS + FastAPI + MySQL)

This web app accepts natural-language database questions, converts them to SQL, runs SQL on MySQL, and returns:
- generated SQL
- tabular output
- concise summary
- graph (only when user explicitly asks)

It now includes:
- session-based query history
- memory for follow-up questions (multi-turn context)
- ChatGPT-style chat UI
- voice-to-text query input

## Stack
- FastAPI (API + UI serving)
- Groq API (NL -> SQL, result summarization)
- FAISS (RAG retrieval over schema/domain notes)
- MySQL
- HTML/CSS/JavaScript + Chart.js + Web Speech API

## Project Structure

backend/
- app/main.py
- app/config.py
- app/database.py
- app/rag.py
- app/llm.py
- app/memory.py
- app/services/query_service.py
- app/templates/index.html
- app/static/styles.css
- app/static/app.js
- knowledge/domain_notes.txt
- .env.example
- requirements.txt

## Setup

1. Create virtual environment and install dependencies:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Configure env file:

```powershell
Copy-Item .env.example .env
```

Fill real values in `.env`:
- `GROQ_API_KEY`
- `MYSQL_*`

3. Run the app:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

4. Open:
- http://127.0.0.1:8000

## API
- `POST /api/query` body: `{ "question": "...", "session_id": "..." }`
- `GET /api/history/{session_id}`
- `DELETE /api/history/{session_id}`

## Notes
- SQL safety guard blocks destructive statements like DROP/TRUNCATE/ALTER/GRANT/REVOKE.
- Only single statement execution is allowed.
- Update `knowledge/domain_notes.txt` with business rules to improve SQL quality.
- Voice input requires a browser that supports `SpeechRecognition`/`webkitSpeechRecognition` and microphone permission.
