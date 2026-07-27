"""
클로드 쿨다운 — 바탕화면 위젯 + 시작표시줄 아이콘 (Windows)
=============================================================
pip install -r ../requirements.txt

실행:  pythonw cooldown_app.py      (검은 콘솔 창 없이)
확인:  python  ../cooldown_core.py  (응답 원본 JSON)

- 바탕화면 위젯 : 드래그로 이동, 위치는 자동 저장. 우클릭으로 메뉴.
- 시작표시줄 아이콘 : 5시간 사용률을 숫자로 표시. 80% 넘으면 한 번 알림.
- 우클릭 > '윈도우 켤 때 자동 실행' 을 켜면 시작 프로그램에 등록된다.
"""

from __future__ import annotations

import json
import os
import queue
import sys
import threading
import tkinter as tk
from datetime import datetime

import pystray
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cooldown_core import (  # noqa: E402
    MIN_INTERVAL,
    LoginRequired,
    Usage,
    UsageError,
    fetch,
)

HOME = os.path.expanduser("~")
STATE_PATH = os.path.join(HOME, ".claude_cooldown_widget.json")
EXPORT_PATH = os.path.join(HOME, ".claude_cooldown.json")
STARTUP_LNK = os.path.join(
    os.environ.get("APPDATA", HOME),
    r"Microsoft\Windows\Start Menu\Programs\Startup",
    "클로드 쿨다운.lnk",
)

WARN_AT = 80  # 5시간 한도가 이 % 를 넘으면 알림
WARN_CLEAR = 70  # 이 아래로 내려가면 알림 재무장

# ---------------------------------------------------------------- 치수·색
WIDTH = 260
PAD = 18
INNER = WIDTH - PAD * 2

BG = "#15171c"
TITLE = "#e6edf3"
LABEL = "#6b7280"
SUB = "#c2cad4"
FAINT = "#5c636e"
TRACK = "#252a32"
LINE = "#232830"
GREEN = "#3fb950"
AMBER = "#e3b341"
RED = "#ff5c61"
RED_BG = "#2b1418"

KR = "맑은 고딕"
NUM = "Segoe UI"


def tone(pct: float | None) -> str:
    """여유 초록 / 보통 노랑 / 임박 빨강."""
    if pct is None:
        return FAINT
    if pct < 50:
        return GREEN
    if pct < 80:
        return AMBER
    return RED


# ---------------------------------------------------------------- 설정 저장


def load_state() -> dict:
    state = {"x": 60, "y": 60, "topmost": False}
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            state.update(json.load(f))
    except (OSError, ValueError):
        pass
    return state


def save_state(state: dict) -> None:
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except OSError:
        pass


def export(usage: Usage) -> None:
    """다른 도구(Rainmeter, 폰 업로더 등)가 읽어가는 파일.
    cooldown_agent.py 와 같은 스키마여야 한다 — Usage.as_dict() 로 통일."""
    try:
        with open(EXPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(usage.as_dict(), f, ensure_ascii=False)
    except OSError:
        pass


# ---------------------------------------------------------------- 자동 실행


def autostart_enabled() -> bool:
    return os.path.exists(STARTUP_LNK)


def set_autostart(on: bool) -> None:
    if not on:
        try:
            os.remove(STARTUP_LNK)
        except OSError:
            pass
        return
    try:
        from win32com.client import Dispatch

        pyw = sys.executable.replace("python.exe", "pythonw.exe")
        script = os.path.abspath(__file__)
        link = Dispatch("WScript.Shell").CreateShortCut(STARTUP_LNK)
        link.TargetPath = pyw
        link.Arguments = f'"{script}"'
        link.WorkingDirectory = os.path.dirname(script)
        link.Save()
    except Exception:  # noqa: BLE001  pywin32 없거나 권한 문제
        pass


# ---------------------------------------------------------------- 트레이 아이콘


def draw_icon(pct: float | None) -> Image.Image:
    text = "?" if pct is None else str(int(round(pct)))
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, 63, 63), radius=15, fill=tone(pct))
    size = 38 if len(text) < 3 else 28
    try:
        font = ImageFont.truetype("segoeuib.ttf", size)
    except OSError:
        try:
            font = ImageFont.truetype("arialbd.ttf", size)
        except OSError:
            font = ImageFont.load_default()
    box = d.textbbox((0, 0), text, font=font)
    d.text(
        ((64 - box[2] - box[0]) / 2, (64 - box[3] - box[1]) / 2),
        text,
        font=font,
        fill="#0d1117",
    )
    return img


