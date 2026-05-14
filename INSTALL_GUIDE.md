# Oathweaver Install Guide (Recipient Version)

This guide is for someone receiving a fresh Oathweaver ZIP and getting it running locally.

## 1) Easiest path: double-click installer EXE

If your ZIP already includes `OathweaverInstaller.exe`, double-click it.

What it does:

- launches `install_oathweaver.ps1` in GUI mode
- installs/checks prerequisites
- prompts for first owner username + 4-digit PIN
- offers to pull missing Ollama models

Optional CLI mode from terminal:

```powershell
.\OathweaverInstaller.exe --cli
```

## 2) Fast script path: run the installer directly

From the project root in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_oathweaver.ps1
```

What this installer does:

- checks Python, Ollama, and optional Node.js
- offers `winget` install for missing prerequisites
- installs Python dependencies from `requirements.lock`
- starts Ollama if needed
- reads `SourceCode/configs/model_routing.json` and pulls missing required models
- prompts for first owner username + 4-digit PIN

After installer completion:

```powershell
powershell -ExecutionPolicy Bypass -File .\start_oathweaver_web.ps1
```

Security default: the launcher binds Ollama to `127.0.0.1:11434` (localhost only).
If you intentionally need LAN/Tailscale access, pass `-OllamaHost "0.0.0.0:11434"` explicitly.

Open:

```text
http://127.0.0.1:5050
```

## 3) Manual install (if you skip installer)

Install prerequisites:

- Python 3.10+
- Ollama
- Node.js LTS (optional; useful for dev tooling)

Then run:

```powershell
python -m pip install -r .\requirements.lock
```

Optional extras:

```powershell
# PDF / DOCX / OCR helpers
python -m pip install -r .\requirements-optional-docs.txt

# Discord bot support
python -m pip install -r .\requirements-optional-bots.txt
```

Pull required models:

```powershell
ollama pull dolphin3:8b
ollama pull deepseek-r1:8b
ollama pull qwen2.5-coder:7b
ollama pull qwen2.5:7b
ollama pull mistral:7b
ollama pull qwen3:4b
ollama pull qwen3:8b
ollama pull nomic-embed-text
```

First boot requires owner credentials through environment variables:

```powershell
$env:OATHWEAVER_OWNER_USERNAME="owner"
$env:OATHWEAVER_OWNER_PASSWORD="1234"
powershell -ExecutionPolicy Bypass -File .\start_oathweaver_web.ps1
```

After first boot, owner is stored in the local DB, so you do not need to keep those env vars.

## 4) Optional web-foraging stack

If you want live web-foraging (SearXNG + Crawl4AI), install Docker Desktop and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\start_web_foraging_stack.ps1
```

## 5) Troubleshooting

- `Oathweaver owner setup is incomplete`: run `install_oathweaver.ps1` or set `OATHWEAVER_OWNER_*` env vars for first boot.
- Ollama not reachable: run `ollama serve`, then retry.
- Missing models: run `ollama list` and pull the missing names shown above.
- PDF / DOCX text extraction unavailable: install `requirements-optional-docs.txt`; OCR also requires the Tesseract binary on your machine.
- Discord bot unavailable: install `requirements-optional-bots.txt`.
- Port already in use: change web port with `-WebPort 5051` on `start_oathweaver_web.ps1`.
- No `OathweaverInstaller.exe` in your ZIP: generate it with `powershell -ExecutionPolicy Bypass -File .\build_installer_exe.ps1`.
