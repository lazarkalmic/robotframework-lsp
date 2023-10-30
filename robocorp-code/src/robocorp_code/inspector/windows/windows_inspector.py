import typing
from typing import Any, Callable, List, Literal, Tuple, TypedDict

from robocorp_ls_core.callbacks import Callback


class ControlLocatorInfoTypedDict(TypedDict):
    control: str
    class_name: str  # Referenced as 'class' in the locator
    name: str
    automation_id: str
    handle: int
    left: int
    right: int
    top: int
    bottom: int
    width: int
    height: int


class WindowLocatorInfoTypedDict(TypedDict):
    # Same as control
    control: str
    class_name: str  # Referenced as 'class' in the locator
    name: str
    automation_id: str
    handle: int
    left: int
    right: int
    top: int
    bottom: int
    width: int
    height: int

    # Additional
    pid: int
    executable: str


class TreeNodeTypedDict(TypedDict):
    data: ControlLocatorInfoTypedDict
    children: List["TreeNodeTypedDict"]


class IOnPickCallback(typing.Protocol):
    def __call__(self, locator_info_tree: Tuple[ControlLocatorInfoTypedDict]):
        """
        Args:
            locator_info_tree: This will provide the structure from parent to
            child containing the nodes to make the pick (i.e.: the first element
            is the first element inside the window and the last element is
            the leaf element picked).
        """

    def register(
        self, callback: Callable[[Tuple[ControlLocatorInfoTypedDict]], Any]
    ) -> None:
        pass

    def unregister(
        self, callback: Callable[[Tuple[ControlLocatorInfoTypedDict]], Any]
    ) -> None:
        pass


class WindowsInspector:
    def __init__(self) -> None:
        # Called as: self.on_pick([ControlLocatorInfoTypedDict])
        self.on_pick: IOnPickCallback = Callback()

    def start_pick(self, window_locator: str) -> None:
        """
        Starts picking so that when the cursor is hovered over an item of the
        UI the `on_pick` callback is triggered.

        Args:
            window_locator: The locator of the window which should be picked.

        Raises:
            ElementNotFound if the window matching the given locator wasn't found.
        """

    def stop_pick(self) -> None:
        """
        Stops picking.
        """

    def start_highlight_matches(
        self,
        locator: str,
        search_depth: int = 8,
        search_strategy: Literal["siblings", "all"] = "all",
    ) -> List[TreeNodeTypedDict]:
        """
        Starts highlighting the matches given by the locator specified.

        Args:
            locator: The locator whose matches should be highlighted.

        Returns:
            The matches found as a tree hierarchy. Note that while picking
            will only give a single tree path, this needs an actual tree structure
            as siblings may be found.

            Note: there's no root element, the first level children of the
            window or element are directly given.
        """
        return []

    def stop_highlight_matches(self) -> None:
        """
        Stops highlighting matches.
        """

    def list_windows(self) -> List[WindowLocatorInfoTypedDict]:
        return []
