# Backward-compat shim — remove in Phase 6
from src.shared.image_cleaner import *  # noqa: F401,F403
from src.shared.image_cleaner import _add_gaussian_noise  # noqa: F401 — used by tests
