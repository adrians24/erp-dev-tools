import argparse
import glob
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pyodbc

from credential_manager import read_generic_credential

_plugin_scripts = Path(__file__).resolve().parents[3] / "scripts"
if str(_plugin_scripts) not in sys.path:
    sys.path.insert(0, str(_plugin_scripts))
from erp_dev_tools_config import ConfigurationError, configured_value, default_config_path, get_profile  # noqa: E402


def load_machine_profile(name: str) -> Dict[str, Any]:
    try:
        return get_profile(name, required=False)
    except ConfigurationError as exc:
        raise RuntimeError(str(exc)) from exc


LOCAL_MACHINE_PROFILE = load_machine_profile("local")
INTERNAL_MACHINE_PROFILE = load_machine_profile("internal")


SERVER_PROFILES = {
    "local": {
        "server": os.getenv("VISMA_SQL_LOCAL_SERVER") or configured_value(LOCAL_MACHINE_PROFILE, "sqlServer"),
        "database": os.getenv("VISMA_SQL_LOCAL_DATABASE") or configured_value(LOCAL_MACHINE_PROFILE, "database"),
        "username_env": "VISMA_SQL_LOCAL_USER",
        "password_env": "VISMA_SQL_LOCAL_PASSWORD",
        "credential_target": "Codex.SqlServer.local",
        "encrypt": False,
    },
    "internal": {
        "server": os.getenv("VISMA_SQL_INTERNAL_SERVER") or configured_value(INTERNAL_MACHINE_PROFILE, "sqlServer"),
        "database": os.getenv("VISMA_SQL_INTERNAL_DATABASE") or configured_value(INTERNAL_MACHINE_PROFILE, "database"),
        "username_env": "VISMA_SQL_INTERNAL_USER",
        "password_env": "VISMA_SQL_INTERNAL_PASSWORD",
        "credential_target": "Codex.SqlServer.internal",
        "encrypt": True,
    },
}

HELPER_APP_NAME = "CodexSqlCaptureHelper"
HELPER_SQL_MARKER = "codex-sql-capture-helper"
HELPER_SQL_FRAGMENTS = [
    HELPER_SQL_MARKER,
    "create event session",
    "alter event session",
    "drop event session",
    "sys.server_event_sessions",
    "serverproperty('errorlogfilename')",
    "serverproperty('errorlogfilename') as error_log_file_name",
    "fn_xe_file_target_read_file",
]
DEFAULT_TEXT_EXCLUSIONS = [
    "exec sp_reset_connection",
]
PREFERRED_DRIVERS = [
    "ODBC Driver 18 for SQL Server",
    "ODBC Driver 17 for SQL Server",
    "SQL Server Native Client 11.0",
    "SQL Server",
]

TABLE_SPECS = {
    "SOOrder": {
        "keys": ["OrderType", "OrderNbr"],
        "columns": [
            "Status",
            "Hold",
            "Cancelled",
            "Completed",
            "OpenOrderQty",
            "BaseOpenOrderQty",
            "OpenLineCntr",
            "OpenShipmentCntr",
            "ShipmentCntr",
            "LastShipDate",
            "ShipDate",
            "RequestDate",
            "CancelDate",
            "ShipComplete",
        ],
    },
    "SOLine": {
        "keys": ["OrderType", "OrderNbr", "LineNbr"],
        "columns": [
            "InventoryID",
            "SubItemID",
            "SiteID",
            "LocationID",
            "Operation",
            "LineType",
            "PlanID",
            "OrderQty",
            "BaseOrderQty",
            "OpenQty",
            "BaseOpenQty",
            "ShippedQty",
            "BaseShippedQty",
            "Completed",
            "OpenLine",
            "ShipDate",
            "RequestDate",
            "CancelDate",
        ],
    },
    "SOLineSplit": {
        "keys": ["OrderType", "OrderNbr", "LineNbr", "SplitLineNbr"],
        "columns": [
            "InventoryID",
            "SubItemID",
            "SiteID",
            "LocationID",
            "Operation",
            "LineType",
            "PlanID",
            "ShipmentNbr",
            "Qty",
            "BaseQty",
            "ShippedQty",
            "BaseShippedQty",
            "Completed",
            "IsAllocated",
            "ShipDate",
            "LotSerialNbr",
        ],
    },
    "SOOrderShipment": {
        "keys": ["OrderType", "OrderNbr", "ShipmentType", "ShipmentNbr", "SiteID"],
        "columns": [
            "ShipDate",
            "Confirmed",
            "Operation",
            "InvoiceType",
            "InvoiceNbr",
            "InvtDocType",
            "InvtRefNbr",
        ],
    },
    "SOShipment": {
        "keys": ["ShipmentType", "ShipmentNbr"],
        "columns": [
            "Status",
            "ShipDate",
            "SiteID",
            "Operation",
            "ShipmentQty",
            "ShipmentWeight",
            "ShipmentVolume",
            "PackageCount",
            "OrderCntr",
            "LineCntr",
            "Confirmed",
            "Released",
            "CustomerID",
            "WorkgroupID",
            "OwnerID",
        ],
    },
    "SOShipLine": {
        "keys": ["ShipmentNbr", "ShipmentType", "LineNbr"],
        "columns": [
            "OrigOrderType",
            "OrigOrderNbr",
            "OrigLineNbr",
            "OrigSplitLineNbr",
            "InventoryID",
            "SubItemID",
            "SiteID",
            "LocationID",
            "Operation",
            "LineType",
            "ShipDate",
            "ShippedQty",
            "BaseShippedQty",
            "PackedQty",
            "BasePackedQty",
            "Confirmed",
            "Released",
            "PlanType",
            "OrigPlanType",
        ],
    },
    "SOShipLineSplit": {
        "keys": ["ShipmentNbr", "LineNbr", "SplitLineNbr"],
        "columns": [
            "OrigOrderType",
            "OrigOrderNbr",
            "OrigLineNbr",
            "OrigSplitLineNbr",
            "InventoryID",
            "SubItemID",
            "SiteID",
            "LocationID",
            "Operation",
            "LineType",
            "ShipDate",
            "Qty",
            "BaseQty",
            "Confirmed",
            "Released",
            "PlanID",
            "PlanType",
            "OrigPlanType",
            "LotSerialNbr",
        ],
    },
    "INItemPlan": {
        "keys": ["PlanID"],
        "columns": [
            "InventoryID",
            "SubItemID",
            "SiteID",
            "LocationID",
            "PlanDate",
            "PlanType",
            "FixedSource",
            "Reverse",
            "Hold",
            "PlanQty",
            "SupplyPlanID",
            "DemandPlanID",
            "RefNoteID",
        ],
    },
    "INSiteStatus": {
        "keys": ["InventoryID", "SubItemID", "SiteID"],
        "columns": [
            "QtyOnHand",
            "QtyAvail",
            "QtyHardAvail",
            "QtyActual",
            "QtySOBackOrdered",
            "QtySOPrepared",
            "QtySOBooked",
            "QtySOShipped",
            "QtySOShipping",
            "QtySOFixed",
            "QtyINIssues",
            "QtyINReceipts",
            "QtyPOReceipts",
            "QtyPOPrepared",
            "QtyPOOrders",
            "LastModifiedDateTime",
        ],
    },
    "INLocationStatus": {
        "keys": ["InventoryID", "SubItemID", "SiteID", "LocationID"],
        "columns": [
            "QtyOnHand",
            "QtyAvail",
            "QtyHardAvail",
            "QtyActual",
            "QtySOBackOrdered",
            "QtySOPrepared",
            "QtySOBooked",
            "QtySOShipped",
            "QtySOShipping",
            "QtySOFixed",
            "QtyINIssues",
            "QtyINReceipts",
            "QtyPOReceipts",
            "QtyPOPrepared",
            "QtyPOOrders",
            "LastModifiedDateTime",
        ],
    },
}

