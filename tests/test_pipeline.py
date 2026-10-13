from io import BytesIO
import json
from pathlib import Path
import shutil
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError
from evidencedoc.app import app
from evidencedoc.backends import parse_model_json
from evidencedoc.dataset import audit
from evidencedoc.ingest import load_pages
from evidencedoc.metrics import score,summarize
from evidencedoc.pipeline import parse
from evidencedoc.schema import Document,markdown
from scripts.generate_data import build


@pytest.fixture
def sample():return build(0,0)


def test_native_pdf_roundtrip_and_table(sample):
    pdf,_,gold=sample
    result=parse(pdf)
    doc=Document.model_validate(result["document"])
    assert {f.name:f.value for f in doc.fields}=={f.name:f.value for f in gold.fields}
    assert any(b.type=="table" for b in doc.pages[0].blocks)
    assert "| Description | Qty | Unit price | Amount |" in result["markdown"]
    assert result["metadata"]["page_routes"]==["pdf-text"]
    assert result["previews"][0].startswith("data:image/png;base64,")


@pytest.mark.skipif(not shutil.which("tesseract"),reason="Tesseract not installed")
def test_real_ocr_on_rendered_scan(sample):
    _,png,_=sample
    result=parse(png,"ocr")
    fields={f["name"]:f["value"] for f in result["document"]["fields"]}
    assert fields["invoice_number"]=="INV-00000"
    assert result["metadata"]["page_routes"]==["tesseract"]


def test_evidence_cannot_point_to_missing_or_wrong_block(sample):
    payload=sample[2].model_dump()
    payload["fields"][0]["evidence"][0]["quote"]="Fabricated vendor"
    with pytest.raises(ValidationError):Document.model_validate(payload)
    payload=sample[2].model_dump()
    payload["fields"][0]["evidence"][0]["block_id"]="missing"
    with pytest.raises(ValidationError):Document.model_validate(payload)


def test_empty_value_and_abstention_rules(sample):
    payload=sample[2].model_dump()
    payload["fields"][0]["value"]=""
    with pytest.raises(ValidationError):Document.model_validate(payload)
    payload=sample[2].model_dump()
    payload["fields"][0]={"name":"vendor","value":None,"evidence":[],"reason":None}
    with pytest.raises(ValidationError):Document.model_validate(payload)


def test_pages_and_rectangle_constraints(sample):
    payload=sample[2].model_dump()
    payload["pages"][0]["index"]=1
    with pytest.raises(ValidationError):Document.model_validate(payload)
    payload=sample[2].model_dump()
    table=next(b for b in payload["pages"][0]["blocks"] if b["type"]=="table")
    table["rows"][1].append("extra")
    with pytest.raises(ValidationError):Document.model_validate(payload)


def test_markdown_escapes_table_delimiters(sample):
    payload=sample[2].model_dump()
    table=next(b for b in payload["pages"][0]["blocks"] if b["type"]=="table")
    table["rows"][1][0]="Sensors | modules"
    assert "Sensors \\| modules" in markdown(Document.model_validate(payload))


def test_perfect_and_missing_prediction_metrics(sample):
    gold=sample[2]
    perfect=summarize(score(gold,gold))
    assert perfect["field_accuracy"]==1
    assert perfect["table_cell_accuracy"]==1
    assert perfect["character_error_rate"]==0
    missing=summarize(score(gold,None))
    assert missing["field_accuracy"]==0
    assert missing["table_cell_accuracy"]==0
    assert missing["emitted_field_accuracy"] is None
    assert missing["reading_order_pair_accuracy"] is None


def test_wrong_field_can_have_text_support_without_being_correct(sample):
    payload=sample[2].model_dump()
    vendor=payload["fields"][0]
    vendor["value"]="Vendor"
    pred=Document.model_validate(payload)
    report=summarize(score(sample[2],pred))
    assert report["field_accuracy"]<1
    assert report["unsupported_literal_value_rate"]==0


def test_leakage_audit_detects_group_and_duplicate_bytes(tmp_path,sample):
    _,png,gold=sample
    image=tmp_path/"page.png";image.write_bytes(png)
    label=tmp_path/"label.json";label.write_text(gold.model_dump_json())
    manifest=tmp_path/"manifest.jsonl"
    rows=[{"id":"a","group_id":"one","split":"train","image_path":str(image),"label_path":str(label)},{"id":"b","group_id":"one","split":"test","image_path":str(image),"label_path":str(label)}]
    manifest.write_text("\n".join(json.dumps(r) for r in rows))
    with pytest.raises(ValueError,match="leakage"):audit(manifest)
    rows[1]["group_id"]="two"
    manifest.write_text("\n".join(json.dumps(r) for r in rows))
    with pytest.raises(ValueError,match="Duplicate image"):audit(manifest)


def test_upload_api_and_invalid_file(sample):
    client=TestClient(app)
    response=client.post("/api/parse",files={"file":("test.pdf",sample[0],"application/pdf")})
    assert response.status_code==200
    assert response.json()["document"]["document_type"]=="invoice"
    response=client.post("/api/parse",files={"file":("bad.png",b"invalid","image/png")})
    assert response.status_code==422
    assert client.get("/").status_code==200
    assert client.get("/api/samples/secret.txt").status_code==404


def test_vlm_missing_config_and_untrusted_json(sample,monkeypatch):
    monkeypatch.delenv("EVIDENCEDOC_VLM_URL",raising=False)
    with pytest.raises(RuntimeError,match="EVIDENCEDOC_VLM_URL"):parse(sample[1],"vlm")
    doc=parse_model_json("```json\n"+sample[2].model_dump_json()+"\n```")
    assert doc.document_type=="invoice"
    with pytest.raises(json.JSONDecodeError):parse_model_json("Here is a summary.")


def test_image_limit_and_resolution(sample):
    with pytest.raises(ValueError):load_pages(b"")
    with pytest.raises(ValueError):load_pages(sample[1],max_edge=32)
    stream=BytesIO();Image.new("RGB",(640,480)).save(stream,format="PNG")
    assert load_pages(stream.getvalue())[0].image.size==(640,480)


def test_vlm_request_and_page_omission_handling(sample,monkeypatch):
    import httpx
    import evidencedoc.backends as backends
    monkeypatch.setenv("EVIDENCEDOC_VLM_URL","http://localhost:8001/v1")
    captured={}
    def response(url,**kwargs):
        captured.update(kwargs["json"])
        return httpx.Response(200,request=httpx.Request("POST",url),json={"choices":[{"finish_reason":"stop","message":{"content":sample[2].model_dump_json()}}],"usage":{"completion_tokens":100}})
    monkeypatch.setattr(backends.httpx,"post",response)
    result=parse(sample[1],"vlm")
    assert captured["temperature"]==0
    assert captured["messages"][1]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert result["metadata"]["backend"]=="vlm"
    def truncated(url,**kwargs):
        return httpx.Response(200,request=httpx.Request("POST",url),json={"choices":[{"finish_reason":"length","message":{"content":"{}"}}]})
    monkeypatch.setattr(backends.httpx,"post",truncated)
    with pytest.raises(ValueError,match="truncated"):parse(sample[1],"vlm")
