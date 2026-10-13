import argparse
import json
from pathlib import Path
from .pipeline import parse
from .dataset import audit


def main():
    parser=argparse.ArgumentParser(prog="evidencedoc")
    sub=parser.add_subparsers(dest="command",required=True)
    parse_cmd=sub.add_parser("parse")
    parse_cmd.add_argument("file",type=Path)
    parse_cmd.add_argument("--backend",choices=["baseline","ocr","vlm"],default="baseline")
    parse_cmd.add_argument("--output",type=Path,default=Path("outputs/document"))
    parse_cmd.add_argument("--max-edge",type=int,default=1600)
    audit_cmd=sub.add_parser("audit");audit_cmd.add_argument("manifest",type=Path)
    args=parser.parse_args()
    if args.command=="audit":print(json.dumps(audit(args.manifest),indent=2));return
    result=parse(args.file.read_bytes(),args.backend,args.max_edge)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.with_suffix(".json").write_text(json.dumps(result["document"],indent=2),encoding="utf-8")
    args.output.with_suffix(".md").write_text(result["markdown"],encoding="utf-8")
    args.output.with_suffix(".metadata.json").write_text(json.dumps(result["metadata"],indent=2))
    print(json.dumps(result["metadata"],indent=2))


if __name__=="__main__":main()
