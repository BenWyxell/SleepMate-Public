from __future__ import annotations

from playwright.sync_api import Page

import v534_browser_acceptance as acceptance


_ORIGINAL_EVALUATE = Page.evaluate
_CACHE_KEYS_EXPRESSION = "() => caches.keys()"


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


def main() -> int:
    Page.evaluate = _navigation_safe_evaluate
    try:
        return acceptance.main()
    finally:
        Page.evaluate = _ORIGINAL_EVALUATE


if __name__ == "__main__":
    raise SystemExit(main())
