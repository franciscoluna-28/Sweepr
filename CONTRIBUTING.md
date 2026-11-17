# Contributing to Sweepr

Thanks for your interest in improving Sweepr. This guide is short. The
project-specific rules live in [`AGENTS.md`](AGENTS.md), which both humans and
automated agents follow.

## Development setup

```sh
uv sync --extra dev
pnpm --dir sweepr_app/ui install
```

Run the backend and the UI together:

```sh
uv run python scripts/dev.py
```

On Windows you can also run `.\scripts\dev.ps1`; on macOS/Linux,
`sh scripts/dev.sh`. Open <http://127.0.0.1:5173/#token=dev>.

Fetch the pinned engine with `uv run sweepr install-assets`. On macOS also
install `ffmpeg` (`brew install ffmpeg`). To use your own build, run
`uv run python scripts/build_engine.py` and set `SWEEPR_BIN_DIR` to a folder
holding `deep-filter`, `ffmpeg`, and `ffprobe`.

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0):

```
<type>(<scope>): <short description>
```

Common types: `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `build`,
`ci`, `chore`. Description is imperative, lowercase, no trailing period. See
`AGENTS.md` for examples.

## Before you open a pull request

Run the checks:

```sh
uv run python scripts/smoke_test.py    # engine, API, security, CLI
pnpm --dir sweepr_app/ui check         # UI typecheck
pnpm --dir sweepr_app/ui build         # UI production build
```

If you changed a route in `sweepr_app/api.py`, a model in `sweepr_app/schemas.py`,
or the error envelope, regenerate the committed API artifacts:

```sh
uv run python scripts/export_openapi.py
pnpm --dir sweepr_app/ui gen:api
```

## Releasing

1. Bump the version in `pyproject.toml`, `sweepr_app/__init__.py`,
   `sweepr_app/assets_manifest.json`, `sweepr_app/ui/package.json`, and the
   installer scripts. The smoke test checks the first and the manifest.
2. Update `CHANGELOG.md`.
3. Build the engine archives for each platform with `scripts/build_engine.py`
   and `scripts/build_assets.py`, then publish the GitHub Release, the PyPI
   package, and the Docker image.
4. When the engine changes, commit the new checksums in
   `sweepr_app/assets_manifest.json` in a reviewed change before tagging. Verify
   every archive against the manifest before publishing.

## Pull requests

- Keep changes focused; one logical change per PR.
- Describe the "why" in the PR body, not just the "what".
- Run the checks above before opening the PR.
