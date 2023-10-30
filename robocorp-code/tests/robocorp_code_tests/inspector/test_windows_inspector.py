import subprocess
from typing import Iterator

import pytest

from robocorp_code.inspector.windows.windows_inspector import WindowsInspector


@pytest.fixture
def tk_process(datadir) -> Iterator[subprocess.Popen]:
    """
    Note: kills existing tk processes prior to starting.
    """
    import sys

    from robocorp_ls_core.basic import kill_process_and_subprocesses

    from robocorp_code.inspector.windows.robocorp_windows import (
        find_window,
        find_windows,
    )

    # Ensure no tk processes when we start...
    windows_found = list(
        x for x in find_windows() if x.name == "Tkinter Elements Showcase"
    )
    for w in windows_found:
        kill_process_and_subprocesses(w.ui_automation_control.ProcessId)

    f = datadir / "snippet_tk.py"
    assert f.exists()
    popen = subprocess.Popen([sys.executable, str(f)])

    # i.e.: wait for it to be visible
    find_window('name:"Tkinter Elements Showcase"', timeout=20)

    yield popen
    if popen.poll() is None:
        kill_process_and_subprocesses(popen.pid)


@pytest.fixture
def windows_inspector(tk_process) -> Iterator["WindowsInspector"]:
    windows_inspector = WindowsInspector()

    yield windows_inspector


def test_windows_inspector(windows_inspector: WindowsInspector) -> None:
    windows = windows_inspector.list_windows()
    for window in windows:
        if window.name == "Tkinter Elements Showcase":
            break
    else:
        raise AssertionError("Did not find tkinter window.")

    windows_inspector.start_pick('name:"Tkinter Elements Showcase"')
    windows_inspector.start_highlight_matches("type:Button")
