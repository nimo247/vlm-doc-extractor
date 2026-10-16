# EvidenceDoc

A document parsing workbench and reproducible VLM fine-tuning project. Upload a PDF or image, inspect ordered blocks and tables, extract labeled fields with evidence references, and export canonical JSON or deterministic Markdown.

**Current state:** functioning CPU baselines and application, plus a DocILE extraction/review workspace at `/docile`. The user completed a three-epoch Qwen3-VL-2B LoRA run on 168 pages using a Kaggle T4. Saved predictions from all 40 validation pages were independently replayed on CPU: key-field text F1 is 36.63%, line-item text F1 is 46.01%, and 30/40 outputs pass the schema. An optional OCR box-alignment experiment raises line-item text-and-box F1 from 17.18% to 29.24%. See [the measured comparison](docs/DOCILE_OCR_ALIGNMENT.md) and [review app setup](docs/DOCILE_APP.md). These are custom validation metrics, not official DocILE scores; the 50-page test remains unevaluated. This source archive includes no trained weights or real DocILE pages. Saved-run review, fresh OCR uploads, manual JSON review and exports are connected; the live GPU adapter-service path is implemented and mock-tested, but still requires a real GPU smoke test and deployment. The optional Docling baseline remains unvalidated.

## Run locally

Use Python 3.10+ (3.12 recommended). Open a terminal in the extracted `EvidenceDoc` directory.

