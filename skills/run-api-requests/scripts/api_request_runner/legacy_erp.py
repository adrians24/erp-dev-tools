from __future__ import annotations

import argparse
import json
from datetime import date
from typing import Any, Dict, Optional

import requests

from .common import (
    abort,
    emit_json,
    get_last_path_segment,
    get_path_value,
    normalize_resolved,
    parse_headers,
    parse_key_value_items,
    read_body,
)
from .http import build_url, parse_response_body, request_json
from .profiles import DEFAULT_LEGACY_ERP_SCOPE, resolve_legacy_erp_profile

GET_ENTITIES = [
    "shipment",
    "salesorder",
    "purchaseorder",
    "inventory",
    "inventory-summary",
    "discount",
    "discount-code",
    "lot-serial-class",
    "kit-specification",
    "kit-assembly",
    "inventory-receipt",
    "customer",
    "customer-internal",
    "customer-class",
    "warehouse",
    "warehouse-location",
    "location",
    "branch",
]

LIST_ENTITIES = [
    "shipment",
    "salesorder",
    "purchaseorder",
    "inventory",
    "discount",
    "discount-code",
    "lot-serial-class",
    "kit-specification",
    "kit-assembly",
    "inventory-receipt",
    "inventory-itemclass",
    "inventory-postingclass",
    "customer",
    "customer-salesorder",
    "customer-contact",
    "customer-class",
    "warehouse",
    "warehouse-location",
    "location",
    "branch",
]

CREATE_ENTITIES = ["salesorder", "purchaseorder", "inventory", "discount", "inventory-receipt", "kit-specification", "kit-assembly", "customer", "location", "warehouse-location"]
UPDATE_ENTITIES = ["shipment", "salesorder", "purchaseorder", "inventory", "customer", "customer-internal", "kit-specification", "kit-assembly", "location", "warehouse-location"]
DELETE_ENTITIES = ["discount", "kit-assembly"]


def resolve_order_number(data: Any, location: Optional[str]) -> Optional[str]:
    value = get_path_value(
        data,
        [
            "orderNo.value",
            "orderNumber.value",
            "orderNbr.value",
            "orderNo",
            "orderNumber",
            "orderNbr",
        ],
    )
    if value is not None:
        return str(value)
    return get_last_path_segment(location)


def resolve_order_type(data: Any, request_body_json: Any) -> Optional[str]:
    value = get_path_value(data, ["orderType.value", "orderType"])
    if value is not None:
        return str(value)
    value = get_path_value(request_body_json, ["orderType.value", "orderType"])
    if value is not None:
        return str(value)
    return "SO"


def resolve_shipment_number(data: Any, location: Optional[str], fallback: Optional[str] = None) -> Optional[str]:
    value = get_path_value(
        data,
        [
            "shipmentDto.shipmentNumber.value",
            "shipmentDto.shipmentNbr.value",
            "shipmentDto.shipmentNo.value",
            "shipmentDto.shipmentNumber",
            "shipmentDto.shipmentNbr",
            "shipmentDto.shipmentNo",
            "shipmentNumber.value",
            "shipmentNbr.value",
            "shipmentNumber",
            "shipmentNbr",
            "referenceNumber",
        ],
    )
    if value is not None:
        return str(value)
    return get_last_path_segment(location) or fallback


def resolve_inventory_number(
    data: Any,
    location: Optional[str],
    request_body_json: Any = None,
    fallback: Optional[str] = None,
) -> Optional[str]:
    value = get_path_value(
        data,
        [
            "inventoryNumber.value",
            "inventoryNumber",
            "inventoryNbr.value",
            "inventoryNbr",
        ],
    )
    if value is not None:
        return str(value)
    value = get_path_value(
        request_body_json,
        [
            "inventoryNumber.value",
            "inventoryNumber",
            "inventoryNbr.value",
            "inventoryNbr",
        ],
    )
    if value is not None:
        return str(value)
    return get_last_path_segment(location) or fallback


def resolve_inventory_receipt_number(
    data: Any,
    location: Optional[str],
    request_body_json: Any = None,
    fallback: Optional[str] = None,
) -> Optional[str]:
    value = get_path_value(
        data,
        [
            "referenceNumber.value",
            "receiptNumber.value",
            "referenceNumber",
            "receiptNumber",
        ],
    )
    if value is not None:
        return str(value)
    value = get_path_value(
        request_body_json,
        [
            "referenceNumber.value",
            "receiptNumber.value",
            "referenceNumber",
            "receiptNumber",
        ],
    )
    if value is not None:
        return str(value)
    return get_last_path_segment(location) or fallback


def resolve_discount_code(data: Any, body_json: Any = None) -> Optional[str]:
    value = get_path_value(data, ["discountCode", "discountCode.value"])
    if value is not None:
        return str(value)
    value = get_path_value(body_json, ["discountCode.value", "discountCode"])
    if value is not None:
        return str(value)
    return None


def resolve_discount_series(data: Any, body_json: Any = None) -> Optional[str]:
    value = get_path_value(data, ["series", "series.value"])
    if value is not None:
        return str(value)
    value = get_path_value(body_json, ["series.value", "series"])
    if value is not None:
        return str(value)
    return None


def resolve_customer_number(
    data: Any,
    location: Optional[str] = None,
    body_json: Any = None,
    fallback: Optional[str] = None,
) -> Optional[str]:
    value = get_path_value(data, ["number", "customerCd", "customerNumber", "customer.number", "number.value"])
    if value is not None:
        return str(value)
    value = get_last_path_segment(location)
    if value:
        return str(value)
    value = get_path_value(body_json, ["number.value", "number", "customerCd.value", "customerCd", "customerNumber.value", "customerNumber"])
    if value is not None:
        return str(value)
    return fallback


