"""VoiceAI – Hauptklasse."""
from __future__ import annotations

import json, os, queue, sys, tempfile, threading, time
from pathlib import Path

import numpy as np
import sounddevice as sd

try:
    import soundfile as sf
except ImportError as e:
    raise ImportError("pip install soundfile") from e

from .stt import STT
from .tts import TTS
from .llm import LLM
from .memory import Memory
from .prompts import CONVERSATION_PROMPT, get_conversation_prompt

THRESHOLD = 0.02
MIN_START = 3
SIL_CHUNKS = 8
SR = 16000
BLOCK_MS = 100

_MSG = {
    "en": {
        "ready": "[ ready – speak ]",
        "nothing_recognized": "  (nothing recognized)\n",
        "you": ">>> You: {text}",
        "thinking": "  Thinking…",
        "llm_error": "  [LLM ERROR] {e}",
        "error": "[ERROR] {e}",
        "textmode_header": "[Text mode – {date}]",
        "input_prompt": "\nYou: ",
        "goodbye": "\nGoodbye!",
        "state_read_failed": "[WARN] State read failed: {e}",
        "state_save_failed": "[WARN] State save failed: {e}",
    },
    "de": {
        "ready": "[ bereit – sprich ]",
        "nothing_recognized": "  (nichts erkannt)\n",
        "you": ">>> Du: {text}",
        "thinking": "  Denke…",
        "llm_error": "  [LLM FEHLER] {e}",
        "error": "[FEHLER] {e}",
        "textmode_header": "[Textmodus – {date}]",
        "input_prompt": "\nDu: ",
        "goodbye": "\nTschüss!",
        "state_read_failed": "[WARN] State lesen fehlgeschlagen: {e}",
        "state_save_failed": "[WARN] State speichern: {e}",
    },
}


def _t(self, key, **kwargs):
    lang = getattr(self, "app_language", "en") or "en"
    template = _MSG.get(lang, _MSG["en"]).get(key, _MSG["en"].get(key, key))
    try:
        return template.format(**kwargs)
    except Exception:
        return template