# ---------------------------------------------------------------- 폴러


class Poller(threading.Thread):
    """백그라운드에서 MIN_INTERVAL 마다 조회해 결과를 큐에 넣는다."""

    def __init__(self, out: queue.Queue):
        super().__init__(daemon=True)
        self.out = out
        self.wake = threading.Event()
        self.stopped = False

    def refresh_now(self) -> None:
        self.wake.set()

    def stop(self) -> None:
        self.stopped = True
        self.wake.set()

    def run(self) -> None:
        while not self.stopped:
            try:
                self.out.put(fetch())
            except (UsageError, LoginRequired) as e:
                self.out.put(e)
            except Exception as e:  # noqa: BLE001  예상 못 한 형식 변경 등
                self.out.put(UsageError(str(e)))
            self.wake.wait(MIN_INTERVAL)
            self.wake.clear()


# ---------------------------------------------------------------- 화면 조각


class Section:
    """한 한도 덩어리 — 라벨 / 큰 숫자 + 남은시간 / 얇은 게이지."""

    def __init__(self, parent: tk.Misc, label: str):
        self.box = tk.Frame(parent, bg=BG)
        self.box.pack(fill="x", padx=PAD)

        self.label = tk.Label(
            self.box, text=label, bg=BG, fg=LABEL, font=(KR, 8), anchor="w"
        )
        self.label.pack(fill="x")

        row = tk.Frame(self.box, bg=BG)
        row.pack(fill="x")
        self.value = tk.Label(row, text="--", bg=BG, fg=FAINT, font=(NUM, 24, "bold"))
        self.value.pack(side="left")
        self.left = tk.Label(row, text="", bg=BG, fg=SUB, font=(KR, 10))
        self.left.pack(side="right", anchor="s", pady=(0, 9))

        self.bar = tk.Canvas(
            self.box, height=3, width=INNER, bg=TRACK, highlightthickness=0, bd=0
        )
        self.bar.pack(fill="x", pady=(3, 0))

        self.widgets = [self.box, self.label, row, self.value, self.left, self.bar]

    def set(self, pct: float | None, left: str) -> None:
        color = tone(pct)
        self.value.config(text="--" if pct is None else f"{pct:.0f}%", fg=color)
        self.left.config(text=left, fg=SUB if pct is not None else FAINT)
        self.bar.delete("all")
        width = self.bar.winfo_width() or INNER
        if pct is not None:
            self.bar.create_rectangle(0, 0, width * pct / 100, 3, fill=color, width=0)


def round_corners(root: tk.Tk) -> None:
    """윈도우 11 둥근 모서리. 안 되는 환경이면 조용히 넘어간다."""
    try:
        import ctypes
        from ctypes import byref, c_int

        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, byref(c_int(2)), 4)
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------- 앱


