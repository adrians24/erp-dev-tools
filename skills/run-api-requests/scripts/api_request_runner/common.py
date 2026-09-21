from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class CliAbort(Exception):
    def __init__(self, payload: Dict[str, Any], exit_code: int = 1) -> None:
        super().__init__(payload.get("error", {}).get("message"))
        self.payload = payload
        self.exit_code = exit_code


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        emit_json(
            make_error_payload(
                method=None,
                url=None,
                error_type="argument_error",
                message=message,
            )
        )
        raise SystemExit(2)


def emit_json(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def make_error_payload(
    method: Optional[str],
    url: Optional[str],
    error_type: str,
    message: str,
    *,
    status_code: Optional[int] = None,
    data: Any = None,
) -> Dict[str, Any]:
    return {
        "ok": False,
        "status_code": status_code,
        "method": method,
        "url": url,
        "data": data,
        "error": {
            "type": error_type,
            "message": message,
        },
    }


def abort(
    error_type: str,
    message: str,
    *,
    method: Optional[str] = None,
    url: Optional[str] = None,
    status_code: Optional[int] = None,
    data: Any = None,
    exit_code: int = 1,
) -> None:
    raise CliAbort(
        make_error_payload(
            method=method,
            url=url,
            error_type=error_type,
            message=message,
            status_code=status_code,
            data=data,
        ),
        exit_code=exit_code,
    )


def parse_json_safe(value: Optional[str]) -> Optional[Any]:
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    try:
        return json.loads(trimmed)
    except json.JSONDecodeError:
        return None


def load_optional_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_body(body_file: Optional[str], body_json: Optional[str]) -> Tuple[Optional[str], Optional[Any]]:
    if body_file and body_json:
        abort(
            "argument_error",
            "Use either --body-file or --body-json, not both.",
            exit_code=2,
        )

    if body_file:
        path = Path(body_file)
        if not path.exists():
            abort("body_file_error", f"Body file not found: {path}")
        text = path.read_text(encoding="utf-8")
        return text, parse_json_safe(text)

    if body_json is not None:
        return body_json, parse_json_safe(body_json)

    return None, None


def parse_key_value_items(items: List[str], item_name: str) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    for item in items:
        if "=" not in item:
            abort(
                "argument_error",
                f"Invalid {item_name} item '{item}'. Expected key=value.",
                exit_code=2,
            )
        key, value = item.split("=", 1)
        pairs.append((key, value))
    return pairs


def parse_headers(items: List[str]) -> Dict[str, str]:
    return {key: value for key, value in parse_key_value_items(items, "header")}


def get_path_value(input_object: Any, paths: List[str]) -> Optional[Any]:
    for path in paths:
        current = input_object
        ok = True
        for part in path.split("."):
            if current is None:
                ok = False
                break
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                ok = False
                break
        if ok and current not in (None, ""):
            return current
    return None


def get_last_path_segment(location: Optional[str]) -> Optional[str]:
    if not location:
        return None
    trimmed = location.rstrip("/")
    if "/" not in trimmed:
        return None
    segment = trimmed.rsplit("/", 1)[-1]
    return segment or None


def normalize_resolved(resolved: Dict[str, Any]) -> Dict[str, Any]:
    clean = {key: value for key, value in resolved.items() if value not in (None, "", {})}
    identifiers = {
        key: value
        for key, value in clean.items()
        if key.endswith("_no") or key.endswith("_type") or key.endswith("_id")
    }
    if identifiers:
        clean["identifiers"] = identifiers
    return clean
