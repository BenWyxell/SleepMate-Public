from pathlib import Path

path = Path('scripts/v534_browser_acceptance.py')
text = path.read_text(encoding='utf-8')

old_hover = '''def hover_canvas(page: Page, canvas_id: str, expected_labels: tuple[str, ...]) -> str:
    canvas = page.locator(f"#{canvas_id}")
    box = canvas.bounding_box()
'''
new_hover = '''def hover_canvas(page: Page, canvas_id: str, expected_labels: tuple[str, ...]) -> str:
    canvas = page.locator(f"#{canvas_id}")
    canvas.scroll_into_view_if_needed()
    page.wait_for_timeout(60)
    box = canvas.bounding_box()
'''
if text.count(old_hover) != 1:
    raise SystemExit(f'hover helper target count: {text.count(old_hover)}')
text = text.replace(old_hover, new_hover, 1)

old_zoom = '''def zoom_canvas(page: Page, canvas_id: str) -> tuple[list[float], list[float]]:
    canvas = page.locator(f"#{canvas_id}")
    box = canvas.bounding_box()
'''
new_zoom = '''def zoom_canvas(page: Page, canvas_id: str) -> tuple[list[float], list[float]]:
    canvas = page.locator(f"#{canvas_id}")
    canvas.scroll_into_view_if_needed()
    page.wait_for_timeout(60)
    box = canvas.bounding_box()
'''
if text.count(old_zoom) != 1:
    raise SystemExit(f'zoom helper target count: {text.count(old_zoom)}')
text = text.replace(old_zoom, new_zoom, 1)

path.write_text(text, encoding='utf-8')
