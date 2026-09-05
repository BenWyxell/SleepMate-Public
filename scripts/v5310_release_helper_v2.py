from pathlib import Path

helper = Path(__file__).with_name("v5310_release_helper.py").read_text(encoding="utf-8")
helper = helper.replace(
    'tests/test_v534_regressions.py',
    'tests/test_o2ring_v534_release_contract.py',
)
exec(compile(helper, "v5310_release_helper.py", "exec"), {"__name__": "__main__", "__file__": str(Path(__file__).with_name("v5310_release_helper.py"))})
