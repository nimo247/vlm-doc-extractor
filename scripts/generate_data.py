"""Generate original, labeled business documents; these are development data, not real-world evidence."""
import argparse
from io import BytesIO
import json
from pathlib import Path
import random
import fitz
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth
from evidencedoc.schema import Block, Document, Evidence, ExtractedField, Page
from evidencedoc.backends import box
from evidencedoc.prompt import FIELD_NAMES


def build(index: int, template: int):
    rng = random.Random(index + 1907)
    width, height = 800, 1100
    margin = [55, 70, 45, 85, 60, 95][template]
    start = [70, 90, 60, 115, 80, 100][template]
    font = ["Helvetica", "Times-Roman", "Courier", "Helvetica", "Times-Roman", "Helvetica"][template]
    kind = "invoice" if (index // 6 + index) % 2 == 0 else "purchase_order"
    vendor = rng.choice(["Northstar Components", "Veridian Instruments", "Orbit Office Supplies", "Aster Electronics"])
    values = {"vendor":vendor, "invoice_number":f"INV-{index:05d}" if kind == "invoice" else None, "purchase_order_number":f"PO-{index:05d}" if kind == "purchase_order" else None, "issue_date":f"2026-10-{1 + index % 28:02d}", "currency":"INR"}
    price1, price2 = rng.randint(100,400), rng.randint(80,200)
    values["total"] = None if index % 11 == 10 else f"{3*price1 + 2*price2}.00"
    stream = BytesIO()
    pdf = canvas.Canvas(stream, pagesize=(width,height))
    pdf.setTitle("EvidenceDoc generated development sample")
    blocks = []
    evidence = {}
    y = start

    def line(text, type="paragraph", size=16, rows=None):
        nonlocal y
        if rows:
            top = y
            for row in rows:
                draw(" | ".join(row), y, 13)
                y += 29
            maximum = max(stringWidth(" | ".join(row), font, 13) for row in rows)
            b = Block(id=f"b{len(blocks)}",type="table",rows=rows,bbox=box((margin/width,(top-5)/height,(margin+maximum+3)/width,(y-10)/height)))
        else:
            draw(text,y,size)
            maximum = stringWidth(text,font,size)
            b = Block(id=f"b{len(blocks)}",type=type,text=text,level=1 if type=="heading" else 2,bbox=box((margin/width,(y-5)/height,(margin+maximum+3)/width,(y+size+5)/height)))
            y += 37 if type != "heading" else 58
        blocks.append(b)
        return b

    def draw(text, top, size):
        pdf.setFont(font,size)
        pdf.setFillColorRGB(.12,.18,.15)
        pdf.drawString(margin,height-top-size,text)

    line("INVOICE" if kind=="invoice" else "PURCHASE ORDER", "heading", 30)
    labels = {"vendor":"Vendor", "invoice_number":"Invoice number", "purchase_order_number":"Purchase order number", "issue_date":"Issue date", "currency":"Currency"}
    order = ["vendor", "invoice_number", "purchase_order_number", "issue_date", "currency"]
    if template in {1,4}:
        order = ["issue_date", "currency", "vendor", "purchase_order_number", "invoice_number"]
    for key in order:
        if values[key] is not None:
            b = line(f"{labels[key]}: {values[key]}")
            evidence[key] = Evidence(page_index=0,block_id=b.id,quote=b.text)
    y += 25
    line("", rows=[["Description","Qty","Unit price","Amount"],["Sensor modules","3",f"{price1}.00",f"{3*price1}.00"],["Cable assemblies","2",f"{price2}.00",f"{2*price2}.00"]])
    y += 25
    if values["total"] is not None:
        b = line("Total: " + values["total"])
        evidence["total"] = Evidence(page_index=0,block_id=b.id,quote=b.text)
    line("Payment terms: payable within 30 days.")
    line("Generated sample. No real customer information.")
    pdf.save()
    data = stream.getvalue()
    fields = [ExtractedField(name=key,value=values[key],evidence=[evidence[key]]) if values[key] is not None else ExtractedField(name=key,value=None,reason="Not present in this document") for key in FIELD_NAMES]
    document = Document(document_type=kind,pages=[Page(index=0,blocks=blocks)],fields=fields)
    with fitz.open(stream=data,filetype="pdf") as rendered:
        png = rendered[0].get_pixmap(alpha=False).tobytes("png")
    return data,png,document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=Path("data/generated"))
    parser.add_argument("--count",type=int,default=60)
    args = parser.parse_args()
    if args.count < 6:
        parser.error("Generate at least six documents so every split is represented")
    args.output.mkdir(parents=True,exist_ok=True)
    samples = Path("samples"); samples.mkdir(exist_ok=True)
    records = []
    for index in range(args.count):
        template = index % 6
        split = "train" if template < 4 else "validation" if template==4 else "test"
        stem = f"document_{index:04d}"
        pdf,png,doc = build(index,template)
        image_path = args.output / (stem + ".png")
        label_path = args.output / (stem + ".json")
        image_path.write_bytes(png)
        label_path.write_text(doc.model_dump_json(indent=2),encoding="utf-8")
        records.append({"id":stem,"group_id":f"template-{template}","source_id":stem,"split":split,"image_path":image_path.as_posix(),"label_path":label_path.as_posix(),"source_kind":"synthetic-rendered"})
        if index==0:
            (samples / "sample_invoice.pdf").write_bytes(pdf)
            (samples / "sample_invoice.png").write_bytes(png)
            (samples / "sample_invoice.gold.json").write_text(doc.model_dump_json(indent=2),encoding="utf-8")
        if index==1:
            (samples / "sample_purchase_order.pdf").write_bytes(pdf)
    manifest = args.output / "manifest.jsonl"
    manifest.write_text("\n".join(json.dumps(r) for r in records)+"\n",encoding="utf-8")
    for split in ["train","validation","test"]:
        (args.output / f"{split}.jsonl").write_text("\n".join(json.dumps(r) for r in records if r["split"]==split)+"\n",encoding="utf-8")
    print(json.dumps({"manifest":str(manifest),"documents":args.count,"split_by":"template family","warning":"Synthetic development data; collect an independently labeled real-document test set"},indent=2))


if __name__=="__main__":
    main()
