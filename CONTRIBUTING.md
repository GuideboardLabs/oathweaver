# Contributing to Oathweaver

Thanks for helping improve Oathweaver.

## Setup

```bash
git clone <your-fork-or-repo-url>
cd Oathweaver
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
```

Install the Ollama models listed in the README, then run:

```bash
make check
# or:
python smoke_test.py
python run_integration_tests.py
python tools/ui_phase_smoke.py
python tools/repo_health_check.py
```

Optional feature extras:

```bash
pip install -r requirements-optional-docs.txt
pip install -r requirements-optional-bots.txt
```

Maintainer note for `requirements.lock`:

```bash
# In a clean venv after installing the exact dependency set you want to ship:
python tools/refresh_requirements_lock.py
```

Do not hand-edit `requirements.lock`; regenerate it from the environment you intend to support.

## Pull request checklist

- Keep changes focused and well-scoped
- Prefer extraction and simplification over adding new branches to giant files
- Add logging instead of silent exception swallowing
- Run `make check` after code changes
- Update docs when behavior changes

## Style guidance

- Follow PEP 8 where practical
- Prefer small helpers over giant conditionals
- Use explicit names for runtime state and result payloads
- Keep request parsing, orchestration, and persistence concerns separated where possible

## Reporting bugs

Please include:

- what you tried
- what you expected
- what happened instead
- relevant logs or tracebacks
- platform details if environment-specific

## License of contributions

By submitting a contribution, you agree that your contribution is provided
under the repository license in [LICENSE](LICENSE)
(Guideboard Service-Only License 1.0).
