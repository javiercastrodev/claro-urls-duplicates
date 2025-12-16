import base64
import json
import os
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from server import DEFAULT_SITEMAP_URL, DEFAULT_SUFFIXES, fetch_all_urls_from_sitemap, find_urls_to_delete

MAILERSEND_API_URL = "https://api.mailersend.com/v1/email"


def _get_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def _send_mailersend_email(
    api_key: str,
    from_email: str,
    to_email: str,
    subject: str,
    text: str,
    html: str,
    attachments: list[dict] | None = None,
    timeout_seconds: int = 30,
) -> dict:
    payload: dict = {
        "from": {"email": from_email},
        "to": [{"email": to_email}],
        "subject": subject,
        "text": text,
        "html": html,
    }
    if attachments:
        payload["attachments"] = attachments

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        MAILERSEND_API_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            raw = resp.read()
            if not raw:
                return {"status": "sent", "http_status": resp.status}
            try:
                return json.loads(raw.decode("utf-8"))
            except Exception:
                return {"status": "sent", "http_status": resp.status, "raw": raw.decode("utf-8", errors="replace")}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"MailerSend HTTPError {e.code}: {body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"MailerSend URLError: {e}")


class handler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict, status_code: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        cron_secret = os.environ.get("CRON_SECRET", "").strip()
        if cron_secret:
            provided = (qs.get("secret", [""])[0] or "").strip()
            if provided != cron_secret:
                self._send_json({"error": "unauthorized"}, status_code=401)
                return

        sitemap_url = qs.get("sitemap", [DEFAULT_SITEMAP_URL])[0]
        suffixes_raw = qs.get("suffixes", [""])[0].strip()
        if suffixes_raw:
            suffixes = tuple([s.strip() for s in suffixes_raw.split(",") if s.strip()])
        else:
            suffixes = DEFAULT_SUFFIXES

        try:
            api_key = _get_env("API_KEY_MAILERSEND")
            from_email = _get_env("FROM_EMAIL")
            to_email = _get_env("TO_EMAIL")

            started = time.time()
            urls_by_loc = fetch_all_urls_from_sitemap(sitemap_url)
            to_delete = find_urls_to_delete(urls_by_loc, suffixes=suffixes)
            elapsed_ms = int((time.time() - started) * 1000)

            report = {
                "sitemap": sitemap_url,
                "suffixes": list(suffixes),
                "total_urls": len(urls_by_loc),
                "urls_to_delete": to_delete,
                "count": len(to_delete),
                "elapsed_ms": elapsed_ms,
            }

            report_json = json.dumps(report, ensure_ascii=False, indent=2)

            subject = f"Claro sitemap - URLs a eliminar ({len(to_delete)})"
            text = report_json
            html = f"<pre>{report_json}</pre>"

            attachment_bytes = report_json.encode("utf-8")
            attachments = [
                {
                    "content": base64.b64encode(attachment_bytes).decode("ascii"),
                    "filename": "urls_a_eliminar.json",
                    "type": "application/json",
                }
            ]

            mailersend_resp = _send_mailersend_email(
                api_key=api_key,
                from_email=from_email,
                to_email=to_email,
                subject=subject,
                text=text,
                html=html,
                attachments=attachments,
            )

            self._send_json({"status": "ok", "report": {"count": len(to_delete)}, "mailersend": mailersend_resp})
        except Exception as e:
            self._send_json({"error": "send_failed", "message": str(e)}, status_code=500)

    def do_POST(self):
        return self.do_GET()

    def log_message(self, format, *args):
        return