ORDER_SCOPED_TABLES = ["SOOrder", "SOLine", "SOLineSplit", "SOOrderShipment"]
SHIPMENT_SCOPED_TABLES = ["SOShipment", "SOShipLine", "SOShipLineSplit"]
DIFF_TABLE_ORDER = [
    "SOOrder",
    "SOLine",
    "SOLineSplit",
    "SOOrderShipment",
    "SOShipment",
    "SOShipLine",
    "SOShipLineSplit",
    "INItemPlan",
    "INSiteStatus",
    "INLocationStatus",
]


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        emit_json(build_error_payload("argument_error", message))
        raise SystemExit(2)


def build_error_payload(error_type: str, message: str) -> Dict[str, Any]:
    return {
        "ok": False,
        "capture_meta": None,
        "command_result": None,
        "raw_event_count": 0,
        "filtered_event_count": 0,
        "events": [],
        "observed_entities": None,
        "changed_tables": [],
        "table_diffs": None,
        "error": {
            "type": error_type,
            "message": message,
        },
    }


def json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return str(value)


def emit_json(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=json_default))


def parse_json_safe(text: Optional[str]) -> Optional[Any]:
    if text is None:
        return None
    trimmed = text.strip()
    if not trimmed:
        return None
    try:
        return json.loads(trimmed)
    except json.JSONDecodeError:
        return None


def sql_string_literal(value: str) -> str:
    return "N'" + value.replace("'", "''") + "'"


def sql_identifier(value: str) -> str:
    return "[" + value.replace("]", "]]") + "]"


def pick_driver() -> str:
    available = set(pyodbc.drivers())
    for driver in PREFERRED_DRIVERS:
        if driver in available:
            return driver
    raise RuntimeError("No SQL Server ODBC driver is installed.")


def resolve_sql_auth(profile_name: str) -> Tuple[str, Optional[str], Optional[str]]:
    profile = SERVER_PROFILES[profile_name]
    username = os.getenv(profile["username_env"], "").strip()
    password = os.getenv(profile["password_env"], "")
    if username or password:
        if not username or not password:
            raise RuntimeError(
                "Incomplete SQL environment override. Set both "
                f"{profile['username_env']} and {profile['password_env']}, or remove both."
            )
        return "sql-password", username, password

    if profile_name == "local":
        return "windows-integrated", None, None

    credential = read_generic_credential(profile["credential_target"])
    if credential is None:
        raise RuntimeError(
            f"SQL credential '{profile['credential_target']}' was not found in Windows Credential Manager."
        )
    return "windows-credential-manager", credential[0], credential[1]


def odbc_braced_value(value: str) -> str:
    return "{" + value.replace("}", "}}") + "}"


def build_connection_string(server_profile: str, database: str, driver: str) -> str:
    profile = SERVER_PROFILES[server_profile]
    missing = []
    if not profile["server"]:
        missing.append("sqlServer")
    if not database:
        missing.append("database")
    if missing:
        raise RuntimeError(
            f"ERP development profile ''{server_profile}'' is missing: {'', ''.join(missing)}. "
            f"Update ''{default_config_path()}''."
        )
    auth_source, username, password = resolve_sql_auth(server_profile)
    parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={profile['server']}",
        f"DATABASE={odbc_braced_value(database)}",
        "TrustServerCertificate=yes",
        f"APP={HELPER_APP_NAME}",
    ]
    if auth_source == "windows-integrated":
        parts.append("Trusted_Connection=yes")
    else:
        parts.extend(
            [
                f"UID={odbc_braced_value(username or '')}",
                f"PWD={odbc_braced_value(password or '')}",
            ]
        )
    if profile["encrypt"]:
        parts.append("Encrypt=yes")
    return ";".join(parts)


