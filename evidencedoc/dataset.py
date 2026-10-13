import hashlib
import json
from pathlib import Path
from .schema import Document


def records(path: str | Path) -> list[dict]:
    source = Path(path)
    return [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]


def audit(path: str | Path) -> dict:
    rows = records(path)
    ids, groups, hashes = set(), {}, {}
    counts = {}
    for row in rows:
        if row["id"] in ids:
            raise ValueError("Duplicate record ID: " + row["id"])
        ids.add(row["id"])
        split = row["split"]
        if split not in {"train","validation","test"}:
            raise ValueError("Invalid split")
        counts[split] = counts.get(split,0)+1
        for group in [row["group_id"], "source:" + row.get("source_id",row["id"])]:
            if group in groups and groups[group] != split:
                raise ValueError("Group or original-source leakage across splits: " + group)
            groups[group] = split
        image = Path(row["image_path"])
        digest = hashlib.sha256(image.read_bytes()).hexdigest()
        if digest in hashes and hashes[digest] != split:
            raise ValueError("Duplicate image bytes across splits")
        hashes[digest] = split
        doc = Document.model_validate_json(Path(row["label_path"]).read_text(encoding="utf-8"))
        if len(doc.pages)!=1:
            raise ValueError("Training manifests currently support single-page examples")
    return {"records":len(rows),"splits":counts,"status":"passed","checks":["unique IDs","group/source isolation","image hashes","schema and evidence references"]}
