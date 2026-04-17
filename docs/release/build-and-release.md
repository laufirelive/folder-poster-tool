# Build and Release Runbook

## Local smoke build

```bash
source .venv/bin/activate
pip install -r requirements.txt
pip install pyinstaller
pyinstaller folder-poster.spec
```

Expected output directory: `dist/Folder-Poster/`

## Trigger GitHub release build

1. Ensure branch is merged to `master`.
2. Create tag and push:

```bash
git tag v0.1.0
git push origin v0.1.0
```

3. Verify GitHub Actions `Build Portable Release` succeeded on both matrix targets.
4. Confirm release assets exist:
- `Folder-Poster-Windows.zip` or split volumes
- `Folder-Poster-macOS-ARM.zip`
