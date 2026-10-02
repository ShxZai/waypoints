"""Waypoints local app.

Run with run.bat (or: python -m uvicorn app.main:app --host 127.0.0.1 --port 8000),
then open http://127.0.0.1:8000
"""
import asyncio
import json
import sys
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from . import config
from .runner import run_python
from .store import Store
from .teacher import AskRequest, TeacherError, make_teacher

app = FastAPI(title="Waypoints")
store = Store(config.DB_PATH)
teacher = make_teacher()

ALLOWED_HOSTS = {f"127.0.0.1:{config.PORT}", f"localhost:{config.PORT}"}


@app.middleware("http")
async def local_only(request: Request, call_next):
    # The API can run Python on this computer, so only this app's own page may
    # call it: the Host must be local (blocks DNS-rebinding tricks) and every
    # write needs a custom header, which other websites can't send without a
    # CORS preflight this server never approves.
    if request.headers.get("host", "") not in ALLOWED_HOSTS:
        return JSONResponse({"error": "forbidden host"}, status_code=403)
    if request.url.path.startswith("/api/") and request.method != "GET" and request.headers.get("x-waypoints") != "1":
        return JSONResponse({"error": "missing x-waypoints header"}, status_code=403)
    return await call_next(request)


# ---------- storage ----------
@app.get("/api/docs/{collection}")
def list_docs(collection: str):
    try:
        return {"docs": store.list(collection)}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.put("/api/docs/{collection}/{doc_id}")
def put_doc(collection: str, doc_id: str, data: dict = Body(...)):
    try:
        store.put(collection, doc_id, data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


# ---------- session-log notes (plain .md files) ----------
@app.post("/api/notes/{name}")
def write_note(name: str, body: dict = Body(...)):
    try:
        Store.check(name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    config.NOTES_DIR.mkdir(parents=True, exist_ok=True)
    path = config.NOTES_DIR / f"{name}.md"
    path.write_text(str(body.get("markdown", "")), encoding="utf-8")
    return {"ok": True, "path": str(path)}


# ---------- running Python ----------
@app.post("/api/run")
def run(body: dict = Body(...)):
    code = str(body.get("code", ""))
    if len(code) > 200_000:
        raise HTTPException(413, "code too long")
    return run_python(code)


# ---------- status ----------
@app.get("/api/status")
async def status():
    info = await run_in_threadpool(teacher.status)
    return {
        "teacher": teacher.name,
        "python": sys.version.split()[0],
        "notes_dir": str(config.NOTES_DIR),
        **info,
        "limits": getattr(teacher, "last_limits", None),
    }


@app.get("/api/limits")
def limits():
    # Subscription usage windows, as last reported by Claude Code (no subprocess).
    return {"limits": getattr(teacher, "last_limits", None)}


# ---------- the teacher ----------
@app.post("/api/ask")
async def ask(body: dict = Body(...)):
    req = AskRequest(
        input=body.get("input", ""),
        json=bool(body.get("json")),
        schema=body.get("schema") if isinstance(body.get("schema"), dict) else None,
        tier=str(body.get("tier") or "default"),
        web=bool(body.get("web")),
    )
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def emit(event):
        loop.call_soon_threadsafe(queue.put_nowait, event)

    def work():
        try:
            out = teacher.ask(req, emit)
            u = out.get("usage") or {}
            print(f"teacher: tier={req.tier} web={req.web} json={req.json} models={u.get('models')} "
                  f"seconds={round((u.get('duration_ms') or 0) / 1000, 1)}", flush=True)
            emit({"t": "done", **out})
        except TeacherError as e:
            emit({"t": "error", "code": e.code, "message": e.message, "text": e.text})
        except Exception as e:  # never leave the page waiting
            emit({"t": "error", "code": "upstream_error", "message": f"{type(e).__name__}: {e}"})
        finally:
            emit(None)

    loop.run_in_executor(None, work)

    async def stream():
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield json.dumps(event, ensure_ascii=False) + "\n"
        finally:
            req.cancel.set()  # browser stopped or left: end the Claude call too

    return StreamingResponse(stream(), media_type="application/x-ndjson")


app.mount("/", StaticFiles(directory=Path(config.WEB_DIR), html=True), name="web")
