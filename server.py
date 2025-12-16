import json
import os
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

DEFAULT_SITEMAP_URL = "https://www.claro.com.pe/sitemap.xml"
DEFAULT_SUFFIXES = ("_test", "-test", "_1", "_bkp", "_2")
DEFAULT_PORT = 8000


def _load_env_file(path: str) -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _parse_suffixes_csv(value: str) -> tuple[str, ...]:
    raw = (value or "").strip()
    if len(raw) >= 2 and ((raw[0] == raw[-1] == "'") or (raw[0] == raw[-1] == '"')):
        raw = raw[1:-1].strip()
    return tuple([s.strip() for s in raw.split(",") if s.strip()])


def _xml_local_name(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _http_get(url: str, timeout_seconds: int = 30) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "claro-sitemaps-bot/1.0 (+https://github.com/)",
            "Accept": "application/xml,text/xml,*/*",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        return resp.read()


def fetch_all_urls_from_sitemap(
    root_sitemap_url: str, timeout_seconds: int = 30, max_sitemaps: int = 2000
) -> dict[str, str | None]:
    sitemap_queue: list[str] = [root_sitemap_url]
    seen_sitemaps: set[str] = set()

    urls_by_loc: dict[str, str | None] = {}

    while sitemap_queue:
        sitemap_url = sitemap_queue.pop(0)
        if sitemap_url in seen_sitemaps:
            continue
        seen_sitemaps.add(sitemap_url)

        if len(seen_sitemaps) > max_sitemaps:
            raise RuntimeError(f"Max sitemaps exceeded ({max_sitemaps}). Last: {sitemap_url}")

        xml_bytes = _http_get(sitemap_url, timeout_seconds=timeout_seconds)
        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as e:
            raise RuntimeError(f"Invalid XML at {sitemap_url}: {e}")

        root_name = _xml_local_name(root.tag)

        if root_name == "sitemapindex":
            for sitemap in root:
                if _xml_local_name(sitemap.tag) != "sitemap":
                    continue
                loc_el = None
                for child in sitemap:
                    if _xml_local_name(child.tag) == "loc":
                        loc_el = child
                        break
                if loc_el is None or not loc_el.text:
                    continue
                loc = loc_el.text.strip()
                if loc and loc not in seen_sitemaps:
                    sitemap_queue.append(loc)

        elif root_name == "urlset":
            for url_el in root:
                if _xml_local_name(url_el.tag) != "url":
                    continue
                loc_el = None
                lastmod_el = None
                for child in url_el:
                    if _xml_local_name(child.tag) == "loc":
                        loc_el = child
                    elif _xml_local_name(child.tag) == "lastmod":
                        lastmod_el = child
                if loc_el is None or not loc_el.text:
                    continue
                loc = loc_el.text.strip()
                if not loc:
                    continue
                if loc in urls_by_loc:
                    continue

                lastmod: str | None
                if lastmod_el is None or not lastmod_el.text:
                    lastmod = None
                else:
                    lastmod = lastmod_el.text.strip() or None

                urls_by_loc[loc] = lastmod
        else:
            raise RuntimeError(f"Unsupported sitemap root element '{root_name}' at {sitemap_url}")

    return urls_by_loc


def find_urls_to_delete(
    urls_by_loc: dict[str, str | None], suffixes: tuple[str, ...] = DEFAULT_SUFFIXES
) -> list[dict]:
    out: list[dict] = []
    for url, lastmod in urls_by_loc.items():
        url_original = url.strip()
        if not url_original:
            continue
        parsed = urlparse(url_original)
        path = parsed.path or ""
        segments = [seg for seg in path.strip("/").split("/") if seg]

        matches_suffix = any(seg.endswith(suffixes) for seg in segments)
        if matches_suffix:
            out.append({"url": url_original, "ultima_actualizacion": lastmod})
    return sorted(out, key=lambda x: x["url"])


class Handler(BaseHTTPRequestHandler):
    server_version = "claro-sitemaps/1.0"

    def _send_json(self, payload: dict, status_code: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/health":
            self._send_json({"status": "ok"})
            return

        if path != "/urls-a-eliminar":
            self._send_json(
                {
                    "error": "not_found",
                    "message": "Use /urls-a-eliminar or /health",
                },
                status_code=404,
            )
            return

        sitemap_url = qs.get("sitemap", [DEFAULT_SITEMAP_URL])[0]
        suffixes_raw = qs.get("suffixes", [""])[0].strip()
        if suffixes_raw:
            suffixes = _parse_suffixes_csv(suffixes_raw)
        else:
            suffixes_from_env = os.environ.get("SUFFIXES", "")
            suffixes = _parse_suffixes_csv(suffixes_from_env) or DEFAULT_SUFFIXES

        started = time.time()
        try:
            urls_by_loc = fetch_all_urls_from_sitemap(sitemap_url)
            to_delete = find_urls_to_delete(urls_by_loc, suffixes=suffixes)
        except urllib.error.URLError as e:
            self._send_json(
                {
                    "error": "fetch_failed",
                    "message": str(e),
                    "sitemap": sitemap_url,
                },
                status_code=502,
            )
            return
        except Exception as e:
            self._send_json(
                {
                    "error": "processing_failed",
                    "message": str(e),
                    "sitemap": sitemap_url,
                },
                status_code=500,
            )
            return

        elapsed_ms = int((time.time() - started) * 1000)
        self._send_json(
            {
                "sitemap": sitemap_url,
                "suffixes": list(suffixes),
                "total_urls": len(urls_by_loc),
                "urls_to_delete": to_delete,
                "count": len(to_delete),
                "elapsed_ms": elapsed_ms,
            }
        )

    def log_message(self, format, *args):
        return


def main() -> None:
    _load_env_file(".env")

    port = DEFAULT_PORT
    if len(sys.argv) >= 2:
        try:
            port = int(sys.argv[1])
        except ValueError:
            raise SystemExit("Port must be an integer")

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Listening on http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
