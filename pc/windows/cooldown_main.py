"""
메인 화면: 사용량 세부 + 모든 설정을 한 창에
=============================================
위젯에서 **클로디가 아닌 곳**을 누르거나, 우클릭·트레이 `메인 화면 열기` 로 뜬다(2026-11-12).
옛 우클릭 갈래(사용량·위젯 모양·모닝 스타터·폰 앱·원격·앱 설정)가 전부 여기로 왔다.

생김새는 다른 팝업과 같은 결이다: 테두리 없는 둥근 창 + 왼쪽 액센트 바 + 볼드 제목 + ✕·Esc·드래그.
안쪽은 **왼쪽 탭 줄**(고른 탭은 바탕이 본문과 이어지고 초록 막대가 선다) + 오른쪽 본문.

- 셈은 하지 않는다. 사용량은 `cooldown_core`, 기록은 `cooldown_stats`, 요금은 `cooldown_api`,
  그리기 몸통은 앱의 `_pace_body`·`_stats_body`·`_api_body` 를 그대로 부른다.
- 설정을 바꾸는 것도 앱의 메서드(`toggle_ping`·`switch_skin`·…)를 부를 뿐이다. 여기서 설정 파일을
  직접 쓰지 않는다.
- **팝업과 따로 센다.** `App._close_panels` 는 팝업만 닫으므로 메인 화면에서 폰 연결·
  로그인 팝업을 열어도 메인 화면은 남는다.
- **밖을 누르면 닫기는 설정**(`앱 설정 > 메인 화면 밖을 누르면 닫기`, 끔이 기본, 11-12). 켜면 팝업의
  click_away 와 같은 방식(포커스가 빠져나가면 조금 뒤 확인)으로 닫는다. 메인 화면에서 띄운 팝업으로
  포커스가 간 것은 밖으로 치지 않고, 그 팝업이 닫힐 때 다시 판단한다(`panel_closed`).
- **값이 바뀌면 저절로 다시 그린다.** 1초마다 지금 값의 지문(`_signature`)을 재서 달라졌을 때만
  본문을 다시 짓는다. 트레이에서 바꾼 것·새로 받은 사용량·남은 시간까지 따라온다.
  밝기가 바뀌면 색이 위젯에 박혀 있으므로 창을 통째로 다시 짓는다.
- 툴팁·설명 문단을 넣지 않는다(폴더 규칙). 이름은 하는 일로, 값은 화면에 그대로.
"""

from __future__ import annotations

import time
import tkinter as tk
from datetime import datetime

import cooldown_api
import cooldown_newver
import cooldown_ping
import cooldown_push
import cooldown_remote
import cooldown_selfupdate
import skins
from cooldown_core import LoginRequired, five_due, pace
from skins import thumbs
from skins.base import KR, MARK_W, NUM, P, mark_x, tone

W = 580  # 창 폭 (px)
MIN_H = 380  # 창 최소 높이. 실제 높이는 모든 탭 중 가장 큰 것에 맞춰 한 번 정해 고정한다
NAV_W = 150  # 왼쪽 탭 줄 폭 (가장 긴 탭 이름 `클로드 모닝 스타터` 가 들어가는 만큼)
PAD = 16  # 본문 좌우 여백
TOP_PAD = 10  # 본문 위 여백
BOT_PAD = 12  # 본문 아래 여백
INNER = W - NAV_W - 1 - PAD * 2  # 본문 안쪽 폭 (차트 폭)
AWAY_MS = 150  # 포커스가 빠져나간 뒤 자리 잡을 틈 (밖 클릭 닫기)
REOPEN_MS = 400  # 밖 클릭으로 막 닫혔으면 이 안의 위젯 클릭으로 다시 열지 않는다
WATCH_MS = 1000  # 값이 바뀌었나 보는 주기
GAP = 12  # 위젯과 메인 화면 사이 간격
EDGE = 8  # 작업 영역 가장자리에서 띄우는 여백 (높이를 줄일 때)


def _fits(x: int, y: int, w: int, h: int, work) -> bool:
    return x >= work[0] and y >= work[1] and x + w <= work[2] and y + h <= work[3]


def _overlaps(x: int, y: int, w: int, h: int, r) -> bool:
    return x < r[0] + r[2] and x + w > r[0] and y < r[1] + r[3] and y + h > r[1]


def main_spot(widget, work, size, gap: int = GAP) -> tuple[int, int]:
    """메인 화면이 처음 뜰 왼쪽 위 자리. 화면·창에 기대지 않는 순수 계산(단위 테스트 대상).

    widget = (x, y, 폭, 높이) 위젯 창, work = (왼, 위, 오른, 아래) 위젯이 있는 모니터의 작업 영역
    (작업표시줄 제외), size = (폭, 높이) 메인 화면.
    위젯 바로 옆에 붙인다: 위젯이 오른쪽 절반에 있으면 왼쪽, 왼쪽 절반이면 오른쪽, 아래 절반이면 위,
    위 절반이면 아래. 납작하고 넓은 위젯(작업표시줄 띠 위 슬림 바 등)은 위·아래를 먼저 본다.
    옆 자리가 작업 영역에 안 들어가면 다음 후보로 넘어가고, 어디도 안 되면 위젯과 안 겹치는 쪽으로 가둔다.
    결과는 늘 창 전체가 작업 영역 안(작업 영역이 창보다 작으면 왼쪽 위 맞춤)이다."""
    wx, wy, ww, wh = widget
    left, top, right, bottom = work
    w, h = size
    cx, cy = wx + ww / 2, wy + wh / 2
    side = "left" if cx > (left + right) / 2 else "right"
    vert = "above" if cy > (top + bottom) / 2 else "below"
    order = [side, vert, "right" if side == "left" else "left", "below" if vert == "above" else "above"]
    if ww > wh * 2:
        order = [vert, order[3], side, order[2]]

    def raw(kind):
        if kind == "left":
            return wx - gap - w, wy
        if kind == "right":
            return wx + ww + gap, wy
        if kind == "above":
            return wx, wy - gap - h
        return wx, wy + wh + gap

    def clamp(x, y):
        x = left if w >= right - left else max(left, min(x, right - w))
        y = top if h >= bottom - top else max(top, min(y, bottom - h))
        return x, y

    for kind in order:
        x, y = raw(kind)
        # 붙는 축은 그대로 들어와야 하고, 나란한 축은 작업 영역 안으로 밀어도 된다
        if kind in ("left", "right"):
            if not (x >= left and x + w <= right):
                continue
        elif not (y >= top and y + h <= bottom):
            continue
        x, y = clamp(x, y)
        if _fits(x, y, w, h, work) and not _overlaps(x, y, w, h, widget):
            return x, y
    # 어느 옆자리도 안 맞음: 작업 영역 안에 두되 위젯과 안 겹치는 후보를 먼저 찾는다
    for kind in order:
        x, y = clamp(*raw(kind))
        if not _overlaps(x, y, w, h, widget):
            return x, y
    return clamp(*raw(order[0]))


def work_area_at(x: int, y: int):
    """(x, y) 가 있는 모니터의 작업 영역 (왼, 위, 오른, 아래). 못 구하면 None."""
    try:
        import win32api

        mon = win32api.MonitorFromPoint((int(x), int(y)), 2)  # MONITOR_DEFAULTTONEAREST
        return tuple(win32api.GetMonitorInfo(mon)["Work"])
    except Exception:  # noqa: BLE001
        pass
    try:
        import ctypes
        from ctypes import wintypes

        rect = wintypes.RECT()
        if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
            return rect.left, rect.top, rect.right, rect.bottom
    except Exception:  # noqa: BLE001
        pass
    return None

# (키, 이름). 이름은 메뉴와 같은 말(`Label`)을 쓴다. API 는 기록이 있는 PC 에서만 보인다.
USAGE_TABS = ("usage", "pace", "stats", "api")
# 옛 탭 키 → 지금 탭 (11-13: `일별 사용 기록` 은 `사용 기록` 의 일별로 들어갔다)
OLD_TABS = {"daily": "stats"}


