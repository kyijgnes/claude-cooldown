"""
끌려 나온 바 캐릭터를 태우는 떠 있는 창 (`Carry`) 과 제자리로 날아오는 길 (`Flight`).

11-20 사용자: 끌어서 납치할 때 바 테두리 안에만 갇혀 답답하다. 그래서 끄는 동안은 캐릭터를
**투명 바탕의 맨 위 작은 창**에 태워 화면 어디로든(모니터 여럿이면 가상 화면 전체) 따라오게 하고,
바 안 제자리는 비운다. 놓으면 그 자리에서 바의 제자리로 곧은 줄을 따라 미끄러지듯 돌아와 다시 바에 선다.
클로디(`claudi.py`)와 팩 캐릭터(`buddy.py`)가 같이 쓴다.

- 창은 테두리 없음(`overrideredirect`) · 맨 위 · 작업표시줄에 안 뜸 · 눌러도 포커스를 안 뺏음.
  바탕은 `KEY` 색을 투명색으로 지정한다(`-transparentcolor`). 반투명 가장자리는 그 색과 섞여
  분홍 테두리가 생기므로 태우는 그림은 알파를 반으로 잘라(`solid`) 쓴다.
- 창은 캐릭터가 그려지던 **캔버스의 자식**으로 만든다. 디자인을 바꾸거나 테마가 바뀌어 캔버스가
  없어지면 같이 없어지고, 앱이 꺼지면 당연히 없어진다. 그래도 남는 일이 없게 `close_all` 도 둔다.
- 좌표는 전부 화면 좌표(이 앱은 배율 인식을 안 켜서 Tk 의 논리 픽셀).
"""

from __future__ import annotations

import math
import sys
import tkinter as tk

KEY = "#ff00fe"  # 투명으로 뚫을 바탕색 (그림에 거의 없는 색)
_open: list["Carry"] = []


