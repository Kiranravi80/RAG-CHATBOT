from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.models import HistoryResponse, QueryRequest, QueryResponse, SessionSummary, SessionsResponse
from app.services.query_service import QueryService


app = FastAPI(title="AI Database Assistant", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

base_dir = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(base_dir / "static")), name="static")
templates = Jinja2Templates(directory=str(base_dir / "templates"))
service = QueryService()


@app.on_event("startup")
def startup() -> None:
    knowledge_file = str(base_dir.parent / "knowledge" / "domain_notes.txt")
    service.startup(knowledge_file)


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/query", response_model=QueryResponse)
def query_db(payload: QueryRequest):
    try:
        return service.run(payload.session_id, payload.question)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/history/{session_id}", response_model=HistoryResponse)
def history(session_id: str):
    return HistoryResponse(session_id=session_id, items=service.get_history(session_id))


@app.delete("/api/history/{session_id}")
def clear_history(session_id: str) -> dict[str, str]:
    service.clear_history(session_id)
    return {"status": "cleared"}


@app.delete("/api/history")
def clear_all_history() -> dict[str, str]:
    service.clear_all_history()
    return {"status": "all_cleared"}


@app.get("/api/sessions", response_model=SessionsResponse)
def list_sessions():
    summaries = [SessionSummary(**item) for item in service.list_sessions()]
    return SessionsResponse(sessions=summaries)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
