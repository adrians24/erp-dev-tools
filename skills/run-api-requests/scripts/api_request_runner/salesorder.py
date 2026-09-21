from __future__ import annotations

import argparse
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

import requests

from .common import abort, emit_json, normalize_resolved, parse_headers, parse_key_value_items, read_body
from .http import build_url, get_token, parse_response_body, request_json
from .profiles import (
    DEFAULT_SALESORDER_WRITE_SCOPE,
    SYSTEM_DATA_SCOPE,
    resolve_internal_company_context,
    resolve_salesorder_profile,
)


def extract_order_from_location(location: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    if not location:
        return None, None
    path_parts = [part for part in urlparse(location).path.split("/") if part]
    if len(path_parts) < 2:
        return None, None
    return path_parts[-1] or None, path_parts[-2] or None


def perform_request(
    args: argparse.Namespace,
    *,
    method: str,
    path: str,
    body_text: Optional[str] = None,
    include_auth: bool = True,
    include_headers: bool = False,
) -> Dict[str, object]:
    profile = resolve_salesorder_profile(args)
    url = build_url(profile.server_url, path, parse_key_value_items(args.query or [], "query"))
    parsed_url = urlparse(url)
    host_verify_tls = profile.verify_tls
    if parsed_url.scheme == "https" and parsed_url.hostname in {"localhost", "127.0.0.1"}:
        host_verify_tls = False
    headers = {"Content-Type": "application/json"}
    if args.header:
        headers.update(parse_headers(args.header))

    token_payload = None
    if include_auth and not getattr(args, "no_auth", False):
        scope = args.scope or (profile.read_scope if method.upper() == "GET" else profile.write_scope)
        try:
            token_payload = get_token(
                profile.token_url,
                profile.client_id,
                args.tenant_id or profile.tenant_id,
                scope,
                args.timeout,
                client_secret=profile.client_secret,
                verify_tls=profile.verify_tls,
            )
        except requests.HTTPError as exc:
            response = exc.response
            abort(
                "token_error",
                "Failed to obtain access token.",
                method="POST",
                url=profile.token_url,
                status_code=None if response is None else response.status_code,
                data=None if response is None else parse_response_body(response),
            )
        except requests.RequestException as exc:
            abort(
                "connection_error",
                str(exc),
                method="POST",
                url=profile.token_url,
            )
        headers["Authorization"] = f"Bearer {token_payload['access_token']}"

    effective_branch_id = args.branch_id if getattr(args, "branch_id", None) is not None else profile.branch_id
    if effective_branch_id:
        headers["ipp-branch-id"] = effective_branch_id

    try:
        response = request_json(
            method,
            url,
            headers=headers,
            body_text=body_text,
            timeout=args.timeout,
            verify_tls=host_verify_tls,
        )
    except requests.RequestException as exc:
        abort(
            "connection_error",
            f"{exc}. Start the local sales-order API first if it is not running.",
            method=method.upper(),
            url=url,
        )

    data = parse_response_body(response)
    payload: Dict[str, object] = {
        "ok": response.ok,
        "status_code": response.status_code,
        "method": method.upper(),
        "url": url,
        "data": data,
        "error": None if response.ok else data,
        "context": normalize_resolved(profile.resolved_context),
    }
    if include_headers:
        payload["headers"] = dict(response.headers)
    if token_payload is not None and getattr(args, "include_token_claims", False):
        payload["token"] = {
            "scope": token_payload.get("scope"),
            "claims": token_payload.get("claims"),
        }
    return payload


def health_command(args: argparse.Namespace) -> int:
    payload = perform_request(
        args,
        method="GET",
        path="/health",
        include_auth=False,
        include_headers=args.include_headers,
    )
    emit_json(payload)
    return 0 if payload["ok"] else 1


def token_command(args: argparse.Namespace) -> int:
    profile = resolve_salesorder_profile(args)
    scope = args.scope or DEFAULT_SALESORDER_WRITE_SCOPE
    try:
        token_payload = get_token(
            profile.token_url,
            profile.client_id,
            args.tenant_id or profile.tenant_id,
            scope,
            args.timeout,
            client_secret=profile.client_secret,
            verify_tls=profile.verify_tls,
        )
    except requests.HTTPError as exc:
        response = exc.response
        abort(
            "token_error",
            "Failed to obtain access token.",
            method="POST",
            url=profile.token_url,
            status_code=None if response is None else response.status_code,
            data=None if response is None else parse_response_body(response),
        )
    except requests.RequestException as exc:
        abort(
            "connection_error",
            str(exc),
            method="POST",
            url=profile.token_url,
        )

    emit_json(
        {
            "ok": True,
            "status_code": 200,
            "method": "POST",
            "url": profile.token_url,
            "data": {
                "token_type": token_payload.get("token_type"),
                "expires_in": token_payload.get("expires_in"),
                "scope": token_payload.get("scope"),
                "claims": token_payload.get("claims"),
            },
            "error": None,
            "resolved": normalize_resolved(profile.resolved_context),
        }
    )
    return 0


def context_command(args: argparse.Namespace) -> int:
    profile = resolve_salesorder_profile(args)
    if profile.resolved_context.get("environment") == "localhost" and not args.company_id:
        emit_json(
            {
                "ok": True,
                "status_code": 200,
                "method": "GET",
                "url": profile.server_url,
                "data": {
                    "message": "Using the configured local profile; no SystemDataService lookup was required.",
                },
                "error": None,
                "resolved": normalize_resolved(
                    {
                        **profile.resolved_context,
                        "resolution_source": "local-profile",
                    }
                ),
            }
        )
        return 0

    args.resolve_context = True
    profile = resolve_salesorder_profile(args)
    company_id = args.company_id or profile.resolved_context.get("company_id")
    if not company_id:
        abort("config_error", "The selected machine profile has no companyId.")
    resolved = resolve_internal_company_context(
        token_url=profile.token_url,
        client_id=profile.client_id,
        client_secret=profile.client_secret,
        tenant_id=args.tenant_id or profile.tenant_id,
        company_id=company_id,
        expected_database_name=profile.database_name,
        scope=SYSTEM_DATA_SCOPE,
        timeout=args.timeout,
        verify_tls=profile.verify_tls,
    )
    emit_json(
        {
            "ok": True,
            "status_code": 200,
            "method": "GET",
            "url": f"{resolved['instance_url'].rstrip('/')}/api",
            "data": {
                "context": resolved["context"],
            },
            "error": None,
            "resolved": normalize_resolved(
                {
                    **profile.resolved_context,
                    "company_id": company_id,
                    "resolved_database_name": resolved["database_name"],
                    "instance_url": resolved["instance_url"],
                }
            ),
        }
    )
    return 0


def request_command(args: argparse.Namespace) -> int:
    body_text, _ = read_body(args.body_file, args.body_json)
    payload = perform_request(
        args,
        method=args.method,
        path=args.path,
        body_text=body_text,
        include_headers=args.include_headers,
    )
    emit_json(payload)
    return 0 if payload["ok"] else 1


def get_command(args: argparse.Namespace) -> int:
    order_type = args.order_type or "SO"
    payload = perform_request(
        args,
        method="GET",
        path=f"/api/v3/SalesOrders/{order_type}/{args.identifier}",
        include_headers=args.include_headers,
    )
    payload["resolved"] = normalize_resolved({"order_no": args.identifier, "order_type": order_type})
    emit_json(payload)
    return 0 if payload["ok"] else 1


def create_command(args: argparse.Namespace) -> int:
    body_text, body_json = read_body(args.body_file, args.body_json)
    if body_text is None:
        abort(
            "argument_error",
            "create salesorder requires --body-file or --body-json.",
            exit_code=2,
        )

    payload = perform_request(
        args,
        method="POST",
        path="/api/v3/SalesOrders",
        body_text=body_text,
        include_headers=True,
    )
    headers = payload.get("headers", {})
    location = headers.get("Location") or headers.get("location")
    order_no, order_type = extract_order_from_location(location)
    if order_type is None and isinstance(body_json, dict):
        order_type = body_json.get("type")
    payload["resolved"] = normalize_resolved(
        {
            "order_no": order_no,
            "order_type": order_type,
            "location": location,
        }
    )
    if not args.include_headers:
        payload.pop("headers", None)
    emit_json(payload)
    return 0 if payload["ok"] else 1


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    salesorder = subparsers.add_parser("salesorder", help="Run requests against the Sales Order Service API.")
    salesorder.set_defaults(surface="salesorder")
    salesorder.add_argument("--environment", default="localhost")
    salesorder.add_argument("--database")
    salesorder.add_argument("--server-url")
    salesorder.add_argument("--token-url")
    salesorder.add_argument("--client-id")
    salesorder.add_argument("--client-secret")
    salesorder.add_argument("--tenant-id")
    salesorder.add_argument("--company-id")
    salesorder.add_argument("--branch-id")
    salesorder.add_argument("--read-scope")
    salesorder.add_argument("--write-scope")
    salesorder.add_argument("--scope")
    salesorder.add_argument("--insecure", action="store_true")
    salesorder.add_argument("--timeout", type=int, default=120)

    salesorder_subparsers = salesorder.add_subparsers(dest="salesorder_command", required=True)

    health_parser = salesorder_subparsers.add_parser("health", help="Check the sales-order host health endpoint.")
    health_parser.set_defaults(handler=health_command)
    health_parser.add_argument("--query", action="append", default=[])
    health_parser.add_argument("--header", action="append", default=[])
    health_parser.add_argument("--include-headers", action="store_true")

    token_parser = salesorder_subparsers.add_parser("token", help="Acquire a sales-order access token.")
    token_parser.set_defaults(handler=token_command)

    context_parser = salesorder_subparsers.add_parser("context", help="Resolve the current tenant/company/database context.")
    context_parser.set_defaults(handler=context_command)

    request_parser = salesorder_subparsers.add_parser("request", help="Run a generic sales-order request.")
    request_parser.set_defaults(handler=request_command)
    request_parser.add_argument("method")
    request_parser.add_argument("path")
    request_parser.add_argument("--query", action="append", default=[])
    request_parser.add_argument("--header", action="append", default=[])
    request_parser.add_argument("--body-file")
    request_parser.add_argument("--body-json")
    request_parser.add_argument("--no-auth", action="store_true")
    request_parser.add_argument("--include-headers", action="store_true")
    request_parser.add_argument("--include-token-claims", action="store_true")

    get_parser = salesorder_subparsers.add_parser("get", help="Read a sales order.")
    get_parser.set_defaults(handler=get_command)
    get_parser.add_argument("entity", choices=["salesorder"])
    get_parser.add_argument("identifier")
    get_parser.add_argument("--order-type")
    get_parser.add_argument("--query", action="append", default=[])
    get_parser.add_argument("--header", action="append", default=[])
    get_parser.add_argument("--include-headers", action="store_true")

    create_parser = salesorder_subparsers.add_parser("create", help="Create a sales order.")
    create_parser.set_defaults(handler=create_command)
    create_parser.add_argument("entity", choices=["salesorder"])
    create_parser.add_argument("--body-file")
    create_parser.add_argument("--body-json")
    create_parser.add_argument("--query", action="append", default=[])
    create_parser.add_argument("--header", action="append", default=[])
    create_parser.add_argument("--include-headers", action="store_true")
