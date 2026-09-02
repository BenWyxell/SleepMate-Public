from pathlib import Path

p = Path('scripts/v534_browser_acceptance.py')
text = p.read_text(encoding='utf-8')


def rep(old, new):
    global text
    n = text.count(old)
    if n != 1:
        raise SystemExit(f'expected one occurrence, got {n}: {old!r}')
    text = text.replace(old, new, 1)


def repn(old, new, expected):
    global text
    n = text.count(old)
    if n != expected:
        raise SystemExit(f'expected {expected} occurrences, got {n}: {old!r}')
    text = text.replace(old, new)


# The product deliberately formats matched O2Ring medians with hu-HU locale.
# The <strong id=hr> node contains only the numeric median; its surrounding card
# already labels the metric as Pulzus/medián. Keep exact assertions, but assert the
# actual product representation instead of an English-decimal/test-only string.
rep(
    'require(page.locator("#spo2").inner_text().strip() == "96.4%", "daily SpO2 card did not hydrate the matched O2 median")',
    'spo2_daily_text = page.locator("#spo2").inner_text().strip()\n        require(spo2_daily_text == "96,4%", f"daily SpO2 card did not hydrate the matched O2 median: {spo2_daily_text!r}")',
)
rep(
    'require(page.locator("#hr").inner_text().strip() == "64 bpm", "daily pulse card did not hydrate the requested median")',
    'hr_daily_text = page.locator("#hr").inner_text().strip()\n        require(hr_daily_text == "64,0", f"daily pulse card did not hydrate the requested median: {hr_daily_text!r}")',
)
repn(
    'page.wait_for_function("() => document.getElementById(\'spo2\')?.textContent.trim()===\'94.6%\' && document.getElementById(\'hr\')?.textContent.trim()===\'67 bpm\'")',
    'page.wait_for_function("() => document.getElementById(\'spo2\')?.textContent.trim()===\'94,6%\' && document.getElementById(\'hr\')?.textContent.trim()===\'67,0\'")',
    2,
)
rep(
    'page.wait_for_function("() => document.getElementById(\'spo2\')?.textContent.trim()===\'91%\' && document.getElementById(\'hr\')?.textContent.trim()===\'58 bpm\'")',
    'page.wait_for_function("() => document.getElementById(\'spo2\')?.textContent.trim()===\'91%\' && document.getElementById(\'hr\')?.textContent.trim()===\'58\'")',
)
rep(
    'require(page.locator("#hr").inner_text().strip() == "58 bpm", "daily pulse card stayed stale after matched O2 data disappeared")',
    'require(page.locator("#hr").inner_text().strip() == "58", "daily pulse card stayed stale after matched O2 data disappeared")',
)
rep(
    'require(page.locator("#spo2").inner_text().strip() == "94.6%", "daily SpO2 median did not return when matched O2 data returned")',
    'require(page.locator("#spo2").inner_text().strip() == "94,6%", "daily SpO2 median did not return when matched O2 data returned")',
)
rep(
    'require(page.locator("#hr").inner_text().strip() == "67 bpm", "daily pulse median did not return when matched O2 data returned")',
    'require(page.locator("#hr").inner_text().strip() == "67,0", "daily pulse median did not return when matched O2 data returned")',
)

p.write_text(text, encoding='utf-8')
print('locale-correct daily O2 acceptance patch applied')
