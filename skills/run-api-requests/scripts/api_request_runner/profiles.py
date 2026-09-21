from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any, Dict

import requests

from .common import abort
from .http import derive_system_data_service_url, get_token, parse_response_body, request_json
from .windows_credentials import read_json_credential

_plugin_scripts = Path(__file__).resolve().parents[4] / "scripts"
if str(_plugin_scripts) not in sys.path:
    sys.path.insert(0, str(_plugin_scripts))
from erp_dev_tools_config import ConfigurationError, configured_value, default_config_path, get_profile  # noqa: E402

DEFAULT_ENVIRONMENT = "localhost"
DEFAULT_TIMEOUT = 120
SYSTEM_DATA_SCOPE = "systemdataserviceapi:api"
DEFAULT_LEGACY_ERP_SCOPE = (
    "vismanet_erp_service_api:read "
    "vismanet_erp_service_api:create "
    "vismanet_erp_service_api:update "
    "vismanet_erp_service_api:delete "
    "systemdataserviceapi:api"
)
DEFAULT_SALESORDER_READ_SCOPE = "visma.net.erp.salesorder:read"
DEFAULT_SALESORDER_WRITE_SCOPE = "visma.net.erp.salesorder:write"
DEFAULT_LOCAL_SALESORDER_SERVER_URL = "https://localhost:5001"
LOCAL_ERP_CREDENTIAL_TARGET = "Codex.VismaErp.local"


@dataclass
class LegacyErpProfile:
    base_url: str
    headers: Dict[str, str]
    verify_tls: bool
    database_name: str
    resolved_context: Dict[str, Any]


@dataclass
class SalesOrderProfile:
    server_url: str
    token_url: str
    client_id: str
    client_secret: str
    tenant_id: str
    branch_id: str
    read_scope: str
    write_scope: str
    verify_tls: bool
    database_name: str
    resolved_context: Dict[str, Any]


def normalize_environment(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized == "local":
        return "localhost"
    if normalized in {"localhost", "internal"}:
        return normalized
    abort(
        "argument_error",
        "Environment must be localhost or internal.",
        exit_code=2,
    )


def default_database(environment: str) -> str:
    normalized = normalize_environment(environment)
    profile_name = "local" if normalized == "localhost" else "internal"
    profile = load_machine_profile(profile_name)
    return require_machine_value(profile_name, profile, "database")


def load_machine_profile(name: str) -> Dict[str, Any]:
    try:
        return get_profile(name, required=False)
    except ConfigurationError as exc:
        abort("config_error", str(exc))


def require_machine_value(profile_name: str, profile: Dict[str, Any], key: str) -> str:
    value = configured_value(profile, key)
    if not value:
        abort(
            "config_error",
            f"ERP development profile ''{profile_name}'' is missing ''{key}''. Update ''{default_config_path()}''.",
        )
    return value


def parse_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"", "0", "false", "no", "off"}


def load_legacy_local_auth(profile: Dict[str, Any]) -> Dict[str, Any]:
    try:
        stored_config = read_json_credential(LOCAL_ERP_CREDENTIAL_TARGET) or {}
    except (OSError, ValueError) as exc:
        abort(
            "config_error",
            f"Unable to read local ERP credential '{LOCAL_ERP_CREDENTIAL_TARGET}': {exc}",
        )

    stored_headers = stored_config.get("headers", {})
    if not isinstance(stored_headers, dict):
        stored_headers = {}

    authorization = os.getenv("VISMA_ERP_AUTHORIZATION") or stored_headers.get("Authorization")
    signature = os.getenv("VISMA_ERP_SIGNATURE") or stored_headers.get("ipp-signature")
    missing = []
    if not authorization:
        missing.append("VISMA_ERP_AUTHORIZATION")
    if not signature:
        missing.append("VISMA_ERP_SIGNATURE")
    if missing:
        abort(
            "config_error",
            "Missing local ERP credentials in environment variables and Windows Credential Manager.",
            data={
                "missing_environment_variables": missing,
                "credential_target": LOCAL_ERP_CREDENTIAL_TARGET,
            },
        )

    profile_company_id = configured_value(profile, "companyId")
    profile_user = configured_value(profile, "erpUser")
    headers = {
        "Authorization": str(authorization),
        "ipp-signature": str(signature),
    }
    headers.update(
        {
            "ipp-company-id": os.getenv("VISMA_ERP_COMPANY_ID")
            or profile_company_id
            or str(stored_headers.get("ipp-company-id") or ""),
            "ipp-user-id": os.getenv("VISMA_ERP_USER_ID")
            or profile_user
            or str(stored_headers.get("ipp-user-id") or ""),
            "Content-Type": "application/json",
        }
    )

    if not headers["ipp-company-id"]:
        require_machine_value("local", profile, "companyId")
    if not headers["ipp-user-id"]:
        require_machine_value("local", profile, "erpUser")

    return {
        "base_url": os.getenv("VISMA_ERP_BASE_URL")
        or configured_value(profile, "erpApiBaseUrl")
        or str(stored_config.get("base_url") or ""),
        "verify_tls": os.getenv("VISMA_ERP_VERIFY_TLS")
        or stored_config.get("verify_tls", "false"),
        "headers": headers,
    }


