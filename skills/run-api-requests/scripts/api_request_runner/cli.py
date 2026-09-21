from __future__ import annotations

from .common import CliAbort, JsonArgumentParser, emit_json
from .legacy_erp import register as register_erp
from .salesorder import register as register_salesorder
from .batch import batch_command


def build_parser() -> JsonArgumentParser:
    parser = JsonArgumentParser(prog="run_api_requests.py")
    subparsers = parser.add_subparsers(dest="surface", required=True)
    register_erp(subparsers)
    register_salesorder(subparsers)
    batch = subparsers.add_parser('batch', help='Run argument arrays from a JSON file in order; stop on first failure.')
    batch.add_argument('--file', required=True)
    batch.set_defaults(handler=batch_command)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.handler(args)
    except CliAbort as exc:
        emit_json(exc.payload)
        return exc.exit_code
