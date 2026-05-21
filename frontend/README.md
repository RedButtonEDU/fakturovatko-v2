# Fakturovatko v2 — frontend

React SPA pro objednávkový formulář Exponential Summit 2026. V produkci se servíruje jako statika z FastAPI (`backend/app/static` po `npm run build` v Dockeru).

## Lokální vývoj

```bash
npm install
npm run dev
```

- UI: `http://localhost:5173`
- API: proxy na `http://127.0.0.1:8000` pro `/api`, `/health`, `/internal` (`vite.config.ts`)
- Backend musí běžet zvlášť (`uvicorn` v `backend/`, viz kořenové [README.md](../README.md))

## Build

```bash
npm run build
```

Výstup: `dist/` — v Docker image kopírován do `backend/app/static`.

## Klíčové soubory

| Soubor | Účel |
|--------|------|
| `src/App.tsx` | Formulář, IČO lookup, odeslání objednávky |
| `src/api.ts` | Fetch na `/api/*` (same-origin v produkci) |
| `src/i18n.ts` | CZ/EN texty |

## API volané z UI

- `GET /api/event`, `/api/releases`, `/api/countries`
- `GET /api/ares/lookup?ico=…&country=CZ|SK` — vyplnění firmy (bez pole `raw` v odpovědi)
- `POST /api/orders` — vytvoření objednávky

Při překročení rate limitu lookup vrací **429**.

## Styling

Tmavý podklad a zlaté akcenty (inspirace leadershipsummit.cz). Font Montserrat z Google Fonts — CSP na backendu povoluje `fonts.googleapis.com` / `fonts.gstatic.com`.
