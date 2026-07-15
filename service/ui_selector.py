"""UI Automation要素セレクタ: コントロールの識別情報の保持・解決・操作を行う。

照合ルール:
- AutomationId優先。Nameは補助（Edit系のNameは入力テキストで変動するため、
  AutomationIdがあるコントロールではNameを記録しない）
- ClassNameは末尾ハッシュがアプリ更新で変わるため記録のみで照合には使わない
- 親ウィンドウはAutomationIdがあればそれで特定し、なければウィンドウ名の部分一致
"""

from _ctypes import COMError
from dataclasses import dataclass
from typing import Any

_SEARCH_DEPTH_ALL = 0xFFFFFFFF


@dataclass
class UiSelector:
    window_automation_id: str = ""
    window_name: str = ""  # 部分一致。window_automation_id指定時は使わない
    control_type: str = ""  # 例: "ButtonControl"
    automation_id: str = ""
    name: str = ""
    class_name: str = ""  # デバッグ表示用
    found_index: int = 1  # 同一条件で複数ヒットしたときの順番(1始まり)

    def has_criteria(self) -> bool:
        return bool(self.automation_id or self.name)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for key in (
            "window_automation_id",
            "window_name",
            "control_type",
            "automation_id",
            "name",
            "class_name",
        ):
            value = getattr(self, key)
            if value:
                data[key] = value
        if self.found_index != 1:
            data["found_index"] = self.found_index
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UiSelector":
        return cls(
            window_automation_id=data.get("window_automation_id", ""),
            window_name=data.get("window_name", ""),
            control_type=data.get("control_type", ""),
            automation_id=data.get("automation_id", ""),
            name=data.get("name", ""),
            class_name=data.get("class_name", ""),
            found_index=int(data.get("found_index", 1)),
        )


def build_selector(
    control_type: str,
    automation_id: str,
    name: str,
    class_name: str,
    window_automation_id: str,
    window_name: str,
) -> UiSelector | None:
    """記録した属性からセレクタを組み立てる。識別子が何もなければNone。"""
    if not automation_id and not name:
        return None
    return UiSelector(
        window_automation_id=window_automation_id,
        window_name="" if window_automation_id else window_name,
        control_type=control_type,
        automation_id=automation_id,
        name="" if automation_id else name,
        class_name=class_name,
    )


def window_matches(window: Any, selector: UiSelector) -> bool:
    if selector.window_automation_id:
        return window.AutomationId == selector.window_automation_id
    if selector.window_name:
        return selector.window_name in window.Name
    return True  # 親ウィンドウ指定なしは全ウィンドウ対象


# --- UIA操作（呼び出しごとにスレッドのCOMを初期化する） ---


def _find_control(selector: UiSelector) -> Any:
    """セレクタに一致するコントロールを返す。COM初期化済みスレッドから呼ぶこと。"""
    import uiautomation

    if not selector.has_criteria():
        return None
    props: dict[str, Any] = {}
    if selector.automation_id:
        props["AutomationId"] = selector.automation_id
    if selector.name:
        props["Name"] = selector.name
    control_type = getattr(uiautomation.ControlType, selector.control_type, None)
    if control_type is not None:
        props["ControlType"] = control_type
    for window in uiautomation.GetRootControl().GetChildren():
        try:
            if not window_matches(window, selector):
                continue
            control = uiautomation.Control(
                searchFromControl=window,
                searchDepth=_SEARCH_DEPTH_ALL,
                foundIndex=selector.found_index,
                **props,
            )
            if control.Exists(maxSearchSeconds=0, searchIntervalSeconds=0):
                return control
        except COMError:
            continue  # 探索中にウィンドウ・要素が消滅した場合は次のウィンドウへ
    return None


def find_clickable_point(selector: UiSelector) -> tuple[int, int] | None:
    """要素を探して中心座標を返す。見つからなければNone（座標フォールバック用）。"""
    import uiautomation

    with uiautomation.UIAutomationInitializerInThread():
        try:
            control = _find_control(selector)
            if control is None or control.IsOffscreen:
                return None
            rect = control.BoundingRectangle
            return (rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2
        except COMError:
            return None  # 発見直後に要素が消滅した場合は座標フォールバックに委ねる


def set_element_text(selector: UiSelector, text: str) -> bool:
    """ValuePatternでテキストを直接書き込む。成功したらTrue。"""
    import uiautomation

    with uiautomation.UIAutomationInitializerInThread():
        try:
            control = _find_control(selector)
            if control is None:
                return False
            pattern = control.GetPattern(uiautomation.PatternId.ValuePattern)
            if pattern is None:
                return False
            pattern.SetValue(text)
            return True
        except COMError:
            return False


def get_element_text(selector: UiSelector) -> str | None:
    """要素のテキストを読み取る。見つからなければNone。"""
    import uiautomation

    with uiautomation.UIAutomationInitializerInThread():
        try:
            control = _find_control(selector)
            if control is None:
                return None
            pattern = control.GetPattern(uiautomation.PatternId.ValuePattern)
            if pattern is not None:
                return pattern.Value
            return control.Name  # ラベル等はNameにテキストが入る
        except COMError:
            return None


# --- 記録用（座標・カーソルからのセレクタ組み立て） ---


def selector_from_point(x: int, y: int) -> UiSelector | None:
    """座標にあるコントロールからセレクタを組み立てる（記録用）。"""
    import uiautomation

    with uiautomation.UIAutomationInitializerInThread():
        return _selector_from_control(uiautomation.ControlFromPoint(x, y))


def selector_from_cursor() -> UiSelector | None:
    """カーソル位置のコントロールからセレクタを組み立てる（要素ピッカー用）。"""
    import uiautomation

    with uiautomation.UIAutomationInitializerInThread():
        return _selector_from_control(uiautomation.ControlFromCursor())


def selector_from_focus() -> UiSelector | None:
    """フォーカス中のコントロールからセレクタを組み立てる（キー入力の記録用）。"""
    import uiautomation

    with uiautomation.UIAutomationInitializerInThread():
        return _selector_from_control(uiautomation.GetFocusedControl())


def rect_from_cursor() -> tuple[int, int, int, int] | None:
    """カーソル位置のコントロールの矩形(left, top, right, bottom)を返す（ハイライト用）。"""
    import uiautomation

    with uiautomation.UIAutomationInitializerInThread():
        control = uiautomation.ControlFromCursor()
        if control is None:
            return None
        rect = control.BoundingRectangle
        return rect.left, rect.top, rect.right, rect.bottom


def _selector_from_control(control: Any) -> UiSelector | None:
    window = _top_level_ancestor(control)
    if control is None or window is None:
        return None
    return build_selector(
        control_type=control.ControlTypeName,
        automation_id=control.AutomationId,
        name=control.Name,
        class_name=control.ClassName,
        window_automation_id=window.AutomationId,
        window_name=window.Name,
    )


def _top_level_ancestor(control: Any) -> Any:
    """コントロールが属するトップレベルウィンドウを返す。"""
    import uiautomation

    if control is None:
        return None
    root = uiautomation.GetRootControl()
    current = control
    parent = current.GetParentControl()
    while parent is not None and not uiautomation.ControlsAreSame(parent, root):
        current = parent
        parent = current.GetParentControl()
    return current if parent is not None else None
