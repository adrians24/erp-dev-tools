from __future__ import annotations

import contextlib
import io
import json
import time
from pathlib import Path

from .common import CliAbort, abort, emit_json, make_error_payload
from .http import request_session


def batch_command(args):
    from .cli import build_parser

    try:
        commands = json.loads(Path(args.file).read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as exc:
        abort('batch_file_error', str(exc), exit_code=2)
    if not isinstance(commands, list) or not commands:
        abort('argument_error', 'Batch file must contain a nonempty array of argument arrays.', exit_code=2)

    parser = build_parser()
    prepared = []
    for index, command in enumerate(commands):
        if not isinstance(command, list) or not command or not all(isinstance(x, str) for x in command) or command[0] not in ('erp', 'salesorder'):
            abort('argument_error', f'Batch command {index + 1} must be an erp or salesorder argument array.', exit_code=2)
        captured = io.StringIO()
        try:
            with contextlib.redirect_stdout(captured):
                parsed = parser.parse_args(command)
        except SystemExit:
            abort('argument_error', f'Invalid batch command {index + 1}: {captured.getvalue().strip()}', exit_code=2)
        # Resolve payload files relative to the manifest, before any action runs.
        if getattr(parsed, 'body_file', None):
            if getattr(parsed, 'body_json', None) is not None:
                abort('argument_error', f'Batch command {index + 1}: use body-file or body-json, not both.', exit_code=2)
            path = Path(parsed.body_file)
            if not path.is_absolute():
                path = Path(args.file).resolve().parent / path
            try:
                parsed.body_json = path.read_text(encoding='utf-8-sig')
            except OSError as exc:
                abort('body_file_error', f'Batch command {index + 1}: {exc}', exit_code=2)
            parsed.body_file = None
        prepared.append(parsed)

    results = []
    started = time.monotonic()
    exit_code = 0
    with request_session():
        for index, command in enumerate(prepared):
            captured = io.StringIO()
            step_started = time.monotonic()
            try:
                with contextlib.redirect_stdout(captured):
                    code = command.handler(command)
                payload = json.loads(captured.getvalue())
            except CliAbort as exc:
                payload, code = exc.payload, exc.exit_code
            except Exception as exc:
                payload = make_error_payload(None, None, 'batch_command_error', str(exc))
                code = 1
            results.append({'index': index + 1, 'elapsedSeconds': round(time.monotonic() - step_started, 3), 'result': payload})
            if code or not payload.get('ok', False):
                exit_code = code or 1
                break
    emit_json({'ok': exit_code == 0, 'results': results, 'skipped': len(prepared) - len(results), 'elapsedSeconds': round(time.monotonic() - started, 3)})
    return exit_code
