import pytest

from modules.utils.config_utils import get_from_env
from modules.utils.exceptions import ConfigFieldIsRequired, ConfigFieldWrongType


def test_get_from_env_returns_default(monkeypatch):
    monkeypatch.delenv("TEST_SETTING", raising=False)

    assert get_from_env("TEST_SETTING", "fallback") == "fallback"


def test_get_from_env_converts_integer(monkeypatch):
    monkeypatch.setenv("TEST_SETTING", "42")

    assert get_from_env("TEST_SETTING", value_type=int) == 42


def test_get_from_env_rejects_missing_required_value(monkeypatch):
    monkeypatch.delenv("TEST_SETTING", raising=False)

    with pytest.raises(ConfigFieldIsRequired):
        get_from_env("TEST_SETTING")


def test_get_from_env_rejects_invalid_integer(monkeypatch):
    monkeypatch.setenv("TEST_SETTING", "not-an-int")

    with pytest.raises(ConfigFieldWrongType):
        get_from_env("TEST_SETTING", value_type=int)
