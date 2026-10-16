# DocILE extraction and review application

The `/docile` workspace connects the separate DocILE extraction contract to the existing FastAPI application. The original full-page document workspace remains at `/`.

## Start the CPU review workspace

Upload the latest source ZIP and `EvidenceDoc-evaluated-backup.zip` into the Codespaces repository root. Existing `data/docile_prepared` validation images are supported. If that data is absent, also upload `EvidenceDoc-validation-review.zip`; the restore helper will use its 40 validation pages.

After applying the source update, run:

```bash
cd /workspaces/vlm-doc-extractor
.venv/bin/python -m scripts.restore_docile_review
.venv/bin/python -m uvicorn evidencedoc.app:app --host 0.0.0.0 --port 8000
```

Open the forwarded port and append `/docile` to its URL. Keep the Codespaces port private while reviewing the dataset. The application has no user accounts.

The restore helper reads only the report and raw prediction files from the evaluation backup; it does not load the adapter weights. It validates every selected image hash against the completed run. Different existing files are preserved rather than overwritten. The optional data bundle is limited to validation rows and is checked for invalid paths.

Saved adapter/base results are explicitly labeled as previously generated validation outputs. Their displayed model time is the recorded generation time, not the time required to load the saved page. Fresh OCR results are labeled separately. No GPU or Torch import is needed for this review mode.

## Review and export

1. Choose a saved page and inspect the trained adapter, base model, or fresh eight-category OCR rules.
2. Select a key field or line-item cell to highlight its normalized box on the page.
3. Optional OCR alignment updates boxes for schema-valid adapter results only. The response records all original/replacement coordinates and retains original raw output.
4. Invalid model output is displayed with JSON/schema errors. Validated exports remain unavailable until the output passes validation.
5. In **JSON & review**, edit the output and choose **Validate and apply edits**. Edits remain in the browser session and do not overwrite predictions, reference labels or benchmark scores. Manual results are labeled separately.
6. Export validated extraction JSON or a deterministic Markdown summary. Downloading the original raw model output remains available, including after manual edits.

Schema validation checks structure only. It does not establish the visual correctness of field text, category, box or row grouping. Manual corrections must not be reported as model benchmark accuracy.

## Fresh uploads

The upload path accepts one English document page (PDF, PNG, JPEG or WEBP) up to 20 MB. Rendering uses a maximum edge of 1280 pixels, matching the prepared data policy. Multi-page PDFs are rejected by this DocILE path. The OCR rule backend supports eight key-field categories and no line-item parser; valid empty results are possible.

Tesseract and its English data are required for CPU OCR or optional box alignment. Saved adapter/base review works without Tesseract.

## Live trained-adapter service

`scripts.serve_docile` loads the saved readable adapter once on a CUDA GPU. It uses the readable training prompt, explicit `do_resize=False`, NF4 inference, the saved adapter/processor, and the sampled decoding settings evaluated earlier. The code checks the prompt fingerprint, image grid, completed training metadata, and actual adapter weight hash. One request runs at a time. There is no fabricated CPU model fallback.

On the GPU machine, with the previously working training dependencies and adapter restored:

```bash
CUDA_VISIBLE_DEVICES=0 python -m scripts.serve_docile \
  --adapter checkpoints/docile-readable-4096-full-3ep \
  --host 127.0.0.1 --port 8001
```

On the same machine, the review application can use:

```bash
EVIDENCEDOC_DOCILE_URL=http://127.0.0.1:8001 \
python -m uvicorn evidencedoc.app:app --host 127.0.0.1 --port 8000
```

For separate CPU/GPU machines, provide the GPU platform's reachable service URL. If binding the adapter server beyond localhost, set `EVIDENCEDOC_DOCILE_API_KEY`; the server requires it. Configure the same key in the CPU app's environment. Do not put keys into source files or browser code. Keep service credentials in environment/secret settings and use HTTPS for a remote connection. No tunnel or public GPU deployment is created by this update.

This is a dedicated adapter-service protocol, not the existing OpenAI-compatible full-page backend. The CPU app submits a rendered PNG with `POST /jobs` and polls `GET /jobs/{job_id}`; the GPU service returns raw model text and provenance. The direct `POST /extract` route remains available for local tests. Set `EVIDENCEDOC_DOCILE_PROTOCOL=direct` only for an older direct service. The CPU app performs schema validation and optional OCR alignment. `GET /health` reports loaded model/adapter provenance and requires the same access key when configured.

The current builder environment has no GPU. Model loading/generation through this new service entry point has not been executed here. Its request/auth contracts have been tested using a mock engine, while the model-generation implementation follows the previously user-tested readable evaluator. A real GPU request and end-to-end latency measurement remain required before claiming live deployment.

## Configuration and API

Environment settings:

