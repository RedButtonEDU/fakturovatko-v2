"""Application settings from environment."""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name: str = "Fakturovatko"
    debug: bool = False
    database_url: str = "sqlite:///./data/fakturovatko.sqlite3"
    sqlite_path: Path = Path("data/fakturovatko.sqlite3")

    # CORS (comma-separated; frontend same origin in production when served by FastAPI)
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Cron (Coolify: CRON_SECRET)
    cron_secret: str = "change-me-in-production"

    # Ti.to
    tito_api_key: Optional[str] = None
    tito_account_slug: str = "redbutton"
    tito_event_slug: str = "es-2026"

    # Allfred GraphQL
    allfred_api_key: Optional[str] = None
    allfred_workspace: str = "redbuttonedu"
    # Dev: treat mock proformas as paid in cron job
    allfred_mock_paid: bool = False
    # quickSetupClientProjectInvoice — výchozí ID v Allfred workspace (lze přepsat env, viz Coolify).
    allfred_workspace_company_id: str = "1"
    # Tým „Eventy & Komunity“
    allfred_team_id: str = "12"
    # Uživatel Michal Šrajer
    allfred_project_manager_id: str = "27"
    allfred_quick_setup_error_email: str = "lukas@redbuttonedu.cz"
    # VAT rate as Allfred BigInt (e.g. 2100 = 21 %)
    allfred_invoice_vat_rate: int = 2100
    # QuickSetupInvoiceInput (optional; workspace default bank account if unset)
    allfred_workspace_bank_account_id: Optional[str] = None
    allfred_invoice_sequence_id: Optional[str] = None
    # QuickSetupInvoiceInput.vat_reverse_charge (EU reverse charge); unset = omit from mutation
    allfred_vat_reverse_charge: Optional[bool] = None
    # PROFORMA: due_date = issue_date + N days (QuickSetupInvoiceInput)
    allfred_proforma_due_days: int = 14
    # Minimální datum vystavení v Allfredu (businessLogic); issue/due/supply = max(today, floor)
    allfred_issue_date_not_before: str = "2026-04-16"
    # Web UI login (optional) — PDF download URLs vrací SPA/HTML bez session; Equilibrium/n8n používá cookie po POST /login
    allfred_ui_email: Optional[str] = None
    allfred_ui_password: Optional[str] = None
    # Jednotková cena v Kč, pokud objednávka nemá ticket_unit_price_czk (starší řádky)
    allfred_fallback_unit_price_czk: float = 1000.0
    # Celé jméno kontaktu na Allfred PDF (QuickSetup client_data contact_*); ne GMAIL_FROM_NAME (odesílatel e-mailu).
    allfred_contact_name: str = "Dominik Holíček"
    # Čárkou oddělené Allfred id proformy a/nebo invoice_no — považovat za zaplacené i bez paid_at (workaround, když Allfred neumí simulovat úhradu). Po testu smažte.
    allfred_fake_paid_proforma_refs: str = ""

    # Gmail (same pattern as RB Universe)
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    gmail_refresh_token: Optional[str] = None
    # Odesílatel systémových e-mailů (MIME From); kontakt na dokladu v Allfredu viz allfred_contact_name
    gmail_from_name: str = "Tým Red Button"
    gmail_from_email: str = "hello@redbuttonedu.cz"

    @field_validator("gmail_from_email", mode="before")
    @classmethod
    def _gmail_from_email_nonempty(cls, v: object) -> str:
        default = "hello@redbuttonedu.cz"
        if v is None:
            return default
        if isinstance(v, str):
            s = v.strip()
            if not s or "@" not in s:
                return default
            return s
        return default

    @field_validator("gmail_from_name", mode="before")
    @classmethod
    def _gmail_from_name_nonempty(cls, v: object) -> str:
        default = "Tým Red Button"
        if v is None:
            return default
        if isinstance(v, str):
            s = v.strip()
            return s if s else default
        return default

    @field_validator("allfred_contact_name", mode="before")
    @classmethod
    def _allfred_contact_name_nonempty(cls, v: object) -> str:
        default = "Dominik Holíček"
        if v is None:
            return default
        if isinstance(v, str):
            s = v.strip()
            return s if s else default
        return default

    # Pipedrive
    pipedrive_api_token: Optional[str] = None
    pipedrive_base_url: str = "https://api.pipedrive.com/v1"

    # Custom field keys (Pipedrive)
    pipedrive_org_field_ico: str = "dc8020a215fd0bb6280841a61ebd3d18861665b6"
    pipedrive_org_field_dic: str = "58817b04de78bb09468b1cb7ee4340a6f471d035"
    pipedrive_person_field_hw_live: str = "3166f6b49ff1259e1ace35bfb691f07a0e86effd"

    # VAT (Czech default for CZK tickets)
    default_vat_rate: float = 0.21

    # OpenData FS (SK) — IČ DPH z informačních seznamů; hlavička ``key`` u iz.opendata.financnasprava.sk
    opendata_fs: Optional[str] = None


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_database_url() -> str:
    s = get_settings()
    url = s.database_url
    if url.startswith("sqlite:///./"):
        path = Path(url.replace("sqlite:///./", ""))
        path.parent.mkdir(parents=True, exist_ok=True)
    return url