class VoiceAI:
    def __init__(self, provider="auto", config_path=None):
        cfg = config_path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                          "voice_ai", "config", "config.json")
        # Try to read config JSON so we can set an explicit input device if provided
        conf = {}
        try:
            with open(cfg, 'r', encoding='utf-8') as _f:
                conf = json.load(_f)
        except Exception:
            conf = {}
        # Allow configuring input device by index or by name in config (input_device_index or input_device_name)
        try:
            input_idx = conf.get("input_device_index")
            input_name = conf.get("input_device_name")
            def _set_input_device_index(index):
                try:
                    cur = sd.default.device
                    out_idx = None
                    if isinstance(cur, tuple) and len(cur) == 2:
                        out_idx = cur[1]
                    # If cur is an int or None, leave out_idx as None to let Output use system default
                    sd.default.device = (int(index), out_idx)
                    print(f"[INFO] sounddevice default input device set to index {int(index)} (output preserved)")
                except Exception as _e:
                    print(f"[WARN] invalid input_device_index in config: {_e}")

            if input_idx is not None:
                _set_input_device_index(input_idx)
            elif input_name:
                try:
                    devs = sd.query_devices()
                    matched = None
                    for i, d in enumerate(devs):
                        name = d.get('name') if isinstance(d, dict) else getattr(d, 'name', None)
                        if name and input_name.lower() in str(name).lower():
                            matched = i
                            break
                    if matched is not None:
                        # Preserve output device if set
                        try:
                            cur = sd.default.device
                            out_idx = cur[1] if isinstance(cur, tuple) and len(cur) == 2 else None
                        except Exception:
                            out_idx = None
                        try:
                            sd.default.device = (matched, out_idx)
                            print(f"[INFO] sounddevice default input device set by name '{input_name}' -> index {matched} (output preserved)")
                        except Exception as _e:
                            print(f"[WARN] could not set input device by index: {_e}")
                    else:
                        print(f"[WARN] input_device_name '{input_name}' not found among audio devices")
                except Exception as _e:
                    print(f"[WARN] could not query audio devices: {_e}")
        except Exception as _e:
            print(f"[WARN] could not apply input device from config: {_e}")

        self.stt = STT(cfg)
        self.tts = TTS(cfg)
        self.llm = LLM(cfg, provider=provider)
        self.memory = Memory()
        self.app_language = conf.get("app_language", "en")

        state = self._load_state()
        if state:
            if provider == "auto":
                self.llm.provider = state.get("provider", self.llm.provider)
            if self.llm.provider == "local":
                self.llm.local_model = state.get("local_model") if state.get("local_model") else None
            elif self.llm.provider == "openrouter":
                self.llm.openrouter_model = state.get("openrouter_model") if state.get("openrouter_model") else None
            self.memory.history = state.get("memory_history", [])

        self.running = True
        self.speaking = False
        self._shutdown = threading.Event()
        self.q = queue.Queue()
        # Counter for detecting sustained speech to interrupt TTS (prevents false positives)
        self._tts_interrupt_run = 0

        threading.Thread(target=self._audio_worker, daemon=True).start()
        threading.Thread(target=self._loop, daemon=True).start()

    # ── State ─────────────────────────────────────────────────────

    def _load_state(self):
        p = Path(__file__).resolve().parent / "state.json"
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception as e:
                print(_t(self, "state_read_failed", e=e))
        return None

    def shutdown(self):
        self.running = False
        self._shutdown.set()
        try:
            p = Path(__file__).resolve().parent / "state.json"
            json.dump({
                "provider": self.llm.provider,
                "local_model": self.llm.local_model if self.llm.provider == "local" else None,
                "openrouter_model": self.llm.openrouter_model if self.llm.provider == "openrouter" else None,
            }, open(p, "w", encoding="utf-8"), indent=2)
        except Exception as e:
            print(_t(self, "state_save_failed", e=e))

    # ── Audio ─────────────────────────────────────────────────────

    def _audio_worker(self):
        bs = int(SR * BLOCK_MS / 1000)
        def cb(indata, _f, _t, _s):
            del _f, _t, _s
            if not self.running:
                return
            # If TTS playback is active and the user speaks, interrupt playback immediately
            try:
                vol = float(np.max(np.abs(indata)))
            except Exception:
                vol = 0.0
            try:
                tts_playing = hasattr(self, 'tts') and getattr(self.tts, '_play_thr', None) is not None
            except Exception:
                tts_playing = False
            # Update sustained-speech counter: only interrupt if we see MIN_START consecutive loud chunks
            try:
                if vol >= THRESHOLD:
                    self._tts_interrupt_run = getattr(self, '_tts_interrupt_run', 0) + 1
                else:
                    self._tts_interrupt_run = 0
            except Exception:
                self._tts_interrupt_run = 0

            if tts_playing and self._tts_interrupt_run >= MIN_START:
                try:
                    print('[INFO] Sustained speech detected during playback — interrupting TTS')
                    self.tts.stop()
                except Exception:
                    pass
                # reset counter after interrupt to avoid repeated stops
                self._tts_interrupt_run = 0

            # enqueue audio frame for normal processing
            self.q.put(indata.copy())
        with sd.InputStream(samplerate=SR, channels=1, callback=cb, blocksize=bs):
            while self.running:
                sd.sleep(50)

    @staticmethod
    def _vol(chunk):
        return float(np.max(np.abs(chunk)))

    def _pop(self, timeout=0.1):
        try:
            return self.q.get(timeout=timeout)
        except queue.Empty:
            return None

    # ── Haupt-Loop ────────────────────────────────────────────────

    def _loop(self):
        print(_t(self, "ready"))

        while self.running:
            # Phase 1 – Warten auf Sprechbeginn
            pre = []; run = 0
            while self.running:
                c = self._pop(0.1)
                if c is None:
                    continue
                if self._vol(c) >= THRESHOLD:
                    run += 1; pre.append(c)
                    if run >= MIN_START:
                        break
                else:
                    run = 0; pre = []

            # Phase 2 – Aufnahme sammeln
            chunks = list(pre); silent = 0
            while self.running and len(chunks) < 120 and silent < SIL_CHUNKS:
                c = self._pop(0.1)
                if c is None:
                    silent += 1; continue
                if self._vol(c) >= THRESHOLD:
                    chunks.append(c); silent = 0
                else:
                    silent += 1
            if not chunks:
                continue

            # Phase 3 – Transkribieren
            self.speaking = True
            try:
                audio = np.concatenate(chunks, axis=0).astype(np.float32)
                audio = np.squeeze(audio)
                mx = float(np.max(np.abs(audio))) or 1.0
                audio /= mx

                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    tmp = f.name
                try:
                    sf.write(tmp, audio, SR)
                    text = self.stt.transcribe(tmp).strip()
                finally:
                    if os.path.exists(tmp):
                        os.unlink(tmp)

                if not text:
                    print(_t(self, "nothing_recognized"))
                    self.speaking = False
                    continue

                print(_t(self, "you", text=text))

                # Phase 4 – LLM
                from datetime import datetime as _dt
                heute = _dt.now().strftime("%A, %d. %B %Y")
                web = self.llm.get_web_context()
                ctx = self.memory.get_context()
                parts = [p for p in [ctx, web] if p.strip()]
                joined = "\n".join(parts)
                prompt = (f"{heute}\n{joined}\nHuman: {text}\nAssistant:"
                          if joined else f"{heute}\nHuman: {text}\nAssistant:")
                print(_t(self, "thinking"))
                try:
                    reply = self.llm.generate(prompt, get_conversation_prompt(self.app_language))
                except Exception as e:
                    print(_t(self, "llm_error", e=e))
                    self.speaking = False
                    continue
                print(f">>> {reply}\n")
                self.memory.add_interaction(text, reply)
                if self.llm.provider != "openrouter":
                    self.tts.synthesize(reply)

            except Exception as e:
                print(_t(self, "error", e=e))
            finally:
                self.speaking = False

    # ── Textmodus ─────────────────────────────────────────────────

    def text_mode(self):
        from datetime import datetime as _dt
        heute = _dt.now().strftime("%A, %d. %B %Y")
        print(_t(self, "textmode_header", date=heute))
        while True:
            try:
                text = input(_t(self, "input_prompt"))
            except (EOFError, KeyboardInterrupt):
                break
            if text.lower() == "quit":
                break
            web = self.llm.get_web_context()
            ctx = self.memory.get_context()
            parts = [p for p in [ctx, web] if p.strip()]
            joined = "\n".join(parts)
            prompt = (f"{heute}\n{joined}\nHuman: {text}\nAssistant:"
                      if joined else f"{heute}\nHuman: {text}\nAssistant:")
            print(_t(self, "thinking"))
            reply = self.llm.generate(prompt, get_conversation_prompt(self.app_language))
            print(f">>> {reply}")
            self.memory.add_interaction(text, reply)
            if self.llm.provider != "openrouter":
                self.tts.synthesize(reply)


if __name__ == "__main__":
    import sounddevice as _sd
    asst = None
    try:
        asst = VoiceAI()
        while not asst._shutdown.is_set():
            _sd.sleep(1000)
    except KeyboardInterrupt:
        print(_t(asst, "goodbye") if asst else "\nGoodbye!")
    finally:
        if asst is not None:
            try:
                asst.shutdown()
            except Exception:
                pass
