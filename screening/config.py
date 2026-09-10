"""Configuration and secrets, kept strictly out of the code.

Secrets  -> .env             (gitignored)
Settings -> config.yaml      (safe to commit)
Criteria -> criteria.yaml    (the user edits this)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Secrets(BaseSettings):
    """Everything sensitive. Fails loudly at startup, not mid-run."""

    groq_api_key: str = ""
    google_credentials_path: str = "credentials/service_account.json"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    @field_validator("groq_api_key")
    @classmethod
    def _key_present(cls, v: str) -> str:
        if not v or v.startswith("your-") or v.startswith("gsk_xxx"):
            raise ValueError(
                "GROQ_API_KEY is not set.\n"
                "  1. Copy .env.example to .env\n"
                "  2. Get a free key at https://console.groq.com/keys\n"
                "  3. Paste it after GROQ_API_KEY=\n"
                "See README step 2."
            )
        return v

    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)


def load_settings(path: Path | str = ROOT / "config.yaml") -> dict[str, Any]:
    with open(path) as f:
        return yaml.safe_load(f)


def load_criteria(path: Path | str = ROOT / "criteria.yaml") -> dict[str, Any]:
    """Load the user-editable criteria file, with a readable error if it's wrong."""
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        raise ValueError(
            f"Could not find your criteria file at {path}. "
            "It should sit next to config.yaml. See README 'Changing your criteria'."
        )
    except yaml.YAMLError as e:
        raise ValueError(
            f"Your criteria file has a formatting problem and could not be read.\n{e}\n"
            "Check that every line under 'criteria:' starts with '- id:' and is indented "
            "the same amount."
        )

    # If the file carries structured filters, they are the source of truth and
    # the criteria list is regenerated from them.
    if data and data.get("filters"):
        from screening.filters import compile_criteria
        data["criteria"] = compile_criteria(
            data.get("role", ""), data["filters"], data.get("summary", ""))

    if not data or "criteria" not in data:
        raise ValueError(
            "Your criteria file has no 'criteria:' section. "
            "See criteria.yaml in the repo for the expected shape."
        )

    for i, c in enumerate(data["criteria"], start=1):
        for field in ("id", "description"):
            if field not in c:
                raise ValueError(
                    f"Criterion #{i} in your criteria file is missing '{field}'. "
                    f"Every criterion needs an id and a description."
                )
        c.setdefault("required", False)

    data.setdefault("decision_rules", {})
    data.setdefault("role", "Unspecified role")
    return data


def output_dir() -> Path:
    """Where exports go, so the user can actually find them.

    Found in use twice: the app runs inside WSL, so it wrote results to a path
    like /home/hp/screening/data/ that is invisible from Windows Explorer. The user
    clicked Export, got a success message, and could not find the file. On WSL
    the output now goes to the Windows Documents folder instead.
    """
    try:
        if "microsoft" in Path("/proc/version").read_text().lower():
            for base in Path("/mnt/c/Users").glob("*"):
                docs = base / "Documents"
                if docs.is_dir():
                    out = docs / "CV Screening"
                    out.mkdir(parents=True, exist_ok=True)
                    return out
    except Exception:
        pass
    out = ROOT / "data"
    out.mkdir(parents=True, exist_ok=True)
    return out


def windows_path(p: Path) -> str:
    """Show a WSL path the way the user will see it in Explorer."""
    s = str(p)
    if s.startswith("/mnt/") and len(s) > 6:
        return s[5].upper() + ":" + s[6:].replace("/", "\\")
    return s


SETTINGS = load_settings()