def connect(server_profile: str, database: str, driver: str) -> pyodbc.Connection:
    return pyodbc.connect(
        build_connection_string(server_profile, database, driver),
        autocommit=True,
        timeout=30,
    )


def fetch_all(connection: pyodbc.Connection, sql: str) -> List[Dict[str, Any]]:
    cursor = connection.cursor()
    cursor.execute(sql)
    columns = [column[0] for column in cursor.description] if cursor.description else []
    rows = []
    for row in cursor.fetchall():
        rows.append(dict(zip(columns, row)))
    cursor.close()
    return rows


def fetch_all_params(connection: pyodbc.Connection, sql: str, params: Sequence[Any]) -> List[Dict[str, Any]]:
    cursor = connection.cursor()
    cursor.execute(sql, list(params))
    columns = [column[0] for column in cursor.description] if cursor.description else []
    rows = []
    for row in cursor.fetchall():
        rows.append(dict(zip(columns, row)))
    cursor.close()
    return rows


def execute_non_query(connection: pyodbc.Connection, sql: str) -> None:
    cursor = connection.cursor()
    cursor.execute(sql)
    cursor.close()


def get_log_directory(connection: pyodbc.Connection) -> Path:
    rows = fetch_all(
        connection,
        f"/* {HELPER_SQL_MARKER} */ "
        "SELECT CONVERT(nvarchar(4000), SERVERPROPERTY('ErrorLogFileName')) AS error_log_file_name;",
    )
    if not rows or not rows[0].get("error_log_file_name"):
        raise RuntimeError("Could not resolve SQL Server error log path.")
    return Path(rows[0]["error_log_file_name"]).parent


def get_table_columns(
    connection: pyodbc.Connection,
    table_name: str,
    column_cache: Dict[str, List[str]],
) -> List[str]:
    cached = column_cache.get(table_name)
    if cached is not None:
        return cached
    rows = fetch_all_params(
        connection,
        """
SELECT COLUMN_NAME
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = ?
ORDER BY ORDINAL_POSITION;
""",
        [table_name],
    )
    columns = [str(row["COLUMN_NAME"]) for row in rows]
    column_cache[table_name] = columns
    return columns


def get_snapshot_columns(
    connection: pyodbc.Connection,
    table_name: str,
    column_cache: Dict[str, List[str]],
) -> Tuple[List[str], List[str]]:
    spec = TABLE_SPECS[table_name]
    available = set(get_table_columns(connection, table_name, column_cache))
    keys = [column for column in spec["keys"] if column in available]
    if len(keys) != len(spec["keys"]):
        missing = [column for column in spec["keys"] if column not in available]
        raise RuntimeError(f"Missing key columns for {table_name}: {', '.join(missing)}")
    compare_columns = [
        column for column in spec["columns"] if column in available and column not in keys
    ]
    return keys, compare_columns


def build_session_name() -> str:
    return f"CodexSqlCapture_{uuid.uuid4().hex[:16]}"


def build_create_session_sql(session_name: str, event_base_path: str) -> str:
    session_id = sql_identifier(session_name)
    filename_literal = sql_string_literal(event_base_path)
    return f"""/* {HELPER_SQL_MARKER} */
IF EXISTS (SELECT 1 FROM sys.server_event_sessions WHERE name = {sql_string_literal(session_name)})
    DROP EVENT SESSION {session_id} ON SERVER;

CREATE EVENT SESSION {session_id} ON SERVER
ADD EVENT sqlserver.rpc_completed(
    ACTION(sqlserver.client_app_name, sqlserver.database_name, sqlserver.sql_text)
),
ADD EVENT sqlserver.sql_batch_completed(
    ACTION(sqlserver.client_app_name, sqlserver.database_name, sqlserver.sql_text)
),
ADD EVENT sqlserver.sql_statement_completed(
    ACTION(sqlserver.client_app_name, sqlserver.database_name, sqlserver.sql_text)
)
ADD TARGET package0.event_file(
    SET filename = {filename_literal},
        max_file_size = 20,
        max_rollover_files = 4
)
WITH (MAX_DISPATCH_LATENCY = 1 SECONDS);

ALTER EVENT SESSION {session_id} ON SERVER STATE = START;
"""


def build_stop_session_sql(session_name: str) -> str:
    session_id = sql_identifier(session_name)
    return f"""/* {HELPER_SQL_MARKER} */
IF EXISTS (SELECT 1 FROM sys.server_event_sessions WHERE name = {sql_string_literal(session_name)})
    ALTER EVENT SESSION {session_id} ON SERVER STATE = STOP;
"""


def build_drop_session_sql(session_name: str) -> str:
    session_id = sql_identifier(session_name)
    return f"""/* {HELPER_SQL_MARKER} */
IF EXISTS (SELECT 1 FROM sys.server_event_sessions WHERE name = {sql_string_literal(session_name)})
    DROP EVENT SESSION {session_id} ON SERVER;
"""


