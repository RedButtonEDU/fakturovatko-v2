# Fakturovatko v2

Webová aplikace pro objednávku vstupenek **Exponential Summit 2026** s proforma fakturou (Allfred), e-mailem z `hello@redbuttonedu.cz`, kontrolou platby, slevovým kódem Ti.to a zápisem do Pipedrive.

## Stack

- **Backend:** FastAPI, SQLAlchemy (SQLite), httpx
- **Frontend:** React + Vite + TypeScript (styling inspirovaný leadershipsummit.cz — tmavý podklad, zlaté akcenty)
- **Deploy:** jeden Docker image (viz `Dockerfile`), statika servírovaná z FastAPI

## Lokální vývoj

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../env.example .env   # upravte
mkdir -p data
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend (proxy na API)

```bash
cd frontend
npm install
npm run dev
```

Otevřete `http://localhost:5173` — požadavky na `/api` jdou přes Vite proxy na port 8000.

## Produkční build (bez Dockeru)

```bash
cd frontend && npm run build
# Zkopírujte dist do backend/app/static nebo použijte jen Docker build
```

## Docker

```bash
docker build -t fakturovatko .
docker run --rm -p 8000:8000 -e TITO_API_KEY=... fakturovatko
```

## Dokumentace nasazení

- [docs/COOLIFY.md](docs/COOLIFY.md)

## Poznámky

- Vytvoření proforma faktury v Allfred API zatím není — používá se **mock PDF**; pole a služby jsou připravené na napojení.
- Cron job `POST /internal/jobs/poll-payments` zpracuje zaplacené proformy; u mock objednávek lze v dev nastavit `ALLFRED_MOCK_PAID=true`.
