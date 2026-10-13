"""Evaluate every selected manifest record; failures stay in the quality denominator."""
import argparse
import json
from pathlib import Path
from evidencedoc.dataset import audit, records
from evidencedoc.metrics import score, summarize
from evidencedoc.pipeline import parse
from evidencedoc.schema import Document


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest",type=Path,default=Path("data/generated/manifest.jsonl"))
    parser.add_argument("--split",choices=["train","validation","test"],default="test")
    parser.add_argument("--backend",choices=["baseline","ocr","vlm"],default="ocr")
    parser.add_argument("--output",type=Path,default=Path("outputs/evaluation"))
    parser.add_argument("--max-edge",type=int,default=1600)
    args=parser.parse_args()
    audit(args.manifest)
    rows=[r for r in records(args.manifest) if r["split"]==args.split]
    if not rows:raise ValueError("Requested split is empty")
    args.output.mkdir(parents=True,exist_ok=True)
    counts={}; details=[]; failures=0
    for row in rows:
        gold=Document.model_validate_json(Path(row["label_path"]).read_text())
        pred=None;error=None;metadata=None
        try:
            result=parse(Path(row["image_path"]).read_bytes(),args.backend,args.max_edge)
            pred=Document.model_validate(result["document"])
            metadata=result["metadata"]
            safe_id=str(row["id"])
            if Path(safe_id).name!=safe_id:raise ValueError("Record IDs must be simple filenames")
            (args.output / (safe_id+".prediction.json")).write_text(json.dumps(result["document"],indent=2))
        except Exception as exc:
            failures+=1;error=f"{type(exc).__name__}: {str(exc)[:250]}"
        raw=score(gold,pred)
        for key,value in raw.items():counts[key]=counts.get(key,0)+value
        details.append({"id":row["id"],"group_id":row["group_id"],"source_kind":row.get("source_kind","unspecified"),"error":error,"metadata":metadata,**summarize(raw)})
        print(row["id"],"failed" if error else "completed")
    report={"backend":args.backend,"split":args.split,"documents":len(rows),"schema_valid_document_rate":(len(rows)-failures)/len(rows),"failure_count":failures,"source_kinds":sorted({r.get("source_kind","unspecified") for r in rows}),"warning":"Synthetic-only scores do not establish real-world performance","metrics":summarize(counts),"documents_detail":details}
    (args.output / "report.json").write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!="documents_detail"},indent=2))


if __name__=="__main__":main()
