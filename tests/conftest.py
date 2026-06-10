import os

import pytest


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point the index at a temp db for every test."""
    monkeypatch.setenv("PHOTA_DB", str(tmp_path / "index.db"))
    yield


@pytest.fixture
def photo_dir(tmp_path):
    d = tmp_path / "photos"
    d.mkdir()
    return d
