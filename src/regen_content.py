# Backward-compat shim — remove in Phase 6
from src.pinterest.regen_content import *  # noqa: F401,F403
from src.pinterest.regen_content import _regen_item  # noqa: F401 — used by tests

if __name__ == "__main__":
    import runpy
    runpy.run_module("src.pinterest.regen_content", run_name="__main__", alter_sys=True)