class MainScreen:
    """메인 화면 한 벌. 앱이 하나 들고 있다가 `open()` 으로 띄운다(이미 떠 있으면 앞으로)."""

    def __init__(self, app, m):
        """`m` 은 cooldown_app 모듈 자체(`Label`·`THEMES`·`clamp_to_screen` 등을 거기서 꺼낸다).
        여기서 `import cooldown_app` 을 하면 안 된다: 앱이 `__main__` 으로 돌 때 그 파일을
        **한 번 더** 읽어 맨 위 일(환경 정리 등)이 두 번 돈다."""
        self.app = app
        self.m = m
        self.top: tk.Toplevel | None = None
        self.tab = "usage"
        self._nav: dict[str, tuple[tk.Frame, tk.Frame, tk.Label]] = {}
        self._content: tk.Frame | None = None
        self._sig = None
        self._theme = None
        self._watch_job = None
        self._banner_box: tk.Frame | None = None
        self._canvas: tk.Canvas | None = None
        self._inner: tk.Frame | None = None
        self._bar: tk.Frame | None = None
        self._win = None
        self._h = 0  # 고정 높이 (창을 지을 때 한 번 정함)
        self._away_at = 0.0  # 밖 클릭으로 닫힌 때 (time.monotonic)
        # 모닝 스타터 탭: 고치는 중인 시각([[시, 분], …], None = 저장된 그대로) · 저장 못 한 까닭 ·
        # 이 탭에서 본 실패 (위젯 표시는 내렸어도 탭을 떠나기 전까지 카드에 남긴다)
        self._ping_draft: list | None = None
        self._ping_warn = ""
        self._fail_seen = None

    # -------------------------------------------------- 열고 닫기
    def is_open(self) -> bool:
        try:
            return self.top is not None and bool(self.top.winfo_exists())
        except tk.TclError:
            return False

    def anchor(self) -> tuple[int, int] | None:
        """떠 있으면 왼쪽 위 자리 (앱이 팝업을 이 위에 띄운다)."""
        if not self.is_open():
            return None
        return self.top.winfo_x(), self.top.winfo_y()

    def open(self, tab: str | None = None) -> None:
        tab = OLD_TABS.get(tab, tab)
        if not self.is_open():
            # 새로 열면 사용 기록은 일별부터 (탭을 오가는 동안은 고른 기간이 그대로다)
            self.app._stats_period = self.m.STATS_TABS[0]
            self._ping_draft, self._ping_warn, self._fail_seen = None, "", None
        if tab in self._tab_keys():
            self.tab = tab
        elif self.tab not in self._tab_keys():
            self.tab = "usage"
        if self.is_open():
            self._render()
            self._raise()
            return
        self._build(None)

    def close(self) -> None:
        if self._watch_job is not None:
            try:
                self.app.root.after_cancel(self._watch_job)
            except (tk.TclError, ValueError):
                pass
            self._watch_job = None
        if self.top is not None:
            try:
                self.top.destroy()
            except tk.TclError:
                pass
        self.top = None

    def _raise(self) -> None:
        try:
            self.top.deiconify()
            self.top.lift()
            self.top.focus_force()
        except tk.TclError:
            pass

    # -------------------------------------------------- 밖을 누르면 닫기 (설정)
    def _away_on(self) -> bool:
        return bool(self.app.state.get("main_click_away"))

    def _away_soon(self) -> None:
        """포커스가 빠져나갔다(밖을 눌렀거나, 안에서 다른 칸·팝업으로 옮겼거나).
        팝업의 click_away 와 같이, 포커스가 자리 잡을 틈을 준 뒤 `_away_check` 로 판단한다."""
        if not self._away_on() or not self.is_open():
            return
        try:
            self.top.after(AWAY_MS, self._away_check)
        except tk.TclError:
            pass

    def _ours(self) -> list:
        """밖으로 치지 않는 창: 메인 화면과, 그 위에 띄운 팝업들."""
        return [self.top] + [t for t in self.app._panels if t is not None]

    def _away_check(self) -> None:
        if not self._away_on() or not self.is_open():
            return
        try:
            foc = self.top.focus_displayof()
            here = foc.winfo_toplevel() if foc is not None else None
        except (KeyError, tk.TclError):
            here = None
        if here is not None and here in self._ours():
            return
        if any(self._alive(t) for t in self.app._panels):
            # 메인 화면에서 띄운 팝업이 아직 떠 있다. 그 팝업이 닫힐 때 다시 본다(`panel_closed`)
            return
        self.close_away()

    def close_away(self) -> None:
        """밖을 눌러 닫는다. 그 시각을 남겨 같은 클릭이 다시 열지 않게 한다(`just_closed`)."""
        self._away_at = time.monotonic()
        self.close()

    @staticmethod
    def _alive(t) -> bool:
        try:
            return bool(t.winfo_exists())
        except tk.TclError:
            return False

    def panel_closed(self, panel) -> None:
        """메인 화면 위에 띄운 팝업이 닫혔다. 팝업 안에서 닫았으면(✕·Esc·저장) 포커스를
        메인 화면으로 돌려 두고, 밖을 눌러 닫혔으면 메인 화면도 같은 클릭으로 닫는다."""
        if not self._away_on() or not self.is_open():
            return
        try:
            foc = panel.focus_displayof()
            inside = foc is not None and foc.winfo_toplevel() is panel
        except (KeyError, tk.TclError):
            inside = False
        if inside:
            try:
                self.top.after(1, self._take_focus)
            except tk.TclError:
                pass
        else:
            self._away_soon()

    def _take_focus(self) -> None:
        if self.is_open():
            try:
                self.top.focus_force()
            except tk.TclError:
                pass

    def just_closed(self) -> bool:
        """밖 클릭(위젯을 누름)으로 막 닫혔나. 같은 클릭으로 다시 열지 않으려고."""
        return time.monotonic() - self._away_at < REOPEN_MS / 1000

    # -------------------------------------------------- 창 짓기
    def _tab_keys(self) -> list[str]:
        return [k for k, _n in self._tabs()]

    def _tabs(self) -> list[tuple[str, str]]:
        Label = self.m.Label
        out = [("usage", "사용량"), ("pace", "이번 주 사용 속도"), ("stats", "사용 기록")]
        if cooldown_api.available():
            out.append(("api", "API 사용 요금"))
        out += [
            ("look", Label.LOOK),
            ("ping", Label.PING),
            ("phone", "폰·원격"),
            ("conf", Label.CONF),
        ]
        return out

    def _build(self, spot: tuple[int, int] | None) -> None:
        """창을 새로 짓는다. `spot` 이 있으면 그 자리에(밝기를 바꿔 다시 지을 때)."""
        app = self.app
        top = tk.Toplevel(app.root)
        top.withdraw()
        top.overrideredirect(True)
        top.configure(bg=P.bg)
        top.attributes("-topmost", True)
        self.top = top
        self._theme = app.applied_theme
        top.bind("<Destroy>", lambda e, t=top: self._on_destroy(t) if e.widget is t else None)

        # ---- 머리말: 액센트 바 + 제목 + ✕ (팝업과 같은 결)
        head = tk.Frame(top, bg=P.bg)
        head.pack(fill="x")
        accent = tk.Frame(head, bg=P.green, width=3)
        accent.pack(side="left", fill="y")
        pad = tk.Frame(head, bg=P.bg)
        pad.pack(side="left", fill="x", expand=True, padx=(PAD - 3, PAD), pady=(10, 8))
        title = tk.Label(pad, text="클로드 쿨다운", bg=P.bg, fg=P.title, font=(KR, 11, "bold"))
        title.pack(side="left")
        ver = cooldown_newver.current()
        ver_lbl = tk.Label(pad, text=f"v{ver}" if ver else "", bg=P.bg, fg=P.faint, font=(NUM, 9))
        ver_lbl.pack(side="left", padx=(8, 0), pady=(2, 0))
        close = tk.Label(pad, text="✕", bg=P.bg, fg=P.faint, font=(KR, 11), cursor="hand2")
        close.pack(side="right")
        close.bind("<Button-1>", lambda _e: self.close())
        close.bind("<Enter>", lambda _e: close.config(fg=P.title))
        close.bind("<Leave>", lambda _e: close.config(fg=P.faint))
        app._bind_panel_drag(top, head, pad, title, ver_lbl, accent)
        tk.Frame(top, bg=P.line, height=1).pack(fill="x")

        # ---- 몸통: 왼쪽 탭 줄 | 본문
        body = tk.Frame(top, bg=P.bg)
        body.pack(fill="both", expand=True)
        nav = tk.Frame(body, bg=P.track, width=NAV_W)
        nav.pack(side="left", fill="y")
        nav.pack_propagate(False)
        tk.Frame(body, bg=P.line, width=1).pack(side="left", fill="y")
        self._content = tk.Frame(body, bg=P.bg)
        self._content.pack(side="left", fill="both", expand=True)
        # 위: 띠 줄(있을 때만 서고 본문이 그만큼 줄어든다) / 아래: 넘치면 휠로 넘기는 본문
        self._banner_box = tk.Frame(self._content, bg=P.bg)
        self._banner_box.pack(side="top", fill="x", padx=PAD)
        area = tk.Frame(self._content, bg=P.bg)
        area.pack(side="top", fill="both", expand=True)
        self._canvas = tk.Canvas(area, bg=P.bg, highlightthickness=0, bd=0)
        self._canvas.pack(fill="both", expand=True)
        self._inner = tk.Frame(self._canvas, bg=P.bg)
        self._win = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._bar = tk.Frame(area, bg=P.line, width=4)
        self._canvas.bind("<Configure>", lambda _e: self._fit())
        self._inner.bind("<Configure>", lambda _e: self._fit())
        top.bind("<MouseWheel>", self._wheel)

        self._nav.clear()
        tk.Frame(nav, bg=P.track, height=6).pack(fill="x")
        for key, name in self._tabs():
            if key == "look":  # 읽는 쪽(사용량)과 바꾸는 쪽(설정) 사이 한 줄
                tk.Frame(nav, bg=P.line, height=1).pack(fill="x", padx=14, pady=6)
            self._nav_item(nav, key, name)

        top.bind("<Escape>", lambda _e: self.close())
        top.bind("<FocusOut>", lambda _e: self._away_soon())
        top.bind("<Up>", lambda _e: self._step(-1))
        top.bind("<Down>", lambda _e: self._step(1))

        top.update_idletasks()
        chrome = head.winfo_reqheight() + 1
        saved = self.tab
        need = self._measure()
        self.tab = saved
        work = self._work(spot)
        h = max(MIN_H, chrome + need)
        if work is not None:  # 작은 화면이면 작업 영역에 맞춰 줄이고 본문은 휠로 넘긴다
            h = min(h, max(300, work[3] - work[1] - EDGE * 2))
        self._h = h
        top.geometry(f"{W}x{h}")
        self._render()
        if spot is None:
            spot = self._place(h)
        x, y = self._clamp(spot[0], spot[1], h)
        top.geometry(f"{W}x{h}+{x}+{y}")
        top.deiconify()
        self._round(top)
        try:
            top.focus_force()
        except tk.TclError:
            pass
        self._sig = self._signature()
        self._watch_job = app.root.after(WATCH_MS, self._watch)

    def _on_destroy(self, t: tk.Toplevel) -> None:
        if self.top is t:
            self.top = None

    def _work(self, spot=None):
        """위젯(없으면 spot)이 있는 모니터의 작업 영역."""
        root = self.app.root
        if spot is not None:
            return work_area_at(spot[0], spot[1])
        return work_area_at(root.winfo_x() + root.winfo_width() // 2,
                            root.winfo_y() + root.winfo_height() // 2)

    def _place(self, h: int) -> tuple[int, int]:
        """처음 뜰 자리: 위젯 바로 옆, 위젯이 있는 모니터 작업 영역 안 (`main_spot`)."""
        root = self.app.root
        root.update_idletasks()
        widget = (root.winfo_x(), root.winfo_y(), root.winfo_width(), root.winfo_height())
        work = self._work()
        if work is None:
            return widget[0] + widget[2] + GAP, widget[1]
        return main_spot(widget, work, (W, h))

    def _clamp(self, x: int, y: int, h: int) -> tuple[int, int]:
        work = self._work((x + W // 2, y + h // 2))
        if work is None:
            return self.m.clamp_to_screen(x, y, W, h)
        left, top, right, bottom = work
        x = left if W >= right - left else max(left, min(x, right - W))
        y = top if h >= bottom - top else max(top, min(y, bottom - h))
        return x, y

    def _round(self, top: tk.Toplevel) -> None:
        self.m.round_corners(top)

    def _fit(self) -> None:
        """창 크기는 그대로 두고 본문이 넘치는지만 다시 잰다 (넘치면 오른쪽에 가는 바가 서고 휠로 넘긴다)."""
        cv, inner = self._canvas, self._inner
        if cv is None or inner is None or not self.is_open():
            return
        try:
            ch = cv.winfo_height()
            need = inner.winfo_reqheight()
            cv.itemconfigure(self._win, width=cv.winfo_width(), height=max(need, ch))
            cv.configure(scrollregion=(0, 0, cv.winfo_width(), max(need, ch)))
            if need <= ch + 1:
                cv.yview_moveto(0)
            self._paint_bar()
        except tk.TclError:
            pass

    def _paint_bar(self) -> None:
        cv, bar = self._canvas, self._bar
        if cv is None or bar is None:
            return
        need = self._inner.winfo_reqheight()
        ch = cv.winfo_height()
        if need <= ch + 1 or ch <= 1:
            bar.place_forget()
            return
        lo, hi = cv.yview()
        bar.place(relx=1.0, x=-2, rely=lo, relheight=max(hi - lo, 0.05), anchor="ne")
        bar.lift()

    def _wheel(self, e) -> None:
        cv = self._canvas
        if cv is None or self._inner.winfo_reqheight() <= cv.winfo_height() + 1:
            return
        cv.yview_scroll(-3 if e.delta > 0 else 3, "units")
        self._paint_bar()

    def _measure(self) -> int:
        """모든 탭을 한 번씩 그려 가장 큰 본문 높이를 잰다 (창 높이를 이 하나로 고정하려고)."""
        a = self.app
        saved = a._stats_period
        best = 0
        try:
            for key in self._tab_keys():
                self.tab = key
                # 사용 기록은 기간(일별·주별·…)마다 높이가 다르다. 다 재서 가장 큰 것을 쓴다
                for period in (self.m.STATS_TABS if key == "stats" else (None,)):
                    if period is not None:
                        a._stats_period = period
                    wrap = self._draw_body(banners=False)
                    self.top.update_idletasks()
                    best = max(best, wrap.winfo_reqheight() + TOP_PAD + BOT_PAD)
        finally:
            a._stats_period = saved
        return best

    # -------------------------------------------------- 탭 줄
    def _nav_item(self, nav: tk.Frame, key: str, name: str) -> None:
        row = tk.Frame(nav, bg=P.track, cursor="hand2")
        row.pack(fill="x")
        bar = tk.Frame(row, bg=P.track, width=3)
        bar.pack(side="left", fill="y")
        lbl = tk.Label(
            row, text=name, bg=P.track, fg=P.label, font=(KR, 10), anchor="w",
            padx=12, pady=6, cursor="hand2",
        )
        lbl.pack(side="left", fill="x", expand=True)
        for w in (row, lbl):
            w.bind("<Button-1>", lambda _e, k=key: self._go(k))
            w.bind("<Enter>", lambda _e, k=key: self._hover(k, True))
            w.bind("<Leave>", lambda _e, k=key: self._hover(k, False))
        self._nav[key] = (row, bar, lbl)

    def _paint_nav(self) -> None:
        for key, (row, bar, lbl) in self._nav.items():
            on = key == self.tab
            bg = P.bg if on else P.track
            row.config(bg=bg)
            bar.config(bg=P.green if on else bg)
            lbl.config(bg=bg, fg=P.title if on else P.label,
                       font=(KR, 10, "bold") if on else (KR, 10))

    def _hover(self, key: str, inside: bool) -> None:
        if key == self.tab or key not in self._nav:
            return
        self._nav[key][2].config(fg=P.sub if inside else P.label)

    def _go(self, key: str) -> None:
        if key == self.tab:
            return
        if self.tab == "ping":
            self._fail_seen = None
        self.tab = key
        self._render()

    def _step(self, d: int) -> None:
        keys = self._tab_keys()
        i = keys.index(self.tab) if self.tab in keys else 0
        self._go(keys[(i + d) % len(keys)])

    # -------------------------------------------------- 저절로 다시 그리기
    def _signature(self):
        """화면에 보이는 값의 지문. 이게 바뀌었을 때만 다시 그린다."""
        a = self.app
        u = a.last_usage
        usage = None
        if u is not None:
            usage = (u.five.pct, u.five.resets_at, u.week.pct, u.week.resets_at,
                     tuple((s.label, s.pct, s.resets_at) for s in u.scoped))
        minute = datetime.now().strftime("%H:%M") if self.tab in ("usage", "pace", "ping") else ""
        return (
            self.tab, usage, minute, type(a.last_error).__name__, str(a.last_error or ""),
            a.skin.key, a.state.get("theme"), a.state.get("topmost"), a.state.get("dock"),
            a.state.get("auto_update"), self._autostart(), a._autostart_locked,
            a.ping_cfg.get("enabled"), tuple(a.ping_cfg.get("times") or ()),
            a.ping_cfg.get("last_ping"), a._ping_busy, a._missed_dt, a._ping_fail,
            a.push_cfg.get("enabled"), a.push_cfg.get("url"), a.push_cfg.get("last_ok"),
            a.push_error,
            a.remote_cfg.get("enabled"), a.remote_cfg.get("folder"), a.remote_error,
            a._update_pending, a._update_busy, a._new_version, a._relogin_item,
            a._login_short(), a._login_state, a._revive_busy,
            a._latest, a._latest_at, a._latest_fail, a._newver_ask,
            a._selfupd_state, a._selfupd_why, a.state.get("self_update", True),
            a.state.get("main_click_away"), a.state.get("widget_click"),
        )

    def _typing(self) -> bool:
        """시:분 칸에 손이 가 있나. 그 사이 다시 그리면 치던 칸이 사라진다. 손을 떼면 그린다."""
        try:
            foc = self.top.focus_get()
        except (KeyError, tk.TclError):
            return False
        return isinstance(foc, tk.Entry)

    def _autostart(self) -> bool:
        return self.m.autostart_enabled()

    def _watch(self) -> None:
        self._watch_job = None
        if not self.is_open():
            return
        try:
            if self.app.applied_theme != self._theme:
                # 색은 만들 때 박히므로 통째로 다시 짓는다 (자리는 그대로)
                spot = (self.top.winfo_x(), self.top.winfo_y())
                self.close()
                self._build(spot)
                return
            sig = self._signature()
            if sig != self._sig and not self._typing():
                self._render()
        except Exception:  # noqa: BLE001 — 다시 그리다 어긋나도 감시는 이어 간다
            pass
        if self.is_open():
            self._watch_job = self.app.root.after(WATCH_MS, self._watch)

    # -------------------------------------------------- 본문
    def _render(self) -> None:
        if self._content is None or not self.is_open():
            return
        if self.tab not in self._tab_keys():
            self.tab = "usage"
        self._paint_nav()
        self._draw_body(banners=True)
        self._sig = self._signature()
        self.top.update_idletasks()
        self._fit()

    def _draw_body(self, banners: bool) -> tk.Frame:
        """띠 줄과 본문을 지금 탭으로 다시 짓는다. 본문 틀(wrap)을 돌려준다."""
        for w in self._banner_box.winfo_children():
            w.destroy()
        for w in self._inner.winfo_children():
            w.destroy()
        wrap = tk.Frame(self._inner, bg=P.bg)
        wrap.pack(fill="both", expand=True, padx=PAD, pady=(TOP_PAD, BOT_PAD))
        if banners:
            self._banners(self._banner_box)
        name = dict(self._tabs())[self.tab]
        head = tk.Frame(wrap, bg=P.bg)
        head.pack(fill="x", pady=(0, 8))
        tk.Label(head, text=name, bg=P.bg, fg=P.title, font=(KR, 14, "bold")).pack(side="left")
        if self.tab == "usage":
            self._button(head, "새로고침", self.app.refresh_now).pack(side="right")

        try:
            {
                "usage": self._tab_usage,
                "pace": lambda w: self.app._pace_body(w, INNER),
                "stats": lambda w: self.app._stats_body(w, INNER, self._fit),
                "api": lambda w: self.app._api_body(w, INNER),
                "look": self._tab_look,
                "ping": self._tab_ping,
                "phone": self._tab_phone,
                "conf": self._tab_conf,
            }[self.tab](wrap)
        except Exception as e:  # noqa: BLE001 — 한 탭이 어긋나도 창은 남긴다
            self.m.applog(f"메인 화면 그리기 오류 ({self.tab}) — {type(e).__name__}: {e}")
            tk.Label(wrap, text="이 화면을 그리지 못함", bg=P.bg, fg=P.red,
                     font=(KR, 10)).pack(anchor="w")
        return wrap

    # ---- 그럴 때만 서는 띠 (어느 탭에서나 맨 위)
    def _banners(self, wrap: tk.Frame) -> None:
        a = self.app
        rows = []
        blocked = isinstance(a.last_error, LoginRequired) or a._login_gone()
        if blocked:
            # 로그인이 막혀 있으면 이게 맨 위다 — 고칠 수 있는 곳으로 바로 보낸다
            rows.append((P.red, a._error_text(a.last_error) if a.last_error else "클로드 코드 로그인 필요",
                         "로그인 잇기", a.open_login))
        elif a._relogin_item:
            rows.append((P.amber, a._login_short(), "다시 로그인", a.relogin))
        if a._update_pending is not None:
            rows.append((P.amber, f"클로드 새 버전 {a._update_pending.target} 대기",
                         "다시 켜기", a.apply_update))
        if a._new_version:
            rows.append((P.green, f"쿨다운 새 버전 v{a._new_version}",
                         "지금 업데이트" if cooldown_selfupdate.can_self_update() else "받기",
                         a.update_now))
        if rows:
            tk.Frame(wrap, bg=P.bg, height=10).pack(fill="x")
        for color, text, btn, fn in rows:
            box = tk.Frame(wrap, bg=P.track)
            box.pack(fill="x", pady=(0, 6))
            tk.Frame(box, bg=color, width=3).pack(side="left", fill="y")
            tk.Label(box, text=text, bg=P.track, fg=P.title, font=(KR, 10), anchor="w",
                     padx=12, pady=6).pack(side="left", fill="x", expand=True)
            b = self._button(box, btn, fn, primary=True)
            b.pack(side="right", padx=8, pady=4)

    # ---- 사용량
    def _tab_usage(self, wrap: tk.Frame) -> None:
        a = self.app
        u = a.last_usage
        if a.last_error is not None and not isinstance(a.last_error, LoginRequired):
            tk.Label(wrap, text=f"{a.last_error_stamp} {a._error_text(a.last_error)}",
                     bg=P.bg, fg=P.red, font=(KR, 9), anchor="w").pack(fill="x", pady=(0, 8))
        if u is None:
            tk.Label(wrap, text="사용량을 아직 못 받았어요.", bg=P.bg, fg=P.faint,
                     font=(KR, 10)).pack(anchor="w", pady=12)
            return
        stamp = u.fetched_at.astimezone().strftime("%H:%M")
        tk.Label(wrap, text=f"기준 {stamp}", bg=P.bg, fg=P.faint, font=(KR, 8),
                 anchor="w").pack(fill="x", pady=(0, 4))
        p = pace(u)
        self._limit(wrap, "5시간 한도", u.five, five_due(u))
        self._limit(wrap, "주간 한도", u.week, p.due if p is not None else None)
        if u.scoped:
            self._section(wrap, "모델별 주간 한도")
            for s in u.scoped:
                self._limit(wrap, s.label, s, None, small=True)

    def _limit(self, wrap, name, limit, due, small=False) -> None:
        box = tk.Frame(wrap, bg=P.bg)
        box.pack(fill="x", pady=(0, 6 if small else 10))
        top = tk.Frame(box, bg=P.bg)
        top.pack(fill="x")
        tk.Label(top, text=name, bg=P.bg, fg=P.title,
                 font=(KR, 10) if small else (KR, 11, "bold")).pack(side="left", anchor="s")
        pct = limit.pct
        tk.Label(top, text="--" if pct is None else f"{pct:.0f}%", bg=P.bg, fg=tone(pct),
                 font=(NUM, 12 if small else 18, "bold")).pack(side="right")
        h = 6 if small else 10
        c = tk.Canvas(box, width=INNER, height=h + 4, bg=P.bg, highlightthickness=0, bd=0)
        c.pack(fill="x", pady=(2, 2))
        c.create_rectangle(0, 2, INNER, 2 + h, fill=P.track, width=0)
        if pct:
            c.create_rectangle(0, 2, INNER * min(100.0, pct) / 100, 2 + h, fill=tone(pct), width=0)
        if due is not None:
            x = mark_x(due, INNER)
            c.create_rectangle(x, 0, x + MARK_W, h + 4, fill=P.title, width=0)
        parts = []
        if limit.resets_at is not None:
            parts.append(f"초기화 {self.app._when_text(limit.resets_at)}")
        if limit.left:
            parts.append(limit.left)
        if due is not None:
            parts.append(f"적정선 {due:.0f}%")
        tk.Label(box, text=" · ".join(parts) or "초기화 시각 모름", bg=P.bg, fg=P.label,
                 font=(KR, 9), anchor="w").pack(fill="x")

    # ---- 위젯 모양
    # 모양은 작은 그림 카드 한 줄, 나머지(밝기·클로디 색·불투명도)는 이름 + 고르기 한 줄씩.
    LOOK_THEMES = (("auto", "윈도우 설정 따름"), ("light", "밝게"), ("dark", "어둡게"))
    LOOK_ALPHAS = ((1.0, "100%"), (0.96, "96%"), (0.88, "88%"), (0.75, "75%"))
    LOOK_COLS = 5  # 카드 한 줄에 몇 개 (넘으면 다음 줄)
    THUMB_H = 46  # 카드 그림 높이

    def _tab_look(self, wrap: tk.Frame) -> None:
        Label = self.m.Label
        a = self.app
        grid = tk.Frame(wrap, bg=P.bg)
        grid.pack(fill="x")
        gap = 6
        cols = self.LOOK_COLS
        cw = (INNER - gap * (cols - 1)) // cols
        for i, cls in enumerate(skins.SKINS):
            card = self._look_card(grid, cls, a.skin.key == cls.key, cw,
                                   lambda k=cls.key: a.switch_skin(k))
            card.grid(row=i // cols, column=i % cols, padx=(0 if i % cols == 0 else gap, 0),
                      pady=(0 if i < cols else gap, 0))

        rows = tk.Frame(wrap, bg=P.bg)
        rows.pack(fill="x", pady=(12, 4))
        rows.columnconfigure(1, weight=1)
        theme = a.state["theme"]
        self._look_row(rows, 0, "밝기", lambda box: self._segments(box, [
            (text, theme == key, lambda k=key: a.switch_theme(k)) for key, text in self.LOOK_THEMES]))
        mascot = a.state.get("mascot") or "coral"
        self._look_row(rows, 1, "클로디 색", lambda box: self._swatches(box, mascot, a.set_mascot))
        alpha = a._alpha()
        self._look_row(rows, 2, "불투명도", lambda box: self._segments(box, [
            (text, abs(alpha - v) < 0.005, lambda v=v: a.set_alpha(v)) for v, text in self.LOOK_ALPHAS]))

        tk.Frame(wrap, bg=P.line, height=1).pack(fill="x", pady=(6, 4))
        self._switch(wrap, Label.TOPMOST, bool(a.state["topmost"]), a.toggle_topmost)
        if a.skin.dockable:
            self._switch(wrap, Label.DOCK, bool(a.state["dock"]), a._tray_toggle_dock)

    def _look_card(self, parent, cls, on: bool, w: int, pick) -> tk.Frame:
        """스킨 하나 = 작은 그림 + 짧은 이름. 고른 것은 초록 테두리."""
        card = tk.Frame(parent, bg=P.bg, cursor="hand2", highlightthickness=2,
                        highlightbackground=P.green if on else P.line,
                        highlightcolor=P.green if on else P.line)
        c = tk.Canvas(card, width=w - 4, height=self.THUMB_H, bg=P.track,
                      highlightthickness=0, bd=0, cursor="hand2")
        c.pack()
        thumbs.draw(c, cls.key, w - 4, self.THUMB_H)
        lbl = tk.Label(card, text=thumbs.short_name(cls), bg=P.bg, fg=P.title if on else P.sub,
                       font=(KR, 9, "bold") if on else (KR, 9), pady=2, cursor="hand2")
        lbl.pack(fill="x")

        def go(_e=None):
            # 고른 슬림 바를 다시 누르면 작업표시줄로 되붙인다(switch_skin 이 맡음)
            pick()
            self._render()

        for x in (card, c, lbl):
            x.bind("<Button-1>", go)
        return card

    @staticmethod
    def _look_row(rows: tk.Frame, r: int, label: str, build) -> None:
        tk.Label(rows, text=label, bg=P.bg, fg=P.title, font=(KR, 10), anchor="w").grid(
            row=r, column=0, sticky="w", pady=4)
        box = tk.Frame(rows, bg=P.bg)
        box.grid(row=r, column=1, sticky="e", pady=4)
        build(box)

    def _segments(self, box: tk.Frame, options) -> None:
        """붙은 단추 여럿 중 하나 고르기. `options` = ((이름, 골랐나, 할 일), …)."""
        frame = tk.Frame(box, bg=P.line, padx=1, pady=1)
        frame.pack(side="right")
        for i, (text, on, pick) in enumerate(options):
            lbl = tk.Label(frame, text=text, bg=P.green if on else P.track,
                           fg=P.bg if on else P.sub, font=(KR, 9, "bold") if on else (KR, 9),
                           padx=10, pady=3, cursor="hand2")
            lbl.pack(side="left", padx=(0 if i == 0 else 1, 0))

            def go(_e=None, on=on, pick=pick):
                if not on:
                    pick()
                    self._render()

            lbl.bind("<Button-1>", go)

    def _swatches(self, box: tk.Frame, picked: str, pick) -> None:
        """클로디 색 견본 동그라미. 고른 것은 바깥 고리 + 이름."""
        dark = self.app.applied_theme != "light"
        name = ""
        for key, text, dc, lc in skins.base.MASCOTS:
            on = key == picked
            name = text if on else name
            c = tk.Canvas(box, width=24, height=24, bg=P.bg, highlightthickness=0, bd=0,
                          cursor="hand2")
            c.pack(side="left", padx=(4, 0))
            if on:
                c.create_oval(1, 1, 23, 23, outline=P.title, width=2)
            c.create_oval(5, 5, 19, 19, fill=dc if dark else lc, outline="")

            def go(_e=None, k=key, on=on):
                if not on:
                    pick(k)
                    self._render()

            c.bind("<Button-1>", go)
        tk.Label(box, text=name or "코랄", bg=P.bg, fg=P.sub, font=(KR, 9), width=4,
                 anchor="w").pack(side="left", padx=(8, 0))

    # ---- 클로드 모닝 스타터
    # 한 장에 위에서 아래로: 켜기 · 다음 시작(+지금 시작) · 시작 시각(바로 고침) · 최근 시작.
    # 11-13 다시 짬: 시각 정하기·시작 기록이 따로 뜨는 팝업이었던 것을 탭 안으로 들였다.
    def _tab_ping(self, wrap: tk.Frame) -> None:
        Label = self.m.Label
        a = self.app
        cfg = a.ping_cfg
        on = bool(cfg.get("enabled"))
        times = cooldown_ping.parse_times(cfg.get("times") or [])
        if self._ping_draft is None:
            self._ping_draft = [[t.hour, t.minute] for t in times] or [[5, 0]]
        if not on:  # 끄면 실패·놓침 표시도 지운다 (`toggle_ping` 과 같은 규칙)
            self._fail_seen = None
        self._switch(wrap, Label.PING_ON, on, a.toggle_ping)
        self._ping_card(wrap, on, times)
        self._ping_times(wrap)
        self._ping_log(wrap)

    def _ping_card(self, wrap: tk.Frame, on: bool, times) -> None:
        """다음 시작을 크게, 그 옆에 [지금 시작]. 실패·놓침은 카드 안 아래 줄에."""
        a = self.app
        card = tk.Frame(wrap, bg=P.track)
        card.pack(fill="x", pady=(6, 12))
        tk.Frame(card, bg=P.green if on and times else P.line, width=3).pack(side="left", fill="y")
        box = tk.Frame(card, bg=P.track)
        box.pack(side="left", fill="x", expand=True, padx=(12, 12), pady=(8, 9))
        row = tk.Frame(box, bg=P.track)
        row.pack(fill="x")
        if a._ping_busy:
            b = self._button(row, "시작하는 중", lambda: None, primary=True)
            b.config(state="disabled", disabledforeground=P.bg)
        else:
            b = self._button(row, self.m.Label.PING_NOW, a.send_ping_now, primary=True)
        b.pack(side="right")
        left = tk.Frame(row, bg=P.track)
        left.pack(side="left")
        tk.Label(left, text="다음 시작", bg=P.track, fg=P.label, font=(KR, 9)).pack(anchor="w")
        if not on:
            text, color = "꺼짐", P.faint
        elif not times:
            text, color = "시각 없음", P.faint
        else:
            nxt = cooldown_ping.predict_next(datetime.now(), times, a._five_resets_local())
            text, color = a._friendly_time(nxt), P.green
        tk.Label(left, text=text, bg=P.track, fg=color, font=(KR, 15, "bold")).pack(anchor="w")

        # 실패를 여기서 봤으니 위젯의 실패 표시는 내린다 (옛 시작 기록 팝업을 열 때와 같다).
        # 탭을 떠나기 전까지는 이 카드에 그대로 둔다.
        if a._ping_fail is not None:
            self._fail_seen = a._ping_fail
            a._ping_fail = None
            a._redraw()
        alerts = []
        if self._fail_seen is not None:
            when, why = self._fail_seen
            alerts.append((P.red, f"{when:%H:%M} 자동 시작 실패 · {cooldown_ping.friendly_error(why)}"))
        if a._missed_dt is not None:
            alerts.append((P.amber, f"{a._missed_dt:%H:%M} 자동 시작 놓침 · 컴퓨터 꺼짐"))
        for color, text in alerts:
            tk.Label(box, text=text, bg=P.track, fg=color, font=(KR, 9), anchor="w").pack(
                fill="x", pady=(4, 0))

    def _ping_times(self, wrap: tk.Frame) -> None:
        """시작 시각을 탭 안에서 바로 고친다. 시:분 칸은 타이핑·화살표·휠 다 된다.
        고친 것은 [저장](엔터)을 눌러야 들어간다. 간격 규칙에 걸리면 까닭을 빨갛게."""
        data = self._ping_draft
        self._head(wrap, "시작 시각", f"간격 5시간 1분 이상 · 하루 {cooldown_ping.MAX_TIMES}개까지")
        grid = tk.Frame(wrap, bg=P.bg)
        grid.pack(fill="x")
        for c in range(2):
            grid.columnconfigure(c, weight=1, uniform="chip")
        foot = tk.Frame(wrap, bg=P.bg)
        foot.pack(fill="x")

        def changed():
            self._ping_warn = ""
            self._ping_foot(foot)

        def drop(i):
            data.pop(i)
            self._ping_warn = ""
            self._render()

        def add():
            data.append([12, 0])
            self._ping_warn = ""
            self._render()

        n = len(data)
        for i in range(n + (1 if n < cooldown_ping.MAX_TIMES else 0)):
            r, c = divmod(i, 2)
            cell = tk.Frame(grid, bg=P.track if i < n else P.bg,
                            highlightthickness=0 if i < n else 1,
                            highlightbackground=P.line)
            cell.grid(row=r, column=c, sticky="nsew", pady=3, padx=(0, 4) if c == 0 else (4, 0))
            if i < n:
                self._time_chip(cell, data[i], changed, (lambda k=i: drop(k)) if n > 1 else None)
            else:  # 빈 칸 = 하나 더 넣을 자리 (최대 개수면 이 칸이 없다)
                plus = tk.Label(cell, text="＋ 시각 추가", bg=P.bg, fg=P.green, font=(KR, 9),
                                cursor="hand2")
                plus.pack(fill="both", expand=True)
                for w in (cell, plus):
                    w.bind("<Button-1>", lambda _e: add())
        self._ping_foot(foot)

    def _time_chip(self, cell: tk.Frame, hm: list, changed, drop) -> None:
        """시각 한 칸: [시]:[분]  ✕. `hm` 은 [시, 분] (그 자리를 바로 고친다).
        숫자 칸은 직접 치기·옆 ▲▼(길게 누르면 빠르게)·휠 다 된다. 윈도우 기본 스핀박스 화살표는
        본문 색을 안 따라 흰 단추로 튀어서 ▲▼ 를 직접 그린다."""
        def field(idx, hi):
            box = tk.Frame(cell, bg=P.track)
            var = tk.StringVar(value=f"{hm[idx]:02d}")
            job = [None]

            def commit(*_a):
                try:
                    v = int(var.get())
                except (ValueError, TypeError):
                    return  # 비었거나 숫자가 아니면 이전 값 그대로
                if hm[idx] != v % (hi + 1):
                    hm[idx] = v % (hi + 1)
                    changed()

            def step(d):
                var.set(f"{(hm[idx] + d) % (hi + 1):02d}")

            def hold(d, first=True):
                step(d)
                job[0] = box.after(400 if first else 60, lambda: hold(d, False))

            def release(_e=None):
                if job[0] is not None:
                    box.after_cancel(job[0])
                    job[0] = None

            def wheel(e):
                step(1 if e.delta > 0 else -1)
                return "break"  # 본문까지 넘어가지 않게

            def enter(_e):
                var.set(f"{hm[idx]:02d}")
                self._ping_save()

            var.trace_add("write", commit)
            ent = tk.Entry(
                box, textvariable=var, width=2, justify="center", font=(NUM, 14, "bold"),
                bg=P.track, fg=P.title, insertbackground=P.title, relief="flat", bd=0,
                highlightthickness=0, selectbackground=P.green, selectforeground=P.bg,
            )
            ent.pack(side="left")
            ent.bind("<FocusIn>", lambda _e: ent.select_range(0, "end"))
            ent.bind("<FocusOut>", lambda _e: var.set(f"{hm[idx]:02d}"))
            ent.bind("<Return>", enter)
            ent.bind("<Up>", lambda _e: (step(1), "break")[1])
            ent.bind("<Down>", lambda _e: (step(-1), "break")[1])
            arrows = tk.Frame(box, bg=P.track)
            arrows.pack(side="left", padx=(1, 0))
            for text, d in (("▲", 1), ("▼", -1)):
                arr = tk.Label(arrows, text=text, bg=P.track, fg=P.faint, font=(KR, 7),
                               cursor="hand2", padx=2, pady=0)
                arr.pack()
                arr.bind("<ButtonPress-1>", lambda _e, d=d: hold(d))
                arr.bind("<ButtonRelease-1>", release)
                arr.bind("<Enter>", lambda _e, w=arr: w.config(fg=P.title))
                arr.bind("<Leave>", lambda _e, w=arr: (w.config(fg=P.faint), release()))
            for w in (box, ent, arrows):
                w.bind("<MouseWheel>", wheel)
            return box

        field(0, 23).pack(side="left", padx=(10, 0), pady=4)
        tk.Label(cell, text=":", bg=P.track, fg=P.faint, font=(NUM, 13, "bold")).pack(
            side="left", padx=2)
        field(1, 59).pack(side="left", pady=4)
        if drop is not None:  # 하나만 남으면 못 지운다
            x = tk.Label(cell, text="✕", bg=P.track, fg=P.faint, font=(KR, 10), cursor="hand2")
            x.pack(side="right", padx=10)
            x.bind("<Button-1>", lambda _e: drop())
            x.bind("<Enter>", lambda _e: x.config(fg=P.red))
            x.bind("<Leave>", lambda _e: x.config(fg=P.faint))

    def _ping_draft_items(self) -> list[str]:
        return sorted({f"{h:02d}:{m:02d}" for h, m in self._ping_draft or []})

    def _ping_dirty(self) -> bool:
        times = cooldown_ping.parse_times(self.app.ping_cfg.get("times") or [])
        return self._ping_draft_items() != [f"{t:%H:%M}" for t in times]

    def _ping_foot(self, foot: tk.Frame) -> None:
        """고친 게 있을 때만 서는 줄: 왼쪽 상태(저장 전·까닭), 오른쪽 [되돌리기] [저장]."""
        for w in foot.winfo_children():
            w.destroy()
        if self._ping_dirty() or self._ping_warn:
            row = tk.Frame(foot, bg=P.bg)
            row.pack(fill="x", pady=(4, 0))
            self._button(row, "저장", self._ping_save, primary=True).pack(side="right")
            self._button(row, "되돌리기", self._ping_reset).pack(side="right", padx=(0, 6))
            text, color = (self._ping_warn, P.red) if self._ping_warn else ("저장 전", P.amber)
            tk.Label(row, text=text, bg=P.bg, fg=color, font=(KR, 9), anchor="w",
                     justify="left", wraplength=INNER - 150).pack(side="left", fill="x", expand=True)
        self._fit()

    def _ping_save(self) -> None:
        msg = self.app.save_ping_times(self._ping_draft_items())
        self._ping_warn = msg
        if not msg:
            self._ping_draft = None
        self._render()

    def _ping_reset(self) -> None:
        self._ping_draft = None
        self._ping_warn = ""
        self._render()

    def _ping_log(self, wrap: tk.Frame) -> None:
        """최근 시작 4번을 2열로. 성공은 점과 시각만, 실패는 빨갛게 하고 가장 최근 실패의 까닭을 한 줄
        (위 카드에 실패 줄이 이미 섰으면 같은 말이라 안 적는다)."""
        a = self.app
        entries = list(reversed(cooldown_ping.read_log_entries(40)))[:4]
        fails = [e for e in entries if not e[1]]
        note = ""
        if entries:
            note = f"최근 {len(entries)}번 · " + (f"실패 {len(fails)}" if fails else "모두 실행됨")
        self._head(wrap, "최근 시작", note, top=10)
        if not entries:
            tk.Label(wrap, text="아직 없음", bg=P.bg, fg=P.faint, font=(KR, 9),
                     anchor="w").pack(fill="x")
            return
        grid = tk.Frame(wrap, bg=P.bg)
        grid.pack(fill="x")
        for c in range(2):
            grid.columnconfigure(c, weight=1, uniform="log")
        for i, (when, ok, _d) in enumerate(entries):
            r, c = divmod(i, 2)
            cell = tk.Frame(grid, bg=P.bg)
            cell.grid(row=r, column=c, sticky="w", pady=1)
            tk.Label(cell, text="●", bg=P.bg, fg=P.green if ok else P.red,
                     font=(KR, 7)).pack(side="left", padx=(0, 7))
            tk.Label(cell, text=a._friendly_time(when) + ("" if ok else " 실패"), bg=P.bg,
                     fg=P.sub if ok else P.red, font=(KR, 9)).pack(side="left")
        if fails and self._fail_seen is None:
            when, _ok, detail = fails[0]
            tk.Label(wrap, text=f"{a._friendly_time(when)} 실패 · {cooldown_ping.friendly_error(detail)}",
                     bg=P.bg, fg=P.red, font=(KR, 9), anchor="w").pack(fill="x", pady=(3, 0))

    @staticmethod
    def _head(wrap, title: str, note: str = "", top: int = 0) -> None:
        """작은 제목 한 줄. 오른쪽에 규칙·요약을 흐리게 (설명 문단 대신)."""
        row = tk.Frame(wrap, bg=P.bg)
        row.pack(fill="x", pady=(top, 3))
        tk.Label(row, text=title, bg=P.bg, fg=P.label, font=(KR, 9, "bold")).pack(side="left")
        if note:
            tk.Label(row, text=note, bg=P.bg, fg=P.faint, font=(KR, 8)).pack(side="right")

    # ---- 폰·원격
    def _tab_phone(self, wrap: tk.Frame) -> None:
        Label = self.m.Label
        a = self.app
        self._section(wrap, Label.PHONE, first=True)
        self._switch(wrap, Label.PUSH, bool(a.push_cfg.get("enabled")), a.toggle_push)
        if not cooldown_push.endpoint(a.push_cfg):
            state, color = "연결 안 됨", P.faint
        elif a.push_error:
            state, color = a.push_error, P.red
        else:
            ok = cooldown_push.last_ok_at(a.push_cfg)
            state = f"마지막 전송 {a._friendly_time(ok)}" if ok else "아직 안 보냄"
            color = P.sub
        self._value(wrap, "폰", state, color, button=(Label.PAIR.rstrip("…"), a.open_phone_link))

        self._section(wrap, Label.REMOTE)
        self._switch(wrap, Label.REMOTE_ON, bool(a.remote_cfg.get("enabled")), a.toggle_remote)
        folder = a.remote_cfg.get("folder") or cooldown_remote.default_folder()
        self._value(wrap, "세션 열 폴더", self._short_path(folder), P.sub,
                    button=("폴더 정하기", lambda: self._dialog(a.open_remote_folder)))
        if a.remote_error:
            self._value(wrap, "연결 실패", a.remote_error, P.red)

    # ---- 앱 설정
    def _tab_conf(self, wrap: tk.Frame) -> None:
        Label = self.m.Label
        a = self.app
        self._section(wrap, "클로드 로그인", first=True)
        if isinstance(a.last_error, LoginRequired) or a._login_gone():
            state, color = a._error_text(a.last_error) if a.last_error else "로그인 필요", P.red
        elif a._login_short():
            state, color = a._login_short(), P.amber
        elif a.last_usage is not None:
            state, color = "이어져 있음", P.green
        else:
            state, color = "확인 전", P.faint
        self._value(wrap, "사용량 읽기", state, color, button=("로그인 확인", a.open_login))

        self._section(wrap, "메인 화면·위젯")
        self._switch(wrap, Label.MAIN_CLICK_AWAY, bool(a.state.get("main_click_away")),
                     a.toggle_main_click_away)
        mode = a.state.get("widget_click") or "main"
        self._choice(wrap, Label.WIDGET_CLICK, (
            (Label.WIDGET_CLICK_MAIN, mode != "refresh", lambda: a.set_widget_click("main")),
            (Label.WIDGET_CLICK_REFRESH, mode == "refresh", lambda: a.set_widget_click("refresh")),
        ))

        self._section(wrap, "자동으로")
        self._switch(wrap, Label.AUTO_UPDATE, bool(a.state.get("auto_update")), a.toggle_auto_update)
        self._switch(wrap, Label.AUTOSTART, self._autostart(), a.toggle_autostart,
                     locked=a._autostart_locked)

        self._section(wrap, "쿨다운 버전")
        ver = cooldown_newver.current() or "모름"
        selfup = cooldown_selfupdate.can_self_update()
        self._value(wrap, "지금 버전", ver if selfup else f"{ver} · 소스에서 실행", P.sub)
        if a._newver_ask:
            latest, color = "확인 중", P.faint
        elif a._latest_fail and a._latest_at:
            latest, color = "확인 못 함", P.amber
        elif a._latest:
            latest, color = a._latest, P.green if a._new_version else P.sub
        else:
            latest, color = "확인 전", P.faint
        if a._latest_at and not a._newver_ask:
            latest += datetime.fromtimestamp(a._latest_at).strftime(" · %H:%M 확인")
        self._value(wrap, "최신 버전", latest, color, button=("업데이트 확인", a.check_now))
        if a._new_version and selfup:
            st = a._selfupd_state or "받을 차례"
            if st == "받아 둠" and a.state.get("self_update", True):
                st = "받아 둠 · 자리 비면 바꿔 켬"
            if a._selfupd_why:
                st += f" · {a._selfupd_why}"
            bad = "실패" in st
            self._value(wrap, f"{a._new_version} 업데이트", st, P.red if bad else P.amber,
                        button=("지금 업데이트", a.update_now, True))
        elif a._new_version:
            self._value(wrap, f"{a._new_version} 업데이트", "릴리스 페이지에서 받기", P.amber,
                        button=(f"v{a._new_version} 받기", a.open_release, True))
        if selfup:
            self._switch(wrap, Label.SELF_UPDATE, bool(a.state.get("self_update", True)),
                         a.toggle_self_update)
        if a._update_pending is not None:
            self._section(wrap, "클로드 앱 버전")
            self._value(wrap, "새 버전", f"{a._update_pending.target} 대기", P.amber,
                        button=("다시 켜기", a.apply_update))

    # -------------------------------------------------- 부품
    @staticmethod
    def _section(wrap, title: str, first: bool = False) -> None:
        tk.Label(wrap, text=title, bg=P.bg, fg=P.label, font=(KR, 9, "bold"),
                 anchor="w").pack(fill="x", pady=(0 if first else 10, 2))

    def _button(self, parent, text, command, primary=False) -> tk.Button:
        return self.app._themed_button(parent, text, command, primary=primary, width=0)

    def _value(self, wrap, label: str, value: str, color: str | None = None,
               button: tuple | None = None) -> tk.Frame:
        """이름 · 값 한 줄. `button=(이름, 할 일[, primary])` 이면 오른쪽에 단추.
        ★ 단추를 **먼저** 붙인다 — pack 은 먼저 붙인 것에 자리를 먼저 주므로, 값이 길어도
          단추가 창 밖으로 밀리지 않는다(긴 폴더 경로에서 실제로 밀렸다)."""
        row = tk.Frame(wrap, bg=P.bg)
        row.pack(fill="x", pady=3)
        if button is not None:
            text, fn, *rest = button
            self._button(row, text, fn, primary=bool(rest and rest[0])).pack(
                side="right", padx=(10, 0))
        tk.Label(row, text=label, bg=P.bg, fg=P.title, font=(KR, 10)).pack(side="left")
        tk.Label(row, text=value, bg=P.bg, fg=color or P.sub, font=(KR, 10, "bold"),
                 anchor="w").pack(side="left", padx=(12, 0), fill="x", expand=True)
        return row

    def _switch(self, wrap, label: str, on: bool, toggle, locked: bool = False) -> None:
        """켜고 끄는 줄. 줄 어디를 눌러도(스페이스·엔터도) 바뀐다. 잠긴 것은 흐리게만."""
        row = tk.Frame(wrap, bg=P.bg, cursor="" if locked else "hand2")
        row.pack(fill="x", pady=2)
        sw = tk.Canvas(row, width=38, height=22, bg=P.bg, highlightthickness=1,
                       highlightbackground=P.bg, highlightcolor=P.green, bd=0,
                       takefocus=0 if locked else 1)
        sw.pack(side="right")
        fill = P.green if on else P.track
        edge = P.green if on else P.faint
        if locked:
            fill, edge = P.track, P.line
        sw.create_oval(2, 3, 18, 19, fill=fill, outline=edge)
        sw.create_oval(20, 3, 36, 19, fill=fill, outline=edge)
        sw.create_rectangle(10, 3, 28, 19, fill=fill, outline="")
        sw.create_line(10, 3, 28, 3, fill=edge)
        sw.create_line(10, 19, 28, 19, fill=edge)
        kx = 22 if on else 6
        sw.create_oval(kx, 7, kx + 10, 15, fill=P.bg if on else P.faint, outline="")
        lbl = tk.Label(row, text=label, bg=P.bg, fg=P.faint if locked else P.title,
                       font=(KR, 10), anchor="w", pady=5)
        lbl.pack(side="left", fill="x", expand=True)
        if locked:
            tk.Label(row, text="이 PC 에선 못 바꿈", bg=P.bg, fg=P.faint,
                     font=(KR, 9)).pack(side="right", padx=(0, 10))
            return

        def flip(_e=None):
            toggle()
            self._render()

        for w in (row, lbl, sw):
            w.bind("<Button-1>", flip)
        sw.bind("<space>", flip)
        sw.bind("<Return>", flip)

    def _choice(self, wrap, label: str, options) -> None:
        """이름 한 줄에 고르기 여럿을 나란히. `options` = ((이름, 골랐나, 할 일), …)."""
        row = tk.Frame(wrap, bg=P.bg)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, bg=P.bg, fg=P.title, font=(KR, 10), anchor="w",
                 pady=4).pack(side="left")
        for text, on, pick in reversed(options):
            box = tk.Frame(row, bg=P.bg)
            box.pack(side="right", padx=(12, 0))
            self._radio(box, text, on, pick, side="left")

    def _radio(self, wrap, label: str, on: bool, pick, side: str | None = None) -> None:
        row = tk.Frame(wrap, bg=P.bg, cursor="hand2")
        if side is None:
            row.pack(fill="x", pady=1)
        else:
            row.pack(side=side)
        dot = tk.Canvas(row, width=18, height=18, bg=P.bg, highlightthickness=0, bd=0)
        dot.pack(side="left", padx=(0, 6 if side else 10))
        dot.create_oval(2, 2, 16, 16, outline=P.green if on else P.faint, width=2 if on else 1)
        if on:
            dot.create_oval(6, 6, 12, 12, fill=P.green, outline="")
        lbl = tk.Label(row, text=label, bg=P.bg, fg=P.title if on else P.sub,
                       font=(KR, 10, "bold") if on else (KR, 10), anchor="w", pady=4)
        lbl.pack(side="left", fill="x", expand=side is None)

        def go(_e=None):
            if not on:
                pick()
                self._render()

        for w in (row, dot, lbl):
            w.bind("<Button-1>", go)

    @staticmethod
    def _short_path(path: str, keep: int = 24) -> str:
        """긴 폴더는 앞을 줄여 끝(폴더 이름)이 보이게."""
        return path if len(path) <= keep else "…" + path[-(keep - 1):]

    def _dialog(self, fn) -> None:
        """윈도우 대화상자(폴더 고르기)는 '항상 위' 창 밑에 깔린다 — 그동안 내린다."""
        top = self.top
        try:
            if top is not None:
                top.attributes("-topmost", False)
            fn()
        finally:
            try:
                if top is not None and top.winfo_exists():
                    top.attributes("-topmost", True)
                    top.lift()
            except tk.TclError:
                pass
