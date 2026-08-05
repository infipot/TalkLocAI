"""Web-Suche (DuckDuckGo HTML) und Nachrichten (Google News RSS) – ohne API-Key."""
from __future__ import annotations

import html, re, xml.etree.ElementTree as ET

import requests

_DDGO = "https://html.duckduckgo.com/html/"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")
NEWS_ALL = "https://news.google.com/rss?hl=de&gl=DE&ceid=DE:de"
NEWS_Q   = "https://news.google.com/rss/search?q={q}&hl=de&gl=DE&ceid=DE:de"


def search_web(query: str, max_results: int = 5) -> str:
    if not query.strip():
        return "Keine Suchanfrage angegeben."
    try:
        r = requests.post(_DDGO, data={"q": query}, headers={"User-Agent": _UA}, timeout=10)
        r.raise_for_status()
    except Exception as e:
        return f"[Websuche fehlgeschlagen: {e}]"
    return _parse_ddgo(r.text, max_results)


def get_news(query: str | None = None, max_results: int = 5) -> str:
    url = NEWS_Q.format(q=requests.utils.quote(query.strip())) if query else NEWS_ALL
    try:
        r = requests.get(url, headers={"User-Agent": _UA}, timeout=10)
        r.raise_for_status()
    except Exception as e:
        return f"[Nachrichten fehlgeschlagen: {e}]"
    return _parse_rss(r.text, max_results)


def build_context_block(use_web: bool = True, news_topic: str | None = None) -> str:
    parts: list[str] = []
    if use_web:
        parts.append("### Aktuelle Informationen\n")
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
    return "\n\n".join(out) if out else "Keine Suchergebnisse."


def _parse_rss(xml_text: str, n: int) -> str:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return "Feed konnte nicht geparst werden."
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
    return "\n\n".join(items) if items else "Keine Nachrichten gefunden."


def _clean(url: str) -> str:
    if url.startswith("/l/?uddg="):
        url = url[9:]
    return html.unescape(url.split("&")[0])

def _strip(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
