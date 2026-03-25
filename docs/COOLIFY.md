# Nasazení na Coolify (invoice.exponentialsummit.cz)

## Build

- **Dockerfile** v kořeni repa (multi-stage: Node build frontend → Python + statika v `app/static`).
- **Port:** `8000` (uvicorn).
- **Health check:** `GET /health` (zahrnuto v Dockerfile).

## Volume

Připojte volume na **`/data`** v kontejneru a nastavte:

```env
DATABASE_URL=sqlite:////data/fakturovatko.sqlite3
```

## Scheduled task (2–3× denně)

| Pole | Hodnota |
|------|---------|
| Command | `curl -fsS -X POST -H "X-Cron-Token: $CRON_SECRET" http://localhost:8000/internal/jobs/poll-payments` |
| Container | stejná služba jako aplikace |
| Timeout | 300 |

`CRON_SECRET` musí být stejný jako proměnná `CRON_SECRET` / `cron_secret` v aplikaci (v kódu `Settings.cron_secret`).

## Doména a TLS

V Coolify přidejte doménu `invoice.exponentialsummit.cz` a nechte vystavit Let's Encrypt certifikát.

## Proměnné prostředí

Viz [env.example](../env.example) v kořeni — zkopírujte hodnoty do Coolify (TITO, Allfred, Gmail, Pipedrive, CRON_SECRET, DATABASE_URL, ALLOWED_ORIGINS pro produkční URL frontendu).

## Auto deploy

Po pushi do připojené větve Coolify sám sestaví image a nasadí (stejný vzor jako RB Universe).
