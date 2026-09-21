from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping


CONFIG_ENVIRONMENT_VARIABLE = "ERP_DEV_TOOLS_CONFIG"
PLACEHOLDER_PREFIX = "<"


class ConfigurationError(RuntimeError):
    pass


def default_config_path() -> Path:
    override = os.getenv(CONFIG_ENVIRONMENT_VARIABLE)
    if override:
        return Path(override).expanduser().resolve()

    local_app_data = os.getenv("LOCALAPPDATA")
    if not local_app_data:
        raise ConfigurationError(
            f"LOCALAPPDATA is unavailable. Set {CONFIG_ENVIRONMENT_VARIABLE} to profiles.json."
        )
    return Path(local_app_data) / "Visma" / "Codex" / "erp-dev-tools" / "profiles.json"


def load_config(*, required: bool = True) -> dict[str, Any]:
    path = default_config_path()
    if not path.is_file():
        if required:
            raise ConfigurationError(
                f"ERP development profile was not found at '{path}'. "
                "Run scripts/Initialize-ErpDevTools.ps1 from the plugin source or set "
                f"{CONFIG_ENVIRONMENT_VARIABLE}."
            )
        return {"version": 1, "profiles": {}}

    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"Unable to read ERP development profile '{path}': {exc}") from exc

    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ConfigurationError(f"ERP development profile '{path}' must have version 1.")
    if not isinstance(payload.get("profiles"), dict):
        raise ConfigurationError(f"ERP development profile '{path}' must contain a profiles object.")
    return payload


def get_profile(name: str, *, required: bool = True) -> dict[str, Any]:
    payload = load_config(required=required)
    profile = payload.get("profiles", {}).get(name)
    if profile is None and not required:
        return {}
    if not isinstance(profile, dict):
        raise ConfigurationError(
            f"ERP development profile '{name}' is missing or is not an object in '{default_config_path()}'."
        )
    return profile


def configured_value(profile: Mapping[str, Any], key: str) -> str:
    value = profile.get(key)
    if value is None:
        return ""
    text = str(value).strip()
    if not text or (text.startswith(PLACEHOLDER_PREFIX) and text.endswith(">")):
        return ""
    return text


def require_values(profile_name: str, profile: Mapping[str, Any], *keys: str) -> dict[str, str]:
    values = {key: configured_value(profile, key) for key in keys}
    missing = [key for key, value in values.items() if not value]
    if missing:
        raise ConfigurationError(
            f"ERP development profile '{profile_name}' is missing: {', '.join(missing)}. "
            f"Update '{default_config_path()}'."
        )
    return values
