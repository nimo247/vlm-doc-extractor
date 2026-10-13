from __future__ import annotations

import base64
import csv
from io import StringIO
import json
import os
import re
import shutil
import subprocess
import tempfile
from urllib.parse import urlsplit
from pathlib import Path
import httpx
from .ingest import InputPage
from .prompt import FIELD_NAMES, system_prompt
from .schema import Block, Box, Document, Evidence, ExtractedField, Page


def box(values) -> Box:
    return Box(**dict(zip(["x0", "y0", "x1", "y1"], [min(1, max(0, float(v))) for v in values])))


def ocr_lines(page: InputPage):
    if not shutil.which("tesseract"):
        raise RuntimeError("Install Tesseract OCR and its English language pack to parse scans")
    with tempfile.TemporaryDirectory(prefix="evidencedoc-") as temp:
        path = Path(temp) / "page.png"
        path.write_bytes(page.png())
        process = subprocess.run(["tesseract", str(path), "stdout", "-l", os.getenv("EVIDENCEDOC_OCR_LANG", "eng"), "--psm", "6", "tsv"], capture_output=True, text=True, timeout=60)
        if process.returncode:
            raise RuntimeError("Tesseract failed; check the configured OCR language pack")
    groups = {}
    for word in csv.DictReader(StringIO(process.stdout), delimiter="\t"):
        if word["level"] != "5" or not word.get("text", "").strip():
            continue
        key = tuple(word[k] for k in ["block_num", "par_num", "line_num"])
        groups.setdefault(key, []).append(word)
    lines = []
    w, h = page.image.size
    for words in groups.values():
        words.sort(key=lambda row: int(row["left"]))
        parts = []
        previous = None
        for word in words:
            left = int(word["left"])
            if previous is not None:
                parts.append(" | " if left - previous > w * .018 else " ")
            parts.append(word["text"])
            previous = left + int(word["width"])
        x0 = min(int(v["left"]) for v in words)
        y0 = min(int(v["top"]) for v in words)
        x1 = max(int(v["left"]) + int(v["width"]) for v in words)
        y1 = max(int(v["top"]) + int(v["height"]) for v in words)
        lines.append(("".join(parts), (x0/w, y0/h, x1/w, y1/h)))
    return sorted(lines, key=lambda item: (item[1][1], item[1][0]))


PATTERNS = {
    "vendor": r"^Vendor\s*:\s*(.+)$",
    "invoice_number": r"^Invoice\s*(?:number|no\.?|#)\s*:\s*(.+)$",
    "purchase_order_number": r"^(?:Purchase order|PO)\s*(?:number|no\.?|#)?\s*:\s*(.+)$",
    "issue_date": r"^(?:Issue date|Date)\s*:\s*(.+)$",
    "total": r"^(?:Grand total|Total)\s*:\s*(.+)$",
    "currency": r"^Currency\s*:\s*(.+)$",
}


def baseline(pages: list[InputPage], force_ocr=False) -> tuple[Document, dict]:
    parsed = []
    routes = []
    for page in pages:
        native = bool(page.native_lines) and not force_ocr
        lines = page.native_lines if native else ocr_lines(page)
        routes.append("pdf-text" if native else "tesseract")
        blocks = []
        i = 0
        while i < len(lines):
            text, coords = lines[i]
            # Conservative rule: only explicit separated rows with a recognized header.
            if text.count("|") >= 2 and re.search(r"description|item|quantity|qty", text, re.I):
                rows = [[c.strip() for c in text.split("|")]]
                end = i + 1
                while end < len(lines) and lines[end][0].count("|") == len(rows[0])-1:
                    rows.append([c.strip() for c in lines[end][0].split("|")])
                    end += 1
                coords = (min(lines[k][1][0] for k in range(i,end)), coords[1], max(lines[k][1][2] for k in range(i,end)), max(lines[k][1][3] for k in range(i,end)))
                blocks.append(Block(id=f"b{len(blocks)}", type="table", bbox=box(coords), rows=rows))
                i = end
            else:
                heading = text.strip().upper() in {"INVOICE", "PURCHASE ORDER", "RECEIPT"}
                blocks.append(Block(id=f"b{len(blocks)}", type="heading" if heading else "paragraph", level=1 if heading else 2, text=text, bbox=box(coords)))
                i += 1
        parsed.append(Page(index=page.index, blocks=blocks))
    fields = []
    for name in FIELD_NAMES:
        matches = []
        for page in parsed:
            for block in page.blocks:
                for line in block.content().splitlines():
                    match = re.match(PATTERNS[name], line.strip(), re.I)
                    if match:
                        matches.append((match.group(1).strip(), Evidence(page_index=page.index, block_id=block.id, quote=line.strip())))
        unique = {value for value, _ in matches}
        if len(unique) == 1:
            fields.append(ExtractedField(name=name, value=matches[0][0], evidence=[matches[0][1]]))
        else:
            fields.append(ExtractedField(name=name, value=None, reason="Conflicting values" if matches else "No explicit labeled value found"))
    all_text = "\n".join(b.content() for p in parsed for b in p.blocks).casefold()
    kind = "purchase_order" if "purchase order" in all_text else "invoice" if "invoice" in all_text else "receipt" if "receipt" in all_text else "other"
    return Document(document_type=kind, pages=parsed, fields=fields), {"backend":"ocr" if force_ocr else "baseline", "page_routes": routes, "model": None}


def parse_model_json(content: str) -> Document:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    return Document.model_validate(json.loads(content))


def vlm(pages: list[InputPage]) -> tuple[Document, dict]:
    url = os.getenv("EVIDENCEDOC_VLM_URL")
    if not url:
        raise RuntimeError("Set EVIDENCEDOC_VLM_URL to an OpenAI-compatible vision model server")
    model = os.getenv("EVIDENCEDOC_MODEL", "Qwen/Qwen3-VL-2B-Instruct")
    images = [{"type":"image_url", "image_url":{"url":"data:image/png;base64," + base64.b64encode(p.png()).decode()}} for p in pages]
    payload = {"model":model, "messages":[{"role":"system","content":system_prompt()}, {"role":"user","content":[{"type":"text","text":f"Parse these {len(pages)} page images in order."}, *images]}], "temperature":0, "max_tokens":int(os.getenv("EVIDENCEDOC_MAX_TOKENS", "8192"))}
    key = os.getenv("EVIDENCEDOC_API_KEY", "")
    headers = {"Authorization":"Bearer " + key} if key else {}
    try:
        response = httpx.post(url.rstrip("/") + "/chat/completions", json=payload, headers=headers, timeout=180, trust_env=urlsplit(url).hostname not in {"localhost","127.0.0.1","::1"})
        response.raise_for_status()
        result = response.json()
    except httpx.HTTPError as exc:
        raise RuntimeError("The VLM server request failed; check its availability, model, and credentials") from exc
    choice = result["choices"][0]
    if choice.get("finish_reason") == "length":
        raise ValueError("VLM output was truncated; reduce pages or increase the generation budget")
    document = parse_model_json(choice["message"]["content"])
    if len(document.pages) != len(pages):
        raise ValueError("VLM omitted or added pages")
    if {f.name for f in document.fields} != set(FIELD_NAMES):
        raise ValueError("VLM must return every required field, with null for missing values")
    return document, {"backend":"vlm", "model":model, "usage":result.get("usage", {}), "page_routes":["vision-model"] * len(pages)}
