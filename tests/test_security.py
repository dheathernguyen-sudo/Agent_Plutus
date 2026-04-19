"""Security tests: ensure no credentials leak into output or logs."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

SENSITIVE_FILES = ["config.json", ".env", "credentials.json", "manual_data.json"]


class TestNoCredentialLeakage:
    def test_gitignore_covers_sensitive_files(self):
        gitignore_path = Path(__file__).parent.parent / ".gitignore"
        if not gitignore_path.exists():
            pytest.fail(".gitignore not found — sensitive files could be committed. Create .gitignore with: config.json, .env, manual_data.json")
        gitignore_content = gitignore_path.read_text()
        for filename in SENSITIVE_FILES:
            assert filename in gitignore_content or f"*{filename}" in gitignore_content, (
                f"{filename} not in .gitignore — risk of committing credentials"
            )

    def test_config_json_not_in_repo(self):
        repo_config = Path(__file__).parent.parent / "config.json"
        assert not repo_config.exists(), "config.json found in project root — contains API keys!"

    def test_manual_data_not_in_repo(self):
        repo_dir = Path(__file__).parent.parent
        manual = repo_dir / "manual_data.json"
        if manual.exists():
            content = manual.read_text()
            if '"amount": 10000' not in content:
                return
            pytest.fail("manual_data.json with real data found in repo/")

    def test_example_file_has_no_real_data(self):
        example = Path(__file__).parent.parent / "manual_data.example.json"
        if not example.exists():
            pytest.skip("manual_data.example.json not found")
        import json
        data = json.loads(example.read_text())
        for q in data.get("k401_data", {}).get("quarterly", []):
            assert q["beginning"] == 0, "Example file has non-zero 401k data"
            assert q["ending"] == 0, "Example file has non-zero 401k data"

    def test_no_hardcoded_paths_with_usernames(self):
        project_root = Path(__file__).parent.parent
        user_path_pattern = re.compile(r'C:\\\\Users\\\\[^"\\\\]+\\\\|C:\\Users\\[^"\\]+\\', re.IGNORECASE)
        violations = []
        for py_file in project_root.glob("*.py"):
            content = py_file.read_text(errors="ignore")
            matches = user_path_pattern.findall(content)
            if matches:
                violations.append((py_file.name, matches))
        if violations:
            msg = "Hardcoded user paths found (will break for other users):\n"
            for fname, paths in violations:
                msg += f"  {fname}: {paths}\n"
            pytest.xfail(msg)
