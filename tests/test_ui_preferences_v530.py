import pytest

from cpap.ui_preferences_v530 import PWA_NAV_DEFAULT, _normalize_nav


def test_default_bottom_nav_preserves_v5220_five_item_layout():
    assert _normalize_nav(None) == PWA_NAV_DEFAULT
    assert PWA_NAV_DEFAULT == ["dashboard", "sessions", "charts", "ai", "more"]


def test_bottom_nav_preserves_selected_order_and_deduplicates():
    assert _normalize_nav(["settings", "dashboard", "settings", "reports"]) == [
        "settings", "dashboard", "reports"
    ]


def test_bottom_nav_allows_six_items():
    items = ["dashboard", "sessions", "charts", "ai", "reports", "settings"]
    assert _normalize_nav(items) == items


def test_bottom_nav_rejects_more_than_six():
    with pytest.raises(ValueError):
        _normalize_nav(["dashboard", "sessions", "charts", "ai", "reports", "settings", "faq"])


def test_bottom_nav_rejects_empty_and_unknown():
    with pytest.raises(ValueError):
        _normalize_nav([])
    with pytest.raises(ValueError):
        _normalize_nav(["dashboard", "not-a-real-page"])
