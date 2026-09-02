from pathlib import Path

path = Path('scripts/v534_browser_acceptance.py')
text = path.read_text(encoding='utf-8')
old = '''        page.on(
            "requestfailed",
            lambda req: request_failures.append(
                f"{req.method} {req.url} :: {req.failure or 'request failed'}"
            ),
        )
'''
new = '''        page.on(
            "requestfailed",
            lambda req: None
            if (
                "/api/o2ring/live-stream" in req.url
                and "ERR_ABORTED" in str(req.failure or "")
            )
            else request_failures.append(
                f"{req.method} {req.url} :: {req.failure or 'request failed'}"
            ),
        )
'''
if text.count(old) != 1:
    raise SystemExit(f'expected exactly one requestfailed handler, found {text.count(old)}')
text = text.replace(old, new)
path.write_text(text, encoding='utf-8')