def resolve_customer_internal_id(data: Any, body_json: Any = None) -> Optional[str]:
    value = get_path_value(data, ["internalId", "internalID", "id", "internalId.value", "internalID.value"])
    if value is not None:
        return str(value)
    value = get_path_value(body_json, ["internalId.value", "internalId", "internalID.value", "internalID", "id.value", "id"])
    if value is not None:
        return str(value)
    return None


def resolve_kit_inventory_id(data: Any, body_json: Any = None) -> Optional[str]:
    value = get_path_value(
        data,
        ["kitInventoryID", "kitInventoryId", "kitInventoryID.value", "kitInventoryId.value"],
    )
    if value is not None:
        return str(value)
    value = get_path_value(
        body_json,
        ["kitInventoryID.value", "kitInventoryId.value", "kitInventoryID", "kitInventoryId"],
    )
    if value is not None:
        return str(value)
    return None


def resolve_kit_revision_id(data: Any, body_json: Any = None) -> Optional[str]:
    value = get_path_value(
        data,
        ["revisionID", "revisionId", "revision", "revisionID.value", "revisionId.value"],
    )
    if value is not None:
        return str(value)
    value = get_path_value(
        body_json,
        ["revisionID.value", "revisionId.value", "revisionID", "revisionId", "revision"],
    )
    if value is not None:
        return str(value)
    return None


def resolve_kit_assembly_type(data: Any, body_json: Any = None) -> Optional[str]:
    value = get_path_value(data, ["type", "type.value"])
    if value is not None:
        return str(value)
    value = get_path_value(body_json, ["type.value", "type"])
    if value is not None:
        return str(value)
    return None


def resolve_kit_assembly_ref_no(
    data: Any,
    location: Optional[str],
    body_json: Any = None,
    fallback: Optional[str] = None,
) -> Optional[str]:
    value = get_path_value(data, ["refNo", "refNbr", "referenceNumber", "refNo.value", "refNbr.value"])
    if value is not None:
        return str(value)
    value = get_path_value(body_json, ["refNo.value", "refNo", "refNbr.value", "refNbr"])
    if value is not None:
        return str(value)
    return get_last_path_segment(location) or fallback


def resolve_location_id(data: Any, body_json: Any = None) -> Optional[str]:
    value = get_path_value(
        data,
        ["locationId.value", "locationID.value", "locationId", "locationID", "id"],
    )
    if value is not None:
        return str(value)
    value = get_path_value(
        body_json,
        ["locationId.value", "locationID.value", "locationId", "locationID", "id"],
    )
    if value is not None:
        return str(value)
    return None


def resolve_b_account_id(data: Any, body_json: Any = None) -> Optional[str]:
    value = get_path_value(
        data,
        [
            "bAccountId.value",
            "bAccountID.value",
            "bAccountId",
            "bAccountID",
            "baccountId.value",
            "baccountID.value",
            "baccountId",
            "baccountID",
        ],
    )
    if value is not None:
        return str(value)
    value = get_path_value(
        body_json,
        [
            "bAccountId.value",
            "bAccountID.value",
            "bAccountId",
            "bAccountID",
            "baccountId.value",
            "baccountID.value",
            "baccountId",
            "baccountID",
        ],
    )
    if value is not None:
        return str(value)
    return None


def build_create_shipment_body(args: argparse.Namespace) -> tuple[str, Dict[str, Any]]:
    if not args.shipment_warehouse:
        abort(
            "argument_error",
            "create-shipment requires --shipment-warehouse when no body is provided.",
            exit_code=2,
        )

    shipment_date = args.shipment_date or f"{date.today().isoformat()}T00:00:00"
    body_json: Dict[str, Any] = {
        "orderType": args.order_type or "SO",
        "shipmentDate": shipment_date,
        "shipmentWarehouse": args.shipment_warehouse,
        "returnShipmentDto": True if args.return_shipment_dto is None else args.return_shipment_dto,
    }
    if args.operation:
        body_json["operation"] = args.operation
    return json.dumps(body_json), body_json


def extract_warehouse_locations(payload: Dict[str, Any], warehouse_id: str, location_id: Optional[str] = None) -> Dict[str, Any]:
    if not payload.get("ok"):
        return payload

    data = payload.get("data")
    if not isinstance(data, dict):
        abort(
            "not_found",
            f"Warehouse '{warehouse_id}' did not return a warehouse payload.",
            method=payload.get("method"),
            url=payload.get("url"),
            status_code=404,
        )

    locations = data.get("locations")
    if not isinstance(locations, list):
        locations = []

    if location_id is None:
        next_payload = dict(payload)
        next_payload["data"] = locations
        next_payload["resolved"] = normalize_resolved({"warehouse_id": warehouse_id})
        return next_payload

    match = None
    for item in locations:
        if not isinstance(item, dict):
            continue
        if str(resolve_location_id(item)) == str(location_id):
            match = item
            break

    if match is None:
        abort(
            "not_found",
            f"Warehouse location '{location_id}' was not found in warehouse '{warehouse_id}'.",
            method=payload.get("method"),
            url=payload.get("url"),
            status_code=404,
        )

    next_payload = dict(payload)
    next_payload["data"] = match
    next_payload["resolved"] = normalize_resolved({"warehouse_id": warehouse_id, "location_id": location_id})
    return next_payload


