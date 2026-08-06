"""Einstiegspunkt: Provider-Auswahl (GUI) und Start von VoiceAI."""

import sys
import os
import json
import time
import urllib.request
from urllib.parse import urlparse, urlunparse
from typing import TYPE_CHECKING

messagebox = None
try:
    import tkinter as tk
    from tkinter import messagebox
except ImportError:
    tk = None
    messagebox = None

if TYPE_CHECKING:
    from tkinter import Widget
else:
    Widget = object

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
VOICE_AI_DIR = os.path.join(ROOT_DIR, 'voice_ai')
if ROOT_DIR not in sys.path:
    sys.path.insert(0, VOICE_AI_DIR)
    sys.path.insert(0, ROOT_DIR)

from voice_ai.main import VoiceAI

DEFAULT_LOCAL_BASE_URL = "http://127.0.0.1:8080"
CONFIG_PATH = os.path.join(VOICE_AI_DIR, 'config', 'config.json')


def _get_app_language() -> str:
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f).get("app_language", "en") or "en"
    except Exception:
        return "en"


_GUI = {
    "en": {
        "window_title": "Voice AI Startup",
        "choose_mode": "Choose AI Mode:",
        "local_radio": "Local LM Studio",
        "openrouter_radio": "OpenRouter (remote)",
        "local_url_label": "Local LM Studio URL:",
        "status_available": "✓ LM Studio available, model: {model}",
        "status_no_model": "⚠ LM Studio available, but NO model loaded.",
        "status_unavailable": "✗ Local LM Studio not available.",
        "status_unavailable_fallback": "✗ Local LM Studio not available. Configured model: {model}",
        "openrouter_model_label": "OpenRouter model: {model}",
        "openrouter_fallback": "If no local model is loaded, OpenRouter will be used.",
        "ui_language_label": "UI Language:",
        "whisper_label": "Whisper Model (STT):",
        "tts_label": "TTS Provider:",
        "piper_label": "Piper Voice:",
        "no_piper_voices": "(No Piper voices found)",
        "piper_unavailable": "(Piper not available)",
        "windows_label": "Windows Voice:",
        "no_sapi_voices": "(No Windows voices found)",
        "sapi_unavailable": "(SAPI not available)",
        "local_not_found": "Local LM Studio not found.",
        "summary_warn": "Warning: Project summary could not be updated: {e}",
        "refresh": "Refresh",
        "start": "Start",
    },
    "de": {
        "window_title": "Voice AI Startup",
        "choose_mode": "Wähle den KI-Modus:",
        "local_radio": "Local LM Studio (lokal)",
        "openrouter_radio": "OpenRouter (remote)",
        "local_url_label": "Lokale LM-Studio-URL:",
        "status_available": "✓ LM Studio verfuegbar, Modell: {model}",
        "status_no_model": "⚠ LM Studio verfuegbar, aber KEIN Modell geladen.",
        "status_unavailable": "✗ Lokales LM Studio nicht verfuegbar.",
        "status_unavailable_fallback": "✗ Lokales LM Studio nicht verfuegbar. Konfiguriertes Modell: {model}",
        "openrouter_model_label": "OpenRouter Modell: {model}",
        "openrouter_fallback": "Falls lokal kein Modell geladen ist, wird OpenRouter verwendet.",
        "ui_language_label": "Sprache der Benutzeroberfläche:",
        "whisper_label": "Whisper Modell (STT):",
        "tts_label": "TTS-Anbieter:",
        "piper_label": "Piper Stimme:",
        "no_piper_voices": "(Keine Piper Stimmen gefunden)",
        "piper_unavailable": "(Piper nicht verfuegbar)",
        "windows_label": "Windows Stimme:",
        "no_sapi_voices": "(Keine Windows Stimmen gefunden)",
        "sapi_unavailable": "(SAPI nicht verfuegbar)",
        "local_not_found": "Lokales LM Studio nicht gefunden.",
        "summary_warn": "Warnung: Projektzusammenfassung konnte nicht aktualisiert werden: {e}",
        "refresh": "Aktualisieren",
        "start": "Starten",
    },
}


def _txt(lang_var, key, **kwargs) -> str:
    lang = lang_var.get() if hasattr(lang_var, "get") else lang_var
    template = _GUI.get(lang, _GUI["en"]).get(key, _GUI["en"].get(key, key))
    assert template is not None
    try:
        return template.format(**kwargs)
    except Exception:
        return template


