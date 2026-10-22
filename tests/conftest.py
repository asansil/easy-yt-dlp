import io
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_text():
    def read(name: str) -> str:
        return (FIXTURES / name).read_text(encoding="utf-8")

    return read


@pytest.fixture
def fixture_json():
    def read(name: str) -> Any:
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    return read


@pytest.fixture(autouse=True)
def isolated_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the data and tools folders at a temp dir so no test touches real user data."""
    monkeypatch.setenv("EASYYTDLP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("EASYYTDLP_TOOLS_DIR", str(tmp_path / "tools" / "bin"))
    return tmp_path


class FakeResponse(io.BytesIO):
    def __init__(self, data: bytes, url: str) -> None:
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))}
        self.url = url


class FakeWeb:
    """Stand-in for ``urllib.request.urlopen`` that serves bytes from a dictionary."""

    def __init__(self) -> None:
        self.pages: dict[str, bytes] = {}
        self.requests: list[str] = []

    def add(self, url: str, data: bytes | str) -> None:
        self.pages[url] = data.encode() if isinstance(data, str) else data

    def __call__(self, request: urllib.request.Request | str, timeout: float | None = None):
        url = request.full_url if isinstance(request, urllib.request.Request) else request
        self.requests.append(url)
        if url not in self.pages:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)  # type: ignore[arg-type]
        return FakeResponse(self.pages[url], url)


@pytest.fixture
def web(monkeypatch: pytest.MonkeyPatch) -> FakeWeb:
    fake = FakeWeb()
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    return fake