def build_read_events_sql(xel_pattern: str, start_utc: datetime, end_utc: datetime) -> str:
    start_literal = sql_string_literal(start_utc.strftime("%Y-%m-%dT%H:%M:%S.%f"))
    end_literal = sql_string_literal(end_utc.strftime("%Y-%m-%dT%H:%M:%S.%f"))
    pattern_literal = sql_string_literal(xel_pattern)
    return f"""
WITH raw_events AS (
    SELECT
        object_name,
        CONVERT(xml, event_data) AS event_xml
    FROM sys.fn_xe_file_target_read_file({pattern_literal}, NULL, NULL, NULL)
)
SELECT
    object_name AS event_name,
    event_xml.value('(event/@timestamp)[1]', 'datetime2(7)') AS utc_timestamp,
    NULLIF(event_xml.value('(event/action[@name="client_app_name"]/value)[1]', 'nvarchar(256)'), '') AS client_app_name,
    NULLIF(event_xml.value('(event/action[@name="database_name"]/value)[1]', 'nvarchar(256)'), '') AS database_name,
    NULLIF(event_xml.value('(event/action[@name="sql_text"]/value)[1]', 'nvarchar(max)'), '') AS sql_text,
    NULLIF(event_xml.value('(event/data[@name="statement"]/value)[1]', 'nvarchar(max)'), '') AS statement_text,
    NULLIF(event_xml.value('(event/data[@name="batch_text"]/value)[1]', 'nvarchar(max)'), '') AS batch_text,
    TRY_CONVERT(bigint, NULLIF(event_xml.value('(event/data[@name="duration"]/value)[1]', 'nvarchar(50)'), '')) AS duration_us,
    TRY_CONVERT(bigint, NULLIF(event_xml.value('(event/data[@name="cpu_time"]/value)[1]', 'nvarchar(50)'), '')) AS cpu_us,
    TRY_CONVERT(bigint, NULLIF(event_xml.value('(event/data[@name="row_count"]/value)[1]', 'nvarchar(50)'), '')) AS row_count
FROM raw_events
WHERE event_xml.value('(event/@timestamp)[1]', 'datetime2(7)') >= CONVERT(datetime2(7), {start_literal})
  AND event_xml.value('(event/@timestamp)[1]', 'datetime2(7)') <= CONVERT(datetime2(7), {end_literal})
ORDER BY utc_timestamp ASC;
"""


def normalize_command(command: List[str]) -> List[str]:
    if command and command[0] == "--":
        return command[1:]
    return command


def run_wrapped_command(command: List[str]) -> Dict[str, Any]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        return {
            "command": command,
            "exit_code": None,
            "stdout": None,
            "stderr": str(exc),
            "stdout_json": None,
        }

    stdout = result.stdout.strip() or None
    stderr = result.stderr.strip() or None
    return {
        "command": command,
        "exit_code": result.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_json": parse_json_safe(stdout),
    }


def choose_event_text(event: Dict[str, Any]) -> Optional[str]:
    for key in ("statement_text", "batch_text", "sql_text"):
        value = event.get(key)
        if value and str(value).strip():
            return str(value)
    return None


def to_event_record(row: Dict[str, Any]) -> Dict[str, Any]:
    duration_us = row.get("duration_us")
    cpu_us = row.get("cpu_us")
    return {
        "event_name": row.get("event_name"),
        "utc_timestamp": row.get("utc_timestamp"),
        "client_app_name": row.get("client_app_name"),
        "database_name": row.get("database_name"),
        "text": choose_event_text(row),
        "duration_ms": round(duration_us / 1000, 3) if isinstance(duration_us, (int, float)) else None,
        "cpu_ms": round(cpu_us / 1000, 3) if isinstance(cpu_us, (int, float)) else None,
        "row_count": row.get("row_count"),
    }


def filter_events(
    events: List[Dict[str, Any]],
    database: str,
    client_app: Optional[str],
    contains_text: Optional[str],
    event_names: List[str],
) -> List[Dict[str, Any]]:
    filtered: List[Dict[str, Any]] = []
    event_name_set = {value.lower() for value in event_names}
    database_lower = database.lower()
    client_app_lower = client_app.lower() if client_app else None
    contains_text_lower = contains_text.lower() if contains_text else None

    for event in events:
        database_name = (event.get("database_name") or "").strip()
        if not database_name or database_name.lower() != database_lower:
            continue

        client_name = (event.get("client_app_name") or "").strip()
        if client_name.lower() == HELPER_APP_NAME.lower():
            continue

        text = event.get("text") or ""
        text_lower = text.lower()
        if any(fragment in text_lower for fragment in HELPER_SQL_FRAGMENTS):
            continue

        if any(fragment in text_lower for fragment in DEFAULT_TEXT_EXCLUSIONS):
            continue

        if client_app_lower and client_app_lower not in client_name.lower():
            continue

        if contains_text_lower and contains_text_lower not in text_lower:
            continue

        event_name = (event.get("event_name") or "").lower()
        if event_name_set and event_name not in event_name_set:
            continue

        filtered.append(event)

    return filtered


def cleanup_capture_files(event_base_path: Path) -> None:
    for candidate in glob.glob(str(event_base_path) + "*"):
        try:
            Path(candidate).unlink()
        except OSError:
            pass