try:
    from voice_ai.summary import ensure_project_summary
    ensure_project_summary()
except Exception as e:
    print(_txt(_get_app_language(), "summary_warn", e=e))


def _load_config() -> dict:
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _normalize(base_url: str) -> str:
    p = urlparse(base_url.strip())
    path = p.path.rstrip('/')
    for prefix in ('/api/v1', '/api'):
        if path.endswith(prefix):
            path = path[:-len(prefix)]
            break
    return urlunparse(p._replace(path=path or '/'))


def _probe_local_lm(base_url: str, fallback_model: str = ""):
    candidates = [_normalize(base_url)]
    try:
        parsed = urlparse(base_url)
        h = parsed.hostname or '127.0.0.1'
        pt = parsed.port
        if h in ('127.0.0.1', 'localhost') and pt and pt != 1234:
            candidates.append(urlunparse(parsed._replace(netloc=f"{h}:1234", path='/')))
    except Exception:
        pass
    for ep in ["/api/status", "/api/v1/models", "/v1/models", "/models"]:
        for base in candidates:
            base = _normalize(base)
            try:
                url = f"{base.rstrip('/')}/{ep.lstrip('/')}"
                with urllib.request.urlopen(url, timeout=2) as resp:
                    d = json.loads(resp.read().decode('utf-8'))
                if ep == "/api/status":
                    model_info = d.get("model") or d.get("Model") or {}
                    if isinstance(model_info, dict):
                        loaded = (
                            model_info.get("loaded_model")
                            or model_info.get("loadedModel")
                            or model_info.get("id")
                            or model_info.get("key")
                        )
                        if loaded:
                            return True, 1, loaded, url
                    if isinstance(d.get("model"), str):
                        return True, 1, d["model"], url
                else:
                    items = d.get("data", d.get("models", [d]))
                    if not items:
                        continue
                    cnt = len(items) if isinstance(items, list) else 1
                    cur = None
                    if isinstance(items, list):
                        for it in items:
                            if isinstance(it, dict):
                                li = it.get("loaded_instances")
                                if li and li > 0:
                                    cur = it.get("id") or it.get("key")
                                    break
                        if cur is None:
                            first = next((it for it in items if isinstance(it, dict)), None)
                            if first:
                                cur = first.get("id") or first.get("key")
                    elif isinstance(items, dict):
                        cur = items.get("id") or items.get("key")
                    if cur:
                        return True, cnt, cur, url
            except Exception:
                continue
    if fallback_model:
        return False, 0, fallback_model, ""
    return False, 0, "", ""


