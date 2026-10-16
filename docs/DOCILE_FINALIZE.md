# Finish EvidenceDoc without another training run

The adapter, prompt, resolution, decoding settings and OCR alignment policy are frozen. Final evaluation measures the existing system, including its failures; it does not guarantee a higher score.

## Completed evaluation; final handoff

The adapter evaluation on all 50 original test pages and the existing CPU OCR/rules and box-alignment comparison completed on 16 October 2026. See [final results](DOCILE_FINAL_RESULTS.md). Raw predictions and fingerprints are preserved in the downloaded `EvidenceDoc-final-results.zip`; aggregate results and provenance are included in this source release. Base VLM versus adapter remains on validation.

The remaining presentation work is to record a short demo and commit the source/report updates to the project repository. Keep the trained adapter backup and final-results archive. No further GPU evaluation is required for this release; the instructions below are for reproduction and recovery.

No additional training, interface redesign, vLLM migration or new PDF semantic-check feature is required for this handoff.

## Start the final run

Apply the latest source. Keep the original `EvidenceDoc-readable-ready` dataset attached in Kaggle and the completed `docile-readable-4096-full-3ep` checkpoint restored. Use the inference dependencies that passed the live API smoke test. Tesseract and English data are required for CPU comparison.

The final runner restores missing portable data from extracted Input folders. It verifies the original 50-page fingerprint registered in `configs/docile-final-eval.json`, checks the completed adapter weight hash, preserves conflicting existing data and audits group/source isolation. Preparation loads no model weights or test predictions:

```bash
python -m scripts.finalize_docile --prepare-only
```

Stop the temporary live GPU service before evaluation:

```python
from scripts.connect_docile import stop_gpu
stop_gpu()
```

Run the final command in a streamed notebook subprocess:

```python
import os, subprocess, sys
env = os.environ.copy()
env['CUDA_VISIBLE_DEVICES'] = '0'
env['TOKENIZERS_PARALLELISM'] = 'false'
p = subprocess.Popen(
    [sys.executable, '-u', '-m', 'scripts.finalize_docile'],
    cwd='/kaggle/working/EvidenceDoc', env=env,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
)
for line in p.stdout:
    print(line, end='', flush=True)
print('Exit code:', p.wait())
```

Budget roughly 2-4 hours of GPU time based on prior measurements, with variability from output length, hardware and availability. This is an estimate. CPU OCR runs afterward. The base VLM is not regenerated.

## Saved results and interruption

Completed pages are flushed and fsynced to `outputs/docile-final-test-v1/adapter_predictions.jsonl`. Progress metrics and a small `progress_backup.zip` snapshot update after each page. Progress is not a final score. Generation errors remain in the denominator and are not selectively retried.

Rerun the same command to resume while output files remain. The runner checks IDs/order, image/gold hashes, adapter/processor hashes, prompt, metric code, dependency versions, GPU/dtype and base model revision. It repairs only an unfinished final journal line. A second process cannot write to the same result directory. Completed caches rebuild reports without loading model weights.

Resume cannot recover files erased by a destroyed platform session. Download the progress archive through Kaggle's Output panel periodically if you need protection against session loss. To restore it, extract under `EvidenceDoc/outputs`, restoring `outputs/docile-final-test-v1/run_spec.json` and the prediction journal. Restore the original data and adapter, then rerun the same command.

An interrupted CPU comparison is preserved in a renamed directory before its inexpensive restart. The completed runner writes `EvidenceDoc-final-results.zip` beside the project directory. Download through Kaggle's Output panel; an absolute filesystem FileLink URL may fail.

Keep the recipe fixed after reading the test results. Further tuning requires a new development experiment and separate untouched evaluation data.

## Two-minute demo

- Introduce the small VLM, LoRA training and structured extraction task.
- Open a saved validation page, highlight a field and show line-item groups and exports.
- Show a completed fresh upload and its live-adapter provenance. Disclose the actual minutes-long T4 latency; a video may cut the waiting period with elapsed time shown.
- Show an incorrect quantity or address and explain why schema validity does not imply correctness. Demonstrate manual review.
- Show validation and final test reports separately. Corrected outputs never replace raw benchmark predictions.

## Resume wording supported by the completed test

- Fine-tuned Qwen3-VL-2B with 4-bit LoRA on 168 document pages using a Tesla T4; trained 8.7M adapter parameters while retaining the frozen base model.
- Built a group/source-separated evaluation pipeline on 50 custom held-out pages; measured 34.9% key-field text F1, 33.7% line-item cell text F1 and 70% schema validity, retaining failed outputs in evaluation.
- Improved line-item text-and-box F1 from 15.7% to 23.0% using OCR box alignment while preserving predicted text, field types and row groups.
- Served the trained adapter through an authenticated FastAPI GPU service with job polling, source-region inspection, manual review and JSON/Markdown exports.

Use stronger claims only when supported by saved results. Production reliability, official DocILE scores, vLLM speedups and superiority to general AI have not been demonstrated.
