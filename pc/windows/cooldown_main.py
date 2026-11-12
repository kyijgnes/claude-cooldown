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
- **팝업과 따로 센다.** `App._close_panels` 는 팝업만 닫으므로 메인 화면에서 시각 정하기·폰 연결·
  로그인 팝업을 열어도 메인 화면은 남는다. 설정을 바꾸는 창이라 밖을 눌러도 안 닫힌다(click_away 없음).
- **값이 바뀌면 저절로 다시 그린다.** 1초마다 지금 값의 지문(`_signature`)을 재서 달라졌을 때만
  본문을 다시 짓는다. 트레이에서 바꾼 것·새로 받은 사용량·남은 시간까지 따라온다.
  밝기가 바뀌면 색이 위젯에 박혀 있으므로 창을 통째로 다시 짓는다.
- 툴팁·설명 문단을 넣지 않는다(폴더 규칙). 이름은 하는 일로, 값은 화면에 그대로.
"""

from __future__ import annotations

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
from skins.base import KR, MARK_W, NUM, P, mark_x, tone

W = 620  # 창 폭 (px)
MIN_H = 520  # 창 최소 높이. 실제 높이는 모든 탭 중 가장 큰 것에 맞춰 한 번 정해 고정한다
NAV_W = 170  # 왼쪽 탭 줄 폭
PAD = 22  # 본문 좌우 여백
INNER = W - NAV_W - 1 - PAD * 2  # 본문 안쪽 폭 (차트 폭)
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

    # -------------------------------------------------- 창 짓기
    def _tab_keys(self) -> list[str]:
        return [k for k, _n in self._tabs()]

    def _tabs(self) -> list[tuple[str, str]]:
        Label = self.m.Label
        out = [("usage", "사용량"), ("pace", "이번 주 사용 속도"), ("stats", "지난 사용 기록")]
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
        pad.pack(side="left", fill="x", expand=True, padx=(PAD - 3, PAD), pady=(14, 12))
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
        tk.Frame(nav, bg=P.track, height=10).pack(fill="x")
        for key, name in self._tabs():
            if key == "look":  # 읽는 쪽(사용량)과 바꾸는 쪽(설정) 사이 한 줄
                tk.Frame(nav, bg=P.line, height=1).pack(fill="x", padx=14, pady=8)
            self._nav_item(nav, key, name)

        top.bind("<Escape>", lambda _e: self.close())
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
        best = 0
        for key in self._tab_keys():
            self.tab = key
            wrap = self._draw_body(banners=False)
            self.top.update_idletasks()
            best = max(best, wrap.winfo_reqheight() + 16 + PAD)
        return best

    # -------------------------------------------------- 탭 줄
    def _nav_item(self, nav: tk.Frame, key: str, name: str) -> None:
        row = tk.Frame(nav, bg=P.track, cursor="hand2")
        row.pack(fill="x")
        bar = tk.Frame(row, bg=P.track, width=3)
        bar.pack(side="left", fill="y")
        lbl = tk.Label(
            row, text=name, bg=P.track, fg=P.label, font=(KR, 10), anchor="w",
            padx=14, pady=8, cursor="hand2",
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
        )

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
            if sig != self._sig:
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
        wrap.pack(fill="both", expand=True, padx=PAD, pady=(16, PAD))
        if banners:
            self._banners(self._banner_box)
        name = dict(self._tabs())[self.tab]
        head = tk.Frame(wrap, bg=P.bg)
        head.pack(fill="x", pady=(0, 12))
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
            tk.Frame(wrap, bg=P.bg, height=16).pack(fill="x")
        for color, text, btn, fn in rows:
            box = tk.Frame(wrap, bg=P.track)
            box.pack(fill="x", pady=(0, 8))
            tk.Frame(box, bg=color, width=3).pack(side="left", fill="y")
            tk.Label(box, text=text, bg=P.track, fg=P.title, font=(KR, 10), anchor="w",
                     padx=12, pady=9).pack(side="left", fill="x", expand=True)
            b = self._button(box, btn, fn, primary=True)
            b.pack(side="right", padx=8, pady=6)

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
                 anchor="w").pack(fill="x", pady=(0, 8))
        p = pace(u)
        self._limit(wrap, "5시간 한도", u.five, five_due(u))
        self._limit(wrap, "주간 한도", u.week, p.due if p is not None else None)
        if u.scoped:
            self._section(wrap, "모델별 주간 한도")
            for s in u.scoped:
                self._limit(wrap, s.label, s, None, small=True)

    def _limit(self, wrap, name, limit, due, small=False) -> None:
        box = tk.Frame(wrap, bg=P.bg)
        box.pack(fill="x", pady=(0, 10 if small else 14))
        top = tk.Frame(box, bg=P.bg)
        top.pack(fill="x")
        tk.Label(top, text=name, bg=P.bg, fg=P.title,
                 font=(KR, 10) if small else (KR, 11, "bold")).pack(side="left", anchor="s")
        pct = limit.pct
        tk.Label(top, text="--" if pct is None else f"{pct:.0f}%", bg=P.bg, fg=tone(pct),
                 font=(NUM, 12 if small else 18, "bold")).pack(side="right")
        h = 6 if small else 10
        c = tk.Canvas(box, width=INNER, height=h + 4, bg=P.bg, highlightthickness=0, bd=0)
        c.pack(fill="x", pady=(4, 4))
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
    def _tab_look(self, wrap: tk.Frame) -> None:
        THEMES, Label = self.m.THEMES, self.m.Label
        a = self.app
        self._section(wrap, "모양", first=True)
        for cls in skins.SKINS:
            self._radio(wrap, cls.name, a.skin.key == cls.key,
                        lambda k=cls.key: a.switch_skin(k))
        self._section(wrap, "밝기")
        for key, label in THEMES:
            self._radio(wrap, label, a.state["theme"] == key, lambda k=key: a.switch_theme(k))
        self._section(wrap, "띄우기")
        self._switch(wrap, Label.TOPMOST, bool(a.state["topmost"]), a.toggle_topmost)
        if a.skin.dockable:
            self._switch(wrap, Label.DOCK, bool(a.state["dock"]), a._tray_toggle_dock)

    # ---- 클로드 모닝 스타터
    def _tab_ping(self, wrap: tk.Frame) -> None:
        Label = self.m.Label
        a = self.app
        cfg = a.ping_cfg
        on = bool(cfg.get("enabled"))
        self._switch(wrap, Label.PING_ON, on, a.toggle_ping)
        times = cooldown_ping.parse_times(cfg.get("times") or [])
        self._value(wrap, "시작 시각", " · ".join(t.strftime("%H:%M") for t in times) or "없음",
                    button=("시각 정하기", a.open_ping_times))
        if on and times:
            nxt = cooldown_ping.predict_next(datetime.now(), times, a._five_resets_local())
            self._value(wrap, "다음 시작", a._friendly_time(nxt), P.green)
        if a._ping_fail is not None:
            when, why = a._ping_fail
            self._value(wrap, "자동 시작 실패", f"{when:%H:%M} · {cooldown_ping.friendly_error(why)}", P.red)
        if a._missed_dt is not None:
            self._value(wrap, "자동 시작 놓침", f"{a._missed_dt:%H:%M} · 컴퓨터 꺼짐", P.amber)

        self._section(wrap, "마지막 시작")
        last = cooldown_ping.read_log_entries(1)
        log_btn = ("시작 기록", a.open_ping_log)
        if last:
            when, ok, detail = last[-1]
            text = a._friendly_time(when) + ("" if ok else f" · {cooldown_ping.friendly_error(detail)}")
            self._value(wrap, "실행됨" if ok else "실패", text, P.sub if ok else P.red, button=log_btn)
        else:
            self._value(wrap, "기록", "아직 없음", P.faint, button=log_btn)

        foot = tk.Frame(wrap, bg=P.bg)
        foot.pack(fill="x", pady=(16, 0))
        if a._ping_busy:
            b = self._button(foot, "시작하는 중", lambda: None, primary=True)
            b.config(state="disabled", disabledforeground=P.bg)
        else:
            b = self._button(foot, Label.PING_NOW, a.send_ping_now, primary=True)
        b.pack(side="left")

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
                 anchor="w").pack(fill="x", pady=(0 if first else 16, 4))

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

    def _radio(self, wrap, label: str, on: bool, pick) -> None:
        row = tk.Frame(wrap, bg=P.bg, cursor="hand2")
        row.pack(fill="x", pady=1)
        dot = tk.Canvas(row, width=18, height=18, bg=P.bg, highlightthickness=0, bd=0)
        dot.pack(side="left", padx=(0, 10))
        dot.create_oval(2, 2, 16, 16, outline=P.green if on else P.faint, width=2 if on else 1)
        if on:
            dot.create_oval(6, 6, 12, 12, fill=P.green, outline="")
        lbl = tk.Label(row, text=label, bg=P.bg, fg=P.title if on else P.sub,
                       font=(KR, 10, "bold") if on else (KR, 10), anchor="w", pady=4)
        lbl.pack(side="left", fill="x", expand=True)

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
