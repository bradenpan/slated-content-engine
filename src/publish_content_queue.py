# Backward-compat shim — remove in Phase 6
from src.pinterest.publish_content_queue import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("src.pinterest.publish_content_queue", run_name="__main__", alter_sys=True)
