from __future__ import annotations

import json
from pathlib import Path

import pytest

from patient_api import __version__
from patient_api.cli import _render_table, main


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("STUDENT_ID", "PASSWORD", "DATA_FILE", "BASE_URL", "SET"):
        monkeypatch.delenv(f"PATIENT_API_{name}", raising=False)


def run(capsys: pytest.CaptureFixture[str], sample: Path, *args: str) -> tuple[int, str, str]:
    code = main(["--data-file", str(sample), *args])
    out = capsys.readouterr()
    return code, out.out, out.err


def test_summary(capsys: pytest.CaptureFixture[str], sample_file: Path) -> None:
    code, out, _ = run(capsys, sample_file, "summary")
    assert code == 0
    body = json.loads(out)
    assert body["admittedCount"] + body["dischargedCount"] == 40


def test_get_existing(capsys: pytest.CaptureFixture[str], sample_file: Path) -> None:
    code, out, _ = run(capsys, sample_file, "get", "201")
    assert code == 0
    assert json.loads(out)["id"] == 201


def test_get_unknown_is_exit_1(capsys: pytest.CaptureFixture[str], sample_file: Path) -> None:
    code, out, err = run(capsys, sample_file, "get", "99999")
    assert (code, out) == (1, "")
    assert "not found" in err


def test_get_invalid_id_is_exit_1(capsys: pytest.CaptureFixture[str], sample_file: Path) -> None:
    code, _, err = run(capsys, sample_file, "get", "abc")
    assert code == 1
    assert "Invalid ID format" in err


@pytest.mark.parametrize("command", ["highest-bill", "longest-stay", "departments"])
def test_json_commands_emit_valid_json(
    capsys: pytest.CaptureFixture[str], sample_file: Path, command: str
) -> None:
    code, out, _ = run(capsys, sample_file, command)
    assert code == 0
    json.loads(out)


def test_filter_table_output(capsys: pytest.CaptureFixture[str], sample_file: Path) -> None:
    code, out, _ = run(capsys, sample_file, "filter", "cardiology", "--format", "table")
    assert code == 0
    header, rule, *rows = out.splitlines()
    assert header.split() == ["id", "name", "department", "doctor"] or "department" in header
    assert set(rule.replace(" ", "")) == {"-"}
    assert rows


def test_format_flag_works_before_the_subcommand(
    capsys: pytest.CaptureFixture[str], sample_file: Path
) -> None:
    code, out, _ = run(capsys, sample_file, "--format", "table", "departments")
    assert code == 0
    assert "patientCount" in out


def test_missing_credentials_is_exit_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["summary"]) == 2
    assert "PATIENT_API_STUDENT_ID" in capsys.readouterr().err


def test_data_file_from_environment(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, sample_file: Path
) -> None:
    monkeypatch.setenv("PATIENT_API_DATA_FILE", str(sample_file))
    assert main(["summary"]) == 0


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as info:
        main(["--version"])
    assert info.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_render_table_empty() -> None:
    assert _render_table([]) == "(no results)"


def test_render_table_aligns_columns() -> None:
    table = _render_table([{"a": 1, "b": "long value"}, {"a": 22, "b": "x"}])
    lines = table.splitlines()
    assert len({len(line.rstrip()) for line in lines[:1]}) == 1
    assert lines[2].startswith("1 ")


def test_serve_starts_uvicorn_with_an_app(
    monkeypatch: pytest.MonkeyPatch, sample_file: Path
) -> None:
    import uvicorn

    captured: dict[str, object] = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: captured.update(app=app, **kw))
    assert main(["--data-file", str(sample_file), "serve", "--port", "9001"]) == 0
    assert captured["port"] == 9001
    assert captured["host"] == "127.0.0.1"
    assert captured["app"] is not None


def test_serve_reload_uses_factory_import_string(monkeypatch: pytest.MonkeyPatch) -> None:
    import uvicorn

    captured: dict[str, object] = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: captured.update(app=app, **kw))
    assert main(["serve", "--reload"]) == 0
    assert captured["app"] == "patient_api.api:create_app"
    assert captured["factory"] is True
