import contextlib
import io
import json
import tempfile
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from api_request_runner import cli, http


class BatchTests(unittest.TestCase):
    def test_tokens_are_reused_and_isolated_by_tenant_scope_and_expiry(self):
        response = Mock()
        response.json.return_value = {'access_token': 'fake', 'expires_in': 120}
        with http.request_session(), patch.object(http, '_session') as session, patch.object(http.time, 'monotonic', return_value=0) as clock:
            session.post.return_value = response
            for _ in range(3):
                http.get_token('https://auth.invalid', 'client', 'tenant', 'read', 5)
            self.assertEqual(session.post.call_count, 1)
            http.get_token('https://auth.invalid', 'client', 'other', 'read', 5)
            http.get_token('https://auth.invalid', 'client', 'tenant', 'write', 5)
            self.assertEqual(session.post.call_count, 3)
            clock.return_value = 121
            http.get_token('https://auth.invalid', 'client', 'tenant', 'read', 5)
            self.assertEqual(session.post.call_count, 4)
            http.get_token('https://auth.invalid', 'client', 'tenant', 'read', 5, client_secret='different')
            self.assertEqual(session.post.call_count, 5)

    def test_missing_later_body_file_prevents_earlier_write(self):
        commands = [['salesorder', 'request', 'POST', '/test'], ['salesorder', 'request', 'POST', '/test', '--body-file', 'missing.json']]
        code, payload, count = self.run_batch(commands, lambda *a, **kw: {'ok': True})
        self.assertNotEqual(code, 0)
        self.assertFalse(payload['ok'])
        self.assertEqual(count, 0)

    def run_batch(self, commands, handler):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / 'batch.json'
            manifest.write_text(json.dumps(commands), encoding='utf-8')
            output = io.StringIO()
            with patch('sys.argv', ['api', 'batch', '--file', str(manifest)]), patch('api_request_runner.salesorder.perform_request', side_effect=handler) as request, contextlib.redirect_stdout(output):
                code = cli.main()
            return code, json.loads(output.getvalue()), request.call_count

    def test_failure_stops_batch_without_retrying_post(self):
        commands = [['salesorder', 'request', 'POST', '/test']] * 3
        code, payload, count = self.run_batch(commands, lambda *a, **kw: {'ok': False, 'status_code': 500})
        self.assertEqual(code, 1)
        self.assertEqual(count, 1)
        self.assertEqual(payload['skipped'], 2)

    def test_invalid_later_command_is_rejected_before_any_request(self):
        commands = [['salesorder', 'request', 'POST', '/test'], ['unknown']]
        code, payload, count = self.run_batch(commands, lambda *a, **kw: {'ok': True})
        self.assertNotEqual(code, 0)
        self.assertFalse(payload['ok'])
        self.assertEqual(count, 0)

    def test_success_has_one_json_envelope(self):
        commands = [['salesorder', 'request', 'GET', '/test']] * 3
        code, payload, count = self.run_batch(commands, lambda *a, **kw: {'ok': True, 'status_code': 200})
        self.assertEqual(code, 0)
        self.assertTrue(payload['ok'])
        self.assertEqual(count, 3)
        self.assertEqual(len(payload['results']), 3)

    def test_real_cli_reuses_one_token_for_three_requests(self):
        counts = {'token': 0, 'read': 0}
        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'
            def log_message(self, *args):
                pass
            def send_json(self, value):
                encoded = json.dumps(value).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)
            def do_POST(self):
                self.rfile.read(int(self.headers.get('Content-Length', 0)))
                counts['token'] += 1
                self.send_json({'access_token': 'local-fake-token', 'expires_in': 3600})
            def do_GET(self):
                counts['read'] += 1
                self.send_json({'number': counts['read']})
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f'http://127.0.0.1:{server.server_port}'
            with tempfile.TemporaryDirectory() as directory:
                manifest = Path(directory) / 'batch.json'
                command = ['salesorder', '--server-url', base, '--token-url', base + '/token', '--client-id', 'fake', '--client-secret', 'fake', '--tenant-id', 'fake', 'request', 'GET', '/test']
                manifest.write_text(json.dumps([command] * 3))
                completed = subprocess.run([sys.executable, str(Path(__file__).with_name('run_api_requests.py')), 'batch', '--file', str(manifest)], capture_output=True, text=True, timeout=20)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertTrue(json.loads(completed.stdout)['ok'])
            self.assertEqual(counts, {'token': 1, 'read': 3})
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
