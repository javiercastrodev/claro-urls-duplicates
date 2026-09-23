# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Python service (stdlib only, no dependencies) that downloads `https://www.claro.com.pe/sitemap.xml`, walks any nested sitemap index, and returns the URLs considered "duplicates" for deletion — those whose path segments end in a configured suffix (default: `_test`, `-test`, `_1`, `_bkp`, `_bk`, `_2`, `_5`, `-2`; overridable via `SUFFIXES` env var or `?suffixes=` query param).

## Commands

Run the local dev server:

```bash
python3 server.py 8000
```

Hit it:

```bash
curl "http://127.0.0.1:8000/health"
curl "http://127.0.0.1:8000/urls-a-eliminar"
curl "http://127.0.0.1:8000/urls-a-eliminar?sitemap=...&suffixes=_test,-test,_1"
```

Send the email report locally (needs `.env` with `FROM_EMAIL`, `TO_EMAIL`, `SERVER_SMTP`, `PORT_SMTP`, `USER_SMTP`, `PASS_SMTP`):

```bash
python3 local_send_report.py
python3 local_send_report.py "https://www.claro.com.pe/sitemap.xml" "_test,-test,_1,_bkp,_2"
```

There is no build step, no lint config, and no test suite in this repo.

## Architecture

**`server.py` is the source of truth.** It contains all core logic:
- `fetch_all_urls_from_sitemap()` — BFS over sitemap index files (handles nested `sitemapindex` → `urlset`), collects `{loc: lastmod}` via `urllib` + `xml.etree.ElementTree`, no external HTTP/XML libs.
- `find_urls_to_delete()` — splits each URL's path into segments and flags any segment ending with a suffix tuple.
- `Handler` (`BaseHTTPRequestHandler`) — serves `/health` and `/urls-a-eliminar` for local dev via `python3 server.py [port]`.

**`api/*.py` are Vercel serverless functions that re-import from `server.py`** rather than duplicating logic — each defines its own `handler(BaseHTTPRequestHandler)` because Vercel's Python runtime expects that per-file. `vercel.json` rewrites map clean paths to these files:
- `/health` → `api/health.py`
- `/urls-a-eliminar` → `api/urls-a-eliminar.py`
- `/send-report` → `api/send-report.py`
- `/` → `api/urls-a-eliminar.py`

When changing the sitemap-fetching or duplicate-detection logic, edit it once in `server.py` — `api/urls-a-eliminar.py` and `api/send-report.py` import those functions rather than reimplementing them. `api/send-report.py` is otherwise a near-duplicate of `local_send_report.py` (same SMTP/email-building code) adapted to the `BaseHTTPRequestHandler` shape and gated by `CRON_SECRET` (via `?secret=` or `X-Cron-Secret` header).

**Email delivery** (`local_send_report.py` and `api/send-report.py`) sends through raw `smtplib` (MailerSend SMTP), not an HTTP API — builds a multipart `EmailMessage` with a plain-text JSON report and an HTML table body.

**Scheduling**: an external cron pinger (cron-job.org) hits the deployed `/send-report?secret=...` endpoint every 5 days (`0 14 */5 * *`, UTC). `.github/workflows/send-report.yml` no longer runs on a schedule — GitHub auto-disables `schedule`-triggered workflows on public repos after 60 days without repository activity, so scheduling moved outside GitHub Actions; the workflow now only exposes `workflow_dispatch` as a manual fallback.

**`extractor.py` and `extractor_duplicados.py` are a legacy manual two-step flow** (regex-extract URLs from a pasted `urls-sitemaps.txt` → filter by suffix into `urls_a_eliminar.txt`). They predate `server.py`'s live-fetch approach and are superseded by it — prefer `server.py`/`/urls-a-eliminar` for anything new.

## Config

Env vars (Vercel project settings, or local `.env`):
- `FROM_EMAIL`, `TO_EMAIL`, `SERVER_SMTP`, `PORT_SMTP`, `USER_SMTP`, `PASS_SMTP` — required for the email-report endpoints/scripts.
- `CRON_SECRET` (optional) — if set, `/send-report` requires a matching `?secret=` or `X-Cron-Secret`.
- `SUFFIXES` (optional) — comma-separated suffix list; falls back to the code defaults in `server.py` when unset and no `?suffixes=`/CLI arg is given.
