from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def replace_once(relative: str, old: str, new: str) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{relative}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_config() -> None:
    path = ROOT / "config/hz23-service.env"
    path.write_text(
        """AIDEAL_HZ23_SERVICE_NAME=aideal-hz23-observer.service
AIDEAL_SYSTEMD_UNIT_DIR=/etc/systemd/system
: \"${HZ23_DAY_START:=09:30}\"
: \"${HZ23_DAY_END:=21:30}\"
: \"${HZ23_LOOP_SLEEP_MIN:=240}\"
: \"${HZ23_LOOP_SLEEP_MAX:=480}\"
: \"${HZ23_ITEM_SLEEP_MIN:=3}\"
: \"${HZ23_ITEM_SLEEP_MAX:=7}\"
: \"${HZ23_PAGE_SLEEP_MIN:=90}\"
: \"${HZ23_PAGE_SLEEP_MAX:=210}\"
: \"${HZ23_LIMIT:=25}\"
: \"${HZ23_CONSERVATIVE_ITEM_SLEEP_MIN:=4}\"
: \"${HZ23_CONSERVATIVE_ITEM_SLEEP_MAX:=8}\"
: \"${HZ23_CONSERVATIVE_PAGE_SLEEP_MIN:=180}\"
: \"${HZ23_CONSERVATIVE_PAGE_SLEEP_MAX:=300}\"
: \"${HZ23_CONSERVATIVE_LIMIT:=25}\"
""",
        encoding="utf-8",
    )


def patch_mainline() -> None:
    replace_once(
        "scripts/hz23_mainline_refresh.sh",
        'cd "$PROJECT_DIR" || exit 1\n',
        'cd "$PROJECT_DIR" || exit 1\n. config/hz23-service.env\n',
    )
    replacements = {
        'ITEM_MIN="${HZ23_ITEM_SLEEP_MIN:-3}"': 'ITEM_MIN="$HZ23_ITEM_SLEEP_MIN"',
        'ITEM_MAX="${HZ23_ITEM_SLEEP_MAX:-7}"': 'ITEM_MAX="$HZ23_ITEM_SLEEP_MAX"',
        'PAGE_MIN="${HZ23_PAGE_SLEEP_MIN:-90}"': 'PAGE_MIN="$HZ23_PAGE_SLEEP_MIN"',
        'PAGE_MAX="${HZ23_PAGE_SLEEP_MAX:-210}"': 'PAGE_MAX="$HZ23_PAGE_SLEEP_MAX"',
        'LIMIT="${HZ23_LIMIT:-25}"': 'LIMIT="$HZ23_LIMIT"',
        'DAY_START="${HZ23_DAY_START:-09:30}"': 'DAY_START="$HZ23_DAY_START"',
        'DAY_END="${HZ23_DAY_END:-21:30}"': 'DAY_END="$HZ23_DAY_END"',
    }
    for old, new in replacements.items():
        replace_once("scripts/hz23_mainline_refresh.sh", old, new)


def patch_observer() -> None:
    replace_once(
        "scripts/hz23_observation_daemon.sh",
        'cd "$PROJECT_DIR" || exit 1\n',
        'cd "$PROJECT_DIR" || exit 1\n. config/hz23-service.env\n',
    )
    replacements = {
        'DAY_START="${HZ23_DAY_START:-09:30}"': 'DAY_START="$HZ23_DAY_START"',
        'DAY_END="${HZ23_DAY_END:-21:30}"': 'DAY_END="$HZ23_DAY_END"',
        'LOOP_MIN="${HZ23_LOOP_SLEEP_MIN:-240}"': 'LOOP_MIN="$HZ23_LOOP_SLEEP_MIN"',
        'LOOP_MAX="${HZ23_LOOP_SLEEP_MAX:-480}"': 'LOOP_MAX="$HZ23_LOOP_SLEEP_MAX"',
    }
    for old, new in replacements.items():
        replace_once("scripts/hz23_observation_daemon.sh", old, new)


def patch_reload() -> None:
    replace_once(
        "scripts/hz23_safe_reload_observer.sh",
        'cd "${HOME}/projects/aideal-cps-data-lab" || exit 1\n',
        'cd "${HOME}/projects/aideal-cps-data-lab" || exit 1\n. config/hz23-service.env\n',
    )
    replace_once(
        "scripts/hz23_safe_reload_observer.sh",
        'DAY_START="${HZ23_DAY_START:-09:30}"',
        'DAY_START="$HZ23_DAY_START"',
    )
    replace_once(
        "scripts/hz23_safe_reload_observer.sh",
        'DAY_END="${HZ23_DAY_END:-21:30}"',
        'DAY_END="$HZ23_DAY_END"',
    )


def patch_conservative() -> None:
    path = "scripts/hz23_resume_nohup_conservative.sh"
    replace_once(
        path,
        'cd "${HOME}/projects/aideal-cps-data-lab" || exit 1\n\n',
        'cd "${HOME}/projects/aideal-cps-data-lab" || exit 1\n. config/hz23-service.env\n\n',
    )
    old = """export HZ23_ITEM_SLEEP_MIN="${HZ23_ITEM_SLEEP_MIN:-4}"
export HZ23_ITEM_SLEEP_MAX="${HZ23_ITEM_SLEEP_MAX:-8}"
export HZ23_PAGE_SLEEP_MIN="${HZ23_PAGE_SLEEP_MIN:-180}"
export HZ23_PAGE_SLEEP_MAX="${HZ23_PAGE_SLEEP_MAX:-300}"
export HZ23_LIMIT="${HZ23_LIMIT:-25}"
"""
    new = """export HZ23_ITEM_SLEEP_MIN="$HZ23_CONSERVATIVE_ITEM_SLEEP_MIN"
export HZ23_ITEM_SLEEP_MAX="$HZ23_CONSERVATIVE_ITEM_SLEEP_MAX"
export HZ23_PAGE_SLEEP_MIN="$HZ23_CONSERVATIVE_PAGE_SLEEP_MIN"
export HZ23_PAGE_SLEEP_MAX="$HZ23_CONSERVATIVE_PAGE_SLEEP_MAX"
export HZ23_LIMIT="$HZ23_CONSERVATIVE_LIMIT"
"""
    replace_once(path, old, new)


def patch_audit() -> None:
    replace_once(
        "config/engineering-audit.toml",
        '".cfg", ".json"]',
        '".cfg", ".json", ".env"]',
    )
    replace_once(
        "src/aideal_cps_data_lab/engineering_audit/service.py",
        'if path.suffix == ".sh":',
        'if path.suffix in {".sh", ".env"}:',
    )
    test_path = "tests/test_engineering_audit_duplicates.py"
    replace_once(test_path, '".json"],', '".json", ".env"],')
    marker = "\n\nclass DefaultSourceTests(unittest.TestCase):\n"
    block = """

class EnvironmentDefaultTests(unittest.TestCase):
    def test_environment_defaults_are_scanned(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "one.env").write_text('PORT=${PORT:-1}\\n', encoding="utf-8")
            (root / "two.env").write_text('PORT=${PORT:-2}\\n', encoding="utf-8")
            report = run_audit(root, SETTINGS)
        self.assertEqual(1, report["duplicate_default_source_count"])
"""
    replace_once(test_path, marker, block + marker)


def main() -> int:
    replace_config()
    patch_mainline()
    patch_observer()
    patch_reload()
    patch_conservative()
    patch_audit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
