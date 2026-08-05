# TalkLocAI

A voice AI application for real-time conversations that supports both local AI models (LM Studio) and external LLM providers (OpenRouter). The app captures speech via microphone, transcribes it, processes the request with a language model, and responds through text-to-speech output.

## Features

- **Speech-to-Text (STT)** with faster-whisper (local)
- **Text-to-Speech (TTS)** with Piper, Windows SAPI, or ElevenLabs
- **LLM backend** — local (LM Studio) or remote (OpenRouter)
- **Automatic fallback** between local and remote models (`auto` mode)
- **Web search & news** via DuckDuckGo and Google News RSS (no API key required)
- **Conversation memory** — short context from the last exchange
- **Graphical provider selection** (tkinter) on Windows
- **Text mode** for use without a microphone

## Requirements

- Python 3.10 or higher
- Windows 10/11 (for full GUI support)
- Recommended: 8 GB RAM or more (depending on the Whisper model chosen)

## Installation

### 1. Clone the repository

```powershell
git clone https://github.com/<user>/TalkLocAI.git
cd TalkLocAI
```

### 2. Set up a virtual environment (recommended)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install Python dependencies

```powershell
pip install -r voice_ai\requirements.txt
```

Alternatively, install in development mode:

```powershell
pip install -e .
```

### 4. Create the configuration file

Copy the example configuration and customize it:

```powershell
Copy-Item voice_ai\config\config.example.json voice_ai\config\config.json
```

Edit `voice_ai\config\config.json` and configure at least one LLM provider.

## Environment Variables

API keys must be provided through environment variables. The application reads them via `os.environ.get()`. You can set them manually in your shell, or use a `.env` file as a reference — but the application does **not** automatically load `.env` files.

| Variable | Description |
|---|---|
| `OPENROUTER_API_KEY` | API key for OpenRouter (required for `auto` or `openrouter` provider) |
| `ELEVENLABS_API_KEY` | API key for ElevenLabs (only with `tts_engine: "elevenlabs"`) |
| `ELEVENLABS_VOICE_ID` | ElevenLabs voice ID (only with `tts_engine: "elevenlabs"`) |

Example `.env` file:

```env
OPENROUTER_API_KEY=
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=
```

## Local AI Setup

For local operation, **LM Studio** is required. Start LM Studio and load a model. The built-in OpenAI-compatible server must be reachable at the `local_lm_base_url` configured in `config.json` (default: `http://127.0.0.1:8080`).

Key settings in `config.json` for local operation:

```json
"llm_provider": "local",
"local_lm_base_url": "http://127.0.0.1:8080/",
"local_lm_auto_select": true
```

In `auto` mode, the app tries the local server first and falls back to OpenRouter if it is unreachable.

## Running the Application

### Windows (with GUI)

```powershell
python run_voice_ai.py
```

A window opens for selecting the provider (local or OpenRouter) and configuring Whisper and TTS settings.

### Text Mode (without microphone)

```powershell
python run_voice_ai.py --text
```

### Direct Start (without GUI)

```powershell
python -m voice_ai.main
```

## Language Support

The application currently supports **English** and **German**. The interface language, LLM conversation language, and system prompts adapt to the selected `app_language` in the configuration.

## Configuration

The central configuration is in `voice_ai\config\config.json`.

### Key Settings

| Key | Default | Description |
|---|---|---|
| `llm_provider` | `"auto"` | `"local"`, `"openrouter"`, or `"auto"` |
| `local_lm_base_url` | `"http://127.0.0.1:8080/"` | URL of the local LM Studio server |
| `local_lm_model` | `""` | Explicit model (empty = auto-select) |
| `openrouter_model` | `"google/gemini-2.0-flash-exp:free"` | Model on OpenRouter |
| `openrouter_api_key` | `""` | API key for OpenRouter |
| `openrouter_retry_on_limit` | `true` | Automatically try alternative models on rate limit |
| `openrouter_retry_models` | `[...]` | List of fallback models |
| `whisper_model` | `"small"` | Whisper model size (`tiny`, `base`, `small`, `medium`, `large`, `large-v2`, `large-v3`, `auto`) |
| `whisper_language` | `"en"` | Language for transcription |
| `whisper_device` | `"auto"` | `"cpu"`, `"cuda"`, or `"auto"` |
| `tts_engine` | `"system"` | `"piper"`, `"system"`, or `"elevenlabs"` |
| `piper_voice` | `"de_DE-kerstin-low"` | Piper voice |
| `windows_voice` | `""` | Windows SAPI voice name |
| `app_language` | `"en"` | Application language (`"en"` or `"de"`) |
| `internet_enabled` | `true` | Enable web search and news |
| `news_topic` | `""` | News topic (empty = general) |
| `max_tokens` | `4096` | Maximum response length in tokens |
| `temperature` | `0.7` | Response creativity |
| `reasoning_timeout` | `60` | LLM request timeout in seconds |
| `input_device_name` | `"Mikrofon (LCS_USB_AUDIO)"` | Audio device by name (optional) |
| `input_device_index` | `null` | Audio device by index (optional) |

## Project Structure

```
TalkLocAI/
├── run_voice_ai.py              # Entry point with GUI / CLI selection
├── generate_project_summary.py  # Generates PROJECT_SUMMARY.md
├── pyproject.toml               # Build system and metadata
├── voice_ai/
│   ├── __init__.py
│   ├── main.py                  # Main VoiceAI class (pipeline)
│   ├── summary.py               # Auto-generation of project summary
│   ├── web_search.py            # DuckDuckGo search & Google News RSS
│   ├── llm/
│   │   └── __init__.py          # LLM providers (local & OpenRouter)
│   ├── stt/
│   │   └── __init__.py          # Whisper speech recognition (faster-whisper)
│   ├── tts/
│   │   └── __init__.py          # TTS engines (Piper, System, ElevenLabs)
│   ├── memory/
│   │   └── __init__.py          # Short-context conversation memory
│   ├── prompts/
│   │   └── __init__.py          # System and conversation prompts
│   └── config/
│       ├── config.example.json   # Configuration template
│       └── config.json           # Local configuration (do not commit)
├── voice_ai/requirements.txt    # Python dependencies
└── .env.example                  # Environment variables template
```

## Privacy & Security

- **Never commit API keys.** API keys must NOT be stored in `config.json`. Use environment variables instead. Add `.env` and `voice_ai\config\config.json` to `.gitignore` — both files are already excluded.
- **Local processing.** Speech recognition (Whisper) and TTS (Piper/System) run locally on your machine by default.
- **External services.** When using OpenRouter, your text inputs are sent to OpenRouter. When using ElevenLabs, response text is sent to ElevenLabs for speech synthesis. Web search uses DuckDuckGo (HTML) and Google News RSS.
- **State files.** `voice_ai/state.json` and temporary `.wav` files are created locally and are not tracked in the repository.

## GitHub / Development

### Clone and Set Up

```powershell
git clone https://github.com/<user>/TalkLocAI.git
cd TalkLocAI
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
pip install pytest black flake8
```

### Useful Commands

```powershell
python run_voice_ai.py --text
pytest
```

### Committing

```powershell
git add .
git commit -m "Description of changes"
git push
```

Make sure you do not accidentally commit `.env`, `config.json`, `state.json`, or `.wav` files.
