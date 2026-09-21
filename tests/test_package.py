import ast
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
os.environ["ERP_DEV_TOOLS_CONFIG"] = str(ROOT / "tests/profiles.test.json")
CAPTURE = ROOT / "skills/sql-server-capture/scripts"
sys.path.insert(0, str(CAPTURE))
import sql_capture
API_SCRIPTS = ROOT / "skills/run-api-requests/scripts"
sys.path.insert(0, str(API_SCRIPTS))
from api_request_runner import profiles as api_profiles
from api_request_runner.common import CliAbort


def powershell(*args, cwd=None, env=None):
    return subprocess.run(["pwsh", "-NoProfile", *map(str, args)], cwd=cwd, env=env, capture_output=True, text=True, timeout=60)


class PackageTests(unittest.TestCase):
    def test_all_python_sources_parse(self):
        for file in ROOT.rglob("*.py"):
            ast.parse(file.read_text(encoding="utf-8-sig"), filename=str(file))

    def test_markdown_links_resolve(self):
        for file in ROOT.rglob("*.md"):
            for target in re.findall(r"\]\(([^)]+)\)", file.read_text(encoding="utf-8-sig")):
                if "://" in target or target.startswith("#"):
                    continue
                self.assertTrue((file.parent / target.split("#")[0]).exists(), f"Broken link in {file.relative_to(ROOT)}: {target}")

    def test_manifest_and_no_personal_paths(self):
        manifest = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
        self.assertEqual(manifest["name"], "erp-dev-tools")
        self.assertEqual({p.name for p in (ROOT / "skills").iterdir()}, {"erp-ui", "run-api-requests", "sql-server", "sql-server-capture"})
        for file in ROOT.rglob("*"):
            if file.is_file() and ".git" not in file.parts and file.suffix in {".md", ".json", ".ps1", ".py", ".yaml", ".lock"}:
                text = file.read_text(encoding="utf-8-sig")
                self.assertIsNone(re.search(r"[A-Z]:[/\\](?:Users|Dev)[/\\]", text, re.I), str(file.relative_to(ROOT)))
                self.assertIsNone(re.search(r"\b[\w.+-]+@visma[.]com\b", text), str(file.relative_to(ROOT)))
                for private_pattern in [
                    r"(?i)https?://[^/\s]*[.]erp[.]int[.]test",
                    r"\bERP_[A-Z]{2}_REAL_\d+\b",
                    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
                ]:
                    self.assertIsNone(re.search(private_pattern, text), str(file.relative_to(ROOT)))

    def test_sql_profile_override_and_explicit_database_precedence(self):
        env = os.environ | {"VISMA_SQL_LOCAL_SERVER": r"sql-host\INSTANCE", "VISMA_SQL_LOCAL_DATABASE": "ConfiguredDatabase"}
        script = ROOT / "skills/sql-server/scripts/Get-SqlServerProfile.ps1"
        for extra, expected in [((), "ConfiguredDatabase"), (("-Database", "ExplicitDatabase"), "ExplicitDatabase")]:
            result = powershell("-File", script, "-Environment", "local", "-AsJson", *extra, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            profile = json.loads(result.stdout)
            self.assertEqual(profile["Server"], r"sql-host\INSTANCE")
            self.assertEqual(profile["Database"], expected)
            self.assertEqual(profile["DefaultDatabase"], "ConfiguredDatabase")

    def test_capture_profile_configuration_and_api_path(self):
        with patch.dict(os.environ, {"VISMA_SQL_LOCAL_SERVER": "sql-host", "VISMA_SQL_LOCAL_DATABASE": "ConfiguredDatabase"}):
            spec = importlib.util.spec_from_file_location("capture_probe", CAPTURE / "sql_capture.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.assertEqual(module.SERVER_PROFILES["local"]["server"], "sql-host")
            self.assertEqual(module.SERVER_PROFILES["local"]["database"], "ConfiguredDatabase")
            self.assertEqual(module.resolve_api_script_path(None), ROOT / "skills/run-api-requests/scripts/run_api_requests.py")
            args = module.build_parser().parse_args(["around", "--database", "ExplicitDatabase", "--", "whoami"])
            self.assertEqual(args.database, "ExplicitDatabase")

    def test_local_erp_credential_headers_remain_atomic(self):
        stored = {
            "base_url": "https://erp.local.invalid/api",
            "headers": {
                "Authorization": "Bearer stored-token",
                "ipp-signature": "stored-signature",
                "ipp-company-id": "stored-company",
                "ipp-user-id": "stored-user",
            },
        }
        environment_names = [
            "VISMA_ERP_AUTHORIZATION",
            "VISMA_ERP_SIGNATURE",
            "VISMA_ERP_COMPANY_ID",
            "VISMA_ERP_USER_ID",
        ]
        with patch.dict(os.environ, {}, clear=False), patch.object(api_profiles, "read_json_credential", return_value=stored):
            for name in environment_names:
                os.environ.pop(name, None)
            resolved = api_profiles.load_legacy_local_auth({"companyId": "profile-company", "erpUser": "profile-user"})
        self.assertEqual(resolved["headers"]["ipp-company-id"], "stored-company")
        self.assertEqual(resolved["headers"]["ipp-user-id"], "stored-user")

    def test_local_erp_partial_environment_authentication_is_rejected(self):
        with patch.dict(os.environ, {"VISMA_ERP_AUTHORIZATION": "Bearer override"}, clear=False), patch.object(api_profiles, "read_json_credential", return_value={}):
            for name in ["VISMA_ERP_SIGNATURE", "VISMA_ERP_COMPANY_ID", "VISMA_ERP_USER_ID"]:
                os.environ.pop(name, None)
            with self.assertRaises(CliAbort) as raised:
                api_profiles.load_legacy_local_auth({})
        self.assertEqual(raised.exception.payload["error"]["type"], "config_error")
        self.assertEqual(
            set(raised.exception.payload["data"]["missing_environment_variables"]),
            {"VISMA_ERP_SIGNATURE", "VISMA_ERP_COMPANY_ID", "VISMA_ERP_USER_ID"},
        )

    def test_screen_url_encoding_and_reserved_keys(self):
        script = ROOT / "skills/erp-ui/scripts/Open-ErpScreen.ps1"
        result = powershell("-File", script, "-Screen", "shipment", "-Company", "A & B", "-BaseUrl", "https://erp.invalid/site", "-Session", "package-probe", "-BuildUrlOnly")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(parse_qs(urlparse(payload["url"]).query), {"CompanyID": ["A & B"], "ScreenId": ["SO302000"]})
        self.assertFalse(payload["browserOpened"])
        common = ROOT / "skills/erp-ui/scripts/ErpUi.Common.ps1"
        result = powershell("-Command", ". '" + str(common).replace("'", "''") + "'; New-ErpScreenUrl -BaseUrl https://erp.invalid -Company Demo -ScreenId SO302000 -Keys @{ ScreenId = 'SO301000' }")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("reserved", result.stderr)

    def test_screen_defaults_come_from_machine_profile(self):
        script = ROOT / "skills/erp-ui/scripts/Open-ErpScreen.ps1"
        result = powershell("-File", script, "-Screen", "shipment", "-Session", "package-probe", "-BuildUrlOnly")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["company"], "Local Test Company")
        self.assertEqual(urlparse(payload["url"]).netloc, "local.invalid")

    def test_playwright_json_parser_ignores_first_run_banner(self):
        common = ROOT / "skills/erp-ui/scripts/ErpUi.Common.ps1"
        command = (
            ". '" + str(common).replace("'", "''") + "'; "
            "$value = ConvertFrom-ErpPlaywrightJson -Context test -Output @('playwright-cli first-run notice', '{\"ok\":true,\"result\":{\"screen\":\"SO302000\"}}'); "
            "$value | ConvertTo-Json -Compress -Depth 5"
        )
        result = powershell("-Command", command)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["result"]["screen"], "SO302000")

    def test_sales_order_helper_starts_stopped_local_service(self):
        ensure = ROOT / "skills/run-api-requests/scripts/Ensure-SalesOrderService.ps1"
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]

        with tempfile.TemporaryDirectory(prefix="erp-service-start-") as folder:
            root = Path(folder)
            project = root / "sales-order-service/src/services/sales-order/sales-order.api/sales-order.api.csproj"
            project.parent.mkdir(parents=True)
            project.write_text("<Project />", encoding="utf-8")
            server = root / "server.py"
            server.write_text(
                "from http.server import BaseHTTPRequestHandler, HTTPServer\n"
                "import os\n"
                "class Handler(BaseHTTPRequestHandler):\n"
                "    def do_GET(self):\n"
                "        self.send_response(200 if self.path == '/health' else 404); self.end_headers()\n"
                "    def log_message(self, *_): pass\n"
                "HTTPServer(('127.0.0.1', int(os.environ['FAKE_SERVER_PORT'])), Handler).handle_request()\n",
                encoding="utf-8",
            )
            fake_bin = root / "bin"
            fake_bin.mkdir()
            (fake_bin / "dotnet.cmd").write_text(
                '@echo off\r\n"%FAKE_PYTHON%" "%FAKE_SERVER_SCRIPT%"\r\n', encoding="utf-8"
            )
            env = os.environ | {
                "PATH": str(fake_bin) + os.pathsep + os.environ["PATH"],
                "FAKE_PYTHON": sys.executable,
                "FAKE_SERVER_SCRIPT": str(server),
                "FAKE_SERVER_PORT": str(port),
            }
            result = powershell(
                "-File", ensure,
                "-ServerUrl", f"http://127.0.0.1:{port}",
                "-SalesOrderRepository", root / "sales-order-service",
                "-TimeoutSeconds", "15",
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout[result.stdout.index("{"):])
            self.assertEqual(payload["status"], "started")
            self.assertIsInstance(payload["processId"], int)

    def test_initializer_creates_template_without_overwriting(self):
        script = ROOT / "scripts/Initialize-ErpDevTools.ps1"
        with tempfile.TemporaryDirectory(prefix="erp-config-") as folder:
            destination = Path(folder) / "profiles.json"
            result = powershell("-File", script, "-Destination", destination, "-AsJson")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(destination.read_text())
            self.assertEqual(payload["version"], 1)
            self.assertTrue(payload["profiles"]["internal"]["tokenUrl"].startswith("<"))
            second = powershell("-File", script, "-Destination", destination)
            self.assertNotEqual(second.returncode, 0)

    def test_setup_reports_configuration_presence_without_values(self):
        script = ROOT / "scripts/Test-Setup.ps1"
        result = powershell("-File", script, "-CheckConfiguration")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout[result.stdout.index("{"):])
        self.assertTrue(payload["configuration"]["valid"])
        self.assertNotIn("test-client", result.stdout)
        self.assertNotIn("test-tenant", result.stdout)

    def test_session_names_are_stable_and_distinct_across_workspaces(self):
        common = ROOT / "skills/erp-ui/scripts/ErpUi.Common.ps1"
        command = ". '" + str(common).replace("'", "''") + "'; Get-ErpUiDefaultSessionName"
        with tempfile.TemporaryDirectory(prefix="erp-workspaces-") as folder:
            first, second = Path(folder)/"one", Path(folder)/"two"
            first.mkdir(); second.mkdir()
            values = [powershell("-Command", command, cwd=directory) for directory in [first, first, second]]
            for result in values:
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(values[0].stdout, values[1].stdout)
            self.assertNotEqual(values[0].stdout, values[2].stdout)

    def test_launchers_work_when_relocated_and_preserve_errors(self):
        with tempfile.TemporaryDirectory(prefix="erp plugin relocation ") as folder:
            relocated = Path(folder)/"erp-dev-tools"
            shutil.copytree(ROOT, relocated, ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv", "artifacts"))
            for relative in ["skills/run-api-requests/scripts/Invoke-RunApi.ps1", "skills/sql-server-capture/scripts/Invoke-SqlCapture.ps1"]:
                script = relocated / relative
                result = powershell("-File", script, "--help", cwd=folder)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout)
                failure = powershell("-File", script, "invalid-package-test-command", cwd=folder)
                self.assertNotEqual(failure.returncode, 0)
            capture = relocated / "skills/sql-server-capture/scripts"
            result = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0,sys.argv[1]); import sql_capture; print(sql_capture.resolve_api_script_path(None))", str(capture)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(Path(result.stdout.strip()).resolve(), (relocated / "skills/run-api-requests/scripts/run_api_requests.py").resolve())


if __name__ == "__main__":
    unittest.main()
