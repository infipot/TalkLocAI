import json, os
from faster_whisper import WhisperModel

class STT:
    def __init__(self, config_path=None):
        self.config_path = config_path or os.path.join(os.path.dirname(__file__), "..", "config", "config.json")
        with open(self.config_path) as f:
            self.config = json.load(f)

        model_name = self.config.get("whisper_model", "auto")
        device = self.config.get("whisper_device", "auto")
        if isinstance(device, str) and device.strip().lower() == "auto":
            try:
                import torch
                if torch.cuda.is_available():
                    device = "cuda"
                elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                    device = "mps"
                else:
                    device = "cpu"
            except Exception:
                device = "cpu"

        if isinstance(model_name, str) and model_name.strip().lower() == "auto":
            if device in ("cuda", "mps"):
                model_name = "medium"
            else:
                model_name = "small"

        self.language = self.config.get("whisper_language") or None
        self.task = self.config.get("whisper_task", "transcribe")
        self.vad_filter = self.config.get("whisper_vad_filter", False)
        self.beam_size = self.config.get("whisper_beam_size", 1)
        self.best_of = self.config.get("whisper_best_of", 1)
        if device == "cpu":
            self.beam_size = 1
            self.best_of = 1
        self.condition_on_previous_text = self.config.get("whisper_condition_on_previous_text", False)
        self.no_speech_threshold = self.config.get("whisper_no_speech_threshold", 0.3)
        self.temperature = self.config.get("whisper_temperature", [0.0])

        self.model = WhisperModel(model_name, device=device)

    def transcribe(self, audio_path: str) -> tuple[str, str | None]:
        segments, info = self.model.transcribe(
            audio_path,
            language=self.language,
            task=self.task,
            vad_filter=self.vad_filter,
            beam_size=self.beam_size,
            best_of=self.best_of,
            condition_on_previous_text=self.condition_on_previous_text,
            no_speech_threshold=self.no_speech_threshold,
            temperature=self.temperature
        )
        detected_language = getattr(info, "language", None)
        return " ".join([s.text for s in segments]), detected_language
