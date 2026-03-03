# Backward-compat shim — remove in Phase 6
from src.shared.content_memory import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("src.shared.content_memory", run_name="__main__", alter_sys=True)
