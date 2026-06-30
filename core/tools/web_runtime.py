"""Real web search and page reading adapters with local-network blocking."""

from __future__ import annotations

from html.parser import HTMLParser
import ipaddress
import json
import socket
from typing import Any
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


class _ReadableHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.skip = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self.skip:
            self.skip -= 1

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not self.skip and text:
            self.parts.append(text)


def _assert_public_http_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("only public http/https URLs are allowed")
    host = parsed.hostname.lower()
    if host in {"localhost", "localhost.localdomain"}:
        raise ValueError("local network URLs are blocked")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        raise ValueError("URL hostname could not be resolved") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise ValueError("private, loopback, link-local, and reserved addresses are blocked")
    return url


class _PublicOnlyRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req: Request, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> Request | None:
        _assert_public_http_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open(request: Request, timeout: int) -> Any:
    return build_opener(_PublicOnlyRedirectHandler()).open(request, timeout=timeout)


class WebRuntime:
    def __init__(self, settings: dict[str, Any]):
        self.settings = dict(settings)

    def search(self, query: str, limit: int = 5) -> dict[str, Any]:
        text = str(query or "").strip()
        if not text:
            raise ValueError("query is required")
        provider = str(self.settings.get("search_provider") or "")
        limit = max(1, min(int(limit), 10))
        if provider == "searxng":
            base = str(self.settings.get("searxng_url") or "").rstrip("/")
            if not base:
                raise ValueError("SearXNG URL is not configured")
            url = _assert_public_http_url(f"{base}/search?{urlencode({'q': text, 'format': 'json', 'language': 'all'})}")
            request = Request(url, headers={"Accept": "application/json", "User-Agent": "SCBKR/2.1"})
        elif provider == "brave":
            token = str(self.settings.get("brave_api_key") or "")
            if not token:
                raise ValueError("Brave Search API key is not configured")
            url = f"https://api.search.brave.com/res/v1/web/search?{urlencode({'q': text, 'count': limit})}"
            request = Request(url, headers={"Accept": "application/json", "X-Subscription-Token": token, "User-Agent": "SCBKR/2.1"})
        else:
            raise ValueError("search_provider must be searxng or brave")
        with _open(request, timeout=int(self.settings.get("search_timeout") or 15)) as response:
            payload = json.loads(response.read(2_000_000).decode("utf-8"))
        raw_results = payload.get("results", []) if provider == "searxng" else payload.get("web", {}).get("results", [])
        results = [{"title": str(item.get("title") or ""), "url": str(item.get("url") or ""), "snippet": str(item.get("content") or item.get("description") or ""), "source": provider} for item in raw_results[:limit]]
        return {"query": text, "provider": provider, "results": results, "count": len(results), "external_call_performed": True}

    def read_page(self, url: str, max_chars: int = 12000) -> dict[str, Any]:
        safe_url = _assert_public_http_url(str(url or "").strip())
        request = Request(safe_url, headers={"Accept": "text/html,text/plain", "User-Agent": "SCBKR/2.1"})
        with _open(request, timeout=int(self.settings.get("search_timeout") or 15)) as response:
            content_type = str(response.headers.get("Content-Type") or "")
            raw = response.read(2_000_000)
            final_url = _assert_public_http_url(response.geturl())
        if not (content_type.startswith("text/html") or content_type.startswith("text/plain")):
            raise ValueError("page reader only accepts text/html or text/plain")
        decoded = raw.decode("utf-8", errors="replace")
        if content_type.startswith("text/html"):
            parser = _ReadableHTML()
            parser.feed(decoded)
            text = "\n".join(parser.parts)
        else:
            text = decoded
        return {"url": final_url, "content_type": content_type, "text": text[:max(1000, min(max_chars, 50000))], "truncated": len(text) > max_chars, "external_call_performed": True}
