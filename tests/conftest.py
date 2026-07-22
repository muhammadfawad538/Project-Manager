# Line ending: LF
# Encoding: UTF-8
"""
conftest.py — allow pmagent.main import despite crewai 1.x SQLite
storage opening a DB file.  We swap the backing class with an in-memory
no-op before pmagent is loaded.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

try:
    from unittest.mock import MagicMock
    import crewai.utilities.task_output_storage_handler as tosh_mod
    import crewai.memory.storage.kickoff_task_outputs_storage as kos_mod

    # A storage class whose __init__ succeeds without touching SQLite
    _MockStorage = type(
        "MockKickoffStorage",
        (),
        {
            "__init__": lambda self, *a, **kw: None,
            "_initialize_db": lambda self: None,
            "save": lambda self, *a, **kw: None,
            "get_all": lambda self: [],
        },
    )

    # Patch at the module level so the handler sees our mock
    kos_mod.KickoffTaskOutputsSQLiteStorage = _MockStorage
    tosh_mod.KickoffTaskOutputsSQLiteStorage = _MockStorage
except Exception:
    pass