def _no_activate(top: tk.Toplevel) -> None:
    """작업표시줄에 안 뜨고 눌러도 포커스를 안 뺏게 (WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        u = ctypes.windll.user32
        top.update_idletasks()  # ★ deiconify 직후엔 바깥 창이 아직 없다 (그러면 안쪽 창에 붙어 헛일)
        hwnd = u.GetAncestor(top.winfo_id(), 2) or top.winfo_id()  # GA_ROOT
        GWL_EXSTYLE, TOOL, NOACT, APPWIN = -20, 0x80, 0x08000000, 0x40000
        style = u.GetWindowLongW(hwnd, GWL_EXSTYLE)
        u.SetWindowLongW(hwnd, GWL_EXSTYLE, (style | TOOL | NOACT) & ~APPWIN)
    except Exception:  # noqa: BLE001 — 꾸밈일 뿐이다. 실패해도 끌기는 된다
        pass


def button_down() -> bool:
    """왼쪽 마우스 단추가 지금 눌려 있나. 놓은 것을 앱이 못 받았을 때(창 전환 등) 알아채려고 쓴다."""
    if sys.platform != "win32":
        return True
    try:
        import ctypes

        return bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)
    except Exception:  # noqa: BLE001
        return True


class Carry:
    """캐릭터를 태운 투명 창 하나. `canvas` 에 그리고 `move` 로 옮긴다.

    `anchor` 는 창 안에서 마우스(또는 날아가는 길)를 따라가는 점이다(팩 캐릭터는 발 가운데,
    클로디는 몸 한가운데)."""

    def __init__(self, master: tk.Misc, w: int, h: int, anchor: tuple[float, float]):
        close_all()  # 한 번에 하나만 뜬다
        self.w, self.h = int(w), int(h)
        self.ax, self.ay = anchor
        self.top = tk.Toplevel(master)
        self.top.withdraw()
        self.top.overrideredirect(True)
        try:
            self.top.attributes("-topmost", True)
            self.top.attributes("-transparentcolor", KEY)
        except tk.TclError:
            pass
        self.top.configure(bg=KEY)
        self.canvas = tk.Canvas(self.top, width=self.w, height=self.h, bg=KEY,
                                highlightthickness=0, bd=0)
        self.canvas.pack()
        self.shown = False
        self.at = (0.0, 0.0)
        _open.append(self)

    def alive(self) -> bool:
        try:
            return bool(self.top.winfo_exists())
        except tk.TclError:
            return False

    def move(self, sx: float, sy: float) -> None:
        """따라가는 점을 화면 (sx, sy) 에 둔다. 처음 옮길 때 창을 띄운다."""
        self.at = (sx, sy)
        if not self.alive():
            return
        x, y = round(sx - self.ax), round(sy - self.ay)
        try:
            self.top.geometry(f"{self.w}x{self.h}+{x}+{y}")
            if not self.shown:
                self.shown = True
                self.top.deiconify()
                _no_activate(self.top)
                self.top.lift()
        except tk.TclError:
            pass

    def on_click(self, cb) -> None:
        """떠 있는 창을 누르면 `cb()` (창 제목 줄에 앉아 있는 캐릭터를 누를 때)."""
        try:
            self.canvas.bind("<Button-1>", lambda _e: cb())
        except tk.TclError:
            pass

    def close(self) -> None:
        if self in _open:
            _open.remove(self)
        try:
            self.top.destroy()
        except tk.TclError:
            pass


def close_all() -> None:
    """떠 있는 창을 다 닫는다 (새로 띄울 때 · 앱이 본체를 다시 지을 때)."""
    for c in list(_open):
        c.close()


def screen_of(canvas: tk.Misc, x: float, y: float) -> tuple[float, float]:
    """캔버스 좌표 → 화면 좌표."""
    return canvas.winfo_rootx() + x, canvas.winfo_rooty() + y


def inside(canvas: tk.Misc, x: float, y: float, pad: float = 0.0) -> bool:
    """캔버스 좌표 (x, y) 가 캔버스(바) 위인가. 놓은 자리가 바 위면 날지 않고 그 자리에 내려앉는다."""
    try:
        w, h = canvas.winfo_width(), canvas.winfo_height()
        if w <= 1:  # 아직 안 그려진 캔버스 (시험) — 정해 둔 크기로
            w, h = int(float(canvas.cget("width"))), int(float(canvas.cget("height")))
    except (tk.TclError, ValueError):
        return False
    return -pad <= x <= w + pad and -pad <= y <= h + pad


def solid(img):
    """반투명 가장자리를 잘라 0 아니면 255 알파로 (투명색 창에 태울 그림)."""
    a = img.getchannel("A").point(lambda v: 255 if v >= 110 else 0)
    out = img.copy()
    out.putalpha(a)
    return out


# 놓은 뒤 제자리로 뛰어 돌아가는 시간 (11-20 넷째: 바 안에서 놓을 때와 밖에서 놓을 때 빠르기가 달랐다.
# 바 안 빠르기(200px 쯤을 1.4초)를 기준으로 한 셈으로 맞추고, 아주 멀어도 RUN_MAX 초 안에 닿는다).
RUN_BASE = 0.5     # 초
RUN_PACE = 220.0   # px/초 (평균. 처음엔 느리고 끝엔 이 두 배쯤)
RUN_MIN, RUN_MAX = 0.8, 2.8


def return_time(dist: float) -> float:
    """제자리까지 `dist` px 를 뛰어가는 시간(초). 바 안·밖 같은 셈."""
    return min(RUN_MAX, max(RUN_MIN, RUN_BASE + abs(dist) / RUN_PACE))


def ease_in(p: float) -> float:
    """처음엔 천천히, 나중엔 빠르게 (11-20 넷째 사용자: 달려갈 때 처음엔 천천히 나중엔 빠르게)."""
    p = min(1.0, max(0.0, p))
    return p * p


class Flight:
    """놓은 자리에서 제자리로 돌아오는 길: **곧은 줄** (11-20 둘째: 포물선은 튀어 보였다).

    `ease="smooth"`(클로디): 천천히 떠나 가운데서 빨라지고 닿을 때 살며시 멎는다(5차 곡선), 0.5~1.1초.
    `ease="in"`(팩 캐릭터, 11-20 넷째): 뛰어 오듯 처음엔 천천히 나중엔 빠르게, 시간은 `return_time`.
    `at(now)` → (x, y, 다 왔나)."""

    def __init__(self, start: tuple[float, float], end: tuple[float, float], now: float,
                 ease: str = "smooth"):
        self.sx, self.sy = start
        self.ex, self.ey = end
        dist = math.hypot(self.ex - self.sx, self.ey - self.sy)
        self.t0 = now
        self.ease = ease
        if ease == "in":
            self.dur = return_time(dist)
        else:
            self.dur = min(1.1, max(0.5, 0.4 + dist / 1600))

    def progress(self, now: float) -> float:
        return min(1.0, max(0.0, (now - self.t0) / self.dur))

    def at(self, now: float) -> tuple[float, float, bool]:
        p = self.progress(now)
        e = ease_in(p) if self.ease == "in" else p * p * p * (p * (6 * p - 15) + 10)
        x = self.sx + (self.ex - self.sx) * e
        y = self.sy + (self.ey - self.sy) * e
        return x, y, p >= 1.0
