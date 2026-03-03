# Backward-compat shim — remove in Phase 6
from src.pinterest.generate_pin_content import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("src.pinterest.generate_pin_content", run_name="__main__", alter_sys=True)
