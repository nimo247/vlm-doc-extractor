import time
import base64
from .backends import baseline, vlm
from .ingest import load_pages
from .schema import markdown


def parse(data: bytes, backend: str = "baseline", max_edge: int = 1600) -> dict:
    start = time.perf_counter()
    pages = load_pages(data, max_edge=max_edge)
    ingest_end = time.perf_counter()
    if backend in {"baseline", "ocr"}:
        document, metadata = baseline(pages, force_ocr=backend == "ocr")
    elif backend == "vlm":
        document, metadata = vlm(pages)
    else:
        raise ValueError("Unknown backend")
    end = time.perf_counter()
    metadata.update({"page_count":len(pages), "max_edge":max_edge, "preprocessing_ms":round((ingest_end-start)*1000, 2), "parsing_ms":round((end-ingest_end)*1000, 2), "total_ms":round((end-start)*1000, 2), "fine_tuning_status":"not established by this client", "evidence_check":"reference/quote consistency only; visual grounding needs labeled evaluation"})
    return {"document":document.model_dump(), "markdown":markdown(document), "metadata":metadata, "previews":["data:image/png;base64," + base64.b64encode(p.png()).decode() for p in pages]}
