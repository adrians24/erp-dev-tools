from __future__ import annotations

import ctypes
import json
import sys
from ctypes import wintypes
from typing import Any, Dict, Optional


CRED_TYPE_GENERIC = 1
ERROR_NOT_FOUND = 1168


class CREDENTIALW(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", wintypes.LPVOID),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


def read_generic_credential(target: str) -> Optional[str]:
    if sys.platform != "win32":
        return None

    advapi32 = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
    cred_read = advapi32.CredReadW
    cred_read.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.POINTER(CREDENTIALW)),
    ]
    cred_read.restype = wintypes.BOOL
    cred_free = advapi32.CredFree
    cred_free.argtypes = [wintypes.LPVOID]

    credential = ctypes.POINTER(CREDENTIALW)()
    if not cred_read(target, CRED_TYPE_GENERIC, 0, ctypes.byref(credential)):
        error_code = ctypes.get_last_error()
        if error_code == ERROR_NOT_FOUND:
            return None
        raise ctypes.WinError(error_code)

    try:
        size = credential.contents.CredentialBlobSize
        if not size:
            return ""
        raw = ctypes.string_at(credential.contents.CredentialBlob, size)
        return raw.decode("utf-16-le")
    finally:
        cred_free(credential)


def read_json_credential(target: str) -> Optional[Dict[str, Any]]:
    value = read_generic_credential(target)
    if value is None:
        return None
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError(f"Windows credential '{target}' must contain a JSON object.")
    return parsed
