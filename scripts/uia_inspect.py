"""UIA調査ツール: 対象アプリのコントロールがUI Automationで見えるかを確認する。

使い方:
    python scripts/uia_inspect.py
    1. 対象アプリ（電子カルテ等）で調べたいボタンや入力欄にマウスカーソルを合わせる
    2. F8 を押すと、その位置のコントロール情報と親ウィンドウまでの階層を表示する
    3. Esc で終了

判断基準:
    - AutomationId か Name に意味のある値が入っていれば、オブジェクト認識ベースの
      自動化（要素指定でのクリック・テキスト読み書き）が可能
    - どのコントロールも AutomationId/Name が空で、ウィンドウ直下に Pane が
    1枚あるだけなら、そのアプリはUIA非対応（現状の座標・画像認識方式を継続）
"""

import threading

import uiautomation
from pynput import keyboard

_capture = threading.Event()
_quit = threading.Event()


def _on_press(key: keyboard.Key | keyboard.KeyCode | None) -> None:
    if key == keyboard.Key.f8:
        _capture.set()
    elif key == keyboard.Key.esc:
        _quit.set()


def _describe(control: uiautomation.Control) -> str:
    rect = control.BoundingRectangle
    return (
        f"{control.ControlTypeName}  "
        f"AutomationId={control.AutomationId!r}  "
        f"Name={control.Name!r}  "
        f"ClassName={control.ClassName!r}  "
        f"Enabled={control.IsEnabled}  "
        f"Rect=({rect.left},{rect.top})-({rect.right},{rect.bottom})"
    )


def _print_control_under_cursor() -> None:
    control = uiautomation.ControlFromCursor()
    if control is None:
        print("カーソル位置のコントロールを取得できませんでした")
        return
    # カーソル下のコントロールからトップレベルウィンドウまでの祖先を集める
    root = uiautomation.GetRootControl()
    chain: list[uiautomation.Control] = []
    current: uiautomation.Control | None = control
    while current is not None and not uiautomation.ControlsAreSame(current, root):
        chain.append(current)
        if len(chain) >= 30:
            break
        current = current.GetParentControl()
    print("\n" + "=" * 80)
    for depth, item in enumerate(reversed(chain)):
        print("  " * depth + _describe(item))
    print("=" * 80)


def main() -> None:
    print(__doc__)
    listener = keyboard.Listener(on_press=_on_press)
    listener.start()
    try:
        while not _quit.is_set():
            if _capture.wait(timeout=0.1):
                _capture.clear()
                try:
                    _print_control_under_cursor()
                except Exception as e:  # 対象アプリ側の例外は表示して継続する
                    print(f"取得エラー: {e}")
    finally:
        listener.stop()


if __name__ == "__main__":
    main()
