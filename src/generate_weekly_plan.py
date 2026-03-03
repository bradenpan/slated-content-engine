# Backward-compat shim — remove in Phase 6
from src.pinterest.generate_weekly_plan import *  # noqa: F401,F403

# Private functions not exported by import * — needed by tests
from src.pinterest.generate_weekly_plan import _validate_plan_structure  # noqa: F401
from src.pinterest.generate_weekly_plan import _build_reprompt_context  # noqa: F401

# Shared functions historically importable from this module
from src.shared.content_planner import (  # noqa: F401
    load_strategy_context,
    load_content_memory,
    load_latest_analysis,
    get_current_seasonal_window,
)

if __name__ == "__main__":
    import runpy
    runpy.run_module("src.pinterest.generate_weekly_plan", run_name="__main__", alter_sys=True)