def load_salesorder_overrides() -> Dict[str, Any]:
    config = {}
    env_mapping = {
        "server_url": "VISMA_SALESORDER_SERVER_URL",
        "token_url": "VISMA_SALESORDER_TOKEN_URL",
        "client_id": "VISMA_SALESORDER_CLIENT_ID",
        "client_secret": "VISMA_SALESORDER_CLIENT_SECRET",
        "read_scope": "VISMA_SALESORDER_READ_SCOPE",
        "write_scope": "VISMA_SALESORDER_WRITE_SCOPE",
        "tenant_id": "VISMA_SALESORDER_TENANT_ID",
        "branch_id": "VISMA_SALESORDER_BRANCH_ID",
        "verify_tls": "VISMA_SALESORDER_VERIFY_TLS",
    }
    for key, env_name in env_mapping.items():
        value = os.getenv(env_name)
        if value is not None:
            config[key] = value

    return config


def resolve_internal_company_context(
    *,
    token_url: str,
    client_id: str,
    client_secret: str,
    tenant_id: str,
    company_id: str,
    expected_database_name: str,
    scope: str,
    timeout: int,
    verify_tls: bool,
) -> Dict[str, Any]:
    system_data_url = derive_system_data_service_url(token_url)
    if not system_data_url:
        abort(
            "config_error",
            "Unable to derive the SystemDataService URL from token_url.",
            method="GET",
            url=token_url,
        )

    try:
        token_payload = get_token(
            token_url,
            client_id,
            tenant_id,
            scope,
            timeout,
            client_secret=client_secret,
            verify_tls=verify_tls,
        )
        response = request_json(
            "GET",
            f"{system_data_url.rstrip('/')}/api/odpcompany/{company_id}/context",
            headers={"Authorization": f"Bearer {token_payload['access_token']}"},
            timeout=timeout,
            verify_tls=verify_tls,
        )
        response.raise_for_status()
        context = response.json()
    except requests.HTTPError as exc:
        response = exc.response
        abort(
            "http_error",
            "Failed to resolve internal company context from SystemDataService.",
            method="GET" if response is None else response.request.method,
            url=None if response is None else response.request.url,
            status_code=None if response is None else response.status_code,
            data=None if response is None else parse_response_body(response),
        )
    except requests.RequestException as exc:
        abort(
            "connection_error",
            str(exc),
            method="GET",
            url=token_url,
        )

    instance_url = str(context.get("InstanceUrl") or "").strip()
    database_name = str(context.get("DatabaseName") or "").strip()
    if not instance_url:
        abort(
            "config_error",
            "SystemDataService returned an empty InstanceUrl.",
            method="GET",
            data=context,
        )

    if expected_database_name and database_name and database_name != expected_database_name:
        abort(
            "config_error",
            (
                f"Resolved database '{database_name}' does not match the requested "
                f"database '{expected_database_name}'."
            ),
            method="GET",
            data=context,
        )

    return {
        "token_payload": token_payload,
        "context": context,
        "instance_url": instance_url,
        "database_name": database_name,
    }


