import json
import html as html_lib
import os
import smtplib
import time
from email.message import EmailMessage
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from server import DEFAULT_SITEMAP_URL, DEFAULT_SUFFIXES, fetch_all_urls_from_sitemap, find_urls_to_delete


def _get_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def _send_email_smtp(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_pass: str,
    from_email: str,
    to_email: str,
    subject: str,
    text: str,
    html_body: str,
) -> dict:
    def _build_message() -> EmailMessage:
        msg = EmailMessage()
        msg["From"] = from_email
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(text)
        msg.add_alternative(html_body, subtype="html")
        return msg

    msg = _build_message()

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.ehlo()
        if smtp_port == 587:
            server.starttls()
            server.ehlo()
        try:
            server.login(smtp_user, smtp_pass)
        except smtplib.SMTPAuthenticationError as e:
            raise RuntimeError(
                "SMTP authentication failed. Verify USER_SMTP and PASS_SMTP from MailerSend SMTP user credentials."
            ) from e

        server.send_message(msg)

    return {"status": "sent"}


def _render_urls_table_html(urls_to_delete: list[dict]) -> str:
    rows = []
    for item in urls_to_delete:
        url = html_lib.escape(str(item.get("url", "")))
        lastmod = item.get("ultima_actualizacion", None)
        lastmod_str = "" if lastmod is None else html_lib.escape(str(lastmod))
        rows.append(
            f"<tr><td style=\"padding:8px;border:1px solid #ddd;\"><a href=\"{url}\">{url}</a></td><td style=\"padding:8px;border:1px solid #ddd;white-space:nowrap;\">{lastmod_str}</td></tr>"
        )

    body_rows = "".join(rows) if rows else "<tr><td colspan=\"2\" style=\"padding:8px;border:1px solid #ddd;\">Sin resultados</td></tr>"
    return (
        "<html><body>"
        "<h3>URLs a eliminar</h3>"
        "<table style=\"border-collapse:collapse;width:100%;font-family:Arial,sans-serif;font-size:14px;\">"
        "<thead><tr>"
        "<th style=\"text-align:left;padding:8px;border:1px solid #ddd;background:#f5f5f5;\">URL</th>"
        "<th style=\"text-align:left;padding:8px;border:1px solid #ddd;background:#f5f5f5;\">Ultima actualización</th>"
        "</tr></thead>"
        f"<tbody>{body_rows}</tbody>"
        "</table>"
        "</body></html>"
    )


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
            if not provided:
                provided = (self.headers.get("X-Cron-Secret") or "").strip()
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
            from_email = _get_env("FROM_EMAIL")
            to_email = _get_env("TO_EMAIL")

            smtp_host = _get_env("SERVER_SMTP")
            smtp_port = int(_get_env("PORT_SMTP"))
            smtp_user = _get_env("USER_SMTP")
            smtp_pass = _get_env("PASS_SMTP")

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

            html_body = _render_urls_table_html(to_delete)

            mailersend_resp = _send_email_smtp(
                smtp_host=smtp_host,
                smtp_port=smtp_port,
                smtp_user=smtp_user,
                smtp_pass=smtp_pass,
                from_email=from_email,
                to_email=to_email,
                subject=subject,
                text=text,
                html_body=html_body,
            )

            self._send_json({"status": "ok", "report": {"count": len(to_delete)}, "mailersend": mailersend_resp})
        except Exception as e:
            self._send_json({"error": "send_failed", "message": str(e)}, status_code=500)

    def do_POST(self):
        return self.do_GET()

    def log_message(self, format, *args):
        return
