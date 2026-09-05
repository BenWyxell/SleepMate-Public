from __future__ import annotations

from pathlib import Path

from cpap.update_resilience_v525 import _is_dns_error, _is_transient_network_error


ROOT = Path(__file__).resolve().parents[1]


def test_windows_dns_11001_is_transient():
    exc = RuntimeError("A GitHub nem érhető el: <urlopen error [Errno 11001] getaddrinfo failed>")
    assert _is_transient_network_error(exc)
    assert _is_dns_error(exc)


def test_authentication_failure_is_not_hidden_as_network_outage():
    exc = RuntimeError("GitHub elérés sikertelen (HTTP 401). Ellenőrizd a GitHub tokent.")
    assert not _is_transient_network_error(exc)
    assert not _is_dns_error(exc)


def test_transient_failure_clears_persistent_red_error_but_keeps_diagnostics():
    text = (ROOT / "cpap" / "update_resilience_v525.py").read_text(encoding="utf-8")
    assert "last_error=None" in text
    assert "last_transient_update_error=str(exc)" in text
    assert '"transient": True' in text
    assert "time.sleep(0.65)" in text


def test_core_package_installs_resilience_patch_before_app_imports_updater():
    text = (ROOT / "cpap" / "__init__.py").read_text(encoding="utf-8")
    assert "install_update_resilience_v525" in text
    assert "install_update_resilience_v525()" in text
