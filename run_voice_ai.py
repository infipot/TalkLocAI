"""Einstiegspunkt: Provider-Auswahl (GUI) und Start von VoiceAI."""

import sys
import os
import json
import time
import urllib.request
from urllib.parse import urlparse, urlunparse

messagebox = None
try:
    import tkinter as tk
    from tkinter import messagebox
except ImportError:
    tk = None
    messagebox = None

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
        "openrouter_model_label": "OpenRouter model: {model}",
        "openrouter_fallback": "If no local model is loaded, OpenRouter will be used.",
        "whisper_label": "Whisper Model (STT):",
        "tts_label": "TTS Engine:",
        "piper_label": "Piper Voice:",
        "no_piper_voices": "(No Piper voices found)",
        "piper_unavailable": "(Piper not available)",
        "windows_label": "Windows Voice:",
        "no_sapi_voices": "(No SAPI voices found)",
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
        "openrouter_model_label": "OpenRouter Modell: {model}",
        "openrouter_fallback": "Falls lokal kein Modell geladen ist, wird OpenRouter verwendet.",
        "whisper_label": "Whisper Modell (STT):",
        "tts_label": "TTS Engine:",
        "piper_label": "Piper Stimme:",
        "no_piper_voices": "(Keine Piper Stimmen gefunden)",
        "piper_unavailable": "(Piper nicht verfuegbar)",
        "windows_label": "Windows Stimme:",
        "no_sapi_voices": "(Keine SAPI Stimmen gefunden)",
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


