"""
바 캐릭터가 다른 창 제목 줄에 걸터앉을 때 쓰는 창 찾기 (윈도우 API, `buddy.py` 가 씀).

- `title_bar_at(sx, sy)`: 화면 (sx, sy)(캐릭터 발) 바로 아래 맨 앞 창의 위 테두리 근처면 (창, 네모).
- `rect_of(hwnd)`: 그 창이 아직 보이면 네모, 닫혔거나 내려갔거나 숨었으면 None.
- `screen_box(widget)`: 가상 화면(모니터 전체) 네모. 던졌을 때 튕길 벽.

★ 모두 몇 ms 안에 끝나는 호출이다(창 수십 개 훑기). 실패하면 None 이라 위젯이 멈추지 않는다.
★ 이 앱은 배율 인식을 안 켜서 Win32 좌표도 Tk 와 같은 논리 픽셀로 받는다(GetWindowRect).
"""

from __future__ import annotations

import os
import sys

TOP_ABOVE = 16   # 발이 창 위 테두리보다 이만큼 위여도 걸터앉는다
TOP_BELOW = 40   # 발이 창 위 테두리 아래 이만큼(제목 줄 높이쯤)까지
SIDE_IN = 12     # 창 양 끝에서 이만큼 안쪽이어야 앉는다
SKIP_CLASS = {"Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Progman", "WorkerW"}


def _user32():
    if sys.platform != "win32":
        return None
    import ctypes

    return ctypes.windll.user32


def _rect(u, hwnd):
    import ctypes
    from ctypes import wintypes

    r = wintypes.RECT()
    if not u.GetWindowRect(hwnd, ctypes.byref(r)):
        return None
    return r.left, r.top, r.right, r.bottom


def _cloaked(hwnd) -> bool:
    try:
        import ctypes

        v = ctypes.c_int(0)
        ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(v), ctypes.sizeof(v))
        return bool(v.value)
    except Exception:  # noqa: BLE001
        return False


def _usable(u, hwnd, me: int) -> bool:
    import ctypes
    from ctypes import wintypes

    if not u.IsWindowVisible(hwnd) or u.IsIconic(hwnd):
        return False
    pid = wintypes.DWORD()
    u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if pid.value == me:
        return False
    ex = u.GetWindowLongW(hwnd, -20)
    if ex & (0x80 | 0x20):  # 도구 창 · 클릭이 지나가는 덮개 창
        return False
    if u.GetWindowTextLengthW(hwnd) <= 0:
        return False
    buf = ctypes.create_unicode_buffer(64)
    u.GetClassNameW(hwnd, buf, 64)
    if buf.value in SKIP_CLASS:
        return False
    return not _cloaked(hwnd)


def pick(windows, sx: float, sy: float):
    """[(창, 네모)] (맨 앞부터) 에서 발 자리 (sx, sy) 의 창을 고른다. 위 테두리 근처면 (창, 네모), 아니면 None.
    발 자리를 덮는 맨 앞 창이 몸통에 놓인 것이면 그 뒤 창은 안 본다 (가려져 있다)."""
    for hwnd, (l, t, r, b) in windows:
        if r - l < 80 or b - t < 40:
            continue
        if not (l <= sx <= r and t - TOP_ABOVE <= sy <= b):
            continue
        if sy <= t + TOP_BELOW and l + SIDE_IN <= sx <= r - SIDE_IN:
            return hwnd, (l, t, r, b)
        return None
    return None


def title_bar_at(sx: float, sy: float):
    u = _user32()
    if u is None:
        return None
    try:
        import ctypes
        from ctypes import wintypes

        me = os.getpid()
        found: list = []
        proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def each(hwnd, _lp):
            try:
                if _usable(u, hwnd, me):
                    r = _rect(u, hwnd)
                    if r:
                        found.append((hwnd, r))
            except Exception:  # noqa: BLE001
                pass
            return len(found) < 200

        u.EnumWindows(proc(each), 0)
        return pick(found, sx, sy)
    except Exception:  # noqa: BLE001 — 못 찾으면 그냥 앉지 않는다
        return None


def rect_of(hwnd):
    u = _user32()
    if u is None:
        return None
    try:
        if not u.IsWindow(hwnd) or not u.IsWindowVisible(hwnd) or u.IsIconic(hwnd):
            return None
        return _rect(u, hwnd)
    except Exception:  # noqa: BLE001
        return None


def screen_box(widget) -> tuple[float, float, float, float]:
    """가상 화면 네모 (left, top, right, bottom)."""
    u = _user32()
    if u is not None:
        try:
            x, y = u.GetSystemMetrics(76), u.GetSystemMetrics(77)
            w, h = u.GetSystemMetrics(78), u.GetSystemMetrics(79)
            if w > 0 and h > 0:
                return float(x), float(y), float(x + w), float(y + h)
        except Exception:  # noqa: BLE001
            pass
    try:
        return 0.0, 0.0, float(widget.winfo_screenwidth()), float(widget.winfo_screenheight())
    except Exception:  # noqa: BLE001
        return 0.0, 0.0, 1920.0, 1080.0