def resolve_legacy_erp_profile(args: Any) -> LegacyErpProfile:
    environment = normalize_environment(args.environment)
    profile_name = "local" if environment == "localhost" else "internal"
    machine_profile = load_machine_profile(profile_name)
    database_name = args.database or default_database(environment)

    if environment == "localhost":
        auth = load_legacy_local_auth(machine_profile)
        headers = dict(auth.get("headers", {}))
        if args.company_id:
            headers["ipp-company-id"] = args.company_id
        if args.user_id:
            headers["ipp-user-id"] = args.user_id
        headers.setdefault("Content-Type", "application/json")
        base_url = args.base_url or auth.get("base_url") or require_machine_value("local", machine_profile, "erpApiBaseUrl")
        return LegacyErpProfile(
            base_url=base_url,
            headers=headers,
            verify_tls=parse_bool(auth.get("verify_tls"), default=False),
            database_name=database_name,
            resolved_context={
                "environment": environment,
                "database_name": database_name,
                "base_url": base_url,
                "company_id": headers.get("ipp-company-id"),
                "user_id": headers.get("ipp-user-id"),
            },
        )

    token_url = args.token_url or os.getenv("VISMA_ERP_TOKEN_URL") or require_machine_value("internal", machine_profile, "tokenUrl")
    client_id = args.client_id or os.getenv("VISMA_ERP_CLIENT_ID") or require_machine_value("internal", machine_profile, "clientId")
    client_secret = (
        args.client_secret
        or os.getenv("VISMA_ERP_CLIENT_SECRET")
        or os.getenv("VISMA_SALESORDER_CLIENT_SECRET")
        or ""
    )
    tenant_id = args.tenant_id or os.getenv("VISMA_ERP_TENANT_ID") or require_machine_value("internal", machine_profile, "tenantId")
    company_id = args.company_id or os.getenv("VISMA_ERP_COMPANY_ID") or require_machine_value("internal", machine_profile, "companyId")
    user_id = args.user_id or os.getenv("VISMA_ERP_USER_ID") or require_machine_value("internal", machine_profile, "erpUser")
    verify_tls = not getattr(args, "insecure", False)
    scope = args.scope or DEFAULT_LEGACY_ERP_SCOPE

    resolved = resolve_internal_company_context(
        token_url=token_url,
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
        company_id=company_id,
        expected_database_name=database_name,
        scope=scope,
        timeout=args.timeout,
        verify_tls=verify_tls,
    )
    base_url = args.base_url or f"{resolved['instance_url'].rstrip('/')}/api"
    return LegacyErpProfile(
        base_url=base_url,
        headers={
            "Authorization": f"Bearer {resolved['token_payload']['access_token']}",
            "ipp-company-id": company_id,
            "ipp-user-id": user_id,
            "Content-Type": "application/json",
        },
        verify_tls=verify_tls,
        database_name=resolved["database_name"] or database_name,
        resolved_context={
            "environment": environment,
            "database_name": resolved["database_name"] or database_name,
            "requested_database_name": database_name,
            "instance_url": resolved["instance_url"],
            "base_url": base_url,
            "tenant_id": tenant_id,
            "company_id": company_id,
            "user_id": user_id,
        },
    )


def resolve_salesorder_profile(args: Any) -> SalesOrderProfile:
    environment = normalize_environment(args.environment)
    profile_name = "local" if environment == "localhost" else "internal"
    machine_profile = load_machine_profile(profile_name)
    database_name = args.database or default_database(environment)
    overrides = load_salesorder_overrides()

    verify_tls = not getattr(args, "insecure", False)
    if "verify_tls" in overrides:
        verify_tls = parse_bool(overrides.get("verify_tls"), default=verify_tls)

    server_url = args.server_url or overrides.get("server_url") or configured_value(machine_profile, "salesOrderServerUrl") or DEFAULT_LOCAL_SALESORDER_SERVER_URL
    token_url = args.token_url or overrides.get("token_url") or configured_value(machine_profile, "tokenUrl")
    client_id = args.client_id or overrides.get("client_id") or configured_value(machine_profile, "clientId")
    client_secret = args.client_secret or overrides.get("client_secret") or ""
    tenant_id = args.tenant_id or overrides.get("tenant_id") or configured_value(machine_profile, "tenantId")
    branch_id = (
        args.branch_id
        if getattr(args, "branch_id", None) is not None
        else str(overrides.get("branch_id") or configured_value(machine_profile, "branchId")).strip()
    )
    read_scope = (
        args.read_scope
        if getattr(args, "read_scope", None)
        else str(overrides.get("read_scope") or DEFAULT_SALESORDER_READ_SCOPE)
    )
    write_scope = (
        args.write_scope
        if getattr(args, "write_scope", None)
        else str(overrides.get("write_scope") or DEFAULT_SALESORDER_WRITE_SCOPE)
    )

    resolved_context: Dict[str, Any] = {
        "environment": environment,
        "database_name": database_name,
        "server_url": server_url,
        "token_url": token_url,
        "tenant_id": tenant_id,
        "branch_id": branch_id,
    }

    company_id = args.company_id or configured_value(machine_profile, "companyId")
    if environment == "internal" or getattr(args, "resolve_context", False):
        if not token_url:
            token_url = require_machine_value(profile_name, machine_profile, "tokenUrl")
        if not client_id:
            client_id = require_machine_value(profile_name, machine_profile, "clientId")
        if not tenant_id:
            tenant_id = require_machine_value(profile_name, machine_profile, "tenantId")
        if not company_id:
            company_id = require_machine_value(profile_name, machine_profile, "companyId")
        resolved = resolve_internal_company_context(
            token_url=token_url,
            client_id=client_id,
            client_secret=client_secret,
            tenant_id=tenant_id,
            company_id=company_id,
            expected_database_name=database_name,
            scope=SYSTEM_DATA_SCOPE,
            timeout=args.timeout,
            verify_tls=verify_tls,
        )
        resolved_context.update(
            {
                "company_id": company_id,
                "resolved_database_name": resolved["database_name"],
                "instance_url": resolved["instance_url"],
            }
        )

    return SalesOrderProfile(
        server_url=server_url,
        token_url=token_url,
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
        branch_id=branch_id,
        read_scope=read_scope,
        write_scope=write_scope,
        verify_tls=verify_tls,
        database_name=database_name,
        resolved_context=resolved_context,
    )
