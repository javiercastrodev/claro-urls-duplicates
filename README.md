# claro-sitemaps

Servicio en Python para descargar y procesar el sitemap de `https://www.claro.com.pe/sitemap.xml` y devolver un JSON con las URLs que se consideran “duplicadas” para eliminación.

Actualmente se consideran duplicadas las URLs que terminan en alguno de estos sufijos (ignorando el `/` final):

- `_test`
- `-test`
- `_1`

Además, para cada URL se devuelve el campo `lastmod` del XML como `ultima_actualizacion`.

## Requisitos

- Python 3.10+ (recomendado)

## Ejecutar en local

```bash
python3 server.py 8000
```

Luego:

```bash
curl "http://127.0.0.1:8000/health"
curl "http://127.0.0.1:8000/urls-a-eliminar"
```

## Desplegar en Vercel

Este repo incluye funciones serverless en la carpeta `api/` y un `vercel.json` con rewrites para exponer:

- `/health` -> `/api/health.py`
- `/urls-a-eliminar` -> `/api/urls-a-eliminar.py`

Pasos:

1. Sube el repositorio a GitHub.
2. En Vercel:
   1. New Project
   2. Importa el repo
   3. Deploy

Una vez desplegado, podrás consultar:

- `https://TU-PROYECTO.vercel.app/health`
- `https://TU-PROYECTO.vercel.app/urls-a-eliminar`

## Envío automático por correo (GitHub Actions + MailerSend)

Se incluyó el endpoint `GET /send-report` (mapea a `/api/send-report.py`). Para ejecutarlo automáticamente cada 3 días se usa un workflow programado de GitHub Actions.

Variables de entorno requeridas en Vercel (Project Settings -> Environment Variables):

- `FROM_EMAIL`
- `TO_EMAIL`
- `SERVER_SMTP`
- `PORT_SMTP`
- `USER_SMTP`
- `PASS_SMTP`

Variable opcional (recomendado):

- `CRON_SECRET`

Si defines `CRON_SECRET`, el endpoint validará `?secret=...` (y también acepta el header `X-Cron-Secret`).

Variable opcional:

- `SUFFIXES`

Lista separada por comas con los sufijos a detectar (por ejemplo `_test,-test,_1,_bkp,_2`). Si NO envías el parámetro `suffixes` en la URL (o por CLI en local), se tomará este valor. Si `SUFFIXES` no está definido, se usan los sufijos por defecto del proyecto.

### Scheduler (GitHub Actions)

El workflow vive en `.github/workflows/send-report.yml`.

Configura estos secrets en GitHub (Settings -> Secrets and variables -> Actions):

- `SEND_REPORT_URL`: por ejemplo `https://TU-PROYECTO.vercel.app/send-report`
- `CRON_SECRET`: el mismo valor que configuraste como variable de entorno en Vercel

Nota: el cron del workflow está en UTC. El ejemplo está configurado para correr a las 09:00 hora Lima (14:00 UTC) cada 3 días.

## Envío por correo en local (sin Vercel)

1. Crea un archivo `.env` (en la raíz del proyecto) con:

```env
FROM_EMAIL=...
TO_EMAIL=...
SERVER_SMTP=smtp.mailersend.net
PORT_SMTP=587
USER_SMTP=...
PASS_SMTP=...
```

2. Ejecuta:

```bash
python3 local_send_report.py
```

Opcional:

```bash
python3 local_send_report.py "https://www.claro.com.pe/sitemap.xml" "_test,-test,_1,_bkp,_2"
```

## Endpoints

- `GET /health`

Devuelve:

```json
{"status":"ok"}
```

- `GET /urls-a-eliminar`

Ejemplo:

```bash
curl "http://127.0.0.1:8000/urls-a-eliminar"
```

Parámetros opcionales:

- `sitemap`: URL del sitemap raíz (por defecto `https://www.claro.com.pe/sitemap.xml`)
- `suffixes`: lista separada por comas (por defecto `SUFFIXES` si está definido; si no, los defaults del proyecto)

Respuesta incluye:

- `total_urls`
- `count`
- `urls_to_delete` (lista de objetos con `url` y `ultima_actualizacion`)
- `suffixes`
- `elapsed_ms`

Ejemplo (local):

```bash
curl "http://127.0.0.1:8000/urls-a-eliminar?suffixes=_test,-test,_1"
```

Ejemplo de respuesta (recortado):

```json
{
  "sitemap": "https://www.claro.com.pe/sitemap.xml",
  "suffixes": ["_test", "-test", "_1"],
  "total_urls": 2793,
  "urls_to_delete": [
    {
      "url": "https://www.claro.com.pe/esim-test/",
      "ultima_actualizacion": "2025-10-23"
    }
  ],
  "count": 1,
  "elapsed_ms": 109
}
```
