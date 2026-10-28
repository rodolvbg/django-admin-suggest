# Contributing

## Development setup

With [uv](https://docs.astral.sh/uv/) (recommended):

```bash
uv sync
uv run playwright install --with-deps chromium
npm install
uv run pre-commit install
```

Without uv:

```bash
pip install -e ".[dev]"
playwright install --with-deps chromium
npm install
pre-commit install
```

## Running the example project

```bash
cd example
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Tests

Python (pytest + pytest-django, coverage always on via `addopts`):

```bash
uv run pytest
```

`tests/e2e/` (real-browser tests via pytest-playwright, driving a real
Chromium against `live_server`) runs as part of that same `uv run pytest`
— no separate command. They need `uv run playwright install chromium`
once (see Setup above) and are slower than the rest of the suite;
everything else under `tests/` is unit/integration-level and doesn't
touch a browser.

JavaScript (vitest + jsdom):

```bash
npm test
npm run coverage
```

## Compatibility matrix (tox)

`uv run pytest` above only runs against whatever Django version `uv.lock`
resolved (the newest one satisfying `dependencies`). To check the full
supported range — every Django series in `classifiers`, against the
oldest and newest Python it supports (within this package's own
`requires-python` floor) — run the tox matrix instead:

```bash
uv run tox run-parallel   # every env, in parallel
uv run tox -e py314-dj52  # a single env, e.g. to debug one failure
```

`[tool.tox]` in `pyproject.toml` lists the exact envs. Each one gets its own ephemeral venv (via
[tox-uv](https://github.com/tox-dev/tox-uv), using uv's own Python
builds — `uv python install <version>` once for any you don't have yet)
with only `pytest`/`pytest-django`/`pytest-cov` and that env's pinned
Django, not the full `dev` group, and skips `tests/e2e/` (no Playwright
in those envs). This only tests boundaries (oldest + newest Python per
Django series), not every valid combination — that catches most real
breakage while staying fast. Runs in CI as a separate
`compat-matrix.yml` workflow, alongside the regular `pytest.yml`. Update
the `env_list` here whenever `classifiers` gains or drops a Django
series.

## Lint / format / type-check

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src example
# or, everything at once:
uv run pre-commit run --all-files
```

The mypy pre-commit hook runs against the project venv (it needs
django-stubs to resolve model types), not an isolated pre-commit env.

## Before opening a PR

- [ ] `uv run pytest`
- [ ] `npm test`
- [ ] `uv run pre-commit run --all-files`