```bash
python -m venv .venv
# Linux / macOS
source .venv/bin/activate
# Windows PowerShell instead:
# .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m scripts.generate_data --count 60
python -m uvicorn evidencedoc.app:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. Click a sample, then **Parse document**. Fields link to the parsed page region. The Structure tab displays ordered blocks and tables. Select Markdown before downloading a `.md` export; the other tabs download JSON.

Tesseract is required for scanned images. Native PDFs with embedded text work without it.

- Ubuntu / WSL: `sudo apt-get install tesseract-ocr tesseract-ocr-eng`
- macOS with Homebrew: `brew install tesseract`
- Windows: install Tesseract using a Windows distribution linked from its official installation documentation, and put its executable directory on PATH. Restart the terminal after changing PATH.

Docker alternative (CPU application):

```bash
docker build -t evidencedoc .
docker run --rm -p 127.0.0.1:8000:8000 evidencedoc
```

The API reference is at `/docs`. Uploads are processed in memory and temporary OCR files are removed after processing. This local app accepts files up to 20 MB and PDFs of up to eight pages. It has no account system or hosted GPU service.

## What works now

| Component | Behavior |
|---|---|
| `baseline` | Native PDF text extraction; Tesseract fallback for image-only pages |
| `ocr` | Tesseract on every page, followed by conservative label/table rules |
| `vlm` | Real request to a configured OpenAI-compatible vision model; no fabricated fallback |
| Schema | Strict types, sequential pages, unique field names, valid boxes, rectangular tables, evidence reference checks |
| Markdown | Deterministically rendered from the validated document JSON |
| Evaluation | Fields, absent-field false extraction, literal unsupported values, text CER, table cells, block coverage, matched reading-order pairs |
| Training | Qwen3-VL QLoRA recipe; the user's three-epoch T4 run completed; saved validation predictions replayed on CPU |
| Benchmark | Client latency, concurrency, failures, throughput; device memory via an independent NVIDIA sampler |

The CPU parser is intentionally simple. It recognizes explicit `Vendor:`, `Invoice number:`, `Purchase order number:`, `Issue date:`, `Currency:`, and `Total:` labels. It recognizes explicitly separated tables with familiar headers. It is not a learned general document parser. Its weaknesses provide measurable tasks for VLM adaptation.

## Output contract

`GET /api/schema` returns the complete JSON Schema. `POST /api/parse?backend=baseline&max_edge=1600` accepts a multipart `file` and returns `document`, `markdown`, `metadata`, and page `previews`.

```json
{
  "schema_version": "1.0",
  "document_type": "invoice",
  "pages": [{"index": 0, "blocks": [{
    "id": "b0", "type": "paragraph",
    "bbox": {"x0": 0.1, "y0": 0.1, "x1": 0.6, "y1": 0.15},
    "text": "Invoice number: INV-001", "rows": [], "level": 2
  }]}],
  "fields": [{
    "name": "invoice_number", "value": "INV-001", "reason": null,
    "evidence": [{"page_index": 0, "block_id": "b0", "quote": "Invoice number: INV-001"}]
  }]
}
```

The app requires the six configured fields; missing values use `null`, an empty evidence array, and a reason. Coordinates are normalized to the rendered page. First table rows are headers. Merged cells, formulas, handwritten text, advanced multi-column reading order, and cross-page tables are outside the initial contract.

**Evidence validation checks self-consistency, not image truth.** A VLM could invent a block and then quote it. Only independently labeled visual evaluation establishes that a value and region are grounded in the page. The UI therefore says “Evidence linked”, not “Verified”.

## Dataset workflow

```bash
python -m scripts.generate_data --count 60
evidencedoc audit data/generated/manifest.jsonl
python -m scripts.train --dry-run
```

The generator creates original business documents across six rendering/layout families. Four families are training, one validation, and one test. Each family contains invoices and purchase orders as count increases. Every label follows the same JSON schema. Samples use fictitious vendors and no real personal information.

Manifest paths are relative to the project root (or absolute). Run scripts from that root. Example record:

```json
{"id":"real_001","group_id":"vendor-layout-A","source_id":"original-document-001","split":"train","image_path":"data/real/001.png","label_path":"data/real/001.json","source_kind":"human-labeled-real"}
```

`group_id` must identify the vendor/template family; `source_id` must be shared by all augmentations of an original. Auditing rejects IDs, group/source leakage, duplicate image bytes across splits, and invalid labels. Hash checks do not detect near-duplicate scans: manually review them and record their common source IDs.

Generated data are a pipeline smoke test. Do not put their scores on a resume as real-world accuracy. Next collect roughly 50 independently checked pages for development, then a separate locked real-document test set. Ensure permitted use of every document. Public receipts such as CORD can help with receipt extraction, but do not provide all full-page structure labels this project needs. Inspect and annotate the missing labels rather than silently treating model outputs as ground truth.

## Evaluate quality

```bash
python -m scripts.evaluate --backend ocr --split test --output outputs/ocr
python -m scripts.evaluate --backend vlm --split test --output outputs/base-vlm
# After training, change EVIDENCEDOC_MODEL / server to the adapted model:
python -m scripts.evaluate --backend vlm --split test --output outputs/tuned-vlm
```

Use the same images, resolution, prompt, output budget, and model size when comparing the base and fine-tuned models. Failed requests remain in the quality denominator. Document-level success includes parsing and schema validation, so failure details must be inspected before interpreting its rate. Empty metric denominators yield `null`, not perfect scores.

Metric definitions and limitations are in `docs/EVALUATION.md`. The optional Docling command exports its own native representation; schema normalization is an explicit follow-up task:

```bash
python -m pip install -e ".[docling]"
python -m scripts.docling_baseline samples/sample_invoice.pdf
```

## Prepare the labeled DocILE extraction task

After obtaining dataset access and downloading the annotated train/validation archive into `data/docile`, follow [docs/DOCILE.md](docs/DOCILE.md). The CPU converter packages a compact English single-page subset with layout/source-separated splits, original field text and boxes, and grouped line items:

```bash
python -m scripts.prepare_docile --dataset data/docile --train-limit 200 --validation-limit 40 --test-limit 50
python -m scripts.train --config configs/docile-t4.yaml --dry-run
```

This uses a separate DocILE extraction schema and task prompt. It produces JSON and an extraction-summary Markdown table; it does not turn partial field labels into full-page transcription gold. The original application's full-page `vlm` backend requires its original `Document` schema. Keep the two tasks explicit when loading checkpoints and reporting results.

## Fine-tune on a CUDA GPU

Your laptop can run the app and prepare data. This QLoRA training path needs an NVIDIA GPU with enough VRAM for the chosen image and output lengths. No fixed fit or cost is promised; start with a short run. Training dependencies are separate so ordinary app setup does not install Torch or download model weights.

```bash
python -m pip install -e ".[train]"
python -m scripts.train --config configs/qlora.yaml --max-steps 2
# Inspect loss, masks, saved adapter, and GPU usage, then:
python -m scripts.train --config configs/qlora.yaml
```

The recipe uses NF4 four-bit weights, LoRA on language projection modules, a frozen vision encoder, completion/assistant loss, and no sequence truncation that could remove image tokens. It runs validation loss on the validation partition; test data are never passed to the trainer. Image pixels are bounded by the processor. Output lengths can still be large, so inspect memory before scaling.

For a guided GPU session, open `notebooks/finetune_colab.ipynb` in Colab and upload the project ZIP. It installs the separate training dependencies and begins with two training steps using `configs/t4-smoke.yaml`. This notebook is supplied without executed GPU outputs.

The current assistant-only VLM masking path follows TRL's documented requirement for Transformers >=5.18. The patched T4 path completed a user-reported two-step synthetic smoke run; the builder has not independently executed GPU training. If dependency APIs change, pin the versions that pass your smoke run and retain them in the recorded run metadata. After training, `run_metadata.json` records versions, configuration, loss metrics, GPU identity, and peak Torch allocated memory. Exporting an adapter alone is not evidence of a quality improvement.

## Serve the original or trained model

Install vLLM on a suitable separate GPU environment following its hardware-specific documentation. Its port is 8001; the CPU app uses 8000.

```bash
vllm serve Qwen/Qwen3-VL-2B-Instruct --host 127.0.0.1 --port 8001 --max-model-len 16384 --limit-mm-per-prompt '{"image":8}'
```

Set the app environment **before starting Uvicorn**:

```bash
export EVIDENCEDOC_VLM_URL=http://127.0.0.1:8001/v1
export EVIDENCEDOC_MODEL=Qwen/Qwen3-VL-2B-Instruct
# If the server requires authentication:
# export EVIDENCEDOC_API_KEY=your-server-key
```

PowerShell equivalents use `$env:EVIDENCEDOC_VLM_URL="http://127.0.0.1:8001/v1"` and `$env:EVIDENCEDOC_MODEL="Qwen/Qwen3-VL-2B-Instruct"`.

For a trained adapter, merge it into unquantized weights, then serve the merged directory:

```bash
python -m scripts.merge_adapter checkpoints/evidencedoc-qwen3vl-2b --output checkpoints/evidencedoc-merged
vllm serve checkpoints/evidencedoc-merged --served-model-name evidencedoc-tuned --port 8001 --max-model-len 16384 --limit-mm-per-prompt '{"image":8}'
export EVIDENCEDOC_MODEL=evidencedoc-tuned
```

The merging step uses additional CPU/GPU memory. The serving configuration is a starting point, not a confirmed VRAM fit. A remote endpoint must be trusted with uploaded document images. `.env.example` is a reference; export variables yourself. Never commit credentials.

## Benchmark and inspect failures

With the app running:

```bash
python -m scripts.benchmark samples/sample_invoice.pdf --backend baseline --requests 10 --concurrency 1
python -m scripts.benchmark samples/sample_invoice.png --backend vlm --requests 10 --concurrency 2 --output outputs/vlm-benchmark.json
```

Repeat with fixed hardware and at least two resolutions/concurrency levels. Record the accuracy change alongside speed. Latency includes upload, page rendering, parsing, previews, and response transfer. Failed calls are counted separately; they are not included in latency quantiles. Model/server warmup is explicit. No GPU memory number is fabricated by the HTTP client.

On the model-server machine:

```bash
python -m scripts.monitor_gpu --output outputs/gpu_samples.json -- vllm serve checkpoints/evidencedoc-merged --served-model-name evidencedoc-tuned --port 8001
```

This samples total device memory, including other processes, and can miss transient peaks. For inference allocator peaks, add instrumentation inside the model server. Keep that distinction in every reported result.

## Tests and next milestones

```bash
python -m pytest -q
```

1. Run the included app and inspect three generated documents.
2. Annotate real pages with ordered blocks, tables, boxes, and the six fields.
3. Run original-model inference and inspect recognition, structure, grounding, and abstention failures.
4. Run a two-step QLoRA smoke test, then a small complete training run.
5. Compare base and adapted checkpoints on locked real test data with confidence intervals.
6. Normalize Docling outputs, add stronger table metrics (e.g. TEDS), and benchmark quality/latency tradeoffs.

Do not claim fine-tuning improvement, real-world accuracy, or GPU efficiency until those experiments exist. The deliverables should include the adapter, data provenance, run configurations, evaluation reports, failure examples, and deployment measurements.

## Sources

- Qwen3-VL model: https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct
- TRL SFT / VLM training: https://huggingface.co/docs/trl/sft_trainer
- PEFT quantization: https://huggingface.co/docs/peft/developer_guides/quantization
- vLLM supported models: https://docs.vllm.ai/en/stable/models/supported_models/
- Docling: https://github.com/docling-project/docling
- Tesseract installation: https://tesseract-ocr.github.io/tessdoc/Installation.html
- CORD receipt dataset: https://github.com/clovaai/cord

Project code and generated samples: MIT license. External tools, models, and datasets retain their own licenses.
