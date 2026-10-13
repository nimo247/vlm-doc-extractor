from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import fitz
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 20 * 1024 * 1024
MAX_PAGES = 8
MAX_PIXELS = 20_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


@dataclass
class InputPage:
    index: int
    image: Image.Image
    native_lines: list[tuple[str, tuple[float, float, float, float]]]

    def png(self) -> bytes:
        stream = BytesIO()
        self.image.save(stream, format="PNG")
        return stream.getvalue()


def load_pages(data: bytes, max_edge: int = 1600) -> list[InputPage]:
    if not data or len(data) > MAX_BYTES:
        raise ValueError("Upload a nonempty file smaller than 20 MB")
    if not 512 <= max_edge <= 2400:
        raise ValueError("max_edge must be between 512 and 2400")
    if data.startswith(b"%PDF-"):
        with fitz.open(stream=data, filetype="pdf") as pdf:
            if pdf.needs_pass:
                raise ValueError("Password-protected PDFs are not supported")
            if not 1 <= len(pdf) <= MAX_PAGES:
                raise ValueError("Upload a PDF with one to eight pages")
            result = []
            for index, page in enumerate(pdf):
                w, h = page.rect.width, page.rect.height
                scale = max_edge / max(w, h)
                pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                lines = []
                for block in page.get_text("dict", sort=True)["blocks"]:
                    for line in block.get("lines", []):
                        parts = []
                        previous = None
                        for span in line["spans"]:
                            if previous is not None and span["bbox"][0] - previous > w * .018:
                                parts.append(" | ")
                            parts.append(span["text"])
                            previous = span["bbox"][2]
                        text = "".join(parts).strip()
                        box = line["bbox"]
                        if text:
                            lines.append((text, (box[0]/w, box[1]/h, box[2]/w, box[3]/h)))
                result.append(InputPage(index, image, lines))
            return result
    try:
        with Image.open(BytesIO(data)) as raw:
            if raw.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError("Supported inputs: PDF, PNG, JPEG, WEBP")
            if raw.width * raw.height > MAX_PIXELS:
                raise ValueError("Image exceeds the 20-megapixel limit")
            image = ImageOps.exif_transpose(raw).convert("RGB")
            image.thumbnail((max_edge, max_edge))
            return [InputPage(0, image, [])]
    except (UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("Unsupported or oversized image") from exc
