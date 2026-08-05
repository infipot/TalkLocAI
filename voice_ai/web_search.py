"""Web search (DuckDuckGo HTML) and news (Google News RSS) – no API key required."""
from __future__ import annotations

import html, json, os, re, xml.etree.ElementTree as ET

import requests

_DDGO = "https://html.duckduckgo.com/html/"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")
NEWS_ALL = "https://news.google.com/rss?hl=de&gl=DE&ceid=DE:de"
NEWS_Q   = "https://news.google.com/rss/search?q={q}&hl=de&gl=DE&ceid=DE:de"

_MSG = {
    "en": {
        "no_query": "No search query provided.",
        "web_failed": "[Web search failed: {e}]",
        "news_failed": "[News fetch failed: {e}]",
        "current_info": "### Current Information\n",
        "no_results": "No search results.",
        "parse_failed": "Feed could not be parsed.",
        "no_news": "No news found.",
    },
    "de": {
        "no_query": "Keine Suchanfrage angegeben.",
        "web_failed": "[Websuche fehlgeschlagen: {e}]",
        "news_failed": "[Nachrichten fehlgeschlagen: {e}]",
        "current_info": "### Aktuelle Informationen\n",
        "no_results": "Keine Suchergebnisse.",
        "parse_failed": "Feed konnte nicht geparst werden.",
        "no_news": "Keine Nachrichten gefunden.",
    },
}


def _get_lang() -> str:
    try:
        cfg_path = os.path.join(os.path.dirname(__file__), "..", "config", "config.json")
        with open(cfg_path, encoding="utf-8") as _f:
            return json.load(_f).get("app_language", "en") or "en"
    except Exception:
        return "en"


def _t(key, **kwargs):
    lang = _get_lang()
    template = _MSG.get(lang, _MSG["en"]).get(key, _MSG["en"].get(key, key))
    try:
        return template.format(**kwargs)
    except Exception:
        return template


def search_web(query: str, max_results: int = 5) -> str:
    if not query.strip():
        return _t("no_query")
    try:
        r = requests.post(_DDGO, data={"q": query}, headers={"User-Agent": _UA}, timeout=10)
        r.raise_for_status()
    except Exception as e:
        return _t("web_failed", e=e)
    return _parse_ddgo(r.text, max_results)


def get_news(query: str | None = None, max_results: int = 5) -> str:
    url = NEWS_Q.format(q=requests.utils.quote(query.strip())) if query else NEWS_ALL
    try:
        r = requests.get(url, headers={"User-Agent": _UA}, timeout=10)
        r.raise_for_status()
    except Exception as e:
        return _t("news_failed", e=e)
    return _parse_rss(r.text, max_results)


def build_context_block(use_web: bool = True, news_topic: str | None = None) -> str:
    parts: list[str] = []
    if use_web:
        parts.append(_t("current_info"))
        parts.append(get_news(news_topic))
    return "\n".join(parts)


# ── interne Parser ────────────────────────────────────────────────────────────

def _parse_ddgo(raw: str, n: int) -> str:
    links = re.findall(r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>', raw, re.I)
    snips = re.findall(r'<a[^>]+class="[^"]*result__snippet[^"]*"[^>]*>([\s\S]*?)</a>', raw, re.I)
    out: list[str] = []
    for i, (url, title_raw) in enumerate(links):
        if i >= n: break
        title = _strip(title_raw)
        if not title: continue
        sn = _strip(snips[i]) if i < len(snips) else ""
        url = _clean(url)
        out.append(f"{i+1}. {title}\n   {url}" + (f"\n   {sn}" if sn else ""))
    return "\n\n".join(out) if out else _t("no_results")


def _parse_rss(xml_text: str, n: int) -> str:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return _t("parse_failed")
    items: list[str] = []
    for item in root.iter("item"):
        if len(items) >= n: break
        t_el = item.find("title"); l_el = item.find("link"); d_el = item.find("description"); p_el = item.find("pubDate")
        t = (t_el.text or "").strip() if t_el is not None else ""
        if not t: continue
        link = (l_el.text or "").strip() if l_el is not None else ""
        desc = _strip(d_el.text or "") if d_el is not None else ""
        date = (p_el.text or "")[:16] if p_el is not None else ""
        line = f"{len(items)+1}. {t}" + (f" ({date})" if date else "")
        if link: line += f"\n   {link}"
        if desc: line += f"\n   {desc}"
        items.append(line)
    return "\n\n".join(items) if items else _t("no_news")


def _clean(url: str) -> str:
    if url.startswith("/l/?uddg="):
        url = url[9:]
    return html.unescape(url.split("&")[0])

def _strip(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
