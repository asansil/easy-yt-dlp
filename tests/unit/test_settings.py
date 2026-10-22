import json
from pathlib import Path

from easy_ytdlp.core import paths, settings
from easy_ytdlp.core.settings import Settings


def test_missing_file_gives_defaults() -> None:
    assert settings.load() == Settings()


def test_save_and_load_round_trip() -> None:
    value = Settings(language="es", theme="dark", max_concurrent=4, command_history=["-x URL"])
    value.last_options = {"mode": "audio"}
    settings.save(value)
    assert paths.settings_file().is_file()
    assert settings.load() == value


def test_corrupt_file_gives_defaults() -> None:
    paths.settings_file().parent.mkdir(parents=True)
    paths.settings_file().write_text("{not json", encoding="utf-8")
    assert settings.load() == Settings()
    paths.settings_file().write_text("[1]", encoding="utf-8")
    assert settings.load() == Settings()


def test_invalid_values_are_ignored(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "language": 3,
                "max_concurrent": 99,
                "auto_update_tools": "yes",
                "last_tools_check": 5,
                "first_run_done": True,
                "unknown": "x",
            }
        ),
        encoding="utf-8",
    )
    loaded = settings.load(path)
    assert loaded.language == "system"
    assert loaded.max_concurrent == 8
    assert loaded.auto_update_tools is True
    assert loaded.last_tools_check == 5.0
    assert loaded.first_run_done is True


def test_migrate_sets_current_version() -> None:
    assert settings.migrate({})["schema_version"] == settings.SCHEMA_VERSION
    assert settings.migrate({"schema_version": "x"})["schema_version"] == settings.SCHEMA_VERSION


def test_atomic_write_leaves_no_temp_files(tmp_path: Path) -> None:
    target = tmp_path / "out.json"
    settings.write_json_atomic(target, {"a": 1})
    settings.write_json_atomic(target, {"a": 2})
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 2}
    assert [p.name for p in tmp_path.iterdir()] == ["out.json"]


def test_effective_download_dir() -> None:
    assert Settings().effective_download_dir() == Path.home() / "Downloads"
    assert Settings(download_dir="D:/x").effective_download_dir() == Path("D:/x")
