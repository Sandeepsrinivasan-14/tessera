from __future__ import annotations

from pathlib import Path

import pytest

from patient_api.cli import main
from patient_api.config import Settings, read_dotenv

SECRET = "s3cr3t-value-must-never-be-printed"


class TestReadDotenv:
    def write(self, tmp_path: Path, text: str) -> Path:
        path = tmp_path / ".env"
        path.write_text(text, encoding="utf-8")
        return path

    def test_parses_plain_quoted_and_exported_values(self, tmp_path: Path) -> None:
        path = self.write(
            tmp_path,
            "# comment\n"
            "\n"
            "PATIENT_API_STUDENT_ID=abc\n"
            'PATIENT_API_PASSWORD="quoted value"\n'
            "export PATIENT_API_SET='setB'\n"
            "PATIENT_API_TIMEOUT=30 # inline comment\n",
        )
        assert read_dotenv(path) == {
            "PATIENT_API_STUDENT_ID": "abc",
            "PATIENT_API_PASSWORD": "quoted value",
            "PATIENT_API_SET": "setB",
            "PATIENT_API_TIMEOUT": "30",
        }

    def test_hash_inside_quotes_is_kept(self, tmp_path: Path) -> None:
        assert read_dotenv(self.write(tmp_path, 'K="a # b"\n')) == {"K": "a # b"}

    def test_ignores_malformed_lines(self, tmp_path: Path) -> None:
        path = self.write(tmp_path, "not a pair\n=novalue\n1BAD=x\nGOOD=y\n")
        assert read_dotenv(path) == {"GOOD": "y"}

    def test_missing_or_binary_file_gives_nothing(self, tmp_path: Path) -> None:
        assert read_dotenv(tmp_path / "absent") == {}
        binary = tmp_path / "bin"
        binary.write_bytes(b"\xff\xfe\x00\x01")
        assert read_dotenv(binary) == {}


class TestSettingsFromDotenv:
    @pytest.fixture(autouse=True)
    def _clean_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for name in ("STUDENT_ID", "PASSWORD", "DATA_FILE", "SET"):
            monkeypatch.delenv(f"PATIENT_API_{name}", raising=False)

    def test_values_come_from_dotenv_in_the_working_directory(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("PATIENT_API_STUDENT_ID=fromfile\nPATIENT_API_PASSWORD=pw\n")
        settings = Settings.from_env()
        assert settings.student_id == "fromfile"
        assert settings.has_credentials

    def test_real_environment_wins_over_dotenv(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".env").write_text("PATIENT_API_STUDENT_ID=fromfile\n")
        monkeypatch.setenv("PATIENT_API_STUDENT_ID", "fromenv")
        assert Settings.from_env().student_id == "fromenv"

    def test_dotenv_can_be_disabled(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("PATIENT_API_STUDENT_ID=fromfile\n")
        assert Settings.from_env(dotenv=None).student_id is None

    def test_explicit_env_dict_ignores_dotenv(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("PATIENT_API_STUDENT_ID=fromfile\n")
        assert Settings.from_env({}).student_id is None

    def test_mode(self, sample_file: Path) -> None:
        assert Settings().mode == "remote"
        assert Settings(data_file=sample_file).mode == "offline"


class TestDoctor:
    @pytest.fixture(autouse=True)
    def _clean_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for name in ("STUDENT_ID", "PASSWORD", "DATA_FILE", "SET"):
            monkeypatch.delenv(f"PATIENT_API_{name}", raising=False)

    def test_offline_mode_is_healthy(
        self, capsys: pytest.CaptureFixture[str], sample_file: Path
    ) -> None:
        assert main(["--data-file", str(sample_file), "doctor"]) == 0
        out = capsys.readouterr().out
        assert "offline" in out and "found" in out and "looks good" in out

    def test_missing_data_file_fails(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        assert main(["--data-file", str(tmp_path / "nope.json"), "doctor"]) == 2
        assert "NOT FOUND" in capsys.readouterr().out

    def test_remote_without_credentials_explains_the_fix(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["doctor"]) == 2
        captured = capsys.readouterr()
        assert "missing" in captured.out
        assert ".env" in captured.err

    def test_never_prints_secret_values(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PATIENT_API_STUDENT_ID", "visible-id-12345")
        monkeypatch.setenv("PATIENT_API_PASSWORD", SECRET)
        assert main(["doctor"]) == 0
        captured = capsys.readouterr()
        assert SECRET not in captured.out + captured.err
        assert "visible-id-12345" not in captured.out + captured.err
        assert "set" in captured.out

    def test_reports_whether_a_dotenv_file_exists(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        (tmp_path / ".env").write_text(f"PATIENT_API_STUDENT_ID=x\nPATIENT_API_PASSWORD={SECRET}\n")
        assert main(["doctor"]) == 0
        out = capsys.readouterr().out
        assert ".env file" in out and "found" in out
        assert SECRET not in out
