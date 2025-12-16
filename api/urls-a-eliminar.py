import json
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from server import DEFAULT_SITEMAP_URL, DEFAULT_SUFFIXES, fetch_all_urls_from_sitemap, find_urls_to_delete


def _parse_suffixes_csv(value: str) -> tuple[str, ...]:
    raw = (value or "").strip()
    if len(raw) >= 2 and ((raw[0] == raw[-1] == "'") or (raw[0] == raw[-1] == '"')):
        raw = raw[1:-1].strip()
    return tuple([s.strip() for s in raw.split(",") if s.strip()])


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        sitemap_url = qs.get("sitemap", [DEFAULT_SITEMAP_URL])[0]
        suffixes_raw = qs.get("suffixes", [""])[0].strip()
        if suffixes_raw:
            suffixes = _parse_suffixes_csv(suffixes_raw)
        else:
            suffixes_from_env = os.environ.get("SUFFIXES", "")
            suffixes = _parse_suffixes_csv(suffixes_from_env) or DEFAULT_SUFFIXES

        try:
            urls_by_loc = fetch_all_urls_from_sitemap(sitemap_url)
            to_delete = find_urls_to_delete(urls_by_loc, suffixes=suffixes)
        except Exception as e:
            body = json.dumps(
                {"error": "processing_failed", "message": str(e), "sitemap": sitemap_url},
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        body = json.dumps(
            {
                "sitemap": sitemap_url,
                "suffixes": list(suffixes),
                "total_urls": len(urls_by_loc),
                "urls_to_delete": to_delete,
                "count": len(to_delete),
            },
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return
