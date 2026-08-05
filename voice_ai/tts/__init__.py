"""TTS – all engines write WAV; playback via sounddevice."""
from __future__ import annotations

import json, os, subprocess, sys, tempfile, threading
from typing import Optional

try:
    import sounddevice as _sd
    import numpy as _np
except ImportError:
    _sd = None  # type: ignore[assignment]
    _np = None  # type: ignore[assignment]

_MSG = {
    "en": {
        "unsupported_sample_width": "Unsupported sample width: {width}",
        "tts_exception": "[TTS] {exc}",
        "wav_read_failed": "[TTS] Failed to read WAV: {e}",
        "output_stream_error": "[TTS] OutputStream: {e}",
    },
    "de": {
        "unsupported_sample_width": "Nicht unterstützte Sample-Breite: {width}",
        "tts_exception": "[TTS] {exc}",
        "wav_read_failed": "[TTS] WAV lesen fehlgeschlagen: {e}",
        "output_stream_error": "[TTS] OutputStream: {e}",
    },
}


def _t(self, key, **kwargs):
    if isinstance(self, str):
        lang = self or "en"
    else:
        lang = getattr(self, "app_language", "en") or "en"
    template = _MSG.get(lang, _MSG["en"]).get(key, _MSG["en"].get(key, key))
    try:
        return template.format(**kwargs)
    except Exception:
        return template


def _read_wav(path: str, lang: str = "en"):
    import wave
    assert _np is not None
    with wave.open(path, "rb") as wf:
        nc = wf.getnchannels()
        sw = wf.getsampwidth()
        fr = wf.getframerate()
        raw = wf.readframes(wf.getnframes())
    if sw == 1:
        d = (_np.frombuffer(raw, dtype=_np.uint8).astype(_np.float32) / 128.0) - 1.0
    elif sw == 2:
        d = (_np.frombuffer(raw, dtype=_np.int16).astype(_np.float32) / 32768.0)
    elif sw == 3:
        b = (_np.frombuffer(raw, dtype=_np.uint8).reshape(-1, 3))
        p = _np.column_stack([b, _np.zeros(len(b), dtype=_np.uint8)])
        d = p.view(_np.int32).flatten().astype(_np.float32) / 8388608.0
    elif sw == 4:
        d = (_np.frombuffer(raw, dtype=_np.int32).astype(_np.float32) / 2147483648.0)
    else:
        raise ValueError(_t(lang, "unsupported_sample_width", width=sw))
    if nc > 1:
        d = d.reshape(-1, nc)
    return d, fr


class TTS:
    _lock = threading.Lock()

    def __init__(self, config_path=None):
        self.cfg_path = config_path or os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "config.json")
        with open(self.cfg_path) as f:
            self.config = json.load(f)
        self.engine = (self.config.get("tts_engine", "system") or "system").lower().strip()
        self.app_language = self.config.get("app_language", "en")
        self.stop_ev = threading.Event()
        self._play_thr: Optional[threading.Thread] = None

    def synthesize(self, text: str, out: Optional[str] = None) -> str:
        self.stop_ev.clear()
        ev = self.stop_ev

        def _work():
            wav_path = out
            tmp_created = False
            try:
                if wav_path is None:
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                        wav_path = tmp.name
                    tmp_created = True
                wav = self._gen_wav(text, wav_path)
                if wav and os.path.exists(wav) and not ev.is_set():
                    self._play(wav, ev)
            except Exception as exc:
                print(_t(self, "tts_exception", exc=exc))
            finally:
                self._play_thr = None
                if tmp_created and wav_path and os.path.exists(wav_path):
                    try:
                        os.remove(wav_path)
                    except Exception:
                        pass

        self._play_thr = threading.Thread(target=_work, daemon=True)
        self._play_thr.start()
        return out or ""

    def stop(self):
        self.stop_ev.set()
        if _sd is not None:
            try:
                _sd.stop()
            except Exception:
                pass

    # ── interne Pipeline ──────────────────────────────────────────────
    def _gen_wav(self, text: str, out: str) -> Optional[str]:
        with self._lock:
            if self.engine == "piper":
                return _synth_piper(text, out, self.config)
            if self.engine == "elevenlabs":
                return _synth_elevenlabs(text, out, self.config)
            return _synth_system(text, out, self.config)

    def _play(self, wav_path: str, ev: threading.Event) -> None:
        if _sd is None or _np is None:
            _play_fallback(wav_path)
            return
        try:
            data, sr = _read_wav(wav_path, self.app_language)
        except Exception as e:
            print(_t(self, "wav_read_failed", e=e))
            _play_fallback(wav_path)
            return
        if data is None or len(data) == 0:
            return
        try:
            st = _sd.OutputStream(samplerate=sr, channels=data.shape[1] if data.ndim > 1 else 1, dtype=data.dtype, blocksize=1024)
        except Exception as e:
            print(_t(self, "output_stream_error", e=e))
            _play_fallback(wav_path)
            return
        st.start()
        try:
            pos, total = 0, len(data)
            while pos < total:
                if ev.is_set():
                    break
                end = min(pos + 1024, total)
                st.write(data[pos:end])
                pos = end
        finally:
            st.stop(); st.close()

    # ── Engines ───────────────────────────────────────────────────────


