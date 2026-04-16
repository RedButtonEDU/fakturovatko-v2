# Fakturovatko v2

**Repository:** [github.com/RedButtonEDU/fakturovatko-v2](https://github.com/RedButtonEDU/fakturovatko-v2)

Webová aplikace pro objednávku vstupenek **Exponential Summit 2026** s proforma fakturou (Allfred), systémovým e-mailem (výchozí odesílatel **Tým Red Button** / `hello@redbuttonedu.cz`), kontrolou platby, slevovým kódem Ti.to a zápisem do Pipedrive.

## Stack

- **Backend:** FastAPI, SQLAlchemy (SQLite), httpx
- **Frontend:** React + Vite + TypeScript (styling inspirovaný leadershipsummit.cz — tmavý podklad, zlaté akcenty)
- **Deploy:** jeden Docker image (viz `Dockerfile`), statika servírovaná z FastAPI

## Lokální vývoj

### Backend

```bash
cd backend
python3 -m venv .venv
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

- **[Kompletní návod (Coolify, Google, GitHub, DNS, …)](docs/NAVOD_NASAZENI.md)**
- [docs/COOLIFY.md](docs/COOLIFY.md) — stručné poznámky k Coolify a cronu

## Poznámky

- Po odeslání formuláře vznikne v Allfredu **zálohová proforma** (`quickSetupClientProjectInvoice` s `type: PROFORMA`), PDF se stáhne po **webovém přihlášení** (`ALLFRED_UI_EMAIL` / `ALLFRED_UI_PASSWORD`, stejný princip jako projekt *Allfred invoices – Equilibrium*) a odešle v e-mailu (dále quick setup + Gmail).
- Cron job `POST /internal/jobs/poll-payments` zpracuje zaplacené proformy; u starých testovacích řádků s `mock-proforma-…` v DB lze v dev nastavit `ALLFRED_MOCK_PAID=true`.
