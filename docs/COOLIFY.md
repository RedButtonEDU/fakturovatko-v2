# Nasazení na Coolify (invoice.exponentialsummit.cz)

Stručný checklist. Kompletní postup: [NAVOD_NASAZENI.md](NAVOD_NASAZENI.md).

## Build

- **Dockerfile** v kořeni (Node → `app/static`, Python 3.12 + uvicorn).
- **Port:** `8000`.
- **Health check:** `GET /health` → `{"status":"ok"}` (bez úniku konfigurace).

## Volume

Mount **`/data`** a nastavte:

```env
DATABASE_URL=sqlite:////data/fakturovatko.sqlite3
```

Název volume v Coolify jen ASCII (např. `fakturovatko-data`).

## Doména a TLS

- Pouze **`https://invoice.exponentialsummit.cz`** (Let's Encrypt v Coolify).
- **`ALLOWED_ORIGINS`:** `https://invoice.exponentialsummit.cz` (bez sslip.io, pokud ho nepoužíváte).

## Produkční bezpečnost (doporučené env)

| Proměnná | Hodnota | Účel |
|----------|---------|------|
| `SECURITY_HSTS_MAX_AGE` | `31536000` | HSTS za HTTPS proxy |
| `FORWARDED_TRUSTED_HOSTS` | `*` | Důvěra `X-Forwarded-Proto` (Coolify/Traefik) |
| `EXPOSE_OPENAPI` | *(nepřidávat / false)* | Skrytí `/openapi.json` a `/docs` |
| `ARES_RATE_LIMIT_PER_MINUTE` | `30` | Limit lookup IČO (default v kódu) |
| `DEBUG` | *(nepřidávat / false)* | `/health` bez `gmail_from_*` |

OpenAPI a Swagger UI jsou ve výchozím nastavení **vypnuté** — nemusíte nic explicitně vypínat, pokud nenastavíte `EXPOSE_OPENAPI=true`.

## Scheduled task (2–3× denně)

| Pole | Hodnota |
|------|---------|
| Command | `curl -fsS -X POST -H "X-Cron-Token: $CRON_SECRET" http://localhost:8000/internal/jobs/poll-payments` |
| Container | stejná služba jako aplikace |
| Timeout | 300 |

- `CRON_SECRET` v env služby = hodnota v hlavičce cronu.
- Job běží jen při **`CRON_POLL_PAYMENTS_ENABLED=true`** (jinak API vrátí `skipped`).

## Proměnné prostředí

Kompletní seznam: [`env.example`](../env.example) a tabulka v [NAVOD §5](NAVOD_NASAZENI.md#5-coolify--proměnné-prostředí).

Minimálně: `DATABASE_URL`, `ALLOWED_ORIGINS`, `CRON_SECRET`, `TITO_*`, `ALLFRED_*`, `GOOGLE_*`, `GMAIL_REFRESH_TOKEN`, `PIPEDRIVE_API_TOKEN`.

## Ověření po deployi

```bash
curl -s https://invoice.exponentialsummit.cz/health
curl -s -o /dev/null -w "%{http_code}\n" https://invoice.exponentialsummit.cz/openapi.json   # očekáváno 404
curl -sI https://invoice.exponentialsummit.cz/ | grep -iE 'strict-transport|content-security|x-frame'
```

## Auto deploy

Push do **`main`** → Coolify rebuild (GitHub App na `RedButtonEDU/fakturovatko-v2`).

Push musí proběhnout pod účtem s přístupem k orgu **RedButtonEDU** (osobní účet bez oprávnění → `403`).
