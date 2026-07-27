"""
클로드 쿨다운 — 바탕화면 위젯 + 시작표시줄 아이콘 (Windows)
=============================================================
pip install -r ../requirements.txt

실행:  pythonw cooldown_app.py      (검은 콘솔 창 없이)
확인:  python  ../cooldown_core.py  (응답 원본 JSON)

- 시작표시줄 아이콘을 누르면 위젯이 맨 앞으로 나온다.
- 위젯은 드래그로 옮기고, 위치는 저장된다. 우클릭으로 메뉴.
- 우클릭 > 디자인 에서 모양을 바꾼다 (skins/ 폴더).
- 우클릭 > 윈도우 켤 때 자동 실행 을 켜면 시작 프로그램에 등록된다.
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

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from cooldown_core import (  # noqa: E402
    MIN_INTERVAL,
    LoginRequired,
    Usage,
    UsageError,
    fetch,
)

import skins  # noqa: E402
from skins.base import BG, tone  # noqa: E402

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


# ---------------------------------------------------------------- 설정 저장


def load_state() -> dict:
    state = {
        "x": 60,
        "y": 60,
        "topmost": False,
        "dock": False,  # 작업표시줄에 붙이기
        "skin": skins.DEFAULT,
    }
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


def autostart_target() -> str | None:
    """등록된 바로가기가 실제로 가리키는 스크립트 경로. 없거나 못 읽으면 None."""
    if not os.path.exists(STARTUP_LNK):
        return None
    try:
        from win32com.client import Dispatch

        return Dispatch("WScript.Shell").CreateShortCut(STARTUP_LNK).Arguments.strip('"')
    except Exception:  # noqa: BLE001
        return None


def repair_autostart() -> None:
    """자동 실행이 켜져 있는데 딴 경로를 가리키면 지금 위치로 고쳐 쓴다.

    폴더를 옮기면 바로가기가 없어진 파일을 가리키게 되고, 재부팅해도 아무 일이
    일어나지 않는다 — 오류도 안 뜬다. 켜 둔 사람은 고장난 줄도 모른다.
    """
    target = autostart_target()
    if target is None:
        return
    here = os.path.normcase(os.path.abspath(__file__))
    if os.path.normcase(os.path.abspath(target)) != here:
        set_autostart(True)


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
    for name in ("segoeuib.ttf", "arialbd.ttf"):
        try:
            font = ImageFont.truetype(name, size)
            break
        except OSError:
            continue
    else:
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


def taskbar_slot(width: int, height: int) -> tuple[int, int] | None:
    """작업표시줄의 빈 자리(알림 영역 왼쪽)에 놓을 좌표. 못 찾으면 None.

    윈도우 11 은 작업표시줄 안에 남의 프로그램을 넣는 길(데스크밴드)을 없앴다.
    그래서 '넣는' 게 아니라 그 위에 겹쳐 놓는다 — 보기에는 같다.
    """
    try:
        import win32gui

        bar = win32gui.FindWindow("Shell_TrayWnd", None)
        if not bar:
            return None
        left, top, right, bottom = win32gui.GetWindowRect(bar)
        tray = win32gui.FindWindowEx(bar, 0, "TrayNotifyWnd", None)
        edge = win32gui.GetWindowRect(tray)[0] if tray else right
        x = max(left, edge - width - 8)
        room = bottom - top
        # 작업표시줄보다 크면 아래를 맞춰 위로 넘치게 둔다
        y = top + (room - height) // 2 if height <= room else bottom - height - 2
        return x, y
    except Exception:  # noqa: BLE001
        return None


def dismiss_menus() -> None:
    """열려 있는 팝업 메뉴를 닫는다.

    Tk 의 메뉴는 윈도우 기본 메뉴 창(#32768)이라 `unpost()` 로는 안 닫힌다.
    주인 창을 감추면 메뉴만 화면에 덩그러니 남으므로 직접 끝내 준다.
    """
    try:
        import ctypes

        ctypes.windll.user32.EndMenu()
    except Exception:  # noqa: BLE001
        pass


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
        self.last_usage: Usage | None = None
        self.last_error: Exception | None = None

        self.root = tk.Tk()
        # 숨긴 채로 만들고 run() 에서 편다. 시작 프로그램·바로가기로 띄우면 부모가
        # '최소화로 시작' 표시 상태를 넘기는 경우가 있어, withdraw → deiconify 를
        # 거쳐 저장된 위치·크기로 확실히 펴지게 한다.
        self.root.withdraw()
        self.root.configure(bg=BG)

        repair_autostart()

        self.body: tk.Frame | None = None
        self.skin = skins.make(self.state["skin"])
        self._build_body()
        self._build_menu()

        self.poller = Poller(self.results)
        self.poller.start()
        self.tray = self._build_tray()
        threading.Thread(target=self.tray.run, daemon=True).start()

        self.root.after(200, self._pump)

    # -------------------------------------------------- 본체(스킨) 그리기
    def _build_body(self) -> None:
        if self.body is not None:
            self.body.destroy()
        self.body = tk.Frame(self.root, bg=BG)
        self.body.pack(fill="both", expand=True)
        self.skin.build(self.body)
        self._bind_drag(self.body)
        self._bind_drag(self.root)

    def _bind_drag(self, widget: tk.Misc) -> None:
        """위젯과 그 아래 모든 자식에 드래그·우클릭을 건다."""
        widget.bind("<Button-1>", self._press)
        widget.bind("<B1-Motion>", self._drag)
        widget.bind("<ButtonRelease-1>", self._release)
        widget.bind("<Button-3>", self._popup)
        for child in widget.winfo_children():
            self._bind_drag(child)

    def switch_skin(self, key: str) -> None:
        if key == self.skin.key:
            return
        self.state["skin"] = key
        save_state(self.state)
        self.skin = skins.make(key)
        self._build_body()
        self.height = 0  # 스킨마다 크기가 다르므로 다시 잰다
        self._replay()
        self.show_window()
        self.var_skin.set(self.skin.key)

    def _replay(self) -> None:
        """새로 그린 스킨에 마지막 상태를 다시 먹인다."""
        if self.last_usage is not None:
            self.skin.show(self.last_usage, self._stamp(self.last_usage))
        if self.last_error is not None:
            relogin = isinstance(self.last_error, LoginRequired)
            self.skin.show_error(
                self._error_text(self.last_error),
                keep_values=not relogin and self.last_usage is not None,
                stamp=datetime.now().strftime("%H:%M"),
            )

    # -------------------------------------------------- 메뉴
    def _build_menu(self) -> None:
        self.var_topmost = tk.BooleanVar(self.root, bool(self.state["topmost"]))
        self.var_autostart = tk.BooleanVar(self.root, autostart_enabled())
        self.var_dock = tk.BooleanVar(self.root, bool(self.state["dock"]))
        self.var_skin = tk.StringVar(self.root, self.skin.key)

        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="지금 새로고침", command=self.refresh_now)

        design = tk.Menu(self.menu, tearoff=0)
        for cls in skins.SKINS:
            design.add_radiobutton(
                label=cls.name,
                value=cls.key,
                variable=self.var_skin,
                command=lambda k=cls.key: self.switch_skin(k),
            )
        self.menu.add_cascade(label="디자인", menu=design)

        self.menu.add_checkbutton(
            label="작업표시줄에 붙이기",
            variable=self.var_dock,
            command=self.toggle_dock,
        )
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
        # 숨겨도 시작표시줄 아이콘은 남는다 — 그 아이콘을 누르면 다시 나온다
        self.menu.add_command(label="위젯 숨기기", command=self.hide_widget)
        self.menu.add_command(label="종료", command=self.quit)

    def _build_tray(self) -> pystray.Icon:
        return pystray.Icon(
            "claude_cooldown",
            draw_icon(None),
            "클로드 쿨다운 — 불러오는 중",
            menu=pystray.Menu(
                # default=True — 아이콘을 클릭(더블클릭 포함)하면 이게 실행된다
                pystray.MenuItem(
                    "위젯 앞으로",
                    lambda: self.commands.put("front"),
                    default=True,
                ),
                pystray.MenuItem("지금 새로고침", lambda: self.refresh_now()),
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
        # 끌어서 옮겼으면 더는 작업표시줄에 붙어 있는 게 아니다
        self.state.update(
            x=self.root.winfo_x(), y=self.root.winfo_y(), dock=False
        )
        self.var_dock.set(False)
        self.root.attributes("-topmost", bool(self.state["topmost"]))
        save_state(self.state)

    def _popup(self, e):
        self.var_topmost.set(bool(self.state["topmost"]))
        self.var_autostart.set(autostart_enabled())
        self.var_dock.set(bool(self.state["dock"]))
        self.var_skin.set(self.skin.key)
        self.menu.tk_popup(e.x_root, e.y_root)

    # -------------------------------------------------- 동작
    def refresh_now(self):
        self.poller.refresh_now()

    def toggle_topmost(self):
        self.state["topmost"] = not self.state["topmost"]
        self.root.attributes("-topmost", bool(self.state["topmost"]))
        self.var_topmost.set(bool(self.state["topmost"]))
        save_state(self.state)

    def toggle_autostart(self):
        set_autostart(not autostart_enabled())
        self.var_autostart.set(autostart_enabled())

    def hide_widget(self):
        """위젯만 감춘다. 시작표시줄 아이콘을 누르면 돌아온다."""
        # 메뉴를 먼저 닫고 한 박자 뒤에 감춘다 (순서가 바뀌면 메뉴가 화면에 남는다)
        dismiss_menus()
        self.root.after(60, self._do_hide)

    def _do_hide(self):
        dismiss_menus()
        self.state.update(x=self.root.winfo_x(), y=self.root.winfo_y())
        save_state(self.state)
        self.widget_visible = False
        self.root.withdraw()

    def bring_to_front(self):
        """트레이 아이콘을 눌렀을 때 — 숨어 있으면 꺼내고 맨 앞으로 올린다."""
        self.widget_visible = True
        self.show_window()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.update_idletasks()
        if not self.state["topmost"]:
            # 잠깐 맨 위로 올렸다 내리면 '항상 위' 를 켜지 않고도 맨 앞에 선다
            self.root.after(400, lambda: self.root.attributes("-topmost", False))

    def show_window(self):
        """창을 저장된 자리에 편다. 시작할 때와 다시 켤 때 모두 여기를 쓴다."""
        self.root.deiconify()
        self.root.overrideredirect(True)
        self.root.attributes("-alpha", 0.96)
        self.root.update_idletasks()
        self.height = self.height or self.root.winfo_reqheight()

        docked = bool(self.state["dock"])
        spot = taskbar_slot(self.skin.width, self.height) if docked else None
        if spot is None:
            docked = False
            spot = (self.state["x"], self.state["y"])
        # 작업표시줄 자체가 항상 위라, 그 위에 얹으려면 이쪽도 항상 위여야 한다
        self.root.attributes("-topmost", docked or bool(self.state["topmost"]))
        self.root.geometry(f"{self.skin.width}x{self.height}+{spot[0]}+{spot[1]}")
        round_corners(self.root)

    def toggle_dock(self):
        self.state["dock"] = not self.state["dock"]
        self.var_dock.set(bool(self.state["dock"]))
        save_state(self.state)
        self.show_window()

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
                "front": self.bring_to_front,
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

    @staticmethod
    def _stamp(usage: Usage) -> str:
        return usage.fetched_at.astimezone().strftime("%H:%M")

    @staticmethod
    def _error_text(err: Exception) -> str:
        return "재로그인 필요" if isinstance(err, LoginRequired) else str(err)

    def _reassert_dock(self):
        """작업표시줄 아이콘이 늘거나 줄면 빈 자리가 옮겨간다 — 갱신할 때마다 다시 맞춘다."""
        if not self.state["dock"]:
            return
        spot = taskbar_slot(self.skin.width, self.height)
        if spot:
            self.root.geometry(
                f"{self.skin.width}x{self.height}+{spot[0]}+{spot[1]}"
            )

    def _show(self, usage: Usage):
        self.last_usage = usage
        self.last_error = None
        self.skin.show(usage, self._stamp(usage))
        self._reassert_dock()
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
        self.last_error = err
        relogin = isinstance(err, LoginRequired)
        # 로그인이 끊겼으면 값이 아예 없는 것이므로 지운다. 일시적인 연결 실패면
        # 마지막으로 받은 값과 그 기준 시각을 그대로 둔다 (오류 표시로 이미 구분된다).
        keep = not relogin and self.last_usage is not None
        if relogin:
            self.last_usage = None
        text = self._error_text(err)
        self.skin.show_error(text, keep, datetime.now().strftime("%H:%M"))
        self.tray.icon = draw_icon(None)
        self.tray.title = f"클로드 쿨다운 — {text}"[:127]

    def run(self):
        self.show_window()
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
