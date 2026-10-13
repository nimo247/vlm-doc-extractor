from __future__ import annotations

import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Box(StrictModel):
    x0: float = Field(ge=0, le=1)
    y0: float = Field(ge=0, le=1)
    x1: float = Field(ge=0, le=1)
    y1: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def ordered(self):
        if self.x1 <= self.x0 or self.y1 <= self.y0:
            raise ValueError("Evidence boxes must have positive width and height")
        return self


class Block(StrictModel):
    id: str = Field(min_length=1)
    type: Literal["heading", "paragraph", "table", "list"]
    bbox: Box
    text: str = ""
    rows: list[list[str]] = Field(default_factory=list)
    level: int = Field(default=2, ge=1, le=6)

    @model_validator(mode="after")
    def table_shape(self):
        if self.type == "table":
            if not self.rows or not self.rows[0]:
                raise ValueError("Tables require at least one nonempty row")
            if any(len(row) != len(self.rows[0]) for row in self.rows):
                raise ValueError("Tables must be rectangular; use empty strings for blank cells")
        elif self.rows:
            raise ValueError("Only table blocks may contain rows")
        return self

    def content(self) -> str:
        return "\n".join(" | ".join(r) for r in self.rows) if self.type == "table" else self.text


class Page(StrictModel):
    index: int = Field(ge=0)
    blocks: list[Block]


class Evidence(StrictModel):
    page_index: int = Field(ge=0)
    block_id: str
    quote: str = Field(min_length=1)


class ExtractedField(StrictModel):
    name: str = Field(min_length=1)
    value: str | None
    evidence: list[Evidence] = Field(default_factory=list)
    reason: str | None = None

    @model_validator(mode="after")
    def require_support(self):
        if self.value is None:
            if not self.reason or self.evidence:
                raise ValueError("Abstentions require a reason and no evidence")
        elif not self.value.strip() or not self.evidence or self.reason is not None:
            raise ValueError("Nonempty extracted values require evidence and no abstention reason")
        return self


class Document(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    document_type: Literal["invoice", "purchase_order", "receipt", "other"]
    pages: list[Page] = Field(min_length=1)
    fields: list[ExtractedField] = Field(default_factory=list)

    @model_validator(mode="after")
    def references(self):
        if [p.index for p in self.pages] != list(range(len(self.pages))):
            raise ValueError("Pages must be complete and ordered, starting at index zero")
        if len({f.name for f in self.fields}) != len(self.fields):
            raise ValueError("Field names must be unique")
        refs = {}
        for page in self.pages:
            for block in page.blocks:
                key = (page.index, block.id)
                if key in refs:
                    raise ValueError("Block IDs must be unique within each page")
                refs[key] = block
        for field in self.fields:
            for ev in field.evidence:
                block = refs.get((ev.page_index, ev.block_id))
                if block is None or normalized(ev.quote) not in normalized(block.content()):
                    raise ValueError("Evidence must quote a referenced block")
            if field.value is not None and not any(normalized(field.value) in normalized(e.quote) for e in field.evidence):
                raise ValueError("Extracted value must appear in at least one evidence quote")
        return self


def markdown(doc: Document) -> str:
    """Render one canonical JSON representation; never ask a second model to rewrite it."""
    def escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")
    output = []
    for page in doc.pages:
        if len(doc.pages) > 1:
            output.append(f"<!-- Page {page.index + 1} -->")
        for block in page.blocks:
            if block.type == "table":
                output.append("| " + " | ".join(escape(c) for c in block.rows[0]) + " |")
                output.append("| " + " | ".join("---" for _ in block.rows[0]) + " |")
                output.extend("| " + " | ".join(escape(c) for c in row) + " |" for row in block.rows[1:])
            elif block.type == "heading":
                output.append("#" * block.level + " " + block.text)
            elif block.type == "list":
                output.extend("- " + line for line in block.text.splitlines())
            else:
                output.append(block.text)
            output.append("")
    return "\n".join(output).strip() + "\n"
