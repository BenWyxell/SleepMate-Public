from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def main() -> int:
    env = os.environ.copy()
    # Simulate the problematic Windows redirected-output encoding. app.py must
    # reconfigure stdout to UTF-8 itself, so U+2192 and Hungarian text survive.
    env["PYTHONIOENCODING"] = "cp1250"
    env.pop("PYTHONUTF8", None)
    code = (
        "import app,sys; "
        "print('Távoli elérés → Beállítások → Távoli elérés'); "
        "print(sys.stdout.encoding)"
    )
    cp = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BASE,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if cp.returncode != 0:
        raise SystemExit(f"UTF-8 startup regression failed: {cp.stderr!r}")
    out = cp.stdout.decode("utf-8")
    assert "Távoli elérés → Beállítások → Távoli elérés" in out
    assert "utf-8" in out.lower()
    print("Windows redirected-stdio UTF-8 regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
