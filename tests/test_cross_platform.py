"""Cross-platform compatibility tests."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest


class TestDateFormatting:
    def test_day_without_leading_zero(self):
        import datetime as _dt
        today = _dt.date(2026, 3, 5)
        if os.name == "nt":
            formatted = today.strftime("%B %#d, %Y")
        else:
            formatted = today.strftime("%B %-d, %Y")
        assert formatted == "March 5, 2026"


class TestPathHandling:
    def test_path_with_spaces(self):
        p = Path("some dir/sub dir/file.json")
        assert p.name == "file.json"
        assert str(p.parent) == "some dir/sub dir" or str(p.parent) == "some dir\\sub dir"

    def test_home_dir_expansion(self):
        config_dir = Path.home() / ".portfolio_extract"
        assert "~" not in str(config_dir)

    def test_pathlib_works_cross_platform(self):
        p = Path(__file__).parent.parent
        assert p.exists()
        assert (p / "tests").exists()


class TestScheduling:
    def test_bat_file_exists_for_windows(self):
        bat = Path(__file__).parent.parent / "run_pipeline.bat"
        if os.name == "nt":
            assert bat.exists(), "run_pipeline.bat missing (needed for Windows Task Scheduler)"
        else:
            pytest.skip("Not on Windows")

    def test_schedule_xml_exists_for_windows(self):
        xml = Path(__file__).parent.parent / "schedule_task.xml"
        if os.name == "nt":
            assert xml.exists(), "schedule_task.xml missing (needed for Windows Task Scheduler)"
        else:
            pytest.skip("Not on Windows")
