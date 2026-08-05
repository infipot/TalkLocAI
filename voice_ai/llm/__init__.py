"""LLM – Lokales LM Studio oder OpenRouter."""
from __future__ import annotations

import json, os, requests
from typing import Any, Optional
from urllib.parse import urlparse, urlunparse

from .. import web_search as _ws


class LLM:
    def __init__(self, config_path=None, provider: str = "auto"):
        self.cfg_path = config_path or os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "config.json")
        with open(self.cfg_path, encoding="utf-8") as f:
            self.config = json.load(f)

        self.provider = (provider or self.config.get("llm_provider", "auto")).lower().strip()
        self.max_tokens    = self.config.get("max_tokens", 4096)
        self.temperature   = self.config.get("temperature", 0.7)
        self.reasoning_timeout = self.config.get("reasoning_timeout", 60)

        # Internet
        self.internet_enabled   = self.config.get("internet_enabled", False)
        self.web_max            = self.config.get("web_search_max_results", 5)
        self.news_topic         = self.config.get("news_topic", "") or None

        # OpenRouter
        self.api_key        = os.environ.get("OPENROUTER_API_KEY", "") or self.config.get("openrouter_api_key", "")
        self.openrouter_model = self.config.get("openrouter_model", "openrouter/free")
        self.openrouter_base  = self.config.get("openrouter_base_url", "https://openrouter.ai/api/v1").rstrip("/")
        self.retry_on         = self.config.get("openrouter_retry_on_limit", True)
        cfg_models: list[str] = self.config.get("openrouter_retry_models", [])
        self.retry_models: list[str] = []
        if self.openrouter_model not in self.retry_models:
            self.retry_models.append(self.openrouter_model)
        for m in cfg_models:
            if m not in self.retry_models:
                self.retry_models.append(m)
        if not self.retry_models:
            self.retry_models = [self.openrouter_model]

        # Lokal
        self.local_base_url   = self._norm(self.config.get("local_lm_base_url", "http://127.0.0.1:8080"))
        self.local_model      = self.config.get("local_lm_model", "").strip()
        self.local_auto_select = self.config.get("local_lm_auto_select", True)
        self.local_models_path = self.config.get("local_lm_models_path", "/v1/models")
        self.local_chat_path   = self.config.get("local_lm_chat_path",  "/v1/chat/completions")
        self.local_gen_path    = self.config.get("local_lm_generate_path","/v1/generate")
        self.local_models: list[str] = []
        self.local_available = False

        if self.provider in ("local", "auto"):
            self.local_available = self._discover_local()
            if self.local_available and not self.local_model and self.local_models:
                self.local_model = self.local_models[0]

        if self.provider == "local" and not self.local_available:
            print(f"Warnung: Lokaler LM Studio-Server nicht erreichbar unter {self.local_base_url}")

    @staticmethod
    def _norm(url: str) -> str:
        p = urlparse(url.strip())
        path = p.path.rstrip('/')
        for prefix in ('/api/v1', '/api'):
            if path.endswith(prefix):
                path = path[:-len(prefix)]
                break
        return urlunparse(p._replace(path=path or '/'))

    def _discover_local(self) -> bool:
        import requests as _req
        eps = [self.local_models_path, "/v1/models", "/models"]
        cands = [self.local_base_url]
        try:
            p = urlparse(self.local_base_url)
            h, pt = p.hostname or "127.0.0.1", p.port
            if h in ("127.0.0.1", "localhost") and pt and pt != 1234:
                cands.append(urlunparse(p._replace(netloc=f"{h}:1234", path="/")))
        except Exception:
            pass
        for base in cands:
            base = self._norm(base)
            for ep in eps:
                try:
                    r = _req.get(f"{base.rstrip('/')}/{ep.lstrip('/')}", timeout=3)
                    if r.status_code != 200:
                        continue
                    d = r.json()
                    items = d.get("data", d.get("models", [d]))
                    if not items:
                        continue
                    self.local_models = [
                        (it.get("key") or it.get("id") or str(it))
                        for it in (items if isinstance(items, list) else [items])
                    ]
                    return bool(self.local_models)
                except Exception:
                    continue
        return False

    # ── Öffentliche API ────────────────────────────────────────────────────────

    def get_web_context(self) -> str:
        """Hole Nachrichten, falls Internet aktiviert."""
        if not self.internet_enabled:
            return ""
        try:
            return _ws.build_context_block(use_web=True, news_topic=self.news_topic)
        except Exception as exc:
            print(f"[LLM] Web-Kontext fehlgeschlagen: {exc}")
            return ""

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        prov = self.provider
        if prov == "local":
            if not self.local_available:
                print(f"[LLM] Lokal nicht verfuegbar, falle auf OpenRouter zurueck")
                return "[OpenRouter] " + self._gen_openrouter(prompt, system_prompt)
            try:
                return self._gen_local(prompt, system_prompt)
            except Exception as exc:
                print(f"[LLM] Lokal fehlgeschlagen: {exc}")
                return "[OpenRouter] " + self._gen_openrouter(prompt, system_prompt)
        if prov == "openrouter":
            return self._gen_openrouter(prompt, system_prompt)
        if self.local_available:
            try:
                return self._gen_local(prompt, system_prompt)
            except Exception as exc:
                print(f"[LLM] Lokal fehlgeschlagen: {exc}")
                return "[OpenRouter] " + self._gen_openrouter(prompt, system_prompt)
        return self._gen_openrouter(prompt, system_prompt)

    def generate_with_reasoning(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        return self.generate(prompt, system_prompt)

    # ── Lokal ─────────────────────────────────────────────────────────────────

    def _gen_local(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        model = self.local_model or (self.local_models[0] if self.local_models else "")
        payload = {
            "model": model, "messages": messages,
            "max_tokens": self.max_tokens, "temperature": self.temperature,
        }
        url = f"{self.local_base_url.rstrip('/')}{self.local_chat_path}"
        r = requests.post(url, json=payload, timeout=self.reasoning_timeout or 120)
        if r.status_code not in (200, 201):
            raise RuntimeError(f"Lokal HTTP {r.status_code}: {r.text[:300]}")
        return _extract_text(r.json())

    # ── OpenRouter ─────────────────────────────────────────────────────────────

    def _gen_openrouter(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        if not self.api_key:
            raise RuntimeError("OpenRouter API-Key fehlt.")

        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        hdrs = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        models = self.retry_models if self.retry_on else [self.openrouter_model]
        last: Optional[Exception] = None

        for model in models:
            try:
                r = requests.post(
                    f"{self.openrouter_base}/chat/completions",
                    json={"model": model, "messages": messages,
                          "max_tokens": self.max_tokens, "temperature": self.temperature},
                    headers=hdrs, timeout=120,
                )
                if r.status_code == 429:
                    last = RuntimeError(f"Rate-Limit auf {model} (429), versuche nächstes …")
                    self.openrouter_model = model
                    continue
                if r.status_code == 401:
                    raise RuntimeError(f"OpenRouter Auth-Fehler (401): {r.text[:200]}")
                if r.status_code != 200:
                    last = RuntimeError(f"OpenRouter HTTP {r.status_code}: {r.text[:200]}")
                    self.openrouter_model = model
                    continue
                self.openrouter_model = model
                return _extract_text(r.json())
            except Exception as exc:
                last = exc
                continue

        raise RuntimeError(f"Alle OpenRouter-Modelle fehlgeschlagen. Letzter Fehler: {last}")


def _extract_text(data: dict) -> str:
    choices = data.get("choices", [])
    if choices:
        msg = choices[0].get("message", {})
        content = msg.get("content", "")
        if isinstance(content, list):
            return "".join(c.get("text", "") if isinstance(c, dict) else str(c) for c in content)
        return content or ""
    return str(data)