# ── freie Funktionen für die Engines ────────────────────────────────────────

def _play_fallback(wav_path: str) -> None:
    if os.name == "nt":
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        f"Add-Type -AssemblyName System.Media; "
                        f"$p = New-Object System.Media.SoundPlayer('{wav_path}'); "
                        f"$p.PlaySync()"], capture_output=True, timeout=300)
    elif sys.platform == "darwin":
        subprocess.run(["afplay", wav_path], capture_output=True, timeout=300)
    else:
        subprocess.run(["aplay", wav_path], capture_output=True, timeout=300)


def _synth_piper(text: str, out: str, cfg: dict) -> Optional[str]:
    voice = cfg.get("piper_voice", "de_DE-karl-medium")
    try:
        from piper import PiperVoice  # type: ignore[import-untyped]
        import numpy as np
        import os

        # Try to find the voice model files
        # Piper models are typically stored in ~/.local/share/piper-voices/
        voice_dir = os.path.expanduser("~/.local/share/piper-voices")
        model_path = os.path.join(voice_dir, f"{voice}.onnx")
        config_path = os.path.join(voice_dir, f"{voice}.onnx.json")

        if not os.path.exists(model_path) or not os.path.exists(config_path):
            return _synth_system(text, out, cfg)

        voice_obj = PiperVoice.load(model_path, config_path)
        audio_chunk = voice_obj.synthesize(text)

        # Convert AudioChunk to numpy array
        audio_data = audio_chunk.samples.astype(np.float32)

        # Save as WAV
        import wave
        import struct
        with wave.open(out, "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(audio_chunk.sample_rate)
            for sample in audio_data:
                f.writeframes(struct.pack('<h', int(sample * 32767)))
        return out
    except ImportError:
        return _synth_system(text, out, cfg)
    except Exception:
        return _synth_system(text, out, cfg)


def _synth_elevenlabs(text: str, out: str, cfg: dict) -> Optional[str]:
    key = os.environ.get("ELEVENLABS_API_KEY") or cfg.get("elevenlabs_api_key", "")
    vid = cfg.get("elevenlabs_voice_id", "")
    if not key or not vid:
        return _synth_system(text, out, cfg)
    import requests
    r = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{vid}",
                      headers={"xi-api-key": key, "Content-Type": "application/json"},
                      json={"text": text, "model_id": "eleven_multilingual_v2",
                            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.5}},
                      timeout=60)
    r.raise_for_status()
    with open(out, "wb") as f:
        f.write(r.content)
    return out