| Variable | Purpose |
|---|---|
| `EVIDENCEDOC_DOCILE_MANIFEST` | Optional explicit validation manifest path |
| `EVIDENCEDOC_DOCILE_DATA_ROOT` | Base directory for manifest image paths |
| `EVIDENCEDOC_DOCILE_RUN` | Saved report and base/adapter prediction directory |
| `EVIDENCEDOC_DOCILE_URL` | Optional live adapter service base URL |
| `EVIDENCEDOC_DOCILE_API_KEY` | Shared service access key, never sent to the browser |

Defaults use `data/docile_review/manifest.jsonl` if restored, otherwise `data/docile_prepared/manifest.jsonl`; the run defaults to `outputs/readable-3ep-validation40-sampled-v1`.

Routes: `/api/docile/status`, `/api/docile/documents`, `/api/docile/documents/{id}`, `/api/docile/images/{id}`, `/api/docile/extract`, `/api/docile/validate`, `/api/docile/schema`. Image access is limited to selected validation IDs, configured data-root boundaries and recorded image hashes. The original full-page routes remain unchanged.

## Verification

The full CPU suite passed: 45 passed, 2 skipped because the optional `datasets` dependency is unavailable in the builder QA environment. New tests cover saved provenance, invalid-output handling, hash checks, editing without mutating benchmarks, box-change provenance, fresh OCR versus disconnected adapter behavior, mocked live forwarding, single-page constraints, and GPU-service authentication/input contracts. All 40 actual validation predictions were served through the review API, reproducing 30 valid and 10 invalid outputs. A real CPU OCR upload passed schema validation. Both uploaded backups were restored into a clean temporary directory and all 40 images verified.

JavaScript syntax and HTML/JS target IDs were checked. DOM interaction checks with real API-response fixtures passed for initial page loading, source rectangles, row groups, failed-output export blocking, manual review, preserving source images, text-injection safety, JSON/Markdown/raw downloads, and keyboard tabs. These use a DOM emulator and do not establish visual layout correctness. A browser visual smoke test could not run because the Chromium download failed; visual QA remains pending on the user's forwarded Codespaces port.


## Temporary live connection from Kaggle to Codespaces

This is an opt-in demonstration connection. Running the GPU launcher creates a public temporary Cloudflare URL protected by the service access key. No tunnel was started by the builder. Quick Tunnels are for development, have no uptime guarantee, and use a new hostname after restart. Reference: https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/ .

Apply this source version to both machines. Keep the trained adapter on Kaggle and the private Codespaces UI on port 8000. The GPU launcher downloads the Linux x86_64 `cloudflared` executable from Cloudflare's official GitHub release to a private temporary directory. It starts the GPU service on localhost, checks authenticated readiness and job-protocol support, opens a tunnel, and verifies that unauthenticated health access is rejected. It prints the URL only after the remote check succeeds. Kaggle networking may block tunnel connections; if so it stops the processes and points to its diagnostic logs rather than claiming a connection.

In a Kaggle Python cell:

```python
import getpass
from scripts.connect_docile import start_gpu
service_url = start_gpu(getpass.getpass("Choose a private access key (24+ characters; save it): "))
```

Save the same key privately for Codespaces. The launcher passes it in the GPU process environment, never in command arguments, browser code, or saved logs. It does not save or print the key. Keep the notebook session active without attempting to evade platform quotas.

In Codespaces, stop the old UI server with Ctrl+C and run:

```bash
cd /workspaces/vlm-doc-extractor
.venv/bin/python -m scripts.connect_docile ui
```

Paste the service URL and enter the same key at the masked prompt. The launcher checks remote health before starting the app and configures the job protocol. Keep the forwarded port private. Open `/docile`, hard refresh the page to load the updated JavaScript, choose the trained adapter under fresh uploads, and submit one readable page. An HTTP connection alone does not establish extraction accuracy. The GPU model's sampling, resolution, prompt, adapter and generation budget remain unchanged by this networking update.

The browser submits a file to `POST /api/docile/jobs` and polls `GET /api/docile/jobs/{job_id}`. The CPU process independently polls the GPU service. This keeps each proxy request short while generation runs. Only one upload and one GPU job are admitted at a time; extra submissions are rejected. Each process retains at most eight job records; completed jobs become unavailable after 30 minutes. Job state is in memory and is lost on process restart. This is a single-user demo, not a durable production queue. Requests are not automatically resubmitted after connection failures, avoiding duplicate GPU inference.

To stop both demo processes in Kaggle:

```python
from scripts.connect_docile import stop_gpu
stop_gpu()
```

Local tests cover authenticated submission/polling, busy handling, failure sanitization, result expiry, CPU upload jobs, remote polling without resubmission, URL checks, launcher key validation and browser polling. The cross-machine tunnel, real browser upload through it, and visual layout remain to be checked on the user's running platforms.