def _probe_local_lm(base_url: str):
    candidates = [_normalize(base_url)]
    try:
        parsed = urlparse(base_url)
        h = parsed.hostname or '127.0.0.1'
        pt = parsed.port
        if h in ('127.0.0.1', 'localhost') and pt and pt != 1234:
            candidates.append(urlunparse(parsed._replace(netloc=f"{h}:1234", path='/')))
    except Exception:
        pass
    for ep in ["/api/v1/models", "/v1/models", "/models"]:
        for base in candidates:
            base = _normalize(base)
            try:
                url = f"{base.rstrip('/')}/{ep.lstrip('/')}"
                with urllib.request.urlopen(url, timeout=2) as resp:
                    d = json.loads(resp.read().decode('utf-8'))
                items = d.get("data", d.get("models", [d]))
                cnt = len(items) if isinstance(items, list) else 1
                cur = None
                for it in (items if isinstance(items, list) else [items]):
                    if isinstance(it, dict):
                        if it.get("selected_variant"):
                            cur = it["selected_variant"]; break
                        li = it.get("loaded_instances", [])
                        if li:
                            cur = it.get("key") or it.get("id"); break
                if cnt > 0:
                    return True, cnt, cur or "Unbekannt", url
            except Exception:
                continue
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
        avail, cnt, cur_mod, src = _probe_local_lm(local_base)
        return ("local" if avail and prov != "openrouter" else "openrouter"), local_base

    root = tk.Tk()
    lang_var = tk.StringVar(value=app_language)
    root.title(_txt(lang_var, "window_title"))
    root.geometry("550x500")
    root.resizable(False, False)
    sel = tk.StringVar(value="local")
    url_var = tk.StringVar(value=local_base)
    whisper_var = tk.StringVar(value=whisper_model)
    voice_var = tk.StringVar(value=windows_voice)
    tts_engine_var = tk.StringVar(value=tts_engine)
    piper_voice_var = tk.StringVar(value=piper_voice)
    f = tk.Frame(root, padx=16, pady=16); f.pack(fill="both", expand=True)
    tk.Label(f, text=_txt(lang_var, "choose_mode"), font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
    tk.Radiobutton(f, text=_txt(lang_var, "local_radio"), variable=sel, value="local").pack(anchor="w", pady=(8, 0))
    tk.Radiobutton(f, text=_txt(lang_var, "openrouter_radio"), variable=sel, value="openrouter").pack(anchor="w", pady=(2, 16))
    tk.Label(f, text=_txt(lang_var, "local_url_label")).pack(anchor="w")
    tk.Entry(f, textvariable=url_var, width=52).pack(anchor="w", pady=(0, 8))

    status_label = tk.Label(f, text="", fg="gray")
    status_label.pack(anchor="w")

    def update_status():
        url = url_var.get().strip() or local_base
        avail, cnt, cur_mod, src = _probe_local_lm(url)
        if avail:
            if cur_mod and cur_mod != "Unbekannt":
                st = _txt(lang_var, "status_available", model=cur_mod)
                fg = "green"
            else:
                st = _txt(lang_var, "status_no_model")
                fg = "orange"
        else:
            st = _txt(lang_var, "status_unavailable")
            fg = "red"
        status_label.config(text=st, fg=fg)
        return avail

    tk.Label(f, text=_txt(lang_var, "openrouter_model_label", model=openrouter_model), fg="blue").pack(anchor="w", pady=(8, 0))
    tk.Label(f, text=_txt(lang_var, "openrouter_fallback"), fg="gray", font=("TkDefaultFont", 8)).pack(anchor="w")

    tk.Label(f, text="App / Conversation Language:").pack(anchor="w", pady=(8, 0))
    lang_frame = tk.Frame(f)
    lang_frame.pack(anchor="w")
    lang_options = ["en", "de"]
    lang_menu = tk.OptionMenu(lang_frame, lang_var, *lang_options)
    lang_menu.pack(side="left")

    tk.Label(f, text=_txt(lang_var, "whisper_label")).pack(anchor="w", pady=(8, 0))
    whisper_frame = tk.Frame(f)
    whisper_frame.pack(anchor="w")
    whisper_options = ["auto", "tiny", "base", "small", "medium", "large", "large-v2", "large-v3"]
    whisper_menu = tk.OptionMenu(whisper_frame, whisper_var, *whisper_options)
    whisper_menu.pack(side="left")

    if os.name == "nt":
        tk.Label(f, text=_txt(lang_var, "tts_label")).pack(anchor="w", pady=(8, 0))
        tts_frame = tk.Frame(f)
        tts_frame.pack(anchor="w")
        tts_options = ["piper", "system"]
        tts_menu = tk.OptionMenu(tts_frame, tts_engine_var, *tts_options)
        tts_menu.pack(side="left")

        def update_voice_selector():
            assert tk is not None
            for w in voice_selector_frame.winfo_children():
                w.destroy()
            engine = tts_engine_var.get()
            if engine == "piper":
                tk.Label(voice_selector_frame, text=_txt(lang_var, "piper_label")).pack(side="left")
                try:
                    from voice_ai.tts import _get_piper_voices
                    piper_voices = _get_piper_voices()
                    if piper_voices:
                        piper_var = tk.StringVar(value=piper_voice_var.get() or piper_voices[0])
                        piper_menu = tk.OptionMenu(voice_selector_frame, piper_var, *piper_voices)
                        piper_menu.pack(side="left")
                        def _save_piper(*args):
                            piper_voice_var.set(piper_var.get())
                        piper_var.trace_add("write", _save_piper)
                    else:
                        tk.Label(voice_selector_frame, text=_txt(lang_var, "no_piper_voices"), fg="gray").pack(side="left")
                except Exception:
                    tk.Label(voice_selector_frame, text=_txt(lang_var, "piper_unavailable"), fg="gray").pack(side="left")
            elif engine == "system":
                tk.Label(voice_selector_frame, text=_txt(lang_var, "windows_label")).pack(side="left")
                try:
                    from voice_ai.tts import _get_windows_sapi_voices
                    sapi_voices = _get_windows_sapi_voices()
                    if sapi_voices:
                        voice_options = [""] + sapi_voices
                        voice_menu = tk.OptionMenu(voice_selector_frame, voice_var, *voice_options)
                        voice_menu.pack(side="left")
                    else:
                        tk.Label(voice_selector_frame, text=_txt(lang_var, "no_sapi_voices"), fg="gray").pack(side="left")
                except Exception:
                    tk.Label(voice_selector_frame, text=_txt(lang_var, "sapi_unavailable"), fg="gray").pack(side="left")

        voice_selector_frame = tk.Frame(f)
        voice_selector_frame.pack(anchor="w", pady=(4, 0))
        tts_engine_var.trace_add("write", lambda *a: update_voice_selector())
        update_voice_selector()

    def go():
        url = url_var.get().strip() or local_base
        if sel.get() == "local":
            av, _, _, _ = _probe_local_lm(url)
            if not av and messagebox:
                messagebox.showwarning("Voice AI", _txt(lang_var, "local_not_found"))
                return
        cfg = _load_config()
        cfg["whisper_model"] = whisper_var.get()
        cfg["tts_engine"] = tts_engine_var.get()
        cfg["piper_voice"] = piper_voice_var.get()
        cfg["app_language"] = lang_var.get()
        cfg["whisper_language"] = lang_var.get()
        if os.name == "nt":
            cfg["windows_voice"] = voice_var.get()
        try:
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=4)
        except Exception:
            pass
        root.destroy()
    
    btn_frame = tk.Frame(f)
    btn_frame.pack(anchor="e", pady=(14, 0))
    tk.Button(btn_frame, text=_txt(lang_var, "refresh"), command=update_status, width=10).pack(side="right", padx=(5, 0))
    tk.Button(btn_frame, text=_txt(lang_var, "start"), command=go, width=14, bg="#2e7d32", fg="white").pack(side="right")
    
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


