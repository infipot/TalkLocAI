"""Automatische Verwaltung von PROJECT_SUMMARY.md."""
from __future__ import annotations

import datetime, hashlib, os, subprocess, sys
from pathlib import Path


HEADER = "<!-- AUTO-GENERATED – do not edit directly -->"

MD_FILES = [
    "generate_project_summary.py", "run_voice_ai.py",
    "voice_ai/main.py", "voice_ai/llm/__init__.py", "voice_ai/tts/__init__.py",
    "voice_ai/stt/__init__.py", "voice_ai/summary.py", "voice_ai/memory/__init__.py",
    "voice_ai/prompts/__init__.py", "voice_ai/web_search.py",
    "voice_ai/config/config.json",
]

FILE_ROLES: dict[str, str] = {
    "generate_project_summary.py": "Erzeugt oder aktualisiert PROJECT_SUMMARY.md.",
    "run_voice_ai.py": "Einstiegspunkt: startet VoiceAI.",
    "voice_ai/main.py": "Kernklasse VoiceAI.",
    "voice_ai/llm/__init__.py": "LLM-Provider-Logik.",
    "voice_ai/tts/__init__.py": "TTS-Engines.",
    "voice_ai/stt/__init__.py": "Whisper-STT.",
    "voice_ai/summary.py": "Auto-Generierung von PROJECT_SUMMARY.md.",
    "voice_ai/memory/__init__.py": "Dialog-Speicher.",
    "voice_ai/prompts/__init__.py": "System- und Konversations-Prompts.",
    "voice_ai/web_search.py": "Websuche und Nachrichten.",
    "voice_ai/config/config.json": "Zentrale Konfiguration.",
}


def _md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest() if p.exists() else ""


def _check_outdated() -> bool:
    root = Path(__file__).resolve().parent.parent
    latest: float | None = None
    for rel in MD_FILES:
        mtime = (root / rel).stat().st_mtime if (root / rel).exists() else 0
        if latest is None or mtime > latest:
            latest = mtime
    if latest is None:
        return True
    return latest > _get_summary_mtime(root)


def _get_summary_mtime(root: Path) -> float:
    p = root / "PROJECT_SUMMARY.md"
    return p.stat().st_mtime if p.exists() else 0.0


def generate_project_summary() -> str:
    root = Path(__file__).resolve().parent.parent
    lines: list[str] = [
        "# KI Freund – Projektzusammenfassung",
        "",
        "*Automatisch generiert. Nicht manuell bearbeiten.*",
        "",
        "## Inhaltsverzeichnis",
        "",
    ]
    for rel in MD_FILES:
        label = rel.replace("voice_ai/", "").replace("__init__", "").replace("/", " · ").replace(".py", "").replace(".json", "")
        if not label: continue
        anchor = label.replace(" ", "-").lower()
        lines.append(f"- [{label}](#{anchor})")
    lines += [
        "",
        "## Funktionsweise",
        "",
        "> Audio → STT → LLM → TTS (siehe Pipeline in `main.py`)",
        "",
    ]
    for rel in MD_FILES:
        f = root / rel
        if not f.exists(): continue
        label = rel.replace("voice_ai/", "").replace("__init__", "").replace("/", " · ").replace(".py", "").replace(".json", "")
        if not label: continue
        lines += [f"### {label}", "", f"`{rel}` — {FILE_ROLES.get(rel, '')}", "",
                  f"```python", f"# {rel}"]
        for ln in f.read_text(encoding="utf-8").splitlines()[:80]:
            lines.append(ln)
        lines += ["```", ""]
    return "\n".join(lines)


def ensure_project_summary(force: bool = False) -> bool:
    root = Path(__file__).resolve().parent.parent
    dst = root / "PROJECT_SUMMARY.md"
    if not force and not _check_outdated():
        return False
    content = generate_project_summary()
    dst.write_text(content, encoding="utf-8")
    return True
