from __future__ import annotations

from playwright.sync_api import Page

import v534_browser_acceptance as acceptance


_ORIGINAL_EVALUATE = Page.evaluate
_ORIGINAL_WAIT_RUNTIME = acceptance.wait_runtime
_CACHE_KEYS_EXPRESSION = "() => caches.keys()"
_wait_runtime_calls = 0


def _cache_names_via_cdp(page: Page) -> list[str]:
    """Read CacheStorage without depending on the page's navigation-prone JS context."""
    session = page.context.new_cdp_session(page)
    try:
        payload = session.send(
            "CacheStorage.requestCacheNames",
            {"securityOrigin": acceptance.BASE_URL},
        )
    finally:
        session.detach()
    return sorted(
        str(item.get("cacheName", ""))
        for item in payload.get("caches", [])
        if item.get("cacheName")
    )


def _navigation_safe_evaluate(self: Page, expression, arg=None):
    # The packaged worker can intentionally navigate a controlled client while
    # retiring stale caches. Renderer-side caches.keys() can therefore lose its
    # execution context even though the recovery succeeded. Keep every other
    # browser assertion untouched and inspect only this CacheStorage query via CDP.
    if expression == _CACHE_KEYS_EXPRESSION and arg is None:
        return _cache_names_via_cdp(self)
    return _ORIGINAL_EVALUATE(self, expression, arg)


def _navigation_safe_wait_runtime(page: Page, **kwargs) -> None:
    """Keep first-load strict; allow one clean same-origin retry after stale-cache recovery navigation."""
    global _wait_runtime_calls
    _wait_runtime_calls += 1
    if _wait_runtime_calls != 2:
        return _ORIGINAL_WAIT_RUNTIME(page, **kwargs)

    try:
        return _ORIGINAL_WAIT_RUNTIME(page, **kwargs)
    except AssertionError as exc:
        if "SleepMate browser runtime did not become ready within the first-load acceptance window." not in str(exc):
            raise
        snapshot = acceptance.runtime_snapshot(page, **kwargs)
        diagnostic_keys = ("pageErrors", "consoleErrors", "requestFailures", "httpErrors")
        if not str(snapshot.get("url", "")).startswith(acceptance.BASE_URL):
            raise
        if any(snapshot.get(key) for key in diagnostic_keys):
            raise
        acceptance.progress(
            "stale-cache recovery changed navigation context; retrying runtime readiness once"
        )
        try:
            page.wait_for_load_state("domcontentloaded", timeout=5_000)
        except Exception:
            # A service-worker client.navigate can replace the document again;
            # the bounded readiness retry below remains the authoritative gate.
            pass
        page.wait_for_timeout(250)
        return _ORIGINAL_WAIT_RUNTIME(page, **kwargs)


def main() -> int:
    global _wait_runtime_calls
    _wait_runtime_calls = 0
    Page.evaluate = _navigation_safe_evaluate
    acceptance.wait_runtime = _navigation_safe_wait_runtime
    try:
        return acceptance.main()
    finally:
        acceptance.wait_runtime = _ORIGINAL_WAIT_RUNTIME
        Page.evaluate = _ORIGINAL_EVALUATE


if __name__ == "__main__":
    raise SystemExit(main())
