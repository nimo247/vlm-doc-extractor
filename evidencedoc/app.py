import os
from pathlib import Path
import shutil
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.concurrency import run_in_threadpool
from .ingest import MAX_BYTES
from .pipeline import parse
from .schema import Document

ROOT = Path(__file__).parent
SAMPLES = ROOT.parent / "samples"
app = FastAPI(title="EvidenceDoc", version="0.1.0")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/")
def index():
    return FileResponse(ROOT / "static/index.html")


@app.get("/api/status")
def status():
    return {"tesseract_available":bool(shutil.which("tesseract")), "vlm_configured":bool(os.getenv("EVIDENCEDOC_VLM_URL")), "model":os.getenv("EVIDENCEDOC_MODEL", "Qwen/Qwen3-VL-2B-Instruct"), "trained_checkpoint_included":False}


@app.get("/api/schema")
def schema():
    return Document.model_json_schema()


@app.get("/api/samples/{name}")
def sample(name: str):
    if name not in {"sample_invoice.pdf", "sample_invoice.png", "sample_purchase_order.pdf"}:
        raise HTTPException(404, "Sample not found")
    path = SAMPLES / name
    if not path.is_file():
        raise HTTPException(404, "Run scripts.generate_data to create sample documents")
    return FileResponse(path)


@app.post("/api/parse")
async def parse_upload(file: UploadFile = File(...), backend: str = Query("baseline", pattern="^(baseline|ocr|vlm)$"), max_edge: int = Query(1600, ge=512, le=2400)):
    data = await file.read(MAX_BYTES + 1)
    await file.close()
    try:
        return await run_in_threadpool(parse, data, backend, max_edge)
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, str(exc)[:500]) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(422, "Could not process this document") from exc
