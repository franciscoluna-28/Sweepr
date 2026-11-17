# AGENTS.md

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0) for all
commits in this repository:

```
<type>(<scope>): <short description>
```

- Common types: `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `build`,
  `ci`, `chore`.
- Scope is optional but encouraged, e.g. `feat(api)`, `fix(engine)`,
  `docs(readme)`.
- Description is imperative, lowercase, no trailing period.
- Body/footer (e.g. `BREAKING CHANGE:`) when the change warrants it.

Examples:

```
feat(assets): verify engine archives against pinned checksums
fix(engine): read 24-bit intermediates as float for deep-filter
docs(readme): document self-hosting with a token
```

## Verification

Run the smoke test after changing Python code (it needs the engine: set
`SWEEPR_BIN_DIR` or let Sweepr download it):

```
uv run python scripts/smoke_test.py
```

Run the UI checks after changing UI code:

```
pnpm --dir sweepr_app/ui check
pnpm --dir sweepr_app/ui build
```

## Engine and releases

- The engine is `deep-filter` built from a pinned DeepFilterNet tag and commit
  (`scripts/build_engine.py`), plus pinned LGPL ffmpeg (`scripts/build_assets.py`).
  Bump pins deliberately and record it in the CHANGELOG.
- `sweepr_app/assets_manifest.json` pins one SHA-256 per platform for either a
  Sweepr engine archive or the upstream `deep-filter` and ffmpeg components.
  Verify every download against its pin before publishing a release.
- The installers (`scripts/install.ps1`, `scripts/install.sh`) pin uv 0.13.8 and
  the release version. Update them together with `pyproject.toml`.

## API client

The UI's types are generated from the FastAPI schema. After changing a route in
`sweepr_app/api.py`, a model in `sweepr_app/schemas.py`, or the error envelope,
regenerate and commit both files:

```
uv run python scripts/export_openapi.py
pnpm --dir sweepr_app/ui gen:api
```

## Security invariants

- Every `/api` route except `/api/health` requires the per-launch token
  (`X-Sweepr-Token`, or `?token=` on GET requests for media). Keep it that way.
- The Host header must match the allowlist; never widen it to a wildcard.
- Never run external programs through a shell. Pass argument lists.
- Engine archives are extracted flat and checksum-verified before use.
