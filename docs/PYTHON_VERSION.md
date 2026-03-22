# Python version (avoid `pydantic-core` build failures)

**Use Python 3.12 or 3.13** for this project. **Python 3.14** often has **no pre-built wheels** for `pydantic-core` yet; pip then compiles Rust/PyO3 and fails with:

> the configured Python interpreter version (3.14) is newer than PyO3's maximum supported version (3.13)

## Fix A (recommended): new venv on 3.12 / 3.13

```bash
cd /path/to/ordered-api
rm -rf venv
python3.12 -m venv venv   # or: python3.13 -m venv venv
source venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

On macOS with Homebrew: `brew install python@3.12` then use `/opt/homebrew/bin/python3.12`.

This repo includes **`.python-version`** (`3.12`) for **pyenv** users.

## Fix B: stay on 3.14 (experimental)

Try forcing the PyO3 forward-compat build (may still fail or be unstable):

```bash
export PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1
pip install -r requirements.txt
```

If it still errors, use Fix A.
