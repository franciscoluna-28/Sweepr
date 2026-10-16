# Contributing to Sweepr

Thanks for your interest in improving Sweepr. This guide is short — the
project-specific rules live in [`AGENTS.md`](AGENTS.md), which both humans and
automated agents follow.

## Development setup

```
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe torch==2.1.2 torchaudio==2.1.2 --index-url https://download.pytorch.org/whl/cpu
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
pnpm --dir app/ui install
```

On macOS/Linux, replace `.venv/Scripts/python.exe` with `.venv/bin/python`.

Run the app in development (Python auto-reload + Vite HMR):

```
run-dev.bat          # Windows
./run.sh --dev       # macOS/Linux
```

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0):

```
<type>(<scope>): <short description>
```

Common types: `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `build`,
`ci`, `chore`. Description is imperative, lowercase, no trailing period. See
`AGENTS.md` for examples.

## Before you open a pull request

Run the same checks CI runs:

```
.venv\Scripts\python.exe scripts\smoke_test.py   # end-to-end API + engine
pnpm --dir app/ui check                          # UI typecheck
pnpm --dir app/ui build                          # UI production build
```

If you changed a route in `app/api.py`, a model in `app/schemas.py`, or the
error envelope, regenerate the committed API artifacts:

```
.venv\Scripts\python.exe scripts\export_openapi.py
pnpm --dir app/ui gen:api
```

## Pull requests

- Keep changes focused; one logical change per PR.
- Describe the "why" in the PR body, not just the "what".
- Make sure CI is green.
