# TalkLocAI

Eine Voice-AI-Anwendung für Echtzeitgespräche, die sowohl lokale KI-Modelle (LM Studio) als auch externe LLM-Anbieter (OpenRouter) unterstützt. Das Programm nimmt Spracheingabe über das Mikrofon entgegen, transkribiert sie, verarbeitet die Anfrage mit einem Sprachmodell und antwortet per Sprachausgabe.

## Hauptfunktionen

- **Spracherkennung (STT)** mit faster-whisper (lokal)
- ** Sprachausgabe (TTS)** mit Piper, Windows SAPI oder ElevenLabs
- **LLM-Backend** wahlweise lokal (LM Studio) oder remote (OpenRouter)
- **Automatischer Fallback** zwischen lokalem und remote Modell (Modus `auto`)
- **Web-Suche & Nachrichten** via DuckDuckGo und Google News RSS (ohne API-Key)
- **Dialog-Speicher** (Kurzzitierter Kontext der letzten Gesprächsrunde)
- **Grafische Provider-Auswahl** (tkinter) unter Windows
- **Textmodus** für die Nutzung ohne Mikrofon

## Voraussetzungen

- Python 3.10 oder höher
- Windows 10/11 (für volle GUI-Unterstützung)
- Empfohlen: 8 GB RAM oder mehr (abhängig vom gewählten Whisper-Modell)

## Installation

### 1. Repository klonen

```powershell
git clone https://github.com/<benutzer>/TalkLocAI.git
cd TalkLocAI
```

### 2. Virtuelle Umgebung einrichten (empfohlen)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Python-Abhängigkeiten installieren

```powershell
pip install -r voice_ai\requirements.txt
```

Alternativ kann das Paket im Entwicklungsmodus installiert werden:

```powershell
pip install -e .
```

### 4. Konfiguration anlegen

Kopiere die Beispielkonfiguration und passe sie an:

```powershell
Copy-Item voice_ai\config\config.example.json voice_ai\config\config.json
```

Bearbeite `voice_ai\config\config.json` und trage mindestens einen LLM-Provider ein.

## Umgebungsvariablen

API-Keys können wahlweise in der `config.json` oder über Umgebungsvariablen gesetzt werden. Für Letzteres kann eine `.env`-Datei im Projektverzeichnis angelegt werden (diese wird von `.gitignore` ignoriert).

| Variable | Beschreibung |
|---|---|
| `OPENROUTER_API_KEY` | API-Key für OpenRouter (benötigt bei Provider `auto` oder `openrouter`) |
| `ELEVENLABS_API_KEY` | API-Key für ElevenLabs (nur bei `tts_engine: "elevenlabs"`) |
| `ELEVENLABS_VOICE_ID` | ElevenLabs Stimmen-ID (nur bei `tts_engine: "elevenlabs"`) |

Beispiel für eine `.env`-Datei:

```env
OPENROUTER_API_KEY=
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=
```

## Lokale KI-Unterstützung

Für den lokalen Betrieb wird **LM Studio** benötigt. Starte LM Studio und lade ein Modell. Der eingebaute OpenAI-kompatible Server von LM Studio muss unter der in der `config.json` eingetragenen `local_lm_base_url` erreichbar sein (Standard: `http://127.0.0.1:8080`).

Wichtige Einstellungen in `config.json` für den lokalen Betrieb:

```json
"llm_provider": "local",
"local_lm_base_url": "http://127.0.0.1:8080/",
"local_lm_auto_select": true
```

Der Modus `auto` probiert zuerst den lokalen Server und fällt bei Nichterreichbarkeit auf OpenRouter zurück.

## Start

### Windows (mit GUI)

```powershell
python run_voice_ai.py
```

Es öffnet sich ein Fenster zur Auswahl des Providers (lokal oder OpenRouter) sowie Einstellungen für Whisper und TTS.

### Textmodus (ohne Mikrofon)

```powershell
python run_voice_ai.py --text
```

### Direkter Start (ohne GUI)

```powershell
python -m voice_ai.main
```

## Konfiguration

Die zentrale Konfiguration erfolgt über die Datei `voice_ai\config\config.json`.

### Wichtige Einstellungen

