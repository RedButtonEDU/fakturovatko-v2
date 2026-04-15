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
| `TITO_EVENT_SLUG` | ano | `es-2026` |
| `ALLFRED_API_KEY` | ano | Bearer token Workspace API |
| `ALLFRED_WORKSPACE` | ano | např. `redbuttonedu` |
| `GOOGLE_CLIENT_ID` | ano* | OAuth klient (Gmail) |
| `GOOGLE_CLIENT_SECRET` | ano* | OAuth secret |
| `GMAIL_REFRESH_TOKEN` | ano* | Refresh token pro Google účet s oprávněním odesílat jako **`GMAIL_FROM_EMAIL`** (výchozí Dominik / dominik@…) |
| `PIPEDRIVE_API_TOKEN` | ano | API token (uživatel s právy zápisu) |
| `OPENDATA_FS` | ne | API klíč z [OpenData FS](https://opendata.financnasprava.sk/en/page/openapi) — doplnění **IČ DPH** (DIČ) při načtení slovenského IČO z RPO; bez klíče zůstane pole DIČ prázdné |
| `ALLFRED_MOCK_PAID` | ne | Produkce: `false`. `true` = simulace zaplacení u mock proformy — viz [§11](#11-alfred) |

\* Bez Gmail proměnných odeslání e-mailu selže; aplikace při chybě může vracet 503 u odeslání objednávky.

Úplný přehled je také v souboru [`env.example`](../env.example) v kořeni repa.

Po nastavení **`OPENDATA_FS`** a redeployi lze ověřit klíč interním endpointem (stejný token jako u cronu):  
`curl -fsS -H "X-Cron-Token: $CRON_SECRET" http://localhost:8000/internal/opendata-fs`  
(v produkci přes HTTPS na `localhost:8000` uvnitř kontejneru v Coolify). Odpověď `ok: true` znamená, že volání `GET …/api/lists` s klíčem funguje.

---

## 6. Coolify — volume pro SQLite

1. U služby přidejte **Volume** (persistentní disk).

2. **Mount path v kontejneru:** `/data`

3. Pole **Name** u volume zadejte jen **ASCII** (např. `fakturovatko-data`) — bez diakritiky a mezer. Název typu „Databáze“ způsobí chybu `docker compose` při validaci (`volumes additional properties … not allowed`).

4. V proměnných musí být `DATABASE_URL=sqlite:////data/fakturovatko.sqlite3` (čtyři lomítka za `sqlite:` — cesta absolutní).

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

6. **Refresh token** (scope `gmail.send`, stejný jako v backendu): v repu je skript `scripts/obtain_gmail_refresh_token.py`. Doporučeně ho spusťte **lokálně** (klon repa), v aktivovaném venv s `backend/requirements.txt`, např. `python3 scripts/obtain_gmail_refresh_token.py --secrets-file ~/Downloads/client_secret_….json` (OAuth klient typu **Desktop app** — stažený JSON z Google Cloud). Pro klient typu **Web application** v **Authorized redirect URIs** přidejte přesně `http://localhost:8080/` (knihovna `google_auth_oauthlib` ve výchozím stavu používá host `localhost`, ne `127.0.0.1` — jinak dostanete chybu `redirect_uri_mismatch`). Můžete přidat i druhou řádku `http://127.0.0.1:8080/`, pokud byste někdy měnili host. Výchozí port skriptu je `8080`. Po novém buildu image je stejný soubor v kontejneru jako `python3 /app/scripts/obtain_gmail_refresh_token.py` (OAuth z kontejneru často potřebuje mapování portu na hosta — jednodušší je lokální běh). V prohlížeči se přihlaste **účtem, pod kterým má Gmail API oprávnění posílat jako `GMAIL_FROM_EMAIL`** (výchozí v kódu je `dominik@redbuttonedu.cz`); výstup `GMAIL_REFRESH_TOKEN=…` vložte do Coolify. **Přihlášení do Allfred webu** (`ALLFRED_UI_EMAIL`) je jen pro stažení PDF a **nemění** odesílatele Gmailu. Pokud v schránce stále vidíte jinou adresu než v `GMAIL_FROM_EMAIL`, zkontrolujte v Coolify, že tam **není** přepsána špatná hodnota (prázdný řetězec se bere jako výchozí z kódu), případně druhý e-mail z Allfredu / Ti.to.

7. V **Google Workspace Admin** (pokud používáte) ověřte, že účet smí používat danou OAuth aplikaci.

### Slovenské IČO, DIČ a IČ DPH (formulář „faktura na firmu“)

- **IČO** (8 číslic) — identifikátor subjektu v obchodnom registri; načítáme z RPO přes veřejné API ŠÚ SR (`api.statistics.sk`).
- **DIČ** — 10 číslic, daňové identifikační číslo; **není** matematicky odvozené od IČO (proto ho aplikace z IČO „nevypočítá“).
- **IČ DPH** (pro faktury v EU / osvobození) — formát **SK** + **stejných 10 číslic jako u DIČ** (příklad tvaru: `SK1234567890`).

**Jak doplnit DIČ / IČ DPH:** při nastaveném **`OPENDATA_FS`** aplikace při „Načíst z RPO“ zkusí **DIČ** doplnit z informačního seznamu registrovaných plátců DPH (formát `SK` + 10 číslic). Jinak ručně z fakturačních údajů firmy, z [overenia IČ DPH](https://www.financnasprava.sk/sk/elektronicke-sluzby/verejne-sluzby/overovanie-ic-dph) / [VIES](https://ec.europa.eu/taxation_customs/vies/) (když už číslo znáte), nebo komerční služby (např. FirmAPI, Finstat) umí vyhledání podle IČO včetně DIČ.

**Registrace k OpenData API (klíč pro vývojáře, ne daňové přihlášení):**

- Portál: [opendata.financnasprava.sk](https://opendata.financnasprava.sk/) — anglická dokumentace a formulář **„Generate an API key“**: [en/page/openapi](https://opendata.financnasprava.sk/en/page/openapi). Po vyplnění povinných polí obdržíte **autorizační klíč**; v hlavičce požadavků: `key: <váš klíč>`. Technická dokumentace datasetů: [en/page/doc](https://opendata.financnasprava.sk/en/page/doc). Samostatné API **informačních seznamů** (DPH, dlužníci, …): [iz.opendata.financnasprava.sk](https://iz.opendata.financnasprava.sk/) (OpenAPI `/openapi.yaml`), příklad: `curl -H "key: …" https://iz.opendata.financnasprava.sk/api/lists`.
- **Není to totéž** jako [registrace uživatele portálu FS](https://www.financnasprava.sk/sk/elektronicke-sluzby/verejne-sluzby/registracia-pouzivatela-portal) (ta je pro fyzické osoby komunikující s finanční správou — formulář, e-mail, často návštěva úřadu nebo slovensko.sk / eID). Pro **čtení otevřených dat přes API** jde o **vývojářskou registraci na portálu OpenData**, ne o slovenské daňové rezidentství.
- **Zahraniční subjekty / vývojáři:** [podmínky použití](https://opendata.financnasprava.sk/page/licence) portálu jsou CC BY 4.0 a nevyžadují slovenské IČO ani rezidentství; klíč slouží hlavně k **limite volání** (standardně **1000 požadavků/hod.**; navýšení přes kontakt na portálu). Konkrétní pole registračního formuláře API se mění — pokud by formulář vyžadoval údaje, které nemáte, použijte kontakt v patičce portálu nebo [kontakt FS](https://www.financnasprava.sk/sk/kontakt).

---

## 10. Ti.to

1. Na [id.tito.io](https://id.tito.io) vytvořte **API token** typu **secret**, režim **live**.

2. Vložte do `TITO_API_KEY`.

3. Účet a event odpovídají `TITO_ACCOUNT_SLUG=redbutton`, `TITO_EVENT_SLUG=es-2026`.

---

## 11. Allfred

1. Z Allfred Workspace získejte **API klíč** pro GraphQL (`workspace-api`).

2. Nastavte `ALLFRED_API_KEY` a `ALLFRED_WORKSPACE` (subdoména před `-api.allfred.io`).

### Simulace druhé fáze (zaplacená proforma bez reálné proformy v Allfredovi)

Normální objednávka z formuláře vytvoří v Allfredu **skutečnou proformu** a uloží její ID. Simulace se týká jen **starých testovacích řádků** v DB s ID `mock-proforma-…` / `mock-project-…` (bez odpovídající proformy v Allfredu).

1. Nastavte **`ALLFRED_MOCK_PAID=true`** (v Coolify nebo lokálně). V produkci nechte **`false`**, jinak by se „zaplacené“ chovaly i tyto mock záznamy.

2. Pokud jsou ve frontě **jen** objednávky s mock proformou, aplikace **nevolá** Allfred GraphQL — stačí mít prázdný `ALLFRED_API_KEY` pro čistou simulaci druhé fáze. Pro reálný běh včetně vytváření proformy při objednávce stačí v Coolify **`ALLFRED_API_KEY`** a **`ALLFRED_WORKSPACE`**; ID firmy / týmu / PM a error e-mail mají **výchozí hodnoty v kódu** (jako projekt Allfred invoices – Equilibrium), případně je přepište env proměnnými.

3. Spusťte job stejně jako cron:  
   `curl -fsS -X POST -H "X-Cron-Token: $CRON_SECRET" http://localhost:8000/internal/jobs/poll-payments`  
   (v Coolify uvnitř kontejneru, nebo přes HTTPS s platným tokenem).

4. Očekávaný výsledek: Ti.to slevový kód, e-mail s finální fakturou (náhled PDF), zápis do Pipedrive, stav objednávky **dokončeno** (vyžaduje nakonfigurované `TITO_API_KEY`, Gmail, případně Pipedrive podle prostředí).

Odpověď jobu obsahuje i **`last_errors`** (text výjimky) a **`skipped`** (objednávky přeskočené — např. mock bez `ALLFRED_MOCK_PAID`, nebo proforma v Allfredovi ještě nezaplacená). Typická chyba při simulaci: **`TITO_API_KEY missing`** nebo chyba API Ti.to.

Po selhání má objednávka stav **`error`** a job ji znovu nevezme. Po opravě konfigurace buď vytvořte novou testovací objednávku, nebo v SQLite ručně vraťte řádek do fronty: `status = 'awaiting_payment'`, `last_error = NULL` (a případně `tito_discount_code` vyprázdněte).

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
| E-mail se neodesílá / špatný odesílatel | `GOOGLE_*`, `GMAIL_REFRESH_TOKEN`, scope `gmail.send`; v logu aplikace řádek `Gmail send: MIME From header` musí odpovídat `GMAIL_FROM_EMAIL` / výchozí Dominik; OAuth účet musí smět odesílat jako tato adresa; `ALLFRED_UI_EMAIL` není odesílatel Gmailu |
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