def select_inventory_from_list(payload: Dict[str, Any], identifier: str, warehouse: Optional[str]) -> Dict[str, Any]:
    if not payload.get("ok"):
        return payload

    data = payload.get("data")
    selected = None
    if isinstance(data, list):
        for item in data:
            if resolve_inventory_number(item, None) == identifier:
                selected = item
                break
        if selected is None and data:
            selected = data[0]
    elif isinstance(data, dict):
        selected = data

    if not isinstance(selected, dict):
        abort(
            "not_found",
            f"Inventory '{identifier}' was not found.",
            method=payload.get("method"),
            url=payload.get("url"),
            status_code=404,
        )

    if warehouse is not None:
        details = selected.get("warehouseDetails")
        if isinstance(details, list):
            selected = dict(selected)
            selected["warehouseDetails"] = [
                item for item in details if str(get_path_value(item, ["warehouse.value", "warehouse.id", "warehouse"])) == str(warehouse)
            ]

    next_payload = dict(payload)
    next_payload["data"] = selected
    return next_payload


def select_discount_code_from_list(payload: Dict[str, Any], identifier: str) -> Dict[str, Any]:
    if not payload.get("ok"):
        return payload

    data = payload.get("data")
    records = data.get("records") if isinstance(data, dict) else None
    selected = None
    if isinstance(records, list):
        for item in records:
            if str(get_path_value(item, ["discountCode"])) == str(identifier):
                selected = item
                break
        if selected is None and records:
            selected = records[0]

    if not isinstance(selected, dict):
        abort(
            "not_found",
            f"Discount code '{identifier}' was not found.",
            method=payload.get("method"),
            url=payload.get("url"),
            status_code=404,
        )

    next_payload = dict(payload)
    next_payload["data"] = selected
    return next_payload


def select_discount_from_list(
    payload: Dict[str, Any],
    discount_code: str,
    series: Optional[str],
    *,
    allow_series_fallback: bool = False,
) -> Dict[str, Any]:
    if not payload.get("ok"):
        return payload

    data = payload.get("data")
    records = data.get("records") if isinstance(data, dict) else None
    selected = None
    candidates = []
    if isinstance(records, list):
        for item in records:
            if not isinstance(item, dict):
                continue
            if str(get_path_value(item, ["discountCode"])) != str(discount_code):
                continue
            candidates.append(item)
            if series is not None and str(get_path_value(item, ["series"])) == str(series):
                selected = item
                break

    if selected is None and allow_series_fallback and candidates:
        selected = max(
            candidates,
            key=lambda item: str(
                get_path_value(
                    item,
                    [
                        "createdDateTime",
                        "lastModifiedDateTime",
                        "effectiveDate",
                        "series",
                    ],
                )
                or ""
            ),
        )

    if not isinstance(selected, dict):
        suffix = f"/{series}" if series else ""
        abort(
            "not_found",
            f"Discount '{discount_code}{suffix}' was not found.",
            method=payload.get("method"),
            url=payload.get("url"),
            status_code=404,
        )

    next_payload = dict(payload)
    next_payload["data"] = selected
    return next_payload


