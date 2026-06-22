# Fakturovatko v2

**Repository:** [github.com/RedButtonEDU/fakturovatko-v2](https://github.com/RedButtonEDU/fakturovatko-v2)

Webová aplikace pro objednávku vstupenek **Exponential Summit 2027** s proforma fakturou (Allfred), systémovým e-mailem (výchozí odesílatel **Tým Red Button** / `hello@redbuttonedu.cz`), kontrolou platby, slevovým kódem Ti.to ([ti.to/redbutton/es-2027](https://ti.to/redbutton/es-2027)) a zápisem do Pipedrive.

**Produkce:** [https://invoice.exponentialsummit.cz](https://invoice.exponentialsummit.cz)

## Stack

| Vrstva | Technologie |
|--------|-------------|
| Backend | FastAPI 0.128, Starlette 0.49, SQLAlchemy 2, SQLite, httpx |
| Frontend | React 19, Vite, TypeScript |
| Deploy | Jeden Docker image — statika v `backend/app/static`, servírovaná z FastAPI |

## Struktura repa

```
backend/app/     # FastAPI (routers, services, middleware)
frontend/        # React SPA (build → dist → Docker kopie do app/static)
scripts/         # Gmail OAuth token, Allfred introspection
docs/            # Nasazení (Coolify, env, ověření)
env.example      # Šablona proměnných prostředí
Dockerfile       # Multi-stage build
```

## API (přehled)

| Endpoint | Auth | Popis |
|----------|------|--------|
| `GET /health` | — | Produkce: `{"status":"ok"}`. S `DEBUG=true`: navíc `gmail_from_*` |
| `GET /api/event` | — | Meta Ti.to (ceny s/bez DPH) |
| `GET /api/releases` | — | Seznam vstupenek (Ti.to) |
| `GET /api/countries` | — | Země pro formulář |
| `GET /api/ares/lookup` | — | IČO → název, adresa, DIČ (CZ ARES / SK RPO); rate limit 30/min/IP |
| `POST /api/orders` | — | Nová objednávka + proforma v Allfredu + e-mail |
| `POST /internal/jobs/poll-payments` | `X-Cron-Token` | Cron: kontrola plateb, Ti.to, finální faktura |
| `GET /internal/opendata-fs` | `X-Cron-Token` | Smoke test klíče OpenData FS (SK DIČ) |

**Produkce:** `/openapi.json` a `/docs` jsou **vypnuté** (`EXPOSE_OPENAPI` default `false`). Interní cesty nejsou veřejně dokumentované.

## Bezpečnost (shrnutí)

- **HTTP hlavičky** — middleware: CSP, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`; HSTS při `SECURITY_HSTS_MAX_AGE` + HTTPS za proxy (`FORWARDED_TRUSTED_HOSTS`).
- **OpenAPI** — vypnuto v produkci; lokálně `EXPOSE_OPENAPI=true`.
- **ARES lookup** — odpověď bez surového `raw` JSON z registru; rate limit (`ARES_RATE_LIMIT_PER_MINUTE`, default 30).
- **Cron / interní API** — hlavička `X-Cron-Token` = `CRON_SECRET`.

Detail a Coolify: [docs/NAVOD_NASAZENI.md](docs/NAVOD_NASAZENI.md), [docs/COOLIFY.md](docs/COOLIFY.md).

## Lokální vývoj

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../env.example .env   # upravte; pro Swagger: EXPOSE_OPENAPI=true
mkdir -p data
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend (proxy na API)

```bash
cd frontend
npm install
npm run dev
```

Otevřete `http://localhost:5173` — Vite proxyuje `/api`, `/health` a `/internal` na port **8000** (viz `frontend/vite.config.ts`).

Volitelně jen backend se zbuilděným frontendem: `cd frontend && npm run build` a zkopírujte `dist/*` do `backend/app/static/`, pak uvicorn.

## Produkční build (bez Dockeru)

```bash
cd frontend && npm run build
# dist zkopírovat do backend/app/static/ — v praxi použijte Docker build
```

## Docker

```bash
docker build -t fakturovatko .
docker run --rm -p 8000:8000 \
  -e DATABASE_URL=sqlite:////data/fakturovatko.sqlite3 \
  -v fakturovatko-data:/data \
  -e TITO_API_KEY=... \
  -e CRON_SECRET=... \
  fakturovatko
```

Health check v image: `GET /health` → 200.

## Dokumentace

| Soubor | Obsah |
|--------|--------|
| [docs/NAVOD_NASAZENI.md](docs/NAVOD_NASAZENI.md) | Kompletní nasazení: Coolify, GitHub, Google, DNS, env, ověření |
| [docs/COOLIFY.md](docs/COOLIFY.md) | Stručný checklist Coolify + cron + bezpečnost |
| [env.example](env.example) | Všechny proměnné prostředí |
| [frontend/README.md](frontend/README.md) | Frontend — dev, proxy, build |

## Poznámky k business flow

- Po odeslání formuláře vznikne v Allfredu **zálohová proforma** (`quickSetupClientProjectInvoice`, `type: PROFORMA`). PDF se stáhne po webovém přihlášení (`ALLFRED_UI_EMAIL` / `ALLFRED_UI_PASSWORD`) a odešle e-mailem (Gmail OAuth).
- Cron `POST /internal/jobs/poll-payments` zpracuje zaplacené proformy; ve výchozím stavu je **vypnutý** (`CRON_POLL_PAYMENTS_ENABLED=false`). Pro test mock řádků: `ALLFRED_MOCK_PAID=true`.
