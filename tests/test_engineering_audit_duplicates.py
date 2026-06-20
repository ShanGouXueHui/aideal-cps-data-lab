from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

from aideal_cps_data_lab.engineering_audit.configuration_scan import scan_configuration
from aideal_cps_data_lab.engineering_audit.default_sources import (
    duplicate_default_source_findings,
    python_default_sources,
    shell_default_sources,
)
from aideal_cps_data_lab.engineering_audit.python_assignments import assignment_findings
from aideal_cps_data_lab.engineering_audit.service import AUDIT_GATE_CATEGORIES, run_audit
from aideal_cps_data_lab.engineering_audit.shell_scan import scan_shell


SETTINGS = {
    "schema_version": "engineering-audit/v5",
    "large_file_line_limit": 300,
    "long_function_line_limit": 80,
    "duplicate_function_min_lines": 5,
    "repeated_literal_min_length": 8,
    "repeated_literal_min_files": 3,
    "scan_extensions": [".py", ".sh", ".toml", ".ini", ".cfg", ".yaml", ".yml", ".json"],
    "excluded_directories": [".git", "reports", "logs", "data"],
    "configuration_directories": ["config", "configuration"],
    "configuration_extensions": [".json", ".yaml", ".yml", ".toml", ".ini", ".cfg"],
    "ignored_function_names": ["main", "__init__"],
    "hardcoded_name_fragments": ["host", "port", "url", "timeout", "interval", "sleep", "window", "selector", "service", "database", "schema"],
    "historical_path_patterns": [],
    "compatibility_path_patterns": [],
    "support_path_patterns": ["^tests/", "^config/"],
}


def categories(findings):
    return [item.category for item in findings]


class PythonAssignmentTests(unittest.TestCase):
    def test_module_assignment_constant_and_dict_duplicates(self):
        tree = ast.parse(
            "value = 1\nvalue = 2\nPORT = 1\nPORT = 2\nconfig = {'x': 1, 'x': 2}\n"
        )
        found = categories(assignment_findings(tree, Path("sample.py")))
        self.assertIn("duplicate_assignment", found)
        self.assertIn("duplicate_constant_assignment", found)
        self.assertIn("duplicate_config_key", found)

    def test_function_runtime_reassignment_is_allowed(self):
        tree = ast.parse("def work():\n    config = 1\n    config = 2\n")
        self.assertEqual([], assignment_findings(tree, Path("sample.py")))

    def test_class_constant_duplicate_is_blocked(self):
        tree = ast.parse("class Settings:\n    PORT = 1\n    PORT = 2\n")
        self.assertIn(
            "duplicate_constant_assignment",
            categories(assignment_findings(tree, Path("sample.py"))),
        )


class ShellAssignmentTests(unittest.TestCase):
    def _scan(self, text: str):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = Path("sample.sh")
            (root / path).write_text(text, encoding="utf-8")
            return scan_shell(root, path, SETTINGS)[0]

    def test_shell_duplicate_preamble_constant_and_long_function(self):
        body = ["PORT=1", "PORT=2", "work() {"]
        body.extend(f"  value_{index}={index}" for index in range(81))
        body.append("}")
        found = categories(self._scan("\n".join(body) + "\n"))
        self.assertIn("duplicate_constant_assignment", found)
        self.assertIn("long_function", found)
        self.assertNotIn("shell_syntax", found)

    def test_shell_runtime_state_reassignment_is_allowed(self):
        found = categories(self._scan("STATUS=INIT\necho ready\nSTATUS=DONE\n"))
        self.assertNotIn("duplicate_constant_assignment", found)

    def test_command_environment_prefix_is_not_a_declaration(self):
        found = categories(
            self._scan("PYTHONPATH=src python3 -V\nPYTHONPATH=src python3 -V\n")
        )
        self.assertNotIn("duplicate_constant_assignment", found)


class ConfigurationKeyTests(unittest.TestCase):
    def _scan(self, name: str, text: str):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = Path(name)
            (root / path).write_text(text, encoding="utf-8")
            return scan_configuration(root, path)[0]

    def test_toml_duplicate_key(self):
        self.assertIn(
            "duplicate_config_key",
            categories(self._scan("settings.toml", "[app]\nport=1\nport=2\n")),
        )

    def test_ini_duplicate_key(self):
        self.assertIn(
            "duplicate_config_key",
            categories(self._scan("settings.ini", "[app]\nport=1\nport=2\n")),
        )

    def test_yaml_duplicate_key_is_scoped(self):
        findings = self._scan("settings.yaml", "app:\n  port: 1\n  port: 2\nother:\n  port: 3\n")
        self.assertEqual(1, categories(findings).count("duplicate_config_key"))

    def test_yaml_sequence_items_have_distinct_scopes(self):
        text = "steps:\n  - name: one\n    run: echo one\n  - name: two\n    run: echo two\n"
        self.assertNotIn(
            "duplicate_config_key",
            categories(self._scan("workflow.yml", text)),
        )

    def test_yaml_duplicate_within_one_sequence_item_is_blocked(self):
        text = "steps:\n  - name: one\n    run: echo one\n    run: echo two\n"
        findings = self._scan("workflow.yml", text)
        self.assertEqual(1, categories(findings).count("duplicate_config_key"))

    def test_json_duplicate_key_in_same_object(self):
        findings = self._scan("settings.json", '{"app":{"port":1,"port":2},"other":{"port":3}}')
        self.assertEqual(1, categories(findings).count("duplicate_config_key"))


class DefaultSourceTests(unittest.TestCase):
    def test_cross_language_environment_default_is_blocked(self):
        python_tree = ast.parse("import os\nvalue = os.getenv('PORT', '1')\n")
        sources = python_default_sources(python_tree, Path("one.py"))
        sources.extend(shell_default_sources(["PORT=${PORT:-2}"], Path("two.sh")))
        findings = duplicate_default_source_findings(sources)
        self.assertEqual(["duplicate_default_source"], categories(findings))

    def test_cli_defaults_are_scoped_to_each_command(self):
        first = python_default_sources(
            ast.parse("parser.add_argument('--report', default='one')"),
            Path("one.py"),
        )
        second = python_default_sources(
            ast.parse("parser.add_argument('--report', default='two')"),
            Path("two.py"),
        )
        self.assertEqual([], duplicate_default_source_findings(first + second))


class ReportContractTests(unittest.TestCase):
    def test_report_includes_zero_counts_and_global_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "clean.py").write_text("VALUE = object()\n", encoding="utf-8")
            report = run_audit(root, SETTINGS)
        self.assertEqual(report["blocker_count"], report["global_blocker_count"])
        self.assertEqual(report["blocker_count"], report["full_gate_blocker_count"])
        for category in AUDIT_GATE_CATEGORIES:
            self.assertIn(category, report["quality_gate_counts"])
            self.assertIn(f"{category}_count", report)
        self.assertEqual("PASS", report["python_shell_syntax"])


if __name__ == "__main__":
    unittest.main()