def capture_wrapped_command(
    server_profile: str,
    database: str,
    driver: str,
    wrapped_command: List[str],
    client_app: Optional[str],
    contains_text: Optional[str],
    event_names: List[str],
    post_wait_seconds: float,
) -> Dict[str, Any]:
    connection = connect(server_profile, database, driver)

    session_name: Optional[str] = None
    event_base_path: Optional[Path] = None
    command_result: Optional[Dict[str, Any]] = None
    capture_start_utc: Optional[datetime] = None
    capture_end_utc: Optional[datetime] = None
    raw_rows: List[Dict[str, Any]] = []

    try:
        log_directory = get_log_directory(connection)
        session_name = build_session_name()
        event_base_path = log_directory / session_name

        execute_non_query(connection, build_create_session_sql(session_name, str(event_base_path)))
        capture_start_utc = datetime.now(UTC)

        command_result = run_wrapped_command(wrapped_command)

        time.sleep(max(post_wait_seconds, 0.0))
        capture_end_utc = datetime.now(UTC)

        execute_non_query(connection, build_stop_session_sql(session_name))
        raw_rows = fetch_all(
            connection,
            build_read_events_sql(str(event_base_path) + "*.xel", capture_start_utc, capture_end_utc),
        )
    finally:
        if session_name:
            try:
                execute_non_query(connection, build_drop_session_sql(session_name))
            except Exception:
                pass
        connection.close()
        if event_base_path and server_profile == "local":
            cleanup_capture_files(event_base_path)

    raw_events = [to_event_record(row) for row in raw_rows]
    filtered_events = filter_events(
        raw_events,
        database=database,
        client_app=client_app,
        contains_text=contains_text,
        event_names=event_names,
    )

    return {
        "ok": command_result.get("exit_code") == 0 if command_result else False,
        "capture_meta": {
            "server_profile": server_profile,
            "database": database,
            "driver": driver,
            "capture_start_utc": capture_start_utc,
            "capture_end_utc": capture_end_utc,
            "event_session": session_name,
            "event_file_base_path": str(event_base_path) if event_base_path else None,
            "default_filters": [
                "time window around wrapped command",
                "target database only",
                f"exclude helper app {HELPER_APP_NAME}",
                "exclude helper SQL/session management statements",
            ],
            "optional_filters": {
                "client_app": client_app,
                "contains_text": contains_text,
                "event_name": event_names,
            },
        },
        "command_result": command_result,
        "raw_event_count": len(raw_events),
        "filtered_event_count": len(filtered_events),
        "events": filtered_events,
        "error": None,
    }