| Schlüssel | Standard | Beschreibung |
|---|---|---|
| `llm_provider` | `"auto"` | `"local"`, `"openrouter"` oder `"auto"` |
| `local_lm_base_url` | `"http://127.0.0.1:8080/"` | URL des lokalen LM-Studio-Servers |
| `local_lm_model` | `""` | Explizites Modell (leer = Auto-Select) |
| `openrouter_model` | `"google/gemini-2.0-flash-exp:free"` | Modell auf OpenRouter |
| `openrouter_api_key` | `""` | API-Key für OpenRouter |
| `openrouter_retry_on_limit` | `true` | Bei Rate-Limit automatisch alternative Modelle versuchen |
| `openrouter_retry_models` | `[...]` | Liste von Fallback-Modellen |
| `whisper_model` | `"small"` | Whisper-Modellgröße (`tiny`, `base`, `small`, `medium`, `large`, `large-v2`, `large-v3`, `auto`) |
| `whisper_language` | `"de"` | Sprache für die Transkription |
| `whisper_device` | `"auto"` | `"cpu"`, `"cuda"` oder `"auto"` |
| `tts_engine` | `"piper"` | `"piper"`, `"system"` oder `"elevenlabs"` |
| `piper_voice` | `"de_DE-kerstin-low"` | Piper-Stimme |
| `windows_voice` | `""` | Windows-SAPI-Stimmenname |
| `internet_enabled` | `true` | Web-Suche und Nachrichten aktivieren |
| `news_topic` | `""` | Thema für Nachrichten (leer = allgemein) |
| `max_tokens` | `4096` | Maximale Token-Antwortlänge |
| `temperature` | `0.7` | Kreativität der Antworten |
| `reasoning_timeout` | `60` | Timeout für LLM-Anfragen in Sekunden |
| `input_device_name` | `"Mikrofon (LCS_USB_AUDIO)"` | Audiogerät nach Name (optional) |
| `input_device_index` | `null` | Audiogerät nach Index (optional) |

## Projektstruktur

```
TalkLocAI/
├── run_voice_ai.py              # Einstiegspunkt mit GUI / CLI-Auswahl
├── generate_project_summary.py  # Erzeugt PROJECT_SUMMARY.md
├── pyproject.toml               # Build-System und Metadaten
├── voice_ai/
│   ├── __init__.py
│   ├── main.py                  # Hauptklasse VoiceAI (Pipeline)
│   ├── summary.py               # Auto-Generierung der Projektzusammenfassung
│   ├── web_search.py            # DuckDuckGo-Suche & Google News RSS
│   ├── llm/
│   │   └── __init__.py          # LLM-Provider (lokal & OpenRouter)
│   ├── stt/
│   │   └── __init__.py          # Whisper-Spracherkennung (faster-whisper)
│   ├── tts/
│   │   └── __init__.py          # TTS-Engines (Piper, System, ElevenLabs)
│   ├── memory/
│   │   └── __init__.py          # Kurzzitierter Dialog-Speicher
│   ├── prompts/
│   │   └── __init__.py          # System- und Konversations-Prompts
│   └── config/
│       ├── config.example.json   # Vorlage für die Konfiguration
│       └── config.json           # Lokale Konfiguration (nicht committen)
├── voice_ai/requirements.txt     # Python-Abhängigkeiten
└── .env.example                  # Vorlage für Umgebungsvariablen
```

## Datenschutz & Sicherheit

- **Keine API-Keys committen.** Lege `.env` oder `voice_ai\config\config.json` in `.gitignore` – beide Dateien sind bereits ausgeschlossen.
- **Lokale Verarbeitung.** Spracherkennung (Whisper) und TTS (Piper/System) laufen standardmäßig lokal auf deinem Rechner.
- **Externe Dienste.** Bei Nutzung von OpenRouter werden deine Texteingaben an OpenRouter übermittelt. Bei Nutzung von ElevenLabs wird der Antworttext zur Sprachsynthese an ElevenLabs übermittelt. Die Websuche nutzt DuckDuckGo (HTML) und Google News RSS.
- **State-Dateien.** `voice_ai/state.json` und temporäre `.wav`-Dateien werden lokal erzeugt und nicht ins Repository aufgenommen.

## GitHub / Entwicklung

### Klonen und einrichten

```powershell
git clone https://github.com/<benutzer>/TalkLocAI.git
cd TalkLocAI
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
pip install pytest black flake8
```

### Nützliche Befehle

```powershell
python run_voice_ai.py --text
pytest
```

### Committen

```powershell
git add .
git commit -m "Beschreibung der Änderung"
git push
```

Stelle sicher, dass keine `.env`, `config.json`, `state.json` oder `.wav`-Dateien versehentlich committed werden.
