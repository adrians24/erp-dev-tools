from __future__ import annotations

import base64
import json
import warnings
import time
from contextlib import contextmanager
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import requests
import urllib3

_session = None
_tokens = {}


@contextmanager
def request_session():
    """Sequential batch lifetime: credentials/tokens are never persisted to disk."""
    global _session, _tokens
    previous_session, previous_tokens = _session, _tokens
    _session, _tokens = requests.Session(), {}
    try:
        yield
    finally:
        _session.close()
        _session, _tokens = previous_session, previous_tokens


def decode_jwt_claims(token: str) -> Optional[Dict[str, Any]]:
    parts = token.split(".")
    if len(parts) < 2:
        return None

    payload = parts[1]
    payload += "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload.encode("ascii"))
        return json.loads(decoded.decode("utf-8"))
    except Exception:
        return None


def get_token(
    token_url: str,
    client_id: str,
    tenant_id: str,
    scope: str,
    timeout: int,
    *,
    client_secret: str = "",
    verify_tls: bool = True,
) -> Dict[str, Any]:
    key = (token_url, client_id, tenant_id, scope, client_secret, verify_tls)
    cached = _tokens.get(key) if _session is not None else None
    if cached and time.monotonic() < cached[0]:
        return dict(cached[1])
    form_data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "scope": scope,
        "tenant_id": tenant_id,
    }

    if client_secret and client_secret != "<insert secret>":
        form_data["client_secret"] = client_secret

    started = time.monotonic()
    if _session is not None:
        _session.cookies.clear()
    response = (_session or requests).post(
        token_url,
        data=form_data,
        timeout=timeout,
        verify=verify_tls,
    )
    response.raise_for_status()
    payload = response.json()
    payload["claims"] = decode_jwt_claims(payload.get("access_token", ""))
    try:
        lifetime = float(payload.get('expires_in', 0))
    except (TypeError, ValueError):
        lifetime = 0
    if _session is not None and payload.get('access_token') and lifetime > 30:
        _tokens[key] = (started + lifetime - 30, dict(payload))
    return payload


def derive_system_data_service_url(token_url: str) -> str:
    parsed = urlparse(token_url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return urlunparse((parsed.scheme, parsed.netloc, "/SystemDataService/", "", "", ""))


def build_url(base_url: str, path: str, query_pairs: Optional[list[Tuple[str, str]]] = None) -> str:
    absolute = urljoin(f"{base_url.rstrip('/')}/", path.lstrip("/"))
    if not query_pairs:
        return absolute

    parsed = urlparse(absolute)
    existing_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    merged_pairs = existing_pairs + query_pairs
    return urlunparse(parsed._replace(query=urlencode(merged_pairs)))


def parse_response_body(response: requests.Response) -> Any:
    if not response.content:
        return None

    content_type = response.headers.get("Content-Type", "")
    if "json" in content_type.lower():
        try:
            return response.json()
        except ValueError:
            pass

    text = response.text
    try:
        return json.loads(text)
    except ValueError:
        return text


def request_json(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    body_text: Optional[str] = None,
    timeout: int = 120,
    verify_tls: bool = True,
) -> requests.Response:
    with warnings.catch_warnings():
        if not verify_tls:
            warnings.simplefilter("ignore", urllib3.exceptions.InsecureRequestWarning)
        # Reuse TCP connections without carrying a legacy company's cookies into
        # another request. Authentication remains explicit in each request.
        if _session is not None:
            _session.cookies.clear()
        return (_session or requests).request(
            method.upper(),
            url,
            headers=headers,
            data=body_text,
            timeout=timeout,
            verify=verify_tls,
        )
