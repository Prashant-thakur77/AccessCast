"""Installed on PYTHONPATH for every worker process when ACCESSCAST_OFFLINE=1 (PLAN §14.6)."""
import os

if os.environ.get("ACCESSCAST_OFFLINE") == "1":
    import importlib.util
    import sys

    _p = os.path.join(os.environ["ACCESSCAST_SRC"], "accesscast", "guard", "network.py")
    _spec = importlib.util.spec_from_file_location("accesscast_offline_guard", _p)
    if _spec is not None and _spec.loader is not None:
        _mod = importlib.util.module_from_spec(_spec)
        sys.modules["accesscast_offline_guard"] = _mod
        _spec.loader.exec_module(_mod)
        _mod.install()
