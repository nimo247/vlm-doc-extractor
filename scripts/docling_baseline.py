"""Optional independent full-document baseline export. Not silently converted into EvidenceDoc metrics."""
import argparse
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file",type=Path)
    parser.add_argument("--output",type=Path,default=Path("outputs/docling"))
    args=parser.parse_args()
    from docling.document_converter import DocumentConverter
    document=DocumentConverter().convert(args.file).document
    args.output.parent.mkdir(parents=True,exist_ok=True)
    document.save_as_json(args.output.with_suffix(".json"))
    args.output.with_suffix(".md").write_text(document.export_to_markdown(),encoding="utf-8")
    print("Exported native Docling JSON and Markdown. Map its schema explicitly before numerical comparison.")


if __name__=="__main__":main()