def _choose_provider() -> tuple[str, str]:
    cfg = _load_config()
    app_language = cfg.get("app_language", "en")
    local_base = _normalize(cfg.get("local_lm_base_url", DEFAULT_LOCAL_BASE_URL))
    prov = cfg.get("llm_provider", "auto").lower().strip()
    openrouter_model = cfg.get("openrouter_model", "openrouter/free")
    whisper_model = cfg.get("whisper_model", "auto")
    windows_voice = cfg.get("windows_voice", "")

    tts_engine = cfg.get("tts_engine", "system")
    piper_voice = cfg.get("piper_voice", "")

    if tk is None:
        avail, cnt, cur_mod, src = _probe_local_lm(local_base, fallback_model=cfg.get("local_lm_model", "").strip())
        return ("local" if avail and prov != "openrouter" else "openrouter"), local_base

    root = tk.Tk()  # type: ignore[attr-defined]
    lang_var = tk.StringVar(value=app_language)  # type: ignore[attr-defined]
    root.title(_txt(lang_var, "window_title"))
    root.geometry("550x500")
    root.resizable(False, False)
    sel = tk.StringVar(value="local")  # type: ignore[attr-defined]
    url_var = tk.StringVar(value=local_base)  # type: ignore[attr-defined]
    whisper_var = tk.StringVar(value=whisper_model)  # type: ignore[attr-defined]
    voice_var = tk.StringVar(value=windows_voice)  # type: ignore[attr-defined]
    tts_engine_var = tk.StringVar(value=tts_engine)  # type: ignore[attr-defined]
    piper_voice_var = tk.StringVar(value=piper_voice)  # type: ignore[attr-defined]
    f = tk.Frame(root, padx=16, pady=16); f.pack(fill="both", expand=True)  # type: ignore[attr-defined]

    widget_refs: list[tuple[Widget, str, dict]] = []

    def _set_text(w: Widget, key: str, **kwargs):
        w.config(text=_txt(lang_var, key, **kwargs))  # type: ignore[call-arg]

    def _refresh_gui():
        for w, key, kwargs in widget_refs:
            _set_text(w, key, **kwargs)

    lang_var.trace_add("write", lambda *_: _refresh_gui())

    def _add_label(parent, key, **kwargs):
        w = tk.Label(parent, text=_txt(lang_var, key, **kwargs))  # type: ignore[attr-defined]
        widget_refs.append((w, key, kwargs))
        return w

    def _add_button(parent, key, **kwargs):
        w = tk.Button(parent, text=_txt(lang_var, key), **kwargs)  # type: ignore[attr-defined]
        widget_refs.append((w, key, {}))
        return w

    tk.Label(f, text=_txt(lang_var, "choose_mode"), font=("TkDefaultFont", 12, "bold")).pack(anchor="w")  # type: ignore[attr-defined]
    tk.Radiobutton(f, text=_txt(lang_var, "local_radio"), variable=sel, value="local").pack(anchor="w", pady=(8, 0))  # type: ignore[attr-defined]
    tk.Radiobutton(f, text=_txt(lang_var, "openrouter_radio"), variable=sel, value="openrouter").pack(anchor="w", pady=(2, 16))  # type: ignore[attr-defined]
    _add_label(f, "local_url_label").pack(anchor="w")
    tk.Entry(f, textvariable=url_var, width=52).pack(anchor="w", pady=(0, 8))  # type: ignore[attr-defined]

    status_label = tk.Label(f, text="", fg="gray")  # type: ignore[attr-defined]
    status_label.pack(anchor="w")

    def update_status():
        url = url_var.get().strip() or local_base
        cfg = _load_config()
        fallback_model = cfg.get("local_lm_model", "").strip()
        avail, cnt, cur_mod, src = _probe_local_lm(url, fallback_model=fallback_model)
        if avail:
            if cur_mod and cur_mod != "Unbekannt":
                st = _txt(lang_var, "status_available", model=cur_mod)
                fg = "green"
            else:
                st = _txt(lang_var, "status_no_model")
                fg = "orange"
        else:
            if fallback_model:
                st = _txt(lang_var, "status_unavailable_fallback", model=fallback_model)
                fg = "orange"
            else:
                st = _txt(lang_var, "status_unavailable")
                fg = "red"
        status_label.config(text=st, fg=fg)  # type: ignore[call-arg]
        return avail

    _add_label(f, "openrouter_model_label", model=openrouter_model, fg="blue").pack(anchor="w", pady=(8, 0))
    _add_label(f, "openrouter_fallback", fg="gray", font=("TkDefaultFont", 8)).pack(anchor="w")

    _add_label(f, "ui_language_label").pack(anchor="w", pady=(8, 0))
    lang_frame = tk.Frame(f)  # type: ignore[attr-defined]
    lang_frame.pack(anchor="w")
    lang_options = ["en", "de"]
    lang_menu = tk.OptionMenu(lang_frame, lang_var, *lang_options)  # type: ignore[attr-defined]
    lang_menu.pack(side="left")

    _add_label(f, "whisper_label").pack(anchor="w", pady=(8, 0))
    whisper_frame = tk.Frame(f)  # type: ignore[attr-defined]
    whisper_frame.pack(anchor="w")
    whisper_options = ["auto", "tiny", "base", "small", "medium", "large", "large-v2", "large-v3"]
    whisper_menu = tk.OptionMenu(whisper_frame, whisper_var, *whisper_options)  # type: ignore[attr-defined]
    whisper_menu.pack(side="left")

    if os.name == "nt":
        _add_label(f, "tts_label").pack(anchor="w", pady=(8, 0))
        tts_frame = tk.Frame(f)  # type: ignore[attr-defined]
        tts_frame.pack(anchor="w")
        tts_options = ["windows", "piper"]
        tts_menu = tk.OptionMenu(tts_frame, tts_engine_var, *tts_options)  # type: ignore[attr-defined]
        tts_menu.pack(side="left")

        voice_selector_frame = tk.Frame(f)  # type: ignore[attr-defined]
        voice_selector_frame.pack(anchor="w", pady=(4, 0))

        def update_voice_selector():
            for w in voice_selector_frame.winfo_children():
                w.destroy()
            engine = tts_engine_var.get()
            if engine == "piper":
                _add_label(voice_selector_frame, "piper_label").pack(side="left")
                try:
                    from voice_ai.tts import get_piper_voices
                    piper_voices = get_piper_voices()
                    if piper_voices:
                        piper_var = tk.StringVar(value=piper_voice_var.get() or piper_voices[0])  # type: ignore[attr-defined]
                        piper_menu = tk.OptionMenu(voice_selector_frame, piper_var, *piper_voices)  # type: ignore[attr-defined]
                        piper_menu.pack(side="left")
                        def _save_piper(*args):
                            piper_voice_var.set(piper_var.get())
                        piper_var.trace_add("write", _save_piper)
                    else:
                        _add_label(voice_selector_frame, "no_piper_voices", fg="gray").pack(side="left")
                except Exception:
                    _add_label(voice_selector_frame, "piper_unavailable", fg="gray").pack(side="left")
            elif engine == "windows":
                _add_label(voice_selector_frame, "windows_label").pack(side="left")
                try:
                    from voice_ai.tts import get_windows_voices
                    sapi_voices = get_windows_voices()
                    if sapi_voices:
                        voice_options = [""] + [v[0] for v in sapi_voices]
                        voice_menu = tk.OptionMenu(voice_selector_frame, voice_var, *voice_options)  # type: ignore[attr-defined]
                        voice_menu.pack(side="left")
                    else:
                        _add_label(voice_selector_frame, "no_sapi_voices", fg="gray").pack(side="left")
                except Exception:
                    _add_label(voice_selector_frame, "sapi_unavailable", fg="gray").pack(side="left")

        tts_engine_var.trace_add("write", lambda *a: update_voice_selector())
        update_voice_selector()

    def go():
        url = url_var.get().strip() or local_base
        if sel.get() == "local":
            cfg = _load_config()
            fallback_model = cfg.get("local_lm_model", "").strip()
            av, _, _, _ = _probe_local_lm(url, fallback_model=fallback_model)
            if not av and not fallback_model and messagebox:
                messagebox.showwarning("Voice AI", _txt(lang_var, "local_not_found"))
                return
        cfg = _load_config()
        cfg["whisper_model"] = whisper_var.get()
        cfg["tts_engine"] = tts_engine_var.get()
        cfg["piper_voice"] = piper_voice_var.get()
        cfg["app_language"] = lang_var.get()
        if os.name == "nt":
            cfg["windows_voice"] = voice_var.get()
        try:
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=4)
        except Exception:
            pass
        root.destroy()

    btn_frame = tk.Frame(f)  # type: ignore[attr-defined]
    btn_frame.pack(anchor="e", pady=(14, 0))
    _add_button(btn_frame, "refresh", command=update_status, width=10).pack(side="right", padx=(5, 0))
    _add_button(btn_frame, "start", command=go, width=14, bg="#2e7d32", fg="white").pack(side="right")

    root.protocol("WM_DELETE_WINDOW", lambda: root.destroy())

    update_status()
    root.mainloop()
    return sel.get(), url_var.get().strip() or local_base


def _run_assistant(provider: str, local_url: str) -> int:
    if provider == "local" and local_url:
        cfg = _load_config()
        if cfg.get("local_lm_base_url") != local_url:
            cfg["local_lm_base_url"] = local_url
            try:
                with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                    json.dump(cfg, f, indent=4)
            except Exception:
                pass
    asst = VoiceAI(provider=provider)
    if len(sys.argv) > 1 and sys.argv[1] == "--text":
        try:
            asst.text_mode()
        except KeyboardInterrupt:
            print("Goodbye!")
    else:
        try:
            while not asst._shutdown.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            print("Goodbye!")
        finally:
            asst.shutdown()
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--text":
        sys.exit(_run_assistant("auto", DEFAULT_LOCAL_BASE_URL))
    prov, url = _choose_provider()
    sys.exit(_run_assistant(prov, url))


