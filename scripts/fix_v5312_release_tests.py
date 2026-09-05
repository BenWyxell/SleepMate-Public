from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "tests/test_mobile_ai_push_v417.py",
    "tests/test_o2ring_v532_release_contract.py",
    "tests/test_o2ring_v534_release_contract.py",
    "tests/test_pwa_sleep_shell_v526.py",
    "tests/test_v534_acceptance_matrix.py",
    "tests/test_v535_user_acceptance_matrix.py",
    "tests/test_v537_targeted_fixes.py",
]

for relative in FILES:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    if "5.3.11" not in text:
        raise RuntimeError(f"Nincs 5.3.11 release marker ebben a tesztben: {relative}")
    path.write_text(text.replace("5.3.11", "5.3.12"), encoding="utf-8")

Path(__file__).unlink()
