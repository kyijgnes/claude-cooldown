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

WIDTH = 244
HEIGHT = 116
BG = "#14161a"
FG = "#e6edf3"
DIM = "#8b949e"
FAINT = "#6e7681"
TRACK = "#2a2f36"


def color_of(pct: float | None) -> str:
    if pct is None:
        return "#6b7280"
    if pct < 50:
        return "#2ea043"
    if pct < 80:
        return "#d29922"
    return "#e5484d"


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
    d.rounded_rectangle((0, 0, 63, 63), radius=14, fill=color_of(pct))
    size = 38 if len(text) < 3 else 28
    try:
        font = ImageFont.truetype("arialbd.ttf", size)
    except OSError:
        font = ImageFont.load_default()
    box = d.textbbox((0, 0), text, font=font)
    d.text(
        ((64 - box[2] - box[0]) / 2, (64 - box[3] - box[1]) / 2),
        text,
        font=font,
        fill="white",
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


# ---------------------------------------------------------------- 위젯


class Row:
    """'5시간  7%   3시간 07분 후' 한 줄 + 게이지."""

    def __init__(self, parent: tk.Misc, label: str):
        line = tk.Frame(parent, bg=BG)
        line.pack(fill="x", padx=12, pady=(9, 0))
        tk.Label(
            line, text=label, bg=BG, fg=DIM, font=("맑은 고딕", 8, "bold"), anchor="w"
        ).pack(side="left")
        self.reset = tk.Label(line, text="", bg=BG, fg=FAINT, font=("맑은 고딕", 8))
        self.reset.pack(side="right")
        self.value = tk.Label(
            line, text="--", bg=BG, fg=FG, font=("맑은 고딕", 12, "bold")
        )
        self.value.pack(side="left", padx=(8, 0))

        self.bar = tk.Canvas(
            parent, height=5, bg=TRACK, highlightthickness=0, width=WIDTH - 24
        )
        self.bar.pack(fill="x", padx=12, pady=(4, 0))
        self.widgets = [line, self.reset, self.value, self.bar]

    def set(self, pct: float | None, left: str) -> None:
        tone = color_of(pct)
        self.value.config(text="--" if pct is None else f"{pct:.0f}%", fg=tone)
        self.reset.config(text=left)
        self.bar.delete("all")
        width = self.bar.winfo_width() or (WIDTH - 24)
        self.bar.create_rectangle(0, 0, width * (pct or 0) / 100, 5, fill=tone, width=0)


class App:
    def __init__(self):
        self.state = load_state()
        self.results: queue.Queue = queue.Queue()
        self.commands: queue.Queue = queue.Queue()
        self.warned = False
        self.widget_visible = True

        self.root = tk.Tk()
        # 숨긴 채로 만들고 run() 에서 편다. 시작 프로그램·바로가기로 띄우면 부모가
        # '최소화로 시작' 표시 상태를 넘기는 경우가 있어, withdraw → deiconify 를
        # 거쳐 저장된 위치·크기로 확실히 펴지게 한다.
        self.root.withdraw()
        self.root.configure(bg=BG)

        self.rows = {
            "five": Row(self.root, "5시간"),
            "week": Row(self.root, "주간"),
        }
        self.footer = tk.Label(
            self.root,
            text="불러오는 중",
            bg=BG,
            fg=FAINT,
            font=("맑은 고딕", 8),
            anchor="w",
        )
        self.footer.pack(fill="x", padx=12, pady=(8, 8))

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

        draggable = [self.root, self.footer] + [
            w for row in self.rows.values() for w in row.widgets
        ]
        for w in draggable:
            w.bind("<Button-1>", self._press)
            w.bind("<B1-Motion>", self._drag)
            w.bind("<ButtonRelease-1>", self._release)
            w.bind("<Button-3>", self._popup)

        self.poller = Poller(self.results)
        self.poller.start()

        self.tray = pystray.Icon(
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
        threading.Thread(target=self.tray.run, daemon=True).start()

        self.root.after(200, self._pump)

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
        self.footer.config(text="새로고침 중")
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
        """창을 지정한 자리에 지정한 크기로 편다. 시작할 때와 다시 켤 때 모두 여기를 쓴다."""
        self.root.deiconify()
        self.root.overrideredirect(True)
        self.root.attributes("-alpha", 0.92)
        self.root.attributes("-topmost", bool(self.state["topmost"]))
        self.root.geometry(f"{WIDTH}x{HEIGHT}+{self.state['x']}+{self.state['y']}")

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
        self.rows["five"].set(usage.five.pct, usage.five.left)
        self.rows["week"].set(usage.week.pct, usage.week.left)

        stamp = usage.fetched_at.astimezone().strftime("%H:%M")
        scoped = "  ".join(
            f"{s.label} {s.pct:.0f}%" for s in usage.scoped if s.pct is not None
        )
        self.footer.config(text=f"{stamp} 기준   {scoped}".rstrip(), fg=FAINT)

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
        relogin = isinstance(err, LoginRequired)
        text = "재로그인 필요" if relogin else str(err)
        stamp = datetime.now().strftime("%H:%M")
        self.footer.config(text=f"{stamp}  {text}", fg="#e5484d")
        self.rows["five"].set(None, "")
        self.rows["week"].set(None, "")
        self.tray.icon = draw_icon(None)
        self.tray.title = f"클로드 쿨다운 — {text}"[:127]

    def run(self):
        self.show_window()
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