def perform_request(
    args: argparse.Namespace,
    *,
    method: str,
    path: str,
    body_text: Optional[str] = None,
    include_headers: bool = False,
    query_items: Optional[list[str]] = None,
    header_items: Optional[list[str]] = None,
) -> Dict[str, Any]:
    profile = resolve_legacy_erp_profile(args)
    url = build_url(profile.base_url, path, parse_key_value_items(query_items or args.query or [], "query"))
    headers = dict(profile.headers)
    effective_header_items = header_items if header_items is not None else args.header
    if effective_header_items:
        headers.update(parse_headers(effective_header_items))

    try:
        response = request_json(
            method,
            url,
            headers=headers,
            body_text=body_text,
            timeout=args.timeout,
            verify_tls=profile.verify_tls,
        )
    except requests.RequestException as exc:
        abort(
            "connection_error",
            str(exc),
            method=method.upper(),
            url=url,
        )

    data = parse_response_body(response)
    payload: Dict[str, Any] = {
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
    return payload


def context_command(args: argparse.Namespace) -> int:
    profile = resolve_legacy_erp_profile(args)
    emit_json(
        {
            "ok": True,
            "status_code": 200,
            "method": "GET",
            "url": profile.base_url,
            "data": None,
            "error": None,
            "resolved": normalize_resolved(profile.resolved_context),
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
    if args.entity == "shipment":
        path = f"/v1/shipment/{args.identifier}"
        payload = perform_request(args, method="GET", path=path, include_headers=args.include_headers)
        payload["resolved"] = normalize_resolved({"shipment_no": args.identifier})
    elif args.entity == "inventory":
        if args.warehouse and not args.warehouse_details:
            abort(
                "argument_error",
                "erp get inventory --warehouse requires --warehouse-details.",
                exit_code=2,
            )
        if args.warehouse_details:
            payload = perform_request(
                args,
                method="GET",
                path="/v1/inventory",
                include_headers=args.include_headers,
                query_items=[*(args.query or []), f"inventoryNumber={args.identifier}", "PageSize=1", "expandWarehouseDetail=true"],
            )
            payload = select_inventory_from_list(payload, args.identifier, args.warehouse)
        else:
            payload = perform_request(args, method="GET", path=f"/v1/inventory/{args.identifier}", include_headers=args.include_headers)
        payload["resolved"] = normalize_resolved({"inventory_no": args.identifier})
    elif args.entity == "inventory-summary":
        query_items = list(args.query or [])
        if args.warehouse:
            query_items.append(f"warehouse={args.warehouse}")
        if args.location:
            query_items.append(f"location={args.location}")
        payload = perform_request(
            args,
            method="GET",
            path=f"/v1/inventorysummary/{args.identifier}",
            include_headers=args.include_headers,
            query_items=query_items,
        )
        payload["resolved"] = normalize_resolved(
            {
                "inventory_no": args.identifier,
                "warehouse_id": args.warehouse,
                "location_id": args.location,
            }
        )
    elif args.entity == "discount":
        if not args.secondary_identifier:
            abort(
                "argument_error",
                "erp get discount requires <discount_code> and <series>.",
                exit_code=2,
            )
        payload = perform_request(
            args,
            method="GET",
            path="/v1/discount",
            include_headers=args.include_headers,
            query_items=[*(args.query or []), f"discountCode={args.identifier}", f"series={args.secondary_identifier}", "PageSize=5"],
        )
        payload = select_discount_from_list(payload, args.identifier, args.secondary_identifier)
        payload["resolved"] = normalize_resolved({"discount_code": args.identifier, "discount_series": args.secondary_identifier})
    elif args.entity == "discount-code":
        payload = perform_request(
            args,
            method="GET",
            path="/v1/discountCode",
            include_headers=args.include_headers,
            query_items=[*(args.query or []), f"discountCode={args.identifier}", "PageSize=1"],
        )
        payload = select_discount_code_from_list(payload, args.identifier)
        payload["resolved"] = normalize_resolved({"discount_code": args.identifier})
    elif args.entity == "lot-serial-class":
        payload = perform_request(
            args,
            method="GET",
            path=f"/v1/lotserialclass/{args.identifier}",
            include_headers=args.include_headers,
        )
        payload["resolved"] = normalize_resolved({"lot_serial_class_id": args.identifier})
    elif args.entity == "kit-specification":
        path = (
            f"/v1/KitSpecifications/{args.identifier}/{args.secondary_identifier}"
            if args.secondary_identifier
            else f"/v1/KitSpecifications/{args.identifier}"
        )
        payload = perform_request(args, method="GET", path=path, include_headers=args.include_headers)
        payload["resolved"] = normalize_resolved(
            {
                "kit_inventory_id": args.identifier,
                "revision_id": args.secondary_identifier,
            }
        )
    elif args.entity == "kit-assembly":
        if not args.secondary_identifier:
            abort(
                "argument_error",
                "erp get kit-assembly requires <type> and <ref_no>.",
                exit_code=2,
            )
        payload = perform_request(
            args,
            method="GET",
            path=f"/v1/kitassembly/{args.identifier}/{args.secondary_identifier}",
            include_headers=args.include_headers,
        )
        payload["resolved"] = normalize_resolved({"kit_assembly_type": args.identifier, "kit_assembly_ref_no": args.secondary_identifier})
    elif args.entity == "inventory-receipt":
        payload = perform_request(
            args,
            method="GET",
            path=f"/v1/inventoryReceipt/{args.identifier}",
            include_headers=args.include_headers,
        )
        payload["resolved"] = normalize_resolved({"inventory_receipt_no": args.identifier})
    elif args.entity == "salesorder":
        path = f"/v1/salesorder/{args.order_type}/{args.identifier}" if args.order_type else f"/v1/salesorder/{args.identifier}"
        payload = perform_request(args, method="GET", path=path, include_headers=args.include_headers)
        payload["resolved"] = normalize_resolved({"order_no": args.identifier, "order_type": args.order_type or "SO"})
    elif args.entity == "purchaseorder":
        payload = perform_request(args, method="GET", path=f"/v1/purchaseorder/{args.identifier}", include_headers=args.include_headers)
        payload["resolved"] = normalize_resolved({"purchase_order_no": args.identifier})
    elif args.entity == "customer":
        payload = perform_request(args, method="GET", path=f"/v1/customer/{args.identifier}", include_headers=args.include_headers)
        payload["resolved"] = normalize_resolved({"customer_no": args.identifier})
    elif args.entity == "customer-internal":
        payload = perform_request(
            args,
            method="GET",
            path=f"/v1/customer/internal/{args.identifier}",
            include_headers=args.include_headers,
        )
        payload["resolved"] = normalize_resolved({"customer_internal_id": args.identifier})
    elif args.entity == "customer-class":
        payload = perform_request(
            args,
            method="GET",
            path=f"/v1/customer/customerClass/{args.identifier}",
            include_headers=args.include_headers,
        )
        payload["resolved"] = normalize_resolved({"customer_class_id": args.identifier})
    elif args.entity == "warehouse":
        payload = perform_request(args, method="GET", path=f"/v1/warehouse/{args.identifier}", include_headers=args.include_headers)
        payload["resolved"] = normalize_resolved({"warehouse_id": args.identifier})
    elif args.entity == "warehouse-location":
        if not args.secondary_identifier:
            abort(
                "argument_error",
                "erp get warehouse-location requires <warehouse_id> and <location_id>.",
                exit_code=2,
            )
        payload = perform_request(args, method="GET", path=f"/v1/warehouse/{args.identifier}", include_headers=args.include_headers)
        payload = extract_warehouse_locations(payload, args.identifier, args.secondary_identifier)
    elif args.entity == "location":
        if not args.secondary_identifier:
            abort(
                "argument_error",
                "erp get location requires <b_account_id> and <location_id>.",
                exit_code=2,
            )
        payload = perform_request(
            args,
            method="GET",
            path=f"/v1/location/{args.identifier}/{args.secondary_identifier}",
            include_headers=args.include_headers,
        )
        payload["resolved"] = normalize_resolved({"b_account_id": args.identifier, "location_id": args.secondary_identifier})
    else:
        payload = perform_request(args, method="GET", path=f"/v1/branch/{args.identifier}", include_headers=args.include_headers)
        payload["resolved"] = normalize_resolved({"branch_no": args.identifier})

    emit_json(payload)
    return 0 if payload["ok"] else 1


def list_command(args: argparse.Namespace) -> int:
    query_items = list(args.query or [])
    if args.page_number is not None:
        query_items.append(f"PageNumber={args.page_number}")
    if args.page_size is not None:
        query_items.append(f"PageSize={args.page_size}")
    if args.number_to_read is not None:
        query_items.append(f"NumberToRead={args.number_to_read}")

    if args.entity == "warehouse-location":
        if not args.warehouse_id:
            abort(
                "argument_error",
                "erp list warehouse-location requires --warehouse-id.",
                exit_code=2,
            )
        payload = perform_request(
            args,
            method="GET",
            path=f"/v1/warehouse/{args.warehouse_id}",
            include_headers=args.include_headers,
            query_items=query_items,
        )
        payload = extract_warehouse_locations(payload, args.warehouse_id)
    else:
        path_map = {
            "shipment": "/v1/shipment",
            "salesorder": "/v1/salesorder",
            "purchaseorder": "/v1/purchaseorder",
            "inventory": "/v1/inventory",
            "discount": "/v1/discount",
            "discount-code": "/v1/discountCode",
            "lot-serial-class": "/v1/lotserialclass",
            "kit-specification": "/v1/KitSpecifications",
            "kit-assembly": "/v1/kitassembly",
            "inventory-receipt": "/v1/inventoryReceipt",
            "inventory-itemclass": "/v1/inventory/itemClass",
            "inventory-postingclass": "/v1/inventory/itemPostClass",
            "customer": "/v1/customer",
            "customer-salesorder": f"/v1/customer/{args.customer_no}/salesorder",
            "customer-contact": f"/v1/customer/{args.customer_no}/contact",
            "customer-class": "/v1/customer/customerClass",
            "warehouse": "/v1/warehouse",
            "location": "/v1/location",
            "branch": "/v1/branch",
        }
        if args.entity in {"customer-salesorder", "customer-contact"} and not args.customer_no:
            abort(
                "argument_error",
                f"erp list {args.entity} requires --customer-no.",
                exit_code=2,
            )
        payload = perform_request(
            args,
            method="GET",
            path=path_map[args.entity],
            include_headers=args.include_headers,
            query_items=[
                *query_items,
                *([f"kitInventoryID={args.kit_inventory_id}"] if args.entity == "kit-specification" and args.kit_inventory_id else []),
                *([f"revisionID={args.revision_id}"] if args.entity == "kit-specification" and args.revision_id else []),
                *([f"discountCode={args.discount_code}"] if args.entity == "discount" and args.discount_code else []),
                *([f"series={args.series}"] if args.entity == "discount" and args.series else []),
                *([f"discountCode={args.discount_code}"] if args.entity == "discount-code" and args.discount_code else []),
                *([f"type={args.kit_assembly_type}"] if args.entity == "kit-assembly" and args.kit_assembly_type else []),
                *([f"refNo={args.kit_assembly_ref_no}"] if args.entity == "kit-assembly" and args.kit_assembly_ref_no else []),
                *([f"status={args.status}"] if args.entity == "kit-assembly" and args.status else []),
                *([f"expandStockComponents={str(args.expand_stock_components).lower()}"] if args.entity == "kit-assembly" and args.expand_stock_components else []),
                *([f"expandNonStockComponents={str(args.expand_non_stock_components).lower()}"] if args.entity == "kit-assembly" and args.expand_non_stock_components else []),
                *([f"expandKitAllocations={str(args.expand_kit_allocations).lower()}"] if args.entity == "kit-assembly" and args.expand_kit_allocations else []),
            ],
        )

    emit_json(payload)
    return 0 if payload["ok"] else 1


def create_command(args: argparse.Namespace) -> int:
    body_text, body_json = read_body(args.body_file, args.body_json)
    if body_text is None:
        abort(
            "argument_error",
            f"create {args.entity} requires --body-file or --body-json.",
            exit_code=2,
        )

    if args.entity == "salesorder":
        path = "/v1/salesorder"
    elif args.entity == "purchaseorder":
        path = "/v1/purchaseorder"
    elif args.entity == "inventory":
        path = "/v1/inventory"
    elif args.entity == "customer":
        path = "/v1/customer"
    elif args.entity == "discount":
        path = "/v1/discount"
    elif args.entity == "kit-specification":
        path = "/v1/KitSpecifications"
    elif args.entity == "kit-assembly":
        path = "/v1/kitassembly"
    elif args.entity == "inventory-receipt":
        path = "/v1/inventoryReceipt"
    elif args.entity == "location":
        path = "/v1/location"
    else:
        if not args.identifier:
            abort(
                "argument_error",
                "create warehouse-location requires <warehouse_id> before the body flags.",
                exit_code=2,
            )
        path = f"/v1/warehouse/{args.identifier}/location"

    payload = perform_request(args, method="POST", path=path, body_text=body_text, include_headers=True)
    headers = payload.get("headers", {})
    location = headers.get("Location") or headers.get("location")

    if args.entity == "salesorder":
        resolved = {
            "order_no": resolve_order_number(payload.get("data"), location),
            "order_type": resolve_order_type(payload.get("data"), body_json),
            "location": location,
        }
    elif args.entity == "purchaseorder":
        resolved = {
            "purchase_order_no": resolve_order_number(payload.get("data"), location),
            "purchase_order_type": resolve_order_type(payload.get("data"), body_json),
            "location": location,
        }
    elif args.entity == "inventory":
        resolved = {
            "inventory_no": resolve_inventory_number(payload.get("data"), location, body_json),
            "location": location,
        }
    elif args.entity == "discount":
        resolved = {
            "discount_code": resolve_discount_code(payload.get("data"), body_json),
            "discount_series": resolve_discount_series(payload.get("data"), body_json),
            "location": location,
        }
        if payload["ok"] and resolved["discount_code"]:
            lookup_payload = perform_request(
                args,
                method="GET",
                path="/v1/discount",
                query_items=[f"discountCode={resolved['discount_code']}", "PageSize=100"],
            )
            if lookup_payload.get("ok"):
                try:
                    lookup_payload = select_discount_from_list(
                        lookup_payload,
                        resolved["discount_code"],
                        resolved["discount_series"],
                        allow_series_fallback=True,
                    )
                    resolved["discount_code"] = resolve_discount_code(lookup_payload.get("data"), body_json)
                    resolved["discount_series"] = resolve_discount_series(lookup_payload.get("data"), body_json)
                except SystemExit:
                    pass
    elif args.entity == "customer":
        internal_id = headers.get("VnfInternalId") or headers.get("vnfinternalid")
        resolved = {
            "customer_no": resolve_customer_number(payload.get("data"), location, body_json),
            "customer_internal_id": str(internal_id) if internal_id is not None else resolve_customer_internal_id(payload.get("data"), body_json),
            "location": location,
        }
    elif args.entity == "kit-specification":
        resolved = {
            "kit_inventory_id": resolve_kit_inventory_id(payload.get("data"), body_json),
            "revision_id": resolve_kit_revision_id(payload.get("data"), body_json),
            "location": location,
        }
    elif args.entity == "kit-assembly":
        resolved = {
            "kit_assembly_type": resolve_kit_assembly_type(payload.get("data"), body_json),
            "kit_assembly_ref_no": resolve_kit_assembly_ref_no(payload.get("data"), location, body_json),
            "location": location,
        }
    elif args.entity == "inventory-receipt":
        resolved = {
            "inventory_receipt_no": resolve_inventory_receipt_number(payload.get("data"), location, body_json),
            "location": location,
        }
    elif args.entity == "location":
        resolved = {
            "b_account_id": resolve_b_account_id(payload.get("data"), body_json),
            "location_id": resolve_location_id(payload.get("data"), body_json),
            "location": location,
        }
    else:
        resolved = {
            "warehouse_id": args.identifier,
            "location_id": resolve_location_id(payload.get("data"), body_json),
            "location": location,
        }

    payload["resolved"] = normalize_resolved(resolved)
    if not args.include_headers:
        payload.pop("headers", None)
    emit_json(payload)
    return 0 if payload["ok"] else 1


def update_command(args: argparse.Namespace) -> int:
    body_text, _ = read_body(args.body_file, args.body_json)
    if body_text is None:
        abort(
            "argument_error",
            f"update {args.entity} requires --body-file or --body-json.",
            exit_code=2,
        )

    if args.entity == "salesorder":
        path = f"/v1/salesorder/{args.identifier}"
        resolved = {"order_no": args.identifier, "order_type": args.order_type}
    elif args.entity == "purchaseorder":
        path = f"/v1/purchaseorder/{args.identifier}"
        resolved = {"purchase_order_no": args.identifier}
    elif args.entity == "inventory":
        path = f"/v1/inventory/{args.identifier}"
        resolved = {"inventory_no": args.identifier}
    elif args.entity == "customer":
        path = f"/v1/customer/{args.identifier}"
        resolved = {"customer_no": args.identifier}
    elif args.entity == "customer-internal":
        path = f"/v1/customer/internal/{args.identifier}"
        resolved = {"customer_internal_id": args.identifier}
    elif args.entity == "kit-specification":
        if not args.secondary_identifier:
            abort(
                "argument_error",
                "update kit-specification requires <kit_inventory_id> and <revision_id>.",
                exit_code=2,
            )
        path = f"/v1/KitSpecifications/{args.identifier}/{args.secondary_identifier}"
        resolved = {"kit_inventory_id": args.identifier, "revision_id": args.secondary_identifier}
    elif args.entity == "kit-assembly":
        if not args.secondary_identifier:
            abort(
                "argument_error",
                "update kit-assembly requires <type> and <ref_no>.",
                exit_code=2,
            )
        path = f"/v1/kitassembly/{args.identifier}/{args.secondary_identifier}"
        resolved = {"kit_assembly_type": args.identifier, "kit_assembly_ref_no": args.secondary_identifier}
    elif args.entity == "shipment":
        path = f"/v1/shipment/{args.identifier}"
        resolved = {"shipment_no": args.identifier}
    elif args.entity == "location":
        if not args.secondary_identifier:
            abort(
                "argument_error",
                "update location requires <b_account_id> and <location_id>.",
                exit_code=2,
            )
        path = f"/v1/location/{args.identifier}/{args.secondary_identifier}"
        resolved = {"b_account_id": args.identifier, "location_id": args.secondary_identifier}
    else:
        if not args.secondary_identifier:
            abort(
                "argument_error",
                "update warehouse-location requires <warehouse_id> and <location_id>.",
                exit_code=2,
            )
        path = f"/v1/warehouse/{args.identifier}/location/{args.secondary_identifier}"
        resolved = {"warehouse_id": args.identifier, "location_id": args.secondary_identifier}

    payload = perform_request(args, method="PUT", path=path, body_text=body_text, include_headers=args.include_headers)
    payload["resolved"] = normalize_resolved(resolved)
    emit_json(payload)
    return 0 if payload["ok"] else 1


def delete_command(args: argparse.Namespace) -> int:
    if args.entity == "discount":
        if not args.secondary_identifier:
            abort(
                "argument_error",
                "delete discount requires <discount_code> and <series>.",
                exit_code=2,
            )
        path = f"/v1/discount/{args.identifier}/{args.secondary_identifier}"
        resolved = {"discount_code": args.identifier, "discount_series": args.secondary_identifier}
    elif args.entity == "kit-assembly":
        if not args.secondary_identifier:
            abort(
                "argument_error",
                "delete kit-assembly requires <type> and <ref_no>.",
                exit_code=2,
            )
        path = f"/v1/kitassembly/{args.identifier}/{args.secondary_identifier}"
        resolved = {"kit_assembly_type": args.identifier, "kit_assembly_ref_no": args.secondary_identifier}
    else:
        abort("argument_error", f"Unsupported delete entity: {args.entity}", exit_code=2)

    payload = perform_request(args, method="DELETE", path=path, include_headers=args.include_headers)
    payload["resolved"] = normalize_resolved(resolved)
    emit_json(payload)
    return 0 if payload["ok"] else 1


def action_command(args: argparse.Namespace) -> int:
    body_text, body_json = read_body(args.body_file, args.body_json)
    if args.entity == "salesorder":
        resolved = {"order_no": args.identifier, "order_type": args.order_type or "SO"}
        if args.action_name == "create-shipment":
            path = f"/v1/salesorder/{args.identifier}/action/createShipment"
            if body_text is None:
                body_text, body_json = build_create_shipment_body(args)
        elif args.action_name == "cancel":
            path = f"/v1/salesorder/{args.identifier}/action/cancelSalesOrder"
            body_text = body_text or json.dumps({"orderType": args.order_type or "SO"})
        elif args.action_name == "reopen":
            path = f"/v1/salesorder/{args.identifier}/action/reopenSalesOrder"
            body_text = body_text or ""
        else:
            abort("argument_error", f"Unsupported salesorder action: {args.action_name}", exit_code=2)
    elif args.entity == "shipment":
        resolved = {"shipment_no": args.identifier}
        if args.action_name == "confirm":
            path = f"/v1/shipment/{args.identifier}/action/confirmShipment"
            body_text = body_text or ""
        elif args.action_name == "add-so-line":
            path = f"/v1/shipment/{args.identifier}/action/addSOLine"
        elif args.action_name == "add-so-order":
            path = f"/v1/shipment/{args.identifier}/action/addSOOrder"
        elif args.action_name == "cancel":
            path = f"/v1/shipment/{args.identifier}/action/cancelShipment"
            body_text = body_text or ""
        elif args.action_name == "correct":
            path = f"/v1/shipment/{args.identifier}/action/correctShipment"
            body_text = body_text or ""
        else:
            abort("argument_error", f"Unsupported shipment action: {args.action_name}", exit_code=2)
    elif args.entity == "inventory-receipt":
        resolved = {"inventory_receipt_no": args.identifier}
        if args.action_name == "release":
            path = f"/v1/inventoryReceipt/{args.identifier}/action/release"
            body_text = body_text or ""
        else:
            abort("argument_error", f"Unsupported inventory-receipt action: {args.action_name}", exit_code=2)
    elif args.entity == "discount":
        if not args.secondary_identifier:
            abort(
                "argument_error",
                "action discount update-discounts requires <discount_code> and <series>.",
                exit_code=2,
            )
        resolved = {"discount_code": args.identifier, "discount_series": args.secondary_identifier}
        if args.action_name == "update-discounts":
            path = f"/v1/discount/{args.identifier}/{args.secondary_identifier}/action/updateDiscounts"
            body_text = body_text or ""
        else:
            abort("argument_error", f"Unsupported discount action: {args.action_name}", exit_code=2)
    elif args.entity == "purchaseorder":
        resolved = {"purchase_order_no": args.identifier}
        if args.action_name == "create-purchase-receipt":
            path = f"/v1/purchaseorder/{args.identifier}/action/createpurchasereceipt"
            body_text = body_text or ""
        else:
            abort("argument_error", f"Unsupported purchaseorder action: {args.action_name}", exit_code=2)
    else:
        if not args.secondary_identifier:
            abort(
                "argument_error",
                "action kit-assembly release requires <type> and <ref_no>.",
                exit_code=2,
            )
        resolved = {"kit_assembly_type": args.identifier, "kit_assembly_ref_no": args.secondary_identifier}
        if args.action_name == "release":
            path = f"/v1/kitassembly/{args.identifier}/{args.secondary_identifier}/action/release"
            body_text = body_text or ""
        else:
            abort("argument_error", f"Unsupported kit-assembly action: {args.action_name}", exit_code=2)

    payload = perform_request(args, method="POST", path=path, body_text=body_text, include_headers=True)
    headers = payload.get("headers", {})
    location = headers.get("Location") or headers.get("location")
    if args.entity == "salesorder" and args.action_name == "create-shipment":
        resolved["shipment_no"] = resolve_shipment_number(payload.get("data"), location)
        resolved["location"] = location
    elif args.entity == "shipment":
        resolved["location"] = location
        if args.action_name in {"add-so-line", "add-so-order"}:
            resolved["order_type"] = get_path_value(body_json, ["orderType", "orderType.value"])
            resolved["order_no"] = get_path_value(body_json, ["orderNumber", "orderNbr", "orderNo"])
    elif args.entity == "inventory-receipt":
        resolved["location"] = location
    else:
        resolved["location"] = location

    payload["resolved"] = normalize_resolved(resolved)
    if not args.include_headers:
        payload.pop("headers", None)
    emit_json(payload)
    return 0 if payload["ok"] else 1


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    erp = subparsers.add_parser("erp", help="Run requests against the legacy ERP API.")
    erp.set_defaults(surface="erp")
    erp.add_argument("--environment", default="localhost")
    erp.add_argument("--database")
    erp.add_argument("--base-url")
    erp.add_argument("--token-url")
    erp.add_argument("--client-id")
    erp.add_argument("--client-secret")
    erp.add_argument("--tenant-id")
    erp.add_argument("--company-id")
    erp.add_argument("--user-id")
    erp.add_argument("--scope", default=DEFAULT_LEGACY_ERP_SCOPE)
    erp.add_argument("--insecure", action="store_true")
    erp.add_argument("--timeout", type=int, default=120)

    erp_subparsers = erp.add_subparsers(dest="erp_command", required=True)

    context_parser = erp_subparsers.add_parser("context", help="Show the resolved ERP context.")
    context_parser.set_defaults(handler=context_command)

    request_parser = erp_subparsers.add_parser("request", help="Run a generic ERP request.")
    request_parser.set_defaults(handler=request_command)
    request_parser.add_argument("method")
    request_parser.add_argument("path")
    request_parser.add_argument("--query", action="append", default=[])
    request_parser.add_argument("--header", action="append", default=[])
    request_parser.add_argument("--body-file")
    request_parser.add_argument("--body-json")
    request_parser.add_argument("--include-headers", action="store_true")

    get_parser = erp_subparsers.add_parser("get", help="Run a convenience ERP GET request.")
    get_parser.set_defaults(handler=get_command)
    get_parser.add_argument("entity", choices=GET_ENTITIES)
    get_parser.add_argument("identifier")
    get_parser.add_argument("secondary_identifier", nargs="?")
    get_parser.add_argument("--order-type")
    get_parser.add_argument("--warehouse-details", action="store_true")
    get_parser.add_argument("--warehouse")
    get_parser.add_argument("--location")
    get_parser.add_argument("--query", action="append", default=[])
    get_parser.add_argument("--header", action="append", default=[])
    get_parser.add_argument("--include-headers", action="store_true")

    list_parser = erp_subparsers.add_parser("list", help="List ERP entities.")
    list_parser.set_defaults(handler=list_command)
    list_parser.add_argument("entity", choices=LIST_ENTITIES)
    list_parser.add_argument("--warehouse-id")
    list_parser.add_argument("--customer-no")
    list_parser.add_argument("--kit-inventory-id")
    list_parser.add_argument("--revision-id")
    list_parser.add_argument("--discount-code")
    list_parser.add_argument("--series")
    list_parser.add_argument("--kit-assembly-type")
    list_parser.add_argument("--kit-assembly-ref-no")
    list_parser.add_argument("--status", choices=["H", "B", "R"])
    list_parser.add_argument("--expand-stock-components", action="store_true")
    list_parser.add_argument("--expand-non-stock-components", action="store_true")
    list_parser.add_argument("--expand-kit-allocations", action="store_true")
    list_parser.add_argument("--query", action="append", default=[])
    list_parser.add_argument("--header", action="append", default=[])
    list_parser.add_argument("--page-number", type=int)
    list_parser.add_argument("--page-size", type=int)
    list_parser.add_argument("--number-to-read", type=int)
    list_parser.add_argument("--include-headers", action="store_true")

    create_parser = erp_subparsers.add_parser("create", help="Create ERP entities.")
    create_parser.set_defaults(handler=create_command)
    create_parser.add_argument("entity", choices=CREATE_ENTITIES)
    create_parser.add_argument("identifier", nargs="?")
    create_parser.add_argument("--body-file")
    create_parser.add_argument("--body-json")
    create_parser.add_argument("--query", action="append", default=[])
    create_parser.add_argument("--header", action="append", default=[])
    create_parser.add_argument("--include-headers", action="store_true")

    update_parser = erp_subparsers.add_parser("update", help="Update ERP entities.")
    update_parser.set_defaults(handler=update_command)
    update_parser.add_argument("entity", choices=UPDATE_ENTITIES)
    update_parser.add_argument("identifier")
    update_parser.add_argument("secondary_identifier", nargs="?")
    update_parser.add_argument("--order-type")
    update_parser.add_argument("--body-file")
    update_parser.add_argument("--body-json")
    update_parser.add_argument("--query", action="append", default=[])
    update_parser.add_argument("--header", action="append", default=[])
    update_parser.add_argument("--include-headers", action="store_true")

    delete_parser = erp_subparsers.add_parser("delete", help="Delete ERP entities.")
    delete_parser.set_defaults(handler=delete_command)
    delete_parser.add_argument("entity", choices=DELETE_ENTITIES)
    delete_parser.add_argument("identifier")
    delete_parser.add_argument("secondary_identifier", nargs="?")
    delete_parser.add_argument("--query", action="append", default=[])
    delete_parser.add_argument("--header", action="append", default=[])
    delete_parser.add_argument("--include-headers", action="store_true")

    action_parser = erp_subparsers.add_parser("action", help="Run named ERP actions.")
    action_parser.set_defaults(handler=action_command)
    action_parser.add_argument("entity", choices=["shipment", "salesorder", "inventory-receipt", "kit-assembly", "discount", "purchaseorder"])
    action_parser.add_argument(
        "action_name",
        choices=["create-shipment", "create-purchase-receipt", "cancel", "reopen", "confirm", "add-so-line", "add-so-order", "correct", "release", "update-discounts"],
    )
    action_parser.add_argument("identifier")
    action_parser.add_argument("secondary_identifier", nargs="?")
    action_parser.add_argument("--order-type")
    action_parser.add_argument("--body-file")
    action_parser.add_argument("--body-json")
    action_parser.add_argument("--shipment-date")
    action_parser.add_argument("--shipment-warehouse")
    action_parser.add_argument("--operation", choices=["I", "R", "i", "r"])
    action_parser.add_argument("--return-shipment-dto", dest="return_shipment_dto", action="store_true")
    action_parser.add_argument("--no-return-shipment-dto", dest="return_shipment_dto", action="store_false")
    action_parser.set_defaults(return_shipment_dto=None)
    action_parser.add_argument("--query", action="append", default=[])
    action_parser.add_argument("--header", action="append", default=[])
    action_parser.add_argument("--include-headers", action="store_true")
