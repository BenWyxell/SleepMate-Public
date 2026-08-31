from __future__ import annotations

from datetime import datetime
import time

from .maintenance import GitHubUpdateManager


_INSTALLED = False
_ORIGINAL_CHECK = GitHubUpdateManager.check


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _is_transient_network_error(exc: Exception) -> bool:
    text = str(exc or "").lower()
    markers = (
        "getaddrinfo failed",
        "temporary failure in name resolution",
        "name or service not known",
        "nodename nor servname provided",
        "errno 11001",
        "timed out",
        "timeout",
        "connection reset",
        "connection aborted",
        "connection refused",
        "network is unreachable",
        "remote end closed connection",
    )
    return any(marker in text for marker in markers)


def _is_dns_error(exc: Exception) -> bool:
    text = str(exc or "").lower()
    return any(marker in text for marker in (
        "getaddrinfo failed",
        "temporary failure in name resolution",
        "name or service not known",
        "nodename nor servname provided",
        "errno 11001",
    ))


def _friendly_result(manager: GitHubUpdateManager, config: dict, exc: Exception) -> dict:
    # The original checker has already recorded the technical failure. A temporary
    # internet/DNS outage is not a SleepMate application error, so clear the
    # persistent red-error state while preserving the previously known latest
    # version / update_available / release metadata.
    try:
        manager._save_state(
            last_check=_now(),
            last_error=None,
            last_transient_update_error=str(exc),
            last_transient_update_error_at=_now(),
        )
    except Exception:
        pass
    try:
        manager._log(
            "WARN",
            "A GitHub frissítésellenőrzés átmeneti hálózati hiba miatt kimaradt.",
            {"error": str(exc)},
        )
    except Exception:
        pass
    return {
        "ok": False,
        "transient": True,
        **manager.status(config),
        "message": "A GitHub most nem érhető el. A SleepMate ettől tovább működik; a frissítésellenőrzés később újrapróbálható.",
    }


def _resilient_check(self: GitHubUpdateManager, config: dict, force: bool = False) -> dict:
    try:
        return _ORIGINAL_CHECK(self, config, force)
    except Exception as first:
        if not _is_transient_network_error(first):
            raise

        # Windows DNS occasionally returns WSAHOST_NOT_FOUND (11001) for a single
        # lookup while the rest of the network is already usable. One short retry
        # fixes that case without turning an optional update check into a long wait.
        if _is_dns_error(first):
            time.sleep(0.65)
            try:
                return _ORIGINAL_CHECK(self, config, force)
            except Exception as second:
                if not _is_transient_network_error(second):
                    raise
                return _friendly_result(self, config, second)

        return _friendly_result(self, config, first)


def install_update_resilience_v525() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    GitHubUpdateManager.check = _resilient_check
    _INSTALLED = True


__all__ = ["install_update_resilience_v525"]
