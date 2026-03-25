# Kompletní návod: Fakturovatko v2 — nasazení a konfigurace

Tento dokument shrnuje kroky od nuly po běžící aplikaci na **invoice.exponentialsummit.cz** v **Coolify**, včetně **Google Cloud**, **GitHub**, **DNS** a dalších služeb.

**Produkce = jedna doména:** stačí **`https://invoice.exponentialsummit.cz`**. Adresy typu **sslip.io** nejsou potřeba — nepřidávejte je do Coolify Domains ani do `ALLOWED_ORIGINS`, pokud je nechcete používat.

Repozitář: [github.com/RedButtonEDU/fakturovatko-v2](https://github.com/RedButtonEDU/fakturovatko-v2)

---

## Obsah

1. [Přehled architektury](#1-přehled-architektury)
2. [GitHub — repozitář a GitHub App](#2-github--repozitář-a-github-app)
3. [Coolify — GitHub App a zdroj kódu](#3-coolify--github-app-a-zdroj-kódu)
4. [Coolify — nová aplikace (služba)](#4-coolify--nová-aplikace-služba)
5. [Coolify — proměnné prostředí](#5-coolify--proměnné-prostředí)
6. [Coolify — volume pro SQLite](#6-coolify--volume-pro-sqlite)
7. [Coolify — doména a TLS](#7-coolify--doména-a-tls)
8. [Coolify — Scheduled Task (cron)](#8-coolify--scheduled-task-cron)
9. [Google Cloud Console — Gmail / OAuth](#9-google-cloud-console--gmail--oauth)
10. [Ti.to](#10-tito)
11. [Allfred](#11-allfred)
12. [Pipedrive](#12-pipedrive)
13. [DNS](#13-dns)
14. [Ověření po nasazení](#14-ověření-po-nasazení)
15. [Časté problémy](#15-časté-problémy)

---

## 1. Přehled architektury

- Jedna **Docker** služba: **FastAPI** (API + statický frontend) na portu **8000**.
- **SQLite** soubor na **persistentním volume** (např. `/data`).
- Deploy z **GitHubu** přes **GitHub App** (webhook + přístup k repozitáři).
- Pravidelný **cron** v Coolify volá interní endpoint pro kontrolu plateb a dokončení flow.

---

## 2. GitHub — repozitář a GitHub App

### 2.1 Repozitář

- Organizace: **RedButtonEDU**
- Repo: **fakturovatko-v2**
- Větev pro produkci: **main**
- V kořeni je **Dockerfile** (Coolify má buildovat z něj, ne Nixpacks).

### 2.2 Vytvoření GitHub App (v Coolify nebo na GitHubu)

Obvykle: v Coolify **Settings → Sources / GitHub → Add GitHub App** a dokončení **Automated Installation** (Register Now, webhook na vaši Coolify URL, např. `http://<IP>:8000`).

### 2.3 Oprávnění GitHub App na github.com (důležité)

1. Jděte na: **Organization RedButtonEDU → Settings → GitHub Apps → vaše aplikace (např. fakturovatko-v2) → Configure**.

2. **Repository access**

   - Buď **All repositories**, nebo **Only select repositories** a vyberte jen **fakturovatko-v2** (bezpečnější).

3. **Permissions & events** — sekce **Repository permissions** musí mít vybrané minimálně:

   | Oprávnění   | Doporučení   | Poznámka                          |
   |------------|--------------|-----------------------------------|
   | **Metadata** | Read-only    | často povinné                     |
   | **Contents** | Read-only    | čtení kódu pro build              |

   Bez **Contents** Coolify často **nenačte žádná repa** („No repositories found“).

4. **Subscribe to events** — typicky stačí:

   - **Push** (auto deploy po pushi)
   - případně **Pull request** (preview deployy)

5. Klikněte **Save changes**. Pokud GitHub vyžádá schválení nových oprávnění u instalace, organizace to musí **schválit**.

---

## 3. Coolify — GitHub App a zdroj kódu

1. V Coolify otevřete záznam **GitHub App** (stejný název jako na GitHubu, vyplněné **App Id**, **Installation Id**, **Private key**).

2. Klikněte **Refetch** (případně **Update** u oprávnění).

3. Poznámka: u některých verzí Coolify zůstává u **Content / Metadata / Pull Request** hodnota **N/A** i při funkčním připojení. Rozhodující je, zda při **výběru repozitáře u nové aplikace** už **vidíte seznam rep** — pokud ano, **N/A** můžete ignorovat.

4. Pokud stále **„No repositories found“**:

   - zkontrolujte [sekci 2.3](#23-oprávnění-github-app-na-githubcom-důležité) (Contents + Metadata, uloženo na GitHubu),
   - používejte **jednu** nakonfigurovanou App, ne vytvářejte druhou prázdnou,
   - zkuste u GitHub App v Coolify zaškrtnout **System wide** (podle verze UI), uložit a znovu otevřít výběr repa.

---

## 4. Coolify — nová aplikace (služba)

1. **Project** (např. Fakturovatko) → **Add Resource** → **Application** (nebo ekvivalent).

2. **Source:** GitHub → vyberte **GitHub App** z kroku 3 → vyberte repository **RedButtonEDU/fakturovatko-v2**, branch **main**.

3. **Build:**

   - Build pack: **Dockerfile**
   - Dockerfile path: **`Dockerfile`** (v kořeni repa)
   - Kontext buildu: kořen repa (default, pokud Coolify nabízí).

4. **Port:** kontejner naslouchá na **8000** (je v Dockerfile / `CMD` uvicorn).

5. Uložte a spusťte první **Deploy**.

---

## 5. Coolify — proměnné prostředí

Nastavte v sekci **Environment Variables** u této služby (hodnoty doplňte vlastními tajemstvími):

| Proměnná | Povinné | Popis |
|----------|---------|--------|
| `DATABASE_URL` | ano | Pro produkci s volume: `sqlite:////data/fakturovatko.sqlite3` |
| `ALLOWED_ORIGINS` | ano | Jen `https://invoice.exponentialsummit.cz` (jedna hodnota; bez sslip.io, pokud ho nepoužíváte) |
| `CRON_SECRET` | ano | Náhodný dlouhý řetězec; **stejná** hodnota jako u scheduled tasku (viz [§8](#8-coolify--scheduled-task-cron)) |
| `TITO_API_KEY` | ano | Token z [id.tito.io](https://id.tito.io) (režim **live**) |
| `TITO_ACCOUNT_SLUG` | ano | `redbutton` |
| `TITO_EVENT_SLUG` | ano | `els-2026` |
| `ALLFRED_API_KEY` | ano | Bearer token Workspace API |
| `ALLFRED_WORKSPACE` | ano | např. `redbuttonedu` |
| `GOOGLE_CLIENT_ID` | ano* | OAuth klient (Gmail) |
| `GOOGLE_CLIENT_SECRET` | ano* | OAuth secret |
| `GMAIL_REFRESH_TOKEN` | ano* | Refresh token pro účet **hello@redbuttonedu.cz** |
| `PIPEDRIVE_API_TOKEN` | ano | API token (uživatel s právy zápisu) |
| `ALLFRED_MOCK_PAID` | ne | Produkce: `false`; pro test mock flow: `true` |

\* Bez Gmail proměnných odeslání e-mailu selže; aplikace při chybě může vracet 503 u odeslání objednávky.

Úplný přehled je také v souboru [`env.example`](../env.example) v kořeni repa.

---

## 6. Coolify — volume pro SQLite

1. U služby přidejte **Volume** (persistentní disk).

2. **Mount path v kontejneru:** `/data`

3. V proměnných musí být `DATABASE_URL=sqlite:////data/fakturovatko.sqlite3` (čtyři lomítka za `sqlite:` — cesta absolutní).

Bez volume se data po redeployi smažou.

---

## 7. Coolify — doména a TLS (jen invoice.exponentialsummit.cz)

Cíl: veřejně používat **pouze** `https://invoice.exponentialsummit.cz` — bez paralelní sslip.io adresy.

1. **DNS** (viz [§13](#13-dns)) nejdřív nasměrujte `invoice.exponentialsummit.cz` na server / proxy podle instrukcí Coolify.

2. V nastavení služby v **Domains** přidejte **jen**  
   `https://invoice.exponentialsummit.cz`  
   (nebo jak Coolify vyžaduje zadání domény — důležité je **HTTPS** a Let’s Encrypt).

3. Pokud Coolify dříve přiřadil automatickou adresu **\*.sslip.io**, můžete ji v **Domains** **odstranit**, až bude produkční doména ověřená a funguje — není nutné mít obě najednou.

4. V `ALLOWED_ORIGINS` nechte **pouze**  
   `https://invoice.exponentialsummit.cz`  
   (bez koncového lomítka; žádný další origin, pokud ho záměrně nepotřebujete).

5. Po změně domény / env spusťte **Redeploy**.

### 7.1 Traefik / Caddy labely

Labely generuje **Coolify**; často obsahují **Traefik i Caddy** najednou (stejný vzor jako v RB Universe — viz jejich `scripts/coolify_dev_labels.sh`). Na serveru aktivní bývá jedna z cest.

**Pro jednu produkční doménu** obvykle **nic ručně nepřepisujte**: po zadání `invoice.exponentialsummit.cz` v UI by měl být `Host(...)` jen pro tuto doménu.

| Kontrola | Co očekávat |
|----------|-------------|
| Port | směrování na kontejnerový port **8000** |
| SPA | `try_files` k `/index.html` je v pořádku pro React |
| HTTPS | routery s TLS / Let’s Encrypt po úspěšném DNS a deployi |

**Readonly labels:** upravujte přes **Domains** v UI; ruční editace jen při konkrétním problému (502, špatný port).

**Volitelně (není potřeba pro vás):** pokud byste někdy chtěli **dvě domény** na jednu službu (např. sslip + vlastní), používá se rozšíření Traefik pravidla `Host(...) || Host(...)` — popis je v RB Universe v `docs/dual_domain_checklist.md`. Pro samotnou **invoice.exponentialsummit.cz** to nepotřebujete.

---

## 8. Coolify — Scheduled Task (cron)

Účel: několikrát denně zavolat interní job (`poll-payments`).

| Pole | Hodnota |
|------|---------|
| Typ | Scheduled Task / Cron |
| Command | `curl -fsS -X POST -H "X-Cron-Token: $CRON_SECRET" http://localhost:8000/internal/jobs/poll-payments` |
| Kontejner | Stejná služba jako aplikace |
| Timeout | např. 300 s |
| Frekvence | např. 2–3× denně (podle potřeby) |

**Důležité:** `CRON_SECRET` musí být v **environment** té služby, aby se `$CRON_SECRET` v příkazu nahradilo. Pokud váš Coolify neexpanduje proměnné, vložte token přímo do hlavičky (méně bezpečné) nebo použijte dokumentaci vaší verze pro „secrets v cronu“.

---

## 9. Google Cloud Console — Gmail / OAuth

1. V [Google Cloud Console](https://console.cloud.google.com) vyberte nebo vytvořte **projekt**.

2. **APIs & Services → Library** — zapněte **Gmail API**.

3. **OAuth consent screen** — nastavte (Internal/External dle organizace), test users pokud je app v režimu Testing.

4. **Credentials → Create credentials → OAuth client ID**

   - Typ závisí na tom, jak získáváte refresh token (často **Desktop** pro jednorázový skript, nebo **Web** s redirect URI jako u RB Universe).

5. Zkopírujte **Client ID** a **Client Secret** → `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`.

6. Přihlaste se účtem **hello@redbuttonedu.cz** a vytvořte **refresh token** se scope pro odesílání pošty (stejný postup jako u RB Universe, pokud ho už máte dokumentovaný). Hodnotu vložte do `GMAIL_REFRESH_TOKEN`.

7. V **Google Workspace Admin** (pokud používáte) ověřte, že účet smí používat danou OAuth aplikaci.

---

## 10. Ti.to

1. Na [id.tito.io](https://id.tito.io) vytvořte **API token** typu **secret**, režim **live**.

2. Vložte do `TITO_API_KEY`.

3. Účet a event odpovídají `TITO_ACCOUNT_SLUG=redbutton`, `TITO_EVENT_SLUG=els-2026`.

---

## 11. Allfred

1. Z Allfred Workspace získejte **API klíč** pro GraphQL (`workspace-api`).

2. Nastavte `ALLFRED_API_KEY` a `ALLFRED_WORKSPACE` (subdoména před `-api.allfred.io`).

---

## 12. Pipedrive

1. V **Pipedrive → Settings → Personal preferences → API** (nebo Company settings) zkopírujte token → `PIPEDRIVE_API_TOKEN` (uživatel s právy na úpravu osob a organizací).

2. U vlastního pole osoby **„H@W Live!“** (`3166f6b49ff1259e1ace35bfb691f07a0e86effd`) přidejte v UI volbu **2026**, pokud tam ještě není (jinak zápis přes API selže).

3. Párování v aplikaci: **osoba podle e-mailu**, **organizace podle IČ** (případně DIČ) — odpovídá polím v kódu/configu.

---

## 13. DNS

Tam, kde spravujete zónu **exponentialsummit.cz**:

- Vytvořte záznam pouze pro **invoice.exponentialsummit.cz** (typ **A** nebo **CNAME**) podle toho, co Coolify zobrazí u služby (cílová IP nebo hostname reverse proxy). Pro tento scénář **sslip.io nepotřebujete**.

Propagace DNS může trvat řádově minuty až hodiny.

---

## 14. Ověření po nasazení

1. `GET https://invoice.exponentialsummit.cz/health` → odpověď `{"status":"ok"}`.

2. Otevřete `https://invoice.exponentialsummit.cz` — načte se formulář.

3. (Volitelně) Otestujte `GET /api/releases` — vyžaduje platný `TITO_API_KEY` na serveru.

4. Odeslání testovací objednávky (s nakonfigurovaným Gmailem).

5. V Coolify **Scheduled Task** spusťte ručně „Run now“ a zkontrolujte logy (job `poll-payments`).

---

## 15. Časté problémy

| Problém | Co zkontrolovat |
|---------|------------------|
| „No repositories found“ | GitHub App má **Contents** + **Metadata** (Read), uloženo na GitHubu; stejná App v Coolify; případně System wide |
| Permissions v Coolify stále N/A | Často kosmetika; ověřte, zda už jdou **vybrat repa** a deploy funguje |
| E-mail se neodesílá | `GOOGLE_*`, `GMAIL_REFRESH_TOKEN`, scope Gmail, účet hello@ |
| Prázdná databáze po deployi | Chybí volume na `/data` nebo špatné `DATABASE_URL` |
| Cron nevolá job | Špatný `X-Cron-Token`, špatný port (8000), příkaz na jiném kontejneru |
| 422 / chyba Pipedrive u pole 2026 | V Pipedrive UI přidat option **2026** do set pole H@W Live! |

---

## Související soubory v repu

- [`README.md`](../README.md) — lokální vývoj, Docker příkaz
- [`env.example`](../env.example) — šablona proměnných
- [`docs/COOLIFY.md`](COOLIFY.md) — stručná poznámka k Coolify a cronu

---

*Poslední úprava: sladěno s aplikací Fakturovatko v2 (FastAPI + React, jeden Docker image).*