def select_rows(
    connection: pyodbc.Connection,
    table_name: str,
    columns: List[str],
    where_clause: Optional[str] = None,
    params: Optional[Sequence[Any]] = None,
    order_by: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    if not columns:
        return []
    sql = f"SELECT {', '.join(sql_identifier(column) for column in columns)} FROM {sql_identifier(table_name)}"
    if where_clause:
        sql += f" WHERE {where_clause}"
    if order_by:
        sql += " ORDER BY " + ", ".join(sql_identifier(column) for column in order_by)
    sql += ";"
    return fetch_all_params(connection, sql, params or [])


def build_tuple_where_clause(
    column_names: Sequence[str],
    key_values: Sequence[Tuple[Any, ...]],
) -> Tuple[Optional[str], List[Any]]:
    if not key_values:
        return None, []

    clauses: List[str] = []
    params: List[Any] = []
    for key_tuple in key_values:
        comparisons: List[str] = []
        for column_name, value in zip(column_names, key_tuple):
            if value is None:
                comparisons.append(f"{sql_identifier(column_name)} IS NULL")
            else:
                comparisons.append(f"{sql_identifier(column_name)} = ?")
                params.append(value)
        clauses.append("(" + " AND ".join(comparisons) + ")")
    return " OR ".join(clauses), params


def sort_tuple_key(values: Tuple[Any, ...]) -> Tuple[str, ...]:
    return tuple("" if value is None else str(value) for value in values)


def distinct_sorted_tuples(values: Sequence[Tuple[Any, ...]]) -> List[Tuple[Any, ...]]:
    return sorted(set(values), key=sort_tuple_key)


def format_key(row: Dict[str, Any], key_columns: Sequence[str]) -> Dict[str, Any]:
    return {column: row.get(column) for column in key_columns}


def row_sort_key(row: Dict[str, Any], key_columns: Sequence[str]) -> str:
    return json.dumps(format_key(row, key_columns), sort_keys=True, default=json_default)


def serialize_row(row: Dict[str, Any], columns: Sequence[str]) -> Dict[str, Any]:
    return {column: row.get(column) for column in columns}


def snapshot_order_scoped_table(
    connection: pyodbc.Connection,
    table_name: str,
    order_type: str,
    order_number: str,
    column_cache: Dict[str, List[str]],
) -> List[Dict[str, Any]]:
    key_columns, compare_columns = get_snapshot_columns(connection, table_name, column_cache)
    return select_rows(
        connection,
        table_name,
        key_columns + compare_columns,
        where_clause="[OrderType] = ? AND [OrderNbr] = ?",
        params=[order_type, order_number],
        order_by=key_columns,
    )


def snapshot_shipment_scoped_table(
    connection: pyodbc.Connection,
    table_name: str,
    shipment_number: Optional[str],
    column_cache: Dict[str, List[str]],
) -> List[Dict[str, Any]]:
    if not shipment_number:
        return []
    key_columns, compare_columns = get_snapshot_columns(connection, table_name, column_cache)
    return select_rows(
        connection,
        table_name,
        key_columns + compare_columns,
        where_clause="[ShipmentNbr] = ?",
        params=[shipment_number],
        order_by=key_columns,
    )


def snapshot_in_item_plan(
    connection: pyodbc.Connection,
    order_type: str,
    order_number: str,
    shipment_number: Optional[str],
    column_cache: Dict[str, List[str]],
) -> List[Dict[str, Any]]:
    key_columns, compare_columns = get_snapshot_columns(connection, "INItemPlan", column_cache)
    columns = key_columns + compare_columns

    query_parts = [
        "SELECT [PlanID] FROM [SOLine] WHERE [OrderType] = ? AND [OrderNbr] = ? AND [PlanID] IS NOT NULL",
        "SELECT [PlanID] FROM [SOLineSplit] WHERE [OrderType] = ? AND [OrderNbr] = ? AND [PlanID] IS NOT NULL",
    ]
    params: List[Any] = [order_type, order_number, order_type, order_number]
    if shipment_number:
        query_parts.append(
            "SELECT [PlanID] FROM [SOShipLineSplit] WHERE [ShipmentNbr] = ? AND [PlanID] IS NOT NULL"
        )
        params.append(shipment_number)

    sql = f"""
WITH relevant_plan_ids AS (
    {' UNION '.join(query_parts)}
)
SELECT {', '.join(sql_identifier(column) for column in columns)}
FROM [INItemPlan]
WHERE [PlanID] IN (SELECT [PlanID] FROM relevant_plan_ids)
ORDER BY {', '.join(sql_identifier(column) for column in key_columns)};
"""
    return fetch_all_params(connection, sql, params)


def collect_site_scope(snapshot_rows: Dict[str, List[Dict[str, Any]]]) -> List[Tuple[Any, ...]]:
    site_keys: List[Tuple[Any, ...]] = []
    for table_name in ["SOLine", "SOLineSplit", "SOShipLine", "SOShipLineSplit", "INItemPlan"]:
        for row in snapshot_rows.get(table_name, []):
            inventory_id = row.get("InventoryID")
            sub_item_id = row.get("SubItemID")
            site_id = row.get("SiteID")
            if inventory_id is None or site_id is None:
                continue
            site_keys.append((inventory_id, sub_item_id, site_id))
    return distinct_sorted_tuples(site_keys)


def collect_location_scope(snapshot_rows: Dict[str, List[Dict[str, Any]]]) -> List[Tuple[Any, ...]]:
    location_keys: List[Tuple[Any, ...]] = []
    for table_name in ["SOLine", "SOLineSplit", "SOShipLine", "SOShipLineSplit", "INItemPlan"]:
        for row in snapshot_rows.get(table_name, []):
            inventory_id = row.get("InventoryID")
            sub_item_id = row.get("SubItemID")
            site_id = row.get("SiteID")
            location_id = row.get("LocationID")
            if inventory_id is None or site_id is None or location_id is None:
                continue
            location_keys.append((inventory_id, sub_item_id, site_id, location_id))
    return distinct_sorted_tuples(location_keys)


def snapshot_in_site_status(
    connection: pyodbc.Connection,
    site_scope: Sequence[Tuple[Any, ...]],
    column_cache: Dict[str, List[str]],
) -> List[Dict[str, Any]]:
    if not site_scope:
        return []
    key_columns, compare_columns = get_snapshot_columns(connection, "INSiteStatus", column_cache)
    where_clause, params = build_tuple_where_clause(key_columns, site_scope)
    return select_rows(
        connection,
        "INSiteStatus",
        key_columns + compare_columns,
        where_clause=where_clause,
        params=params,
        order_by=key_columns,
    )


def snapshot_in_location_status(
    connection: pyodbc.Connection,
    site_scope: Sequence[Tuple[Any, ...]],
    column_cache: Dict[str, List[str]],
) -> List[Dict[str, Any]]:
    if not site_scope:
        return []
    key_columns, compare_columns = get_snapshot_columns(connection, "INLocationStatus", column_cache)
    site_key_columns = ["InventoryID", "SubItemID", "SiteID"]
    where_clause, params = build_tuple_where_clause(site_key_columns, site_scope)
    return select_rows(
        connection,
        "INLocationStatus",
        key_columns + compare_columns,
        where_clause=where_clause,
        params=params,
        order_by=key_columns,
    )


def diff_rows(
    table_name: str,
    pre_rows: List[Dict[str, Any]],
    post_rows: List[Dict[str, Any]],
    key_columns: Sequence[str],
    compare_columns: Sequence[str],
) -> Dict[str, Any]:
    selected_columns = list(key_columns) + list(compare_columns)
    pre_map = {tuple(row.get(column) for column in key_columns): row for row in pre_rows}
    post_map = {tuple(row.get(column) for column in key_columns): row for row in post_rows}

    inserted = [
        serialize_row(post_map[key], selected_columns)
        for key in post_map.keys() - pre_map.keys()
    ]
    deleted = [
        serialize_row(pre_map[key], selected_columns)
        for key in pre_map.keys() - post_map.keys()
    ]

    updated: List[Dict[str, Any]] = []
    for key in pre_map.keys() & post_map.keys():
        before = pre_map[key]
        after = post_map[key]
        changes = {}
        for column in compare_columns:
            if before.get(column) != after.get(column):
                changes[column] = {
                    "before": before.get(column),
                    "after": after.get(column),
                }
        if changes:
            updated.append(
                {
                    "key": format_key(after, key_columns),
                    "changes": changes,
                }
            )

    inserted.sort(key=lambda row: row_sort_key(row, key_columns))
    deleted.sort(key=lambda row: row_sort_key(row, key_columns))
    updated.sort(key=lambda row: json.dumps(row["key"], sort_keys=True, default=json_default))

    return {
        "table": table_name,
        "key_columns": list(key_columns),
        "compare_columns": list(compare_columns),
        "pre_row_count": len(pre_rows),
        "post_row_count": len(post_rows),
        "inserted_count": len(inserted),
        "updated_count": len(updated),
        "deleted_count": len(deleted),
        "changed": bool(inserted or updated or deleted),
        "inserted": inserted,
        "updated": updated,
        "deleted": deleted,
    }


def resolve_api_script_path(custom_path: Optional[str]) -> Path:
    if custom_path:
        return Path(custom_path).resolve()
    return (
        Path(__file__).resolve().parents[2]
        / "run-api-requests"
        / "scripts"
        / "run_api_requests.py"
    )


def build_create_shipment_command(args: argparse.Namespace, database: str) -> List[str]:
    api_script = resolve_api_script_path(args.api_script)
    if not api_script.exists():
        raise FileNotFoundError(f"Unified API request runner not found: {api_script}")

    command = [
        sys.executable,
        str(api_script),
        "erp",
        "--environment",
        "localhost",
        "--database",
        database,
        "--timeout",
        str(args.api_timeout),
        "action",
        "salesorder",
        "create-shipment",
        args.order_number,
        "--order-type",
        args.order_type,
        "--shipment-warehouse",
        str(args.shipment_warehouse),
    ]
    if args.shipment_date:
        command.extend(["--shipment-date", args.shipment_date])
    if args.operation:
        command.extend(["--operation", args.operation])
    return command


def resolve_shipment_number_from_command(command_result: Optional[Dict[str, Any]]) -> Optional[str]:
    if not command_result:
        return None
    stdout_json = command_result.get("stdout_json")
    if not isinstance(stdout_json, dict):
        return None
    resolved = stdout_json.get("resolved")
    if not isinstance(resolved, dict):
        return None
    shipment_number = resolved.get("shipment_no")
    if shipment_number in (None, ""):
        return None
    return str(shipment_number)


def infer_shipment_number_from_order_shipment(
    pre_rows: List[Dict[str, Any]],
    post_rows: List[Dict[str, Any]],
) -> Optional[str]:
    pre_keys = {
        (
            row.get("OrderType"),
            row.get("OrderNbr"),
            row.get("ShipmentType"),
            row.get("ShipmentNbr"),
            row.get("SiteID"),
        )
        for row in pre_rows
    }
    inserted = [
        row
        for row in post_rows
        if (
            row.get("OrderType"),
            row.get("OrderNbr"),
            row.get("ShipmentType"),
            row.get("ShipmentNbr"),
            row.get("SiteID"),
        )
        not in pre_keys
    ]
    if not inserted:
        return None
    inserted.sort(key=lambda row: row_sort_key(row, TABLE_SPECS["SOOrderShipment"]["keys"]))
    shipment_number = inserted[0].get("ShipmentNbr")
    if shipment_number in (None, ""):
        return None
    return str(shipment_number)


def tuple_dicts(values: Sequence[Tuple[Any, ...]], column_names: Sequence[str]) -> List[Dict[str, Any]]:
    return [{column: value for column, value in zip(column_names, item)} for item in values]


def capture_around_command(args: argparse.Namespace) -> Dict[str, Any]:
    wrapped_command = normalize_command(args.wrapped_command)
    if not wrapped_command:
        raise ValueError("Wrapped command missing. Use -- <command ...>.")

    database = args.database or SERVER_PROFILES[args.server]["database"]
    driver = pick_driver()
    return capture_wrapped_command(
        server_profile=args.server,
        database=database,
        driver=driver,
        wrapped_command=wrapped_command,
        client_app=args.client_app,
        contains_text=args.contains_text,
        event_names=args.event_name,
        post_wait_seconds=args.post_wait_seconds,
    )


def capture_create_shipment_diff(args: argparse.Namespace) -> Dict[str, Any]:
    if args.server != "local":
        raise ValueError(
            "create-shipment-diff supports only --server local because it invokes the localhost ERP API. "
            "Use 'around' for internal captures."
        )
    database = args.database or SERVER_PROFILES[args.server]["database"]
    driver = pick_driver()
    column_cache: Dict[str, List[str]] = {}
    connection = connect(args.server, database, driver)

    try:
        pre_snapshots: Dict[str, List[Dict[str, Any]]] = {}
        for table_name in ORDER_SCOPED_TABLES:
            pre_snapshots[table_name] = snapshot_order_scoped_table(
                connection,
                table_name,
                args.order_type,
                args.order_number,
                column_cache,
            )
        pre_snapshots["INItemPlan"] = snapshot_in_item_plan(
            connection,
            args.order_type,
            args.order_number,
            shipment_number=None,
            column_cache=column_cache,
        )

        pre_site_scope = collect_site_scope(pre_snapshots)
        pre_location_scope = collect_location_scope(pre_snapshots)
        pre_snapshots["INSiteStatus"] = snapshot_in_site_status(connection, pre_site_scope, column_cache)
        pre_snapshots["INLocationStatus"] = snapshot_in_location_status(connection, pre_site_scope, column_cache)

        capture_payload = capture_wrapped_command(
            server_profile=args.server,
            database=database,
            driver=driver,
            wrapped_command=build_create_shipment_command(args, database),
            client_app=args.client_app,
            contains_text=args.contains_text,
            event_names=args.event_name,
            post_wait_seconds=args.post_wait_seconds,
        )

        post_snapshots: Dict[str, List[Dict[str, Any]]] = {}
        for table_name in ORDER_SCOPED_TABLES:
            post_snapshots[table_name] = snapshot_order_scoped_table(
                connection,
                table_name,
                args.order_type,
                args.order_number,
                column_cache,
            )

        shipment_number = resolve_shipment_number_from_command(capture_payload.get("command_result"))
        shipment_number_source = "command_result" if shipment_number else None
        if not shipment_number:
            shipment_number = infer_shipment_number_from_order_shipment(
                pre_snapshots["SOOrderShipment"],
                post_snapshots["SOOrderShipment"],
            )
            if shipment_number:
                shipment_number_source = "soordershipment_diff"

        for table_name in SHIPMENT_SCOPED_TABLES:
            post_snapshots[table_name] = snapshot_shipment_scoped_table(
                connection,
                table_name,
                shipment_number,
                column_cache,
            )

        post_snapshots["INItemPlan"] = snapshot_in_item_plan(
            connection,
            args.order_type,
            args.order_number,
            shipment_number=shipment_number,
            column_cache=column_cache,
        )

        post_site_scope = collect_site_scope(post_snapshots)
        post_location_scope = collect_location_scope(post_snapshots)
        pre_site_scope_set = set(pre_site_scope)
        union_site_scope = distinct_sorted_tuples(pre_site_scope + post_site_scope)
        new_post_site_scope = [value for value in post_site_scope if value not in pre_site_scope_set]
        post_snapshots["INSiteStatus"] = snapshot_in_site_status(connection, union_site_scope, column_cache)
        post_snapshots["INLocationStatus"] = snapshot_in_location_status(
            connection,
            union_site_scope,
            column_cache,
        )

        table_diffs: Dict[str, Any] = {}
        changed_tables: List[str] = []
        for table_name in DIFF_TABLE_ORDER:
            key_columns, compare_columns = get_snapshot_columns(connection, table_name, column_cache)
            pre_rows = pre_snapshots.get(table_name, [])
            post_rows = post_snapshots.get(table_name, [])
            diff = diff_rows(table_name, pre_rows, post_rows, key_columns, compare_columns)
            table_diffs[table_name] = diff
            if diff["changed"]:
                changed_tables.append(table_name)

        observed_entities = {
            "order_type": args.order_type,
            "order_no": args.order_number,
            "shipment_no": shipment_number,
            "shipment_no_source": shipment_number_source,
            "pre_scope": {
                "site_keys": tuple_dicts(pre_site_scope, ["InventoryID", "SubItemID", "SiteID"]),
                "location_keys": tuple_dicts(
                    pre_location_scope,
                    ["InventoryID", "SubItemID", "SiteID", "LocationID"],
                ),
            },
            "post_scope": {
                "site_keys": tuple_dicts(post_site_scope, ["InventoryID", "SubItemID", "SiteID"]),
                "location_keys": tuple_dicts(
                    post_location_scope,
                    ["InventoryID", "SubItemID", "SiteID", "LocationID"],
                ),
            },
            "scope_warnings": {
                "new_post_site_keys_not_in_pre_scope": tuple_dicts(
                    new_post_site_scope,
                    ["InventoryID", "SubItemID", "SiteID"],
                )
            },
        }

        return {
            "ok": capture_payload["ok"],
            "capture_meta": capture_payload["capture_meta"],
            "command_result": capture_payload["command_result"],
            "raw_event_count": capture_payload["raw_event_count"],
            "filtered_event_count": capture_payload["filtered_event_count"],
            "events": capture_payload["events"],
            "observed_entities": observed_entities,
            "changed_tables": changed_tables,
            "table_diffs": table_diffs,
            "error": capture_payload["error"],
        }
    finally:
        connection.close()


def build_parser() -> JsonArgumentParser:
    parser = JsonArgumentParser(prog="sql_capture.py")
    subparsers = parser.add_subparsers(dest="command", required=True)

    around_parser = subparsers.add_parser("around", help="Capture SQL Server activity around a wrapped command.")
    around_parser.add_argument("--server", choices=sorted(SERVER_PROFILES.keys()), default="local")
    around_parser.add_argument("--database")
    around_parser.add_argument("--client-app")
    around_parser.add_argument("--contains-text")
    around_parser.add_argument("--event-name", action="append", default=[])
    around_parser.add_argument("--post-wait-seconds", type=float, default=2.0)
    around_parser.add_argument("wrapped_command", nargs=argparse.REMAINDER)

    create_diff_parser = subparsers.add_parser(
        "create-shipment-diff",
        help="Run create-shipment, capture SQL, and diff the main SO and IN tables.",
    )
    create_diff_parser.add_argument("order_number")
    create_diff_parser.add_argument("--order-type", default="SO")
    create_diff_parser.add_argument("--shipment-warehouse", required=True)
    create_diff_parser.add_argument("--shipment-date")
    create_diff_parser.add_argument("--operation", choices=["I", "R", "i", "r"])
    create_diff_parser.add_argument("--server", choices=sorted(SERVER_PROFILES.keys()), default="local")
    create_diff_parser.add_argument("--database")
    create_diff_parser.add_argument("--client-app")
    create_diff_parser.add_argument("--contains-text")
    create_diff_parser.add_argument("--event-name", action="append", default=[])
    create_diff_parser.add_argument("--post-wait-seconds", type=float, default=2.0)
    create_diff_parser.add_argument("--api-timeout", type=int, default=120)
    create_diff_parser.add_argument("--api-script")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "around":
            payload = capture_around_command(args)
            emit_json(payload)
            if payload["command_result"] and payload["command_result"]["exit_code"] is not None:
                return int(payload["command_result"]["exit_code"])
            return 0 if payload["ok"] else 1

        if args.command == "create-shipment-diff":
            payload = capture_create_shipment_diff(args)
            emit_json(payload)
            if payload["command_result"] and payload["command_result"]["exit_code"] is not None:
                return int(payload["command_result"]["exit_code"])
            return 0 if payload["ok"] else 1
    except Exception as exc:
        emit_json(build_error_payload("capture_error", str(exc)))
        return 1

    emit_json(build_error_payload("argument_error", f"Unknown command: {args.command}"))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