class App:
    def __init__(self):
        self.state = load_state()
        self.results: queue.Queue = queue.Queue()
        self.commands: queue.Queue = queue.Queue()
        self.warned = False
        self.widget_visible = True
        self.height = 0

        self.root = tk.Tk()
        # 숨긴 채로 만들고 run() 에서 편다. 시작 프로그램·바로가기로 띄우면 부모가
        # '최소화로 시작' 표시 상태를 넘기는 경우가 있어, withdraw → deiconify 를
        # 거쳐 저장된 위치·크기로 확실히 펴지게 한다.
        self.root.withdraw()
        self.root.configure(bg=BG)

        self._build()
        self._bind_drag()
        self._build_menu()

        self.poller = Poller(self.results)
        self.poller.start()
        self.tray = self._build_tray()
        threading.Thread(target=self.tray.run, daemon=True).start()

        self.root.after(200, self._pump)

    # -------------------------------------------------- 화면 구성
    def _build(self) -> None:
        # 머리말 — 평소엔 제목, 오류일 땐 빨간 띠로 바뀐다 (높이는 그대로)
        self.head = tk.Frame(self.root, bg=BG)
        self.head.pack(fill="x", pady=(0, 4))
        self.accent = tk.Frame(self.head, bg=BG, width=3)
        self.accent.pack(side="left", fill="y")
        self.head_pad = tk.Frame(self.head, bg=BG)
        self.head_pad.pack(fill="x", padx=(PAD - 3, PAD), pady=(15, 9))
        self.title = tk.Label(
            self.head_pad, text="클로드 사용량", bg=BG, fg=TITLE, font=(KR, 10, "bold")
        )
        self.title.pack(side="left")
        self.stamp = tk.Label(self.head_pad, text="", bg=BG, fg=FAINT, font=(KR, 8))
        self.stamp.pack(side="right")

        self.five = Section(self.root, "5시간 한도")
        self.gap = tk.Frame(self.root, bg=BG, height=17)
        self.gap.pack()
        self.week = Section(self.root, "주간 한도")

        self.divider = tk.Frame(self.root, bg=LINE, height=1)
        self.divider.pack(fill="x", padx=PAD, pady=(18, 0))

        self.foot = tk.Frame(self.root, bg=BG)
        self.foot.pack(fill="x", padx=PAD, pady=(9, 15))
        self.foot_label = tk.Label(self.foot, text="", bg=BG, fg=LABEL, font=(KR, 8))
        self.foot_label.pack(side="left")
        self.foot_value = tk.Label(self.foot, text="", bg=BG, fg=SUB, font=(KR, 9))
        self.foot_value.pack(side="left", padx=(7, 0))
        self.note = tk.Label(
            self.foot, text="불러오는 중", bg=BG, fg=FAINT, font=(KR, 8)
        )
        self.note.pack(side="right")

    def _head_normal(self) -> None:
        for w in (self.head, self.head_pad, self.title, self.stamp):
            w.configure(bg=BG)
        self.accent.configure(bg=BG)
        self.title.configure(text="클로드 사용량", fg=TITLE)
        self.stamp.configure(fg=FAINT)

    def _head_error(self, text: str) -> None:
        for w in (self.head, self.head_pad, self.title, self.stamp):
            w.configure(bg=RED_BG)
        self.accent.configure(bg=RED)
        self.title.configure(text=text, fg=RED)
        self.stamp.configure(fg="#a06068")

    def _bind_drag(self) -> None:
        targets = [
            self.root,
            self.head,
            self.head_pad,
            self.title,
            self.stamp,
            self.gap,
            self.divider,
            self.foot,
            self.foot_label,
            self.foot_value,
            self.note,
            *self.five.widgets,
            *self.week.widgets,
        ]
        for w in targets:
            w.bind("<Button-1>", self._press)
            w.bind("<B1-Motion>", self._drag)
            w.bind("<ButtonRelease-1>", self._release)
            w.bind("<Button-3>", self._popup)

    def _build_menu(self) -> None:
        self.var_topmost = tk.BooleanVar(self.root, bool(self.state["topmost"]))
        self.var_autostart = tk.BooleanVar(self.root, autostart_enabled())

        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="지금 새로고침", command=self.refresh_now)
        self.menu.add_checkbutton(
            label="항상 위에 표시",
            variable=self.var_topmost,
            command=self.toggle_topmost,
        )
        self.menu.add_checkbutton(
            label="윈도우 켤 때 자동 실행",
            variable=self.var_autostart,
            command=self.toggle_autostart,
        )
        self.menu.add_separator()
        self.menu.add_command(label="종료", command=self.quit)

    def _build_tray(self) -> pystray.Icon:
        return pystray.Icon(
            "claude_cooldown",
            draw_icon(None),
            "클로드 쿨다운 — 불러오는 중",
            menu=pystray.Menu(
                pystray.MenuItem("지금 새로고침", lambda: self.refresh_now()),
                pystray.MenuItem(
                    "바탕화면 위젯 보이기",
                    lambda: self.commands.put("toggle_widget"),
                    checked=lambda item: self.widget_visible,
                ),
                pystray.MenuItem(
                    "윈도우 켤 때 자동 실행",
                    lambda: self.commands.put("toggle_autostart"),
                    checked=lambda item: autostart_enabled(),
                ),
                pystray.MenuItem("종료", lambda: self.commands.put("quit")),
            ),
        )

    # -------------------------------------------------- 드래그
    def _press(self, e):
        self._dx = e.x_root - self.root.winfo_x()
        self._dy = e.y_root - self.root.winfo_y()

    def _drag(self, e):
        self.root.geometry(f"+{e.x_root - self._dx}+{e.y_root - self._dy}")

    def _release(self, _e):
        self.state.update(x=self.root.winfo_x(), y=self.root.winfo_y())
        save_state(self.state)

    def _popup(self, e):
        self.var_topmost.set(bool(self.state["topmost"]))
        self.var_autostart.set(autostart_enabled())
        self.menu.tk_popup(e.x_root, e.y_root)

    # -------------------------------------------------- 메뉴
    def refresh_now(self):
        self.note.config(text="새로고침 중", fg=FAINT)
        self.poller.refresh_now()

    def toggle_topmost(self):
        self.state["topmost"] = not self.state["topmost"]
        self.root.attributes("-topmost", bool(self.state["topmost"]))
        self.var_topmost.set(bool(self.state["topmost"]))
        save_state(self.state)

    def toggle_autostart(self):
        set_autostart(not autostart_enabled())
        self.var_autostart.set(autostart_enabled())

    def toggle_widget(self):
        self.widget_visible = not self.widget_visible
        if self.widget_visible:
            self.show_window()
        else:
            self.root.withdraw()

    def show_window(self):
        """창을 저장된 자리에 편다. 시작할 때와 다시 켤 때 모두 여기를 쓴다."""
        self.root.deiconify()
        self.root.overrideredirect(True)
        self.root.attributes("-alpha", 0.96)
        self.root.attributes("-topmost", bool(self.state["topmost"]))
        self.root.update_idletasks()
        self.height = self.height or self.root.winfo_reqheight()
        self.root.geometry(
            f"{WIDTH}x{self.height}+{self.state['x']}+{self.state['y']}"
        )
        round_corners(self.root)

    def quit(self):
        self.state.update(x=self.root.winfo_x(), y=self.root.winfo_y())
        save_state(self.state)
        self.poller.stop()
        try:
            self.tray.stop()
        except Exception:  # noqa: BLE001
            pass
        self.root.destroy()

    # -------------------------------------------------- 화면 갱신
    def _pump(self):
        while True:
            try:
                cmd = self.commands.get_nowait()
            except queue.Empty:
                break
            {
                "quit": self.quit,
                "toggle_widget": self.toggle_widget,
                "toggle_autostart": self.toggle_autostart,
            }[cmd]()
            if cmd == "quit":
                return

        while True:
            try:
                item = self.results.get_nowait()
            except queue.Empty:
                break
            if isinstance(item, Usage):
                self._show(item)
            else:
                self._show_error(item)

        self.root.after(300, self._pump)

    def _show(self, usage: Usage):
        self._head_normal()
        self.five.set(usage.five.pct, usage.five.left)
        self.week.set(usage.week.pct, usage.week.left)

        stamp = usage.fetched_at.astimezone().strftime("%H:%M")
        self.stamp.config(text=f"{stamp} 기준")

        scoped = [s for s in usage.scoped if s.pct is not None]
        if scoped:
            self.foot_label.config(text="모델별")
            self.foot_value.config(
                text="  ".join(f"{s.label} {s.pct:.0f}%" for s in scoped)
            )
        else:
            self.foot_label.config(text="")
            self.foot_value.config(text="")
        self.note.config(text="", fg=FAINT)

        export(usage)

        pct = usage.five.pct
        self.tray.icon = draw_icon(pct)
        self.tray.title = self._tray_text(usage)[:127]
        if pct is not None:
            if pct >= WARN_AT and not self.warned:
                self.tray.notify(f"5시간 한도 {pct:.0f}% 사용", "클로드 쿨다운")
                self.warned = True
            elif pct < WARN_CLEAR:
                self.warned = False

    def _tray_text(self, usage: Usage) -> str:
        parts = ["클로드 쿨다운"]
        for limit in (usage.five, usage.week):
            if limit.pct is not None:
                parts.append(f"{limit.label} {limit.pct:.0f}%  {limit.left}")
        return "\n".join(parts)

    def _show_error(self, err: Exception):
        text = "재로그인 필요" if isinstance(err, LoginRequired) else str(err)
        self._head_error(text)
        self.stamp.config(text=datetime.now().strftime("%H:%M"))
        self.five.set(None, "")
        self.week.set(None, "")
        self.foot_label.config(text="")
        self.foot_value.config(text="")
        self.note.config(text="", fg=FAINT)
        self.tray.icon = draw_icon(None)
        self.tray.title = f"클로드 쿨다운 — {text}"[:127]

    def run(self):
        self.show_window()
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
