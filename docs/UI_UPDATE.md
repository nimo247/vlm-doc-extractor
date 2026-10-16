# EvidenceDoc UI update

This update changes the three files in `evidencedoc/static/`. It preserves the existing FastAPI parsing API and document schema.

## Apply to an existing Codespace

Upload the updated `EvidenceDoc.zip` into the repository root, beside `pyproject.toml`. Then extract only its frontend files:

```bash
python - <<'PY'
from pathlib import Path
from zipfile import ZipFile
with ZipFile('EvidenceDoc.zip') as archive:
    for filename in ('index.html', 'style.css', 'app.js'):
        target = Path('evidencedoc/static') / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(archive.read('EvidenceDoc/evidencedoc/static/' + filename))
print('Updated the three frontend files.')
PY
```

Refresh the forwarded app URL with Ctrl+Shift+R. If the server is stopped, run:

```bash
.venv/bin/python -m uvicorn evidencedoc.app:app --host 0.0.0.0 --port 8000
```

Open port 8000 through the Codespaces Ports panel.

## Changes

- Compact workbench layout; source, document preview, and extraction are visible together on wide screens.
- Consistent SVG icons, readable typography, and deliberate spacing within the existing green identity.
- Document zoom, page navigation, and amber evidence highlights connected to selected fields.
- JSON and Markdown copy/export actions, with the current export format shown explicitly.
- Loading skeletons, actionable errors, and unavailable OCR/VLM states.
- Keyboard-operated tabs, visible focus, and tablet/mobile layouts.
- No remote font or icon dependencies.

## Verification

The JavaScript was syntax-checked. DOM interaction checks exercised selection, parsing, six fields, evidence linking, zoom, JSON/Markdown tabs, keyboard navigation, copying, tables, failure handling, stale-export prevention, and document removal. Python tests cover the existing API and document pipeline.

Browser visual QA was not available in the managed environment. DOM checks do not verify rendered layout. Inspect the updated page at your normal browser size and on a narrow viewport.

## Design guidance

Applied Impeccable's published Operate, layout, typography, and craft-floor guidance to the existing interface:
https://github.com/pbakaus/impeccable/tree/main/.agents/skills/impeccable

The Impeccable context launcher was attempted but its engine was unavailable. This update does not claim an engine audit or an installed skill in your Codespace.
