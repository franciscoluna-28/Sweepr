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
feat(limits): make limits and port configurable via env vars
fix(jobs): prune job dirs on interrupted restart
docs(readme): document configuration section
```

## Verification

Run the smoke test after changing app code:

```
.venv\Scripts\python.exe scripts\smoke_test.py
```

Run the UI typecheck after changing UI code:

```
pnpm --dir app/ui check
```

## API client

The UI's types are generated from the FastAPI schema. After changing a route in
`app/api.py`, a model in `app/schemas.py`, or the error envelope, regenerate and
commit both files:

```
.venv\Scripts\python.exe scripts\export_openapi.py
pnpm --dir app/ui gen:api
```
