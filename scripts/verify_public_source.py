from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TEXT_EXTS = {
    ".py", ".pyw", ".js", ".mjs", ".cjs", ".html", ".htm", ".css", ".json",
    ".yml", ".yaml", ".toml", ".ini", ".cfg", ".conf", ".txt", ".md", ".rst",
    ".ps1", ".bat", ".cmd", ".vbs", ".iss", ".xml", ".csv", ".tsv", ".env",
    ".sh", ".webmanifest"
}

FORBIDDEN = [
    ("local-user-path", re.compile(r"(?i)\b[A-Z]:[\\/]+Users[\\/]+hello(?:[\\/][^\s\"'<>|]*)?")),
    ("github-token", re.compile(r"\b(?:github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9_]{20,})\b")),
    ("groq-key", re.compile(r"\bgsk_[A-Za-z0-9_-]{20,}\b")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")),
    ("google-oauth-secret", re.compile(r"\bGOCSPX-[0-9A-Za-z_-]{15,}\b")),
    ("openai-key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
]

RISKY_FILES = [
    re.compile(r"(^|/)\.env(?:\.|$)", re.I),
    re.compile(r"(^|/)config\.json$", re.I),
    re.compile(r"(^|/)private/", re.I),
    re.compile(r"\.(?:pfx|p12|key|sqlite3?|db|log|edf|cpapbackup)$", re.I),
    re.compile(r"(^|/).*backup.*\.zip$", re.I),
]

REQUIRED = [
    "LICENSE",
    "README.md",
    "PRIVACY.md",
    "SECURITY.md",
    "CODE_SIGNING_POLICY.md",
    "THIRD_PARTY_NOTICES.md",
    "TRADEMARKS.md",
]

errors: list[str] = []

for name in REQUIRED:
    if not (ROOT / name).is_file():
        errors.append(f"missing required file: {name}")

license_text = (ROOT / "LICENSE").read_text(encoding="utf-8", errors="replace") if (ROOT / "LICENSE").is_file() else ""
if "GNU AFFERO GENERAL PUBLIC LICENSE" not in license_text or "Version 3" not in license_text:
    errors.append("LICENSE is not recognizable as GNU AGPL v3")

for path in ROOT.rglob("*"):
    if not path.is_file():
        continue
    rel = path.relative_to(ROOT).as_posix()
    if rel.startswith(".git/") or rel == "scripts/verify_public_source.py":
        continue
    if any(rx.search(rel) for rx in RISKY_FILES):
        errors.append(f"risky tracked filename: {rel}")
    if path.suffix.lower() not in TEXT_EXTS and path.name not in {"LICENSE", ".gitignore"}:
        continue
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        continue
    for kind, rx in FORBIDDEN:
        if rx.search(text):
            errors.append(f"{kind}: {rel}")

# The provided privacy policy intentionally still requires real publisher/contact data.
privacy = (ROOT / "PRIVACY.md").read_text(encoding="utf-8", errors="replace") if (ROOT / "PRIVACY.md").is_file() else ""
placeholders = [
    "[FEJLESZTŐ VAGY KIADÓ NEVE]",
    "[KAPCSOLATI E-MAIL-CÍM]",
    "[LEVELEZÉSI CÍM – HA ALKALMAZANDÓ]",
]
remaining = [p for p in placeholders if p in privacy]
if remaining:
    print("WARNING: PRIVACY.md publication-contact placeholders remain:")
    for p in remaining:
        print(f"  - {p}")
    print("These must be filled accurately before the repository is made public.")

if errors:
    print("PUBLIC SOURCE GATE: FAIL")
    for item in sorted(set(errors)):
        print(f"  - {item}")
    raise SystemExit(1)

print("PUBLIC SOURCE GATE: PASS")
print("No forbidden credential pattern, personal C:\\Users\\hello path or risky tracked data filename was detected.")
if remaining:
    print("Status: source-clean, but privacy contact placeholders are still a publication checklist item.")
