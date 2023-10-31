import subprocess
import threading
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
    windows_inspector.dispose()


def test_windows_inspector(windows_inspector: WindowsInspector) -> None:
    from robocorp_code.inspector.windows.robocorp_windows._vendored.uiautomation.uiautomation import (
        SetCursorPos,
    )

    windows = windows_inspector.list_windows()
    for window in windows:
        if window["name"] == "Tkinter Elements Showcase":
            break
    else:
        raise AssertionError("Did not find tkinter window.")

    assert window["pid"]
    assert window["name"]
    windows_inspector.set_window_locator(f"name:{window['name']}")
    ev = threading.Event()

    found_elements = []

    def on_pick(found):
        found_elements.append(found)
        ev.set()

    try:
        windows_inspector.on_pick.register(on_pick)
        tree_elements = windows_inspector.collect_tree(f"control:Button")
        assert len(tree_elements) == 10

        bt = tree_elements[0]
        x, y = bt["xcenter"], bt["ycenter"]

        windows_inspector.start_pick()

        SetCursorPos(x, y)
        ev.wait(5)
        assert found_elements
        found = found_elements[-1][-1]
        assert found["path"] == bt["path"]

        # Should automatically stop the pick and start the highlight
        highlighted = windows_inspector.start_highlight(f"path:{bt['path']}")
        assert [bt["path"]] == highlighted["matched_paths"]

    finally:
        # Stops picking and highlight.
        windows_inspector.reset_to_default_state()
