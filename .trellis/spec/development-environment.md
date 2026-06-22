# Development Environment

## Python

- Prefer Python 3.11 or 3.12.
- The package declares `>=3.10,<3.14`.
- Do not use Python 3.14; UI dependencies are not compatible.

## Dependency Tiers

Install the smallest tier that matches the work:

```bash
uv venv
uv pip install -e .
```

For bundled UI work:

```bash
uv pip install -e ".[ui]"
```

For IM frontends such as Feishu, Telegram, Discord, WeCom, or DingTalk:

```bash
uv pip install -e ".[all-frontends]"
```

Do not install every optional dependency by default.

## Secrets and LLM Config

Supported local config sources include:

- `mykey.py`
- `mykey.toml`
- `MYKEY_JSON`
- generic env vars such as `APIKEY`, `APIBASE`, `MODEL`, `API_MODE`, `REASONING_EFFORT`
- legacy `JARVIS_*` env vars as fallback only

`mykey.py`, `mykey.toml`, `.env`, `.env.*`, `auth.json`, and raw logs must stay untracked.

## Runtime Entrypoints

Common local entrypoints:

```bash
python3 agentmain.py
python3 frontends/tui_v3.py
python3 launch.pyw
python3 frontends/fsapp.py
python3 frontends/aegis_mesh_webgui.py --port 8765
```

Streamlit helper scripts:

```bash
./scripts/start.sh
./scripts/status.sh
./scripts/stop.sh
```

The helper scripts use `.venv/bin/python`, default `PORT=18601`, and default `APP=frontends/stapp.py`.

## Aegis Mesh State

Ledger path priority:

1. `AEGIS_MESH_LEDGER_PATH`
2. `AVATAR_STATE_DIR`
3. `GA_WORKSPACE_ROOT/temp/state/aegis_mesh_ledger.sqlite3`
4. `temp/state/aegis_mesh_ledger.sqlite3`

The ledger is runtime state. It may be inspected for verification, but it must not be committed.

## Verification

Run targeted tests for the area changed. Useful commands:

```bash
uv run python -m unittest discover -s tests -p 'test_llmcore_env.py' -v
uv run python -m unittest discover -s tests -p 'test_aegis_mesh_*.py' -v
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q agent_loop.py agentmain.py ga.py hub.pyw launch.pyw llmcore.py simphtml.py TMWebDriver.py assets frontends ga_cli memory plugins reflect tests
```

For docs/Trellis-only changes, at minimum run the Trellis validator and `git diff --check`.
