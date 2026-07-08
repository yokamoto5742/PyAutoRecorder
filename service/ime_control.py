"""前面ウィンドウのIMEをオン/オフ/トグルする（imm32のWM_IME_CONTROL経由）。"""

import ctypes

_WM_IME_CONTROL = 0x0283
_IMC_GETOPENSTATUS = 0x0005
_IMC_SETOPENSTATUS = 0x0006


def _ime_window_handle() -> int:
    user32 = ctypes.windll.user32
    imm32 = ctypes.windll.imm32
    foreground = user32.GetForegroundWindow()
    return imm32.ImmGetDefaultIMEWnd(foreground)


def set_ime(enabled: bool) -> None:
    handle = _ime_window_handle()
    if handle:
        ctypes.windll.user32.SendMessageW(
            handle, _WM_IME_CONTROL, _IMC_SETOPENSTATUS, 1 if enabled else 0
        )


def toggle_ime() -> None:
    handle = _ime_window_handle()
    if handle:
        user32 = ctypes.windll.user32
        status = user32.SendMessageW(handle, _WM_IME_CONTROL, _IMC_GETOPENSTATUS, 0)
        user32.SendMessageW(
            handle, _WM_IME_CONTROL, _IMC_SETOPENSTATUS, 0 if status else 1
        )