def _synth_system(text: str, out: str, cfg: dict) -> Optional[str]:
    if os.name == "nt":
        return _synth_windows_wav(text, out, cfg)
    if sys.platform == "darwin":
        subprocess.run(["say", "-v", "Anna", "-r", "190", "-o", out, text], capture_output=True, timeout=60)
        return out if os.path.exists(out) else None
    try:
        r = subprocess.run(["espeak-ng", "--stdout", "-v", cfg.get("linux_voice", "de"), "-s", "150", text],
                           capture_output=True, timeout=30)
        if r.returncode == 0 and r.stdout:
            with open(out, "wb") as f:
                f.write(r.stdout)
            return out
    except FileNotFoundError:
        pass
    subprocess.run(["espeak", "-v", cfg.get("linux_voice", "de"), "-s", "150", text], capture_output=True, timeout=60)
    return out if os.path.exists(out) else None


def _get_windows_sapi_voices() -> list[str]:
    """Get list of available Windows SAPI voices."""
    voices = []
    try:
        import comtypes.client as cc
        import pythoncom as pc
        try:
            import comtypes.gen.SpeechLib as sl  # type: ignore[import-untyped]
        except ImportError:
            try:
                cc.GetModule("SAPI.SpVoice")
                import comtypes.gen.SpeechLib as sl  # type: ignore[import-untyped]
            except Exception:
                return voices
        pc.CoInitialize()
        try:
            sp = cc.CreateObject("SAPI.SpVoice")
            voice_collection = sp.GetVoices()
            count = voice_collection.Count
            for i in range(count):
                voice = voice_collection.Item(i)
                desc = voice.GetDescription()
                voices.append(desc)
        except Exception:
            pass
        finally:
            try:
                pc.CoUninitialize()
            except Exception:
                pass
    except Exception:
        pass
    return voices


def _get_piper_voices() -> list[str]:
    """Discover available Piper voices from the piper-voices directory."""
    voices = []
    voice_dir = os.path.expanduser("~/.local/share/piper-voices")
    if not os.path.isdir(voice_dir):
        return voices
    for fname in sorted(os.listdir(voice_dir)):
        if fname.endswith(".onnx") and not fname.endswith(".onnx.json"):
            voice_name = fname[:-5]
            config_path = os.path.join(voice_dir, f"{voice_name}.onnx.json")
            if os.path.exists(config_path):
                voices.append(voice_name)
    return voices


def _synth_windows_wav(text: str, out: str, cfg: dict) -> Optional[str]:
    import comtypes.client as cc
    import pythoncom as pc
    try:
        import comtypes.gen.SpeechLib as sl  # type: ignore[import-untyped]
    except ImportError:
        try:
            cc.GetModule("SAPI.SpVoice")
            import comtypes.gen.SpeechLib as sl  # type: ignore[import-untyped]
        except Exception:
            return _synth_windows_powershell(text, out)
    pc.CoInitialize()
    try:
        sp = cc.CreateObject("SAPI.SpVoice")
        voice_name = cfg.get("windows_voice", "")
        if voice_name:
            try:
                for i in range(sp.GetVoices().Count):
                    voice = sp.GetVoices().Item(i)
                    if voice_name in voice.GetDescription():
                        sp.Voice = voice
                        break
            except Exception:
                pass
        fs = cc.CreateObject("SAPI.SpFileStream")
        fs.Open(out, sl.SSFMCreateForWrite)
        sp.AudioOutputStream = fs
        sp.Rate = -1; sp.Volume = 95
        sp.Speak(text)
        fs.Close()
        return out
    except Exception:
        try:
            pc.CoUninitialize()
        except Exception:
            pass
        return _synth_windows_powershell(text, out)
    finally:
        try:
            pc.CoUninitialize()
        except Exception:
            pass


def _synth_windows_powershell(text: str, out: str) -> Optional[str]:
    safe = text.replace("'", "''")
    abs_ = os.path.abspath(out).replace("'", "''")
    ps = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$fs = New-Object System.IO.FileStream('{abs_}', 'Create'); "
        "$s.SetOutputToWaveStream($fs); $s.Rate=-1; $s.Volume=95; "
        f"$s.Speak('{safe}'); $s.SetOutputToDefaultAudio(); $fs.Close(); exit 0"
    )
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=60)
    return out if os.path.exists(out) else None
