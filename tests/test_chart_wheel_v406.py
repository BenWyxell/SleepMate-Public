from pathlib import Path

root = Path(__file__).resolve().parents[1]
js = (root / "web" / "app-core.js").read_text(encoding="utf-8")
compact = "".join(js.split())
assert "function panHeroWithWheel" in js
assert "addEventListener('wheel'" in js
assert "{passive:false}" in compact
assert "x<pr.l||x>pr.l+pr.w||y<pr.t||y>pr.t+pr.h" in compact
assert "span>=fullSpan-1000" in compact
assert "scheduleWheelSignalReload" in js
assert "constshift=span*.08*strength" in compact
print("PASS: v4.0.6 hero-chart wheel horizontal pan is plot-only and debounced")
