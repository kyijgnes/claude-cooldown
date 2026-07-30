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

import atexit
import faulthandler
import json
import os
import queue
import sys
import threading
import time
import tkinter as tk
import traceback
from datetime import datetime

import pystray
from PIL import Image, ImageDraw, ImageFont, ImageTk

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from cooldown_core import (  # noqa: E402
    MIN_INTERVAL,
    ConnectionFailed,
    LoginRequired,
    Usage,
    UsageError,
    fetch,
    pace,
)

import cooldown_ping  # noqa: E402
import cooldown_push  # noqa: E402
import skins  # noqa: E402
from skins.base import (  # noqa: E402
    KR,
    MARK_W,
    NUM,
    P,
    mark_x,
    pace_color,
    set_palette,
    tone,
)

HOME = os.path.expanduser("~")
STATE_PATH = os.path.join(HOME, ".claude_cooldown_widget.json")
EXPORT_PATH = os.path.join(HOME, ".claude_cooldown.json")
SUMMON_PATH = os.path.join(HOME, ".claude_cooldown.summon")
STARTUP_LNK = os.path.join(
    os.environ.get("APPDATA", HOME),
    r"Microsoft\Windows\Start Menu\Programs\Startup",
    "클로드 쿨다운.lnk",
)

# ---------------------------------------------------------------- 블랙박스
# pythonw·exe(--windowed) 로 돌면 콘솔이 없어 오류가 **어디에도 안 남는다** —
# 앱이 소리 없이 사라져도 원인을 알 길이 없었다. 그래서 켜고·끄고·죽는 순간을
# 여기 한 줄씩 남긴다. 다음에 또 꺼지면 이 파일부터 본다.
#   '종료 — …' 줄 없이 다음 '시작' 이 나오면 = 밖에서 죽임(또는 갑작스런 종료),
#   'Fatal Python error' 뭉치가 있으면 = 파이썬이 스스로 abort (faulthandler 가 남김).
APPLOG_PATH = os.path.join(HOME, ".claude_cooldown_app.log")
APPLOG_KEEP = 400  # 시작할 때 이 줄 수만 남기고 줄인다
_applog_file = None


def open_applog() -> None:
    """로그를 열어 둔다. 돌아가는 동안엔 덧붙이기만 하고, 줄이는 건 시작할 때 한 번.
    faulthandler 가 같은 파일 핸들로 C 스택까지 쏟아부으므로 열어 둔 채로 둔다."""
    global _applog_file
    try:
        if os.path.exists(APPLOG_PATH):
            with open(APPLOG_PATH, encoding="utf-8", errors="replace") as f:
                keep = f.read().splitlines()[-APPLOG_KEEP:]
            with open(APPLOG_PATH, "w", encoding="utf-8") as f:
                f.write("\n".join(keep) + "\n")
        _applog_file = open(APPLOG_PATH, "a", encoding="utf-8", buffering=1)
    except OSError:
        _applog_file = None


def applog(line: str) -> None:
    if _applog_file is None:
        return
    try:
        _applog_file.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {line}\n")
        _applog_file.flush()
    except (OSError, ValueError):
        pass


def install_crash_log() -> None:
    """죽는 길을 전부 로그로 모은다. 콘솔이 없어도 흔적이 남게."""
    open_applog()
    if _applog_file is not None:
        try:
            # 파이썬이 통째로 죽을 때(abort·세그폴트) 마지막 스택을 남긴다.
            # 어젯밤 c0000409(FATAL_APP_EXIT) 같은 게 이 길로 잡힌다.
            faulthandler.enable(file=_applog_file)
        except (OSError, ValueError, RuntimeError):
            pass

    def on_uncaught(exc_type, exc, tb):
        applog("치명적 오류\n" + "".join(traceback.format_exception(exc_type, exc, tb)).rstrip())

    def on_thread_error(args):
        name = getattr(args.thread, "name", "?")
        applog(
            f"스레드 오류 ({name})\n"
            + "".join(
                traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
            ).rstrip()
        )

    sys.excepthook = on_uncaught
    threading.excepthook = on_thread_error
    # quit() 은 os._exit 로 끝내므로 여기까지 오면 '메뉴로 끝낸 게 아닌' 종료다
    atexit.register(lambda: applog("종료 — 인터프리터 정리"))


WARN_AT = 80  # 한도가 이 % 를 넘으면 알림
WARN_CLEAR = 70  # 이 아래로 내려가면 알림 재무장
RETRY_FIRST = 20  # 연결이 끊겼을 때 첫 재시도까지 (초)
DRAG_SLOP = 4  # 이만큼 안 움직였으면 '끌었다' 로 치지 않는다 (px)
UNDOCK_SLOP = 120  # 붙여 둔 상태에선 이만큼 넘게 끌어야 떼어 낸다 (그 안이면 클릭으로 보고 제자리로)
MANUAL_FLOOR = 15  # '지금 새로고침' 을 연타해도 이 간격은 지킨다 (초)
TICK = 60  # 남은 시간을 다시 그리는 주기 (초)
PING_TICK = 20  # 자동 핑을 쏠 때가 됐는지 보는 주기 (초). 앵커 여유(GRACE_MIN)보다 촘촘히.
PANEL_PAD = 18  # 팝업창 좌우 여백 (px). 카드 스킨의 PAD 와 맞춰 위젯과 같은 결로.
THEME_TICK = 4  # 윈도우 테마가 바뀌었는지 보는 주기 (초). 'auto' 일 때만 쓴다.
THEMES = (("auto", "윈도우 설정 따름"), ("light", "밝게"), ("dark", "어둡게"))
STAY_TICK = 250  # 붙어 있을 때 다시 맨 앞으로 올리는 주기 (ms). 가려지는 시간이 곧 이 값.
ALPHA = 0.96  # 평소 창 불투명도
BUSY_ALPHA = 0.78  # 새로고침 누른 직후

_MUTEX = None  # 중복 실행 판정용. 프로세스가 살아 있는 동안 붙들고 있어야 한다.


def already_running() -> bool:
    """이 프로그램이 이미 떠 있는가. 이름 있는 뮤텍스로 판정한다."""
    global _MUTEX
    try:
        import ctypes

        # use_last_error 로 만들어야 ctypes 가 오류 코드를 제대로 넘겨준다
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_bool,
            ctypes.c_wchar_p,
        ]
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        _MUTEX = kernel32.CreateMutexW(None, False, "claude_cooldown_single_instance")
        return ctypes.get_last_error() == 183  # ERROR_ALREADY_EXISTS
    except Exception:  # noqa: BLE001
        return False


def summon_running_instance() -> None:
    """이미 떠 있는 쪽더러 앞으로 나오라고 표시만 남긴다 (그쪽이 지우고 나온다)."""
    try:
        with open(SUMMON_PATH, "w", encoding="utf-8") as f:
            f.write("1")
    except OSError:
        pass


def clamp_to_screen(x: int, y: int, w: int, h: int) -> tuple[int, int]:
    """창이 화면 밖으로 나가지 않게 한다.

    모니터를 뺐거나 해상도를 줄이면 저장해 둔 자리가 화면 밖이 될 수 있다.
    제목표시줄이 없어 끌어올 수도 없으니 창째로 안쪽에 넣는다.
    기준은 화면 전체가 아니라 **작업 영역**(작업표시줄을 뺀 자리)이다 —
    전체 기준이면 작업표시줄에 덮여 12px 만 남는다.
    """
    try:
        import ctypes
        from ctypes import wintypes

        rect = wintypes.RECT()
        # SPI_GETWORKAREA = 0x0030
        ok = ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
        if ok:
            left, top, right, bottom = rect.left, rect.top, rect.right, rect.bottom
        else:
            raise OSError
    except Exception:  # noqa: BLE001
        try:
            import ctypes

            user32 = ctypes.windll.user32
            left, top = 0, 0
            right, bottom = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        except Exception:  # noqa: BLE001
            return x, y

    # 창이 화면보다 크면 위/왼쪽을 맞춘다
    x = left if w >= right - left else max(left, min(x, right - w))
    y = top if h >= bottom - top else max(top, min(y, bottom - h))
    return x, y


# ---------------------------------------------------------------- 설정 저장


def load_state() -> dict:
    state = {
        "x": 60,
        "y": 60,
        "topmost": False,
        "dock": True,  # 슬림 바는 작업표시줄에 붙는 게 기본 (자유 위치로 끌면 꺼진다)
        "theme": "auto",  # auto(윈도우 설정 따름) / light / dark
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


def launch_command() -> tuple[str, str, str]:
    """(실행 파일, 인자, 작업 폴더) — 지금 이 프로그램을 다시 띄우는 방법.

    exe 로 묶으면 파이썬도 스크립트도 없다. 그때는 exe 자신이 곧 실행 파일이다.
    """
    if getattr(sys, "frozen", False):  # PyInstaller 로 묶인 상태
        exe = os.path.abspath(sys.executable)
        return exe, "", os.path.dirname(exe)
    pyw = sys.executable.replace("python.exe", "pythonw.exe")
    script = os.path.abspath(__file__)
    return pyw, f'"{script}"', os.path.dirname(script)


def autostart_points_here() -> bool | None:
    """등록된 바로가기가 지금 이 프로그램을 가리키는가. 없거나 못 읽으면 None."""
    if not os.path.exists(STARTUP_LNK):
        return None
    try:
        from win32com.client import Dispatch

        link = Dispatch("WScript.Shell").CreateShortCut(STARTUP_LNK)
        target, args, _ = launch_command()
        same_exe = os.path.normcase(link.TargetPath) == os.path.normcase(target)
        return same_exe and link.Arguments.strip() == args.strip()
    except Exception:  # noqa: BLE001
        return None


def repair_autostart() -> None:
    """자동 실행이 켜져 있는데 딴 것을 가리키면 지금 것으로 고쳐 쓴다.

    폴더를 옮기거나 exe 로 바꾸면 바로가기가 없어진 파일을 가리키게 되고,
    재부팅해도 아무 일이 일어나지 않는다 — 오류도 안 뜬다. 켜 둔 사람은
    고장난 줄도 모른다.
    """
    ok = autostart_points_here()
    if ok is False:
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

        target, args, workdir = launch_command()
        link = Dispatch("WScript.Shell").CreateShortCut(STARTUP_LNK)
        link.TargetPath = target
        link.Arguments = args
        link.WorkingDirectory = workdir
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
        fill=P.icon_text,
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
        misses = 0
        while not self.stopped:
            try:
                self.out.put(fetch())
                misses = 0
                delay = MIN_INTERVAL
            except ConnectionFailed as e:
                # 요청이 서버에 닿지도 않았으니 곧바로 다시 시도해도 rate limit 과 무관하다.
                # 랜선이 잠깐 빠진 것 때문에 5분을 '연결 실패' 로 앉아 있지 않게.
                self.out.put(e)
                misses += 1
                delay = min(MIN_INTERVAL, RETRY_FIRST * 2 ** (misses - 1))
            except UsageError as e:  # 429·5xx·로그인 만료 — 빨리 다시 물어도 소용없다
                self.out.put(e)
                delay = MIN_INTERVAL
            except Exception as e:  # noqa: BLE001  예상 못 한 형식 변경 등
                self.out.put(UsageError(str(e)))
                delay = MIN_INTERVAL
            self.wake.wait(delay)
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


def raise_above_taskbar(root: tk.Tk) -> None:
    """항상 위 창들 중에서도 맨 앞으로 올린다.

    작업표시줄도 '항상 위' 라서, 그냥 topmost 로 두면 작업표시줄이 위에 와서
    붙여 놓은 위젯이 가려진다. 작업표시줄은 조작할 때마다 스스로를 올리므로
    붙어 있는 동안은 주기적으로 다시 올려야 한다.
    """
    try:
        import win32con
        import win32gui

        hwnd = win32gui.GetParent(root.winfo_id()) or root.winfo_id()
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOPMOST,
            0,
            0,
            0,
            0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE,
        )
    except Exception:  # noqa: BLE001
        pass


def popup_menu_open() -> bool:
    """지금 화면에 열려 있는 팝업 메뉴가 있는가.

    붙여 둔 위젯을 계속 맨 앞으로 올리다 보면 **우클릭 메뉴까지 덮어 버린다.**
    메뉴가 떠 있는 동안에는 올리지 않는다. (#32768 은 윈도우 기본 메뉴 창)
    """
    try:
        import win32gui

        # FindWindow 는 다 쓰고 숨겨 둔 메뉴 창까지 찾아낸다 — 보이는 것만 센다
        handle = 0
        while True:
            handle = win32gui.FindWindowEx(0, handle, "#32768", None)
            if not handle:
                return False
            if win32gui.IsWindowVisible(handle):
                return True
    except Exception:  # noqa: BLE001
        return False


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
        self.warned = {"five": False, "week": False}
        self.height = 0
        self.alive = True
        self.last_usage: Usage | None = None
        self.last_error: Exception | None = None
        self.last_error_stamp = ""
        self.last_manual = 0.0
        self._dragging = False
        self._menu_open = False

        # 자동 핑(모닝 스타터) 상태 — _build_menu 가 참조하므로 그 전에 잡아 둔다
        self.ping_cfg = cooldown_ping.load_cfg()
        self.ping_out: queue.Queue = queue.Queue()
        self._ping_busy = False
        self._last_ping_dt = cooldown_ping._parse_iso(self.ping_cfg.get("last_ping"))

        # 폰으로 보내기 — 조회에 성공할 때마다 퍼센트만 릴레이 서버로 올린다
        self.push_cfg = cooldown_push.load_cfg()
        self.push_out: queue.Queue = queue.Queue()
        self._push_busy = False
        self.push_error = ""  # 마지막 전송 실패 사유 (성공하면 비운다)

        self.root = tk.Tk()
        # 숨긴 채로 만들고 run() 에서 편다. 시작 프로그램·바로가기로 띄우면 부모가
        # '최소화로 시작' 표시 상태를 넘기는 경우가 있어, withdraw → deiconify 를
        # 거쳐 저장된 위치·크기로 확실히 펴지게 한다.
        self.root.withdraw()
        # Tk 콜백에서 난 오류는 원래 stderr 로 나가는데, 콘솔이 없으면 그대로 증발한다.
        # (그림 그리다 한 번 어긋나면 그 뒤로 조용히 안 도는 식) — 블랙박스로 돌린다.
        self.root.report_callback_exception = lambda exc, val, tb: applog(
            "화면 오류\n" + "".join(traceback.format_exception(exc, val, tb)).rstrip()
        )
        self.applied_theme = set_palette(self.state["theme"])
        self.root.configure(bg=P.bg)

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
        self.root.after(STAY_TICK, self._stay_above)
        self.root.after(TICK * 1000, self._tick)
        self.root.after(THEME_TICK * 1000, self._theme_watch)
        self.root.after(3000, self._ping_tick)  # 첫 조회가 들어올 시간을 준 뒤 시작

    # -------------------------------------------------- 본체(스킨) 그리기
    def _build_body(self) -> None:
        if self.body is not None:
            self.body.destroy()
        self.body = tk.Frame(self.root, bg=P.bg)
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
            # 이미 이 디자인이다 — 슬림 바를 다시 고르면 작업표시줄로 되붙인다.
            # (자유 위치로 떼어 낸 걸 되돌리는 유일한 길. 붙이기 토글은 없앴다.)
            if self.skin.dockable and not self.state["dock"]:
                self.state["dock"] = True
                save_state(self.state)
                self.show_window()
            return
        self.state["skin"] = key
        self.skin = skins.make(key)
        # 붙일 수 있는 디자인(슬림 바)이면 자동으로 작업표시줄에 붙는다.
        # 아니면 저장된 자유 위치로 돌아간다.
        self.state["dock"] = self.skin.dockable
        save_state(self.state)
        self._build_body()
        self.height = 0  # 스킨마다 크기가 다르므로 다시 잰다
        self._replay()
        self.show_window()
        self.var_skin.set(self.skin.key)

    def switch_theme(self, kind: str) -> None:
        self.state["theme"] = kind
        save_state(self.state)
        self.var_theme.set(kind)
        self._apply_theme(force=True)

    def _apply_theme(self, force: bool = False) -> None:
        """색을 바꿔 끼우고 다시 그린다. 색은 만들 때 위젯에 박히므로 새로 그려야 한다."""
        picked = set_palette(self.state["theme"])
        if picked == self.applied_theme and not force:
            return
        self.applied_theme = picked
        self.root.configure(bg=P.bg)
        self._build_body()
        self._replay()
        self.show_window()
        if self.last_usage is not None:
            self.tray.icon = draw_icon(self.last_usage.five.pct)

    def _theme_watch(self) -> None:
        """윈도우의 밝기 설정을 따라간다 ('윈도우 설정 따름' 일 때만)."""
        try:
            if self.state["theme"] == "auto":
                self._apply_theme()
        except Exception:  # noqa: BLE001
            pass
        finally:
            if self.alive:
                self.root.after(THEME_TICK * 1000, self._theme_watch)

    def _replay(self) -> None:
        """새로 그린 스킨에 마지막 상태를 다시 먹인다."""
        if self.last_usage is not None:
            self.skin.show(self.last_usage, self._stamp(self.last_usage))
        if self.last_error is not None:
            # 오류가 난 시각을 그대로 쓴다. 지금 시각으로 찍으면 디자인만 바꿨는데
            # 방금 실패한 것처럼 보인다.
            self.skin.show_error(
                self._error_text(self.last_error),
                keep_values=self.last_usage is not None,
                stamp=self.last_error_stamp,
            )

    # -------------------------------------------------- 메뉴
    def _build_menu(self) -> None:
        self.var_topmost = tk.BooleanVar(self.root, bool(self.state["topmost"]))
        self.var_autostart = tk.BooleanVar(self.root, autostart_enabled())
        self.var_skin = tk.StringVar(self.root, self.skin.key)
        self.var_theme = tk.StringVar(self.root, self.state["theme"])
        self.var_ping = tk.BooleanVar(self.root, bool(self.ping_cfg.get("enabled")))
        self.var_push = tk.BooleanVar(self.root, bool(self.push_cfg.get("enabled")))

        # 메인 메뉴는 두 진입점으로 나눈다 — 하나의 앱이지만 기능은 직관적으로 분리.
        #   · 쿨다운 (사용량 표시): 위젯 모양·동작 (새로고침·디자인·밝기·붙이기·항상위)
        #   · 모닝 스타터 (자동 핑): 5시간 창을 앵커 시각에 맞춰 여는 기능
        # 공통(앱 전체)인 자동 실행·종료만 메인에 둔다.
        self.menu = tk.Menu(self.root, tearoff=0)

        # 게이지의 '지금쯤' 눈금이 무슨 뜻인지, 숫자와 판정까지 여기서 다 본다.
        self.menu.add_command(label="이번 주 사용 속도…", command=self.open_pace)
        self.menu.add_separator()

        # ---- 쿨다운 (사용량 표시) ----
        # '지금 새로고침' 항목은 뺀다 — 위젯을 클릭하면 새로고침되고 스피너가 돈다.
        cool = tk.Menu(self.menu, tearoff=0)

        design = tk.Menu(cool, tearoff=0)
        for cls in skins.SKINS:
            design.add_radiobutton(
                label=cls.name,
                value=cls.key,
                variable=self.var_skin,
                command=lambda k=cls.key: self.switch_skin(k),
            )
        cool.add_cascade(label="디자인", menu=design)

        theme = tk.Menu(cool, tearoff=0)
        for key, label in THEMES:
            theme.add_radiobutton(
                label=label,
                value=key,
                variable=self.var_theme,
                command=lambda k=key: self.switch_theme(k),
            )
        cool.add_cascade(label="밝기", menu=theme)

        # '작업표시줄에 붙이기' 는 따로 두지 않는다 — 디자인에서 '슬림 바' 를 고르면
        # 바로 작업표시줄에 붙고, 끌어 옮기면 그 자리에 남는다.
        cool.add_checkbutton(
            label="항상 위에 표시", variable=self.var_topmost, command=self.toggle_topmost
        )
        self.menu_cool = cool
        self.menu.add_cascade(label="쿨다운 (사용량 표시)", menu=cool)

        # ---- 모닝 스타터 ----
        # '핑' 같은 개발자 용어를 쓰지 않는다. 항목 이름이 곧 하는 일이 되게 한다.
        # 값(다음 시각·마지막 결과)은 메뉴에 나열하지 않는다 — 설정·기록 창에서 본다.
        ping = tk.Menu(self.menu, tearoff=0)
        ping.add_checkbutton(
            label="정한 시각마다 5시간 자동 시작",
            variable=self.var_ping,
            command=self.toggle_ping,
        )
        ping.add_separator()
        ping.add_command(label="지금 한 번 실행", command=self.send_ping_now)
        ping.add_command(label="시각 설정…", command=self.open_ping_times)
        ping.add_command(label="실행 기록…", command=self.open_ping_log)
        self.menu.add_cascade(label="모닝 스타터 (5시간 자동 시작)", menu=ping)

        # ---- 폰에서 보기 ----
        # 조회에 성공할 때마다 퍼센트만 릴레이 서버로 올린다. 폰 앱이 그걸 읽는다.
        phone = tk.Menu(self.menu, tearoff=0)
        phone.add_checkbutton(
            label="폰으로 보내기", variable=self.var_push, command=self.toggle_push
        )
        phone.add_separator()
        phone.add_command(label="폰 연결…", command=self.open_phone_link)
        self.menu.add_cascade(label="폰에서 보기 (앱·위젯)", menu=phone)

        # ---- 앱 공통 ----
        self.menu.add_separator()
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
                # default=True — 아이콘을 클릭(더블클릭 포함)하면 이게 실행된다
                pystray.MenuItem(
                    "위젯 앞으로",
                    lambda: self.commands.put("front"),
                    default=True,
                ),
                pystray.MenuItem("지금 새로고침", lambda: self.refresh_now()),
                pystray.MenuItem(
                    "이번 주 사용 속도", lambda: self.commands.put("pace")
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
        self._from = (e.x_root, e.y_root)
        self._dragging = True
        # 누른 순간 마스코트가 반응한다 (스킨이 지원하면). 끌기로 이어져도 무해하다.
        # _dx/_dy 는 창 기준 누른 자리 = 캔버스 좌표(창을 꽉 채우므로) — 마스코트를
        # 직접 찔렀는지 스킨이 이 값으로 판단한다.
        try:
            self.skin.react(self._dx, self._dy)
        except Exception:  # noqa: BLE001
            pass

    def _drag(self, e):
        self.root.geometry(f"+{e.x_root - self._dx}+{e.y_root - self._dy}")

    def _release(self, e):
        self._dragging = False
        # 그냥 한 번 누른 것과 끌어서 옮긴 것을 구분한다.
        start = getattr(self, "_from", (e.x_root, e.y_root))
        moved = max(abs(e.x_root - start[0]), abs(e.y_root - start[1]))
        docked = bool(self.state["dock"]) and self.skin.dockable

        # 붙여 둔 상태에서는 웬만큼 움직여도 '클릭'으로 본다.
        # 그냥 눌러 새로고침하려다 마우스가 몇 px 밀렸을 뿐인데 작업표시줄에서
        # 떨어져 위로 떠 버리는 걸 막는다 — UNDOCK_SLOP 안이면 제자리로 다시 붙인다.
        threshold = UNDOCK_SLOP if docked else DRAG_SLOP
        if moved < threshold:
            if docked:
                self._reassert_dock()  # 밀린 만큼 작업표시줄 자리로 다시 붙인다
            self.refresh_now()
            return

        # 확실히 끌어 옮겼다 — 자유 위치로 떼어 낸다. (다시 붙이려면 우클릭 메뉴에서)
        x, y = clamp_to_screen(
            self.root.winfo_x(), self.root.winfo_y(), self.skin.width, self.height
        )
        self.root.geometry(f"+{x}+{y}")
        self.state.update(x=x, y=y, dock=False)
        self.root.attributes("-topmost", bool(self.state["topmost"]))
        save_state(self.state)

    def _popup(self, e):
        self.var_topmost.set(bool(self.state["topmost"]))
        self.var_autostart.set(autostart_enabled())
        self.var_skin.set(self.skin.key)
        self.var_theme.set(self.state["theme"])
        self.var_ping.set(bool(self.ping_cfg.get("enabled")))
        # 메뉴가 떠 있는 동안에는 위젯을 위로 올리지 않는다 (올리면 메뉴를 덮는다)
        self._menu_open = True
        try:
            self.menu.tk_popup(e.x_root, e.y_root)
        finally:
            self._menu_open = False

    # -------------------------------------------------- 동작
    def refresh_now(self):
        # 연타해도 최소 간격은 지킨다 (수동 경로로 rate limit 규칙을 우회하지 않게)
        now = time.monotonic()
        if now - self.last_manual < MANUAL_FLOOR:
            # 너무 자주 눌렀다. 눌린 티(스피너)만 내고 조회는 하지 않는다 —
            # 아무 반응이 없으면 고장난 줄 안다.
            self._spin_once()
            return
        self.last_manual = now
        # 눌렀다는 티: 깜빡임(창 흐리기) 대신 오른쪽 위에 작은 스피너를 한 바퀴 돌린다.
        self._spin_once()
        self.poller.refresh_now()

    def _spin_once(self):
        """새로고침을 눌렀다는 표시 — 오른쪽 위 모서리에서 스피너를 한 바퀴 돌린다.
        스킨과 무관하게 root 위에 얹는 작은 캔버스 하나로 그린다. 색은 그릴 때 정한다."""
        try:
            sp = getattr(self, "_spinner", None)
            if sp is None:
                sp = tk.Canvas(self.root, width=16, height=16, highlightthickness=0, bd=0)
                self._spinner = sp
            sp.configure(bg=P.bg)
            sp.place(relx=1.0, rely=0.0, x=-7, y=7, anchor="ne")
            if getattr(self, "_spinning", False):
                return  # 이미 도는 중이면 겹쳐 시작하지 않는다
            self._spinning = True
            frames = 12  # 12칸 × 42ms ≈ 0.5초에 한 바퀴

            def step(n):
                if not self.alive:
                    return
                try:
                    sp.delete("all")
                    sp.create_oval(2, 2, 14, 14, outline=P.track, width=2)  # 배경 링
                    sp.create_arc(
                        2, 2, 14, 14, start=(90 - n * 30) % 360, extent=110,
                        style="arc", outline=P.title, width=2,  # 도는 조각(밝게)
                    )
                except tk.TclError:
                    self._spinning = False
                    return
                if n < frames:
                    self.root.after(42, lambda: step(n + 1))
                else:
                    self._spinning = False
                    try:
                        sp.place_forget()
                    except tk.TclError:
                        pass

            step(0)
        except Exception:  # noqa: BLE001
            pass

    def _clear_busy(self):
        self.root.attributes("-alpha", ALPHA)

    def toggle_topmost(self):
        self.state["topmost"] = not self.state["topmost"]
        self.root.attributes("-topmost", bool(self.state["topmost"]))
        self.var_topmost.set(bool(self.state["topmost"]))
        save_state(self.state)

    def toggle_autostart(self):
        want = not autostart_enabled()
        set_autostart(want)
        got = autostart_enabled()
        self.var_autostart.set(got)
        if got != want:
            # 시작 폴더에 못 쓰는 환경(정책·보안 솔루션)이다. 체크가 도로 풀려서
            # 눌러도 아무 일이 없는 것처럼 보이므로, 아예 잠가 이유를 드러낸다.
            self.menu.entryconfig("윈도우 켤 때 자동 실행", state="disabled")
        try:
            self.tray.update_menu()  # 트레이 쪽 체크는 스스로 갱신되지 않는다
        except Exception:  # noqa: BLE001
            pass

    def _remember_spot(self):
        """자유 위치를 저장한다. 붙어 있는 동안에는 저장하지 않는다 —
        작업표시줄 좌표가 원래 자리를 덮으면, 나중에 풀었을 때 12px 만 남는다."""
        if self.state["dock"] and self.skin.dockable:
            return
        self.state.update(x=self.root.winfo_x(), y=self.root.winfo_y())

    def bring_to_front(self):
        """트레이 아이콘을 눌렀을 때 — 숨어 있으면 꺼내고 맨 앞으로 올린다."""
        self.show_window()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.update_idletasks()
        docked = bool(self.state["dock"]) and self.skin.dockable
        if not (docked or self.state["topmost"]):
            # 잠깐 맨 위로 올렸다 내리면 '항상 위' 를 켜지 않고도 맨 앞에 선다.
            # 붙여 둔 상태에서는 내리면 안 된다 — 작업표시줄 뒤로 사라졌다 돌아온다.
            self.root.after(400, lambda: self.root.attributes("-topmost", False))

    def show_window(self):
        """창을 저장된 자리에 편다. 시작할 때와 다시 켤 때 모두 여기를 쓴다."""
        self.root.deiconify()
        self.root.overrideredirect(True)
        self.root.attributes("-alpha", ALPHA)
        self.root.update_idletasks()
        self.height = self.height or self.root.winfo_reqheight()

        docked = bool(self.state["dock"]) and self.skin.dockable
        spot = taskbar_slot(self.skin.width, self.height) if docked else None
        if spot is None:
            docked = False
            spot = clamp_to_screen(
                self.state["x"], self.state["y"], self.skin.width, self.height
            )
        # 작업표시줄 자체가 항상 위라, 그 위에 얹으려면 이쪽도 항상 위여야 한다
        self.root.attributes("-topmost", docked or bool(self.state["topmost"]))
        self.root.geometry(f"{self.skin.width}x{self.height}+{spot[0]}+{spot[1]}")
        round_corners(self.root)
        if docked:
            raise_above_taskbar(self.root)

    def quit(self):
        self.alive = False
        self._remember_spot()
        save_state(self.state)
        self.poller.stop()
        try:
            self.tray.stop()
        except Exception:  # noqa: BLE001
            pass
        applog("종료 — 메뉴")
        try:
            self.root.destroy()
        except tk.TclError:
            pass
        # 데몬 스레드(트레이·폴러·핑)가 살아 있는 채로 인터프리터를 정리하면 파이썬이
        # abort() 로 죽는다 — WER 에 c0000409 / FATAL_APP_EXIT 로 찍힌 그 크래시다.
        # 저장은 위에서 이미 끝냈으니 뒷정리를 건너뛰고 곧바로 끝낸다.
        os._exit(0)

    # -------------------------------------------------- 화면 갱신
    def _pump(self):
        """화면 갱신과 명령 처리. **여기서 예외가 새면 앱이 통째로 얼어붙는다** —
        다시 예약하는 줄까지 못 가면 갱신이 멈추고, 트레이의 '종료' 마저
        이 큐를 거치므로 작업 관리자로 죽여야 한다. 그래서 통째로 감싼다."""
        try:
            self._pump_once()
        except Exception:  # noqa: BLE001
            pass
        finally:
            if self.alive:
                try:
                    self.root.after(300, self._pump)
                except tk.TclError:  # 종료 중
                    pass

    def _pump_once(self):
        # 두 번째로 실행된 프로세스가 남긴 표시 — 새 창을 띄우는 대신 이쪽이 나선다
        if os.path.exists(SUMMON_PATH):
            try:
                os.remove(SUMMON_PATH)
            except OSError:
                pass
            self.bring_to_front()

        while True:
            try:
                cmd = self.commands.get_nowait()
            except queue.Empty:
                break
            {
                "quit": self.quit,
                "front": self.bring_to_front,
                "toggle_autostart": self.toggle_autostart,
                "pace": self.open_pace,
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

        while True:
            try:
                ok, detail, manual, when = self.ping_out.get_nowait()
            except queue.Empty:
                break
            self._on_ping_result(ok, detail, manual, when)

        while True:
            try:
                self.push_error = self.push_out.get_nowait()
            except queue.Empty:
                break

    @staticmethod
    def _stamp(usage: Usage) -> str:
        return usage.fetched_at.astimezone().strftime("%H:%M")

    @staticmethod
    def _error_text(err: Exception) -> str:
        # cooldown_core 가 이미 짧은 명사형으로 던진다 —
        # '로그인 안 됨' / '로그인 만료' / '연결 실패' / '요청 과다' / '형식 변경'
        return str(err) or "알 수 없는 오류"

    def _tick(self):
        """1분마다 마지막 값으로 다시 그린다. 남은 시간이 조회 시점에 굳어
        '1분 후' 라고 떠 있는 동안 이미 초기화가 끝나 있는 일을 막는다."""
        try:
            if self.last_usage is not None and self.last_error is None:
                self.skin.show(self.last_usage, self._stamp(self.last_usage))
        except Exception:  # noqa: BLE001
            pass
        finally:
            if self.alive:
                self.root.after(TICK * 1000, self._tick)

    def _stay_above(self):
        """붙어 있는 동안 작업표시줄에 가리지 않게 지킨다.

        작업표시줄은 눌릴 때마다 스스로를 맨 앞으로 올린다. 그때 가려지는 시간이
        곧 주기이므로 짧게 잡는다 — SetWindowPos 한 번이라 비용은 사실상 없다.
        다만 메뉴가 떠 있는 동안 올리면 그 메뉴를 덮어 버리므로 그때는 쉰다.
        """
        try:
            docked = self.state["dock"] and self.skin.dockable
            if docked and not self._menu_open and not popup_menu_open():
                raise_above_taskbar(self.root)
        except Exception:  # noqa: BLE001
            pass
        finally:
            if self.alive:
                self.root.after(STAY_TICK, self._stay_above)

    def _reassert_dock(self):
        """작업표시줄 아이콘이 늘거나 줄면 빈 자리가 옮겨간다 — 갱신할 때마다 다시 맞춘다."""
        # 끌고 있는 중이면 건드리지 않는다 (손 안에서 창이 작업표시줄로 튄다)
        if self._dragging or not (self.state["dock"] and self.skin.dockable):
            return
        spot = taskbar_slot(self.skin.width, self.height)
        if spot:
            self.root.geometry(
                f"{self.skin.width}x{self.height}+{spot[0]}+{spot[1]}"
            )

    def _show(self, usage: Usage):
        self.last_usage = usage
        self.last_error = None
        self._clear_busy()
        self.skin.show(usage, self._stamp(usage))
        self._reassert_dock()
        export(usage)
        self._start_push(usage)

        self.tray.icon = draw_icon(usage.five.pct)
        self.tray.title = self._tray_text(usage)[:127]

        # 5시간·주간을 따로 본다. 주간이 차면 며칠을 묶이므로 이쪽이 오히려 아프다.
        for key, limit in (("five", usage.five), ("week", usage.week)):
            if limit.pct is None:
                continue
            if limit.pct >= WARN_AT and not self.warned[key]:
                self.tray.notify(
                    f"{limit.label} 한도 {limit.pct:.0f}% 사용   {limit.left}",
                    "클로드 쿨다운",
                )
                self.warned[key] = True
            elif limit.pct < WARN_CLEAR:
                self.warned[key] = False

    def _tray_text(self, usage: Usage) -> str:
        parts = ["클로드 쿨다운"]
        for limit in (usage.five, usage.week):
            if limit.pct is not None:
                parts.append(f"{limit.label} {limit.pct:.0f}%  {limit.left}")
        # 좁은 스킨(슬림 바)에는 눈금만 서므로, 숫자는 여기서도 읽을 수 있게 한다
        p = pace(usage)
        if p is not None:
            parts.append(f"이번 주 지금쯤 {p.due:.0f}%  ·  {p.verdict}")
        if self.ping_cfg.get("enabled"):
            times = cooldown_ping.parse_times(self.ping_cfg["times"])
            nxt = cooldown_ping.predict_next(datetime.now(), times, self._five_resets_local())
            parts.append(f"다음 시작 {nxt:%H:%M}")
        return "\n".join(parts)

    def _show_error(self, err: Exception):
        self.last_error = err
        self.last_error_stamp = datetime.now().strftime("%H:%M")
        self._clear_busy()
        # 무엇이든 마지막으로 받은 값은 남긴다. 그 값이 언제 것인지는 기준 시각이
        # 이미 보여 주므로, 지워 버리는 쪽이 오히려 정보를 없앤다.
        # (토큰은 8시간마다 만료돼서 자고 일어나면 매번 걸린다 — 그때마다 값이
        #  전부 사라지면 정작 궁금한 '얼마나 썼나' 를 볼 수가 없다)
        keep = self.last_usage is not None
        text = self._error_text(err)
        self.skin.show_error(text, keep, self.last_error_stamp)
        self.tray.icon = draw_icon(None)
        detail = f"{type(err).__name__}: {err}" if not str(err) else text
        self.tray.title = f"클로드 쿨다운 — {detail}"[:127]

    # -------------------------------------------------- 자동 핑 (모닝 스타터)
    def _five_resets_local(self) -> datetime | None:
        """지금 5시간 창이 풀리는 시각(로컬, naive). 창이 없으면 None.
        응답의 resets_at 은 UTC(aware)라 로컬 naive 로 바꿔 스케줄 계산과 맞춘다."""
        u = self.last_usage
        if u is None or u.five.resets_at is None:
            return None
        try:
            return u.five.resets_at.astimezone().replace(tzinfo=None)
        except (ValueError, OSError):
            return None

    def _ping_tick(self):
        """앵커 시각이 됐고 창이 비어 있으면 핑을 쏜다. _pump 와 달리 20초마다.
        여기서 예외가 새도 다음 예약까지는 가야 하므로 통째로 감싼다."""
        try:
            cfg = self.ping_cfg
            if (
                cfg.get("enabled")
                and not self._ping_busy
                and self.last_usage is not None  # 창 상태를 모르면 함부로 쏘지 않는다
            ):
                now = datetime.now()
                times = cooldown_ping.parse_times(cfg["times"])
                if cooldown_ping.should_ping_now(
                    now, times, self._five_resets_local(), self._last_ping_dt
                ):
                    self._start_ping(anchor_now=now)
        except Exception:  # noqa: BLE001
            pass
        finally:
            if self.alive:
                self.root.after(PING_TICK * 1000, self._ping_tick)

    def _start_ping(self, anchor_now: datetime | None = None, manual: bool = False):
        """핑 전송을 백그라운드 스레드에서 시작한다. Tk 스레드를 막지 않게."""
        if self._ping_busy:
            return
        self._ping_busy = True
        # 자동 핑은 같은 앵커에 두 번 쏘지 않도록 낙관적으로 지금을 마지막으로 세운다.
        # (실패하면 이 앵커는 건너뛴다 — 다음 앵커가 다시 정렬한다)
        if not manual and anchor_now is not None:
            self._last_ping_dt = anchor_now

        def worker():
            ok, detail = cooldown_ping.send_ping(self.ping_cfg)
            self.ping_out.put((ok, detail, manual, datetime.now()))

        threading.Thread(target=worker, daemon=True).start()

    def _on_ping_result(self, ok: bool, detail: str, manual: bool, when: datetime):
        self._ping_busy = False
        self.ping_cfg["last_result"] = (
            f"{when:%H:%M} " + ("성공 · " if ok else "실패 · ") + detail
        )
        if ok and not manual:
            self.ping_cfg["last_ping"] = when.isoformat()
            self._last_ping_dt = when
        cooldown_ping.save_cfg(self.ping_cfg)
        if ok:
            self.poller.refresh_now()  # 창이 열렸으니 위젯 숫자를 곧바로 갱신
        else:
            try:
                reason = cooldown_ping.friendly_error(detail)
                self.tray.notify(f"자동 시작 실패 · {reason}", "클로드 쿨다운")
            except Exception:  # noqa: BLE001
                pass

    def toggle_ping(self):
        self.ping_cfg["enabled"] = not self.ping_cfg.get("enabled")
        cooldown_ping.save_cfg(self.ping_cfg)
        self.var_ping.set(bool(self.ping_cfg["enabled"]))

    def send_ping_now(self):
        """지금 한 번 쏜다 (테스트/즉시 창 열기). 앵커 정렬과 무관."""
        self._start_ping(manual=True)

    # -------------------------------------------------- 폰으로 보내기
    def toggle_push(self):
        self.push_cfg["enabled"] = not self.push_cfg.get("enabled")
        cooldown_push.save_cfg(self.push_cfg)
        self.var_push.set(bool(self.push_cfg["enabled"]))
        if self.push_cfg["enabled"] and self.last_usage is not None:
            self._start_push(self.last_usage)  # 켜자마자 한 번 올려 폰이 바로 받게

    def _start_push(self, usage: Usage) -> None:
        """퍼센트만 릴레이 서버로. 네트워크는 별도 스레드 — Tk 를 붙잡으면 위젯이 언다."""
        if self._push_busy or not cooldown_push.ready(self.push_cfg):
            return
        self._push_busy = True

        def worker():
            try:
                cooldown_push.push(usage, self.push_cfg)
                self.push_out.put("")
            except Exception as e:  # noqa: BLE001
                self.push_out.put(str(e) or "전송 실패")
            finally:
                self._push_busy = False

        threading.Thread(target=worker, daemon=True).start()

    def open_phone_link(self):
        """폰 연결 — 서버 주소를 넣고, 폰 앱이 찍을 QR 을 본다."""
        try:
            top, body = self._open_panel("폰 연결")
            wrap = tk.Frame(body, bg=P.bg)
            wrap.pack(fill="both", expand=True, padx=PANEL_PAD, pady=(4, PANEL_PAD))
            width = 300

            row = tk.Frame(wrap, bg=P.bg)
            row.pack(fill="x")
            tk.Label(
                row, text="서버 주소", bg=P.bg, fg=P.label, font=(KR, 9)
            ).pack(side="left", padx=(0, 8))
            entry = tk.Entry(
                row,
                bg=P.track,
                fg=P.title,
                insertbackground=P.title,
                relief="flat",
                highlightthickness=0,
                font=(NUM, 9),
            )
            entry.pack(side="left", fill="x", expand=True, ipady=4)
            entry.insert(0, self.push_cfg.get("url") or "")

            hold = tk.Frame(wrap, bg=P.bg)  # QR 또는 안내가 들어가는 자리
            hold.pack(fill="x", pady=(12, 0))

            state = tk.Label(wrap, text="", bg=P.bg, fg=P.faint, font=(KR, 8), anchor="w")
            state.pack(fill="x", pady=(10, 0))

            def render():
                for child in hold.winfo_children():
                    child.destroy()
                uri = cooldown_push.pair_uri(self.push_cfg)
                img = cooldown_push.qr_image(uri)
                if img is not None:
                    photo = ImageTk.PhotoImage(img)
                    lbl = tk.Label(hold, image=photo, bg=P.bg, bd=0)
                    lbl.image = photo  # 참조를 잡아 두지 않으면 지워져 빈칸이 된다
                    lbl.pack()
                    tk.Label(
                        hold, text="폰 앱에서 QR 스캔", bg=P.bg, fg=P.sub, font=(KR, 9)
                    ).pack(pady=(8, 0))
                elif uri:
                    # qrcode 가 없어 그림을 못 만든다 — 폰에 손으로 넣을 값을 보여 준다
                    tk.Label(
                        hold,
                        text=cooldown_push.read_url(self.push_cfg),
                        bg=P.bg,
                        fg=P.sub,
                        font=(NUM, 8),
                        wraplength=width - PANEL_PAD * 2,
                        justify="left",
                    ).pack(anchor="w")
                else:
                    tk.Label(
                        hold,
                        text="주소를 넣으면 QR 이 나와요.",
                        bg=P.bg,
                        fg=P.faint,
                        font=(KR, 9),
                    ).pack(anchor="w")

                when = cooldown_push.last_ok_at(self.push_cfg)
                if self.push_error:
                    state.config(text=f"마지막 전송 실패 · {self.push_error}", fg=P.red)
                elif when:
                    state.config(text=f"마지막 전송  {self._friendly_time(when)}", fg=P.faint)
                else:
                    state.config(text="아직 보낸 적이 없어요.", fg=P.faint)
                self._refit_panel(top, width)

            def save():
                url = cooldown_push.normalize_url(entry.get())
                entry.delete(0, "end")
                entry.insert(0, url)
                self.push_cfg["url"] = url
                # 주소를 넣었다는 건 보내겠다는 뜻이다 — 체크박스를 따로 켜게 하지 않는다
                self.push_cfg["enabled"] = bool(url)
                cooldown_push.save_cfg(self.push_cfg)
                self.var_push.set(bool(self.push_cfg["enabled"]))
                render()
                if self.last_usage is not None:
                    self._start_push(self.last_usage)

            def regen():
                self.push_cfg["key"] = cooldown_push.new_key()
                self.push_cfg["last_ok"] = ""
                cooldown_push.save_cfg(self.push_cfg)
                self.push_error = ""
                render()
                if self.last_usage is not None:
                    self._start_push(self.last_usage)

            entry.bind("<Return>", lambda _e: save())

            buttons = tk.Frame(wrap, bg=P.bg)
            buttons.pack(fill="x", pady=(14, 0))
            self._themed_button(buttons, "저장", save, primary=True).pack(side="right")
            self._themed_button(buttons, "키 바꾸기", regen).pack(side="right", padx=(0, 8))

            render()
            self._finalize_panel(top, width)
            entry.focus_set()
        except Exception:  # noqa: BLE001
            pass

    # -------------------------------------------------- 이번 주 사용 속도
    def open_pace(self):
        """주간 한도를 '지금쯤 얼마나 썼어야 하나' 와 견줘 보여 준다.

        주간 창은 달력 주가 아니라 초기화 시각에서 7일 뺀 순간부터다 — 창이 흐른
        만큼이 곧 알맞은 사용률이고, 게이지의 눈금이 그 자리다.
        """
        W = 300
        try:
            top, body = self._open_panel("이번 주 사용 속도")
            wrap = tk.Frame(body, bg=P.bg)
            wrap.pack(fill="both", expand=True, padx=PANEL_PAD, pady=(2, PANEL_PAD))
            inner = W - PANEL_PAD * 2

            p = pace(self.last_usage) if self.last_usage is not None else None
            if p is None:
                tk.Label(
                    wrap,
                    text="주간 한도 값을 아직 못 받았어요.",
                    bg=P.bg,
                    fg=P.faint,
                    font=(KR, 9),
                ).pack(anchor="w", pady=16)
                self._finalize_panel(top, W)
                return

            tk.Label(
                wrap, text=p.verdict, bg=P.bg, fg=pace_color(p.level),
                font=(KR, 16, "bold"),
            ).pack(anchor="w")

            # 위젯 게이지와 같은 그림 — 채운 색이 눈금을 앞질렀으면 빨리 쓰는 중
            bar = tk.Canvas(
                wrap, width=inner, height=10, bg=P.bg, highlightthickness=0, bd=0
            )
            bar.pack(fill="x", pady=(10, 14))
            bar.create_rectangle(0, 0, inner, 10, fill=P.track, width=0)
            bar.create_rectangle(0, 0, inner * p.used / 100, 10, fill=tone(p.used), width=0)
            x = mark_x(p.due, inner)
            bar.create_rectangle(x, 0, x + MARK_W, 10, fill=P.title, width=0)

            self._pair(wrap, "지금쯤", f"{p.due:.0f}%", P.sub)
            self._pair(wrap, "지금", f"{p.used:.0f}%", tone(p.used))

            tk.Frame(wrap, bg=P.line, height=1).pack(fill="x", pady=(10, 8))

            if p.projected is not None:
                self._pair(
                    wrap, "이 속도면 주 끝", f"{min(999, p.projected):.0f}%",
                    pace_color(p.level),
                )
            per = p.per_day
            if per is not None:
                self._pair(wrap, f"남은 {int(p.days_left)}일 · 하루", f"{per:.0f}%", P.sub)
            else:
                hours = int(p.left_sec // 3600)
                self._pair(
                    wrap, f"남은 {hours}시간", f"{max(0.0, 100 - p.used):.0f}%", P.sub
                )
            if p.runout is not None:
                self._pair(wrap, "다 쓰는 때", self._when_text(p.runout), P.red)
            reset = self.last_usage.week.resets_at
            if reset is not None:
                self._pair(wrap, "초기화", self._when_text(reset), P.sub)

            self._finalize_panel(top, W)
        except Exception:  # noqa: BLE001
            pass

    @staticmethod
    def _pair(parent: tk.Misc, label: str, value: str, color: str) -> None:
        """왼쪽 이름 · 오른쪽 값 한 줄."""
        row = tk.Frame(parent, bg=P.bg)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, bg=P.bg, fg=P.label, font=(KR, 9)).pack(side="left")
        tk.Label(row, text=value, bg=P.bg, fg=color, font=(KR, 9, "bold")).pack(
            side="right"
        )

    @staticmethod
    def _when_text(when: datetime) -> str:
        """'8/02(토) 09:12' — 응답은 UTC 라 로컬로 돌려서 보여 준다."""
        try:
            t = when.astimezone()
        except (ValueError, OSError):
            return ""
        return f"{t.month}/{t.day:02d}({'월화수목금토일'[t.weekday()]}) {t:%H:%M}"

    # -------------------------------------------------- 위젯과 같은 결의 팝업
    # 팝업도 본체 위젯과 똑같이: 테두리 없는 둥근 창 + 왼쪽 액센트 바 + 볼드 제목,
    # 드래그로 이동, ✕·Esc 로 닫기. OS 창틀을 쓰지 않아 카드 스킨과 한 몸처럼 보인다.
    def _open_panel(self, title: str):
        """(top, body) 를 돌려준다. body 에 내용을 채운 뒤 _finalize_panel(top, w) 호출."""
        top = tk.Toplevel(self.root)
        top.withdraw()
        top.overrideredirect(True)
        top.configure(bg=P.bg)
        top.attributes("-topmost", True)

        head = tk.Frame(top, bg=P.bg)
        head.pack(fill="x")
        accent = tk.Frame(head, bg=P.green, width=3)  # 카드 머리말의 액센트 바와 같은 결
        accent.pack(side="left", fill="y")
        pad = tk.Frame(head, bg=P.bg)
        pad.pack(side="left", fill="x", expand=True, padx=(PANEL_PAD - 3, PANEL_PAD), pady=(14, 10))
        title_lbl = tk.Label(pad, text=title, bg=P.bg, fg=P.title, font=(KR, 10, "bold"))
        title_lbl.pack(side="left")
        close = tk.Label(pad, text="✕", bg=P.bg, fg=P.faint, font=(KR, 11), cursor="hand2")
        close.pack(side="right")
        close.bind("<Button-1>", lambda _e: top.destroy())
        close.bind("<Enter>", lambda _e: close.config(fg=P.title))
        close.bind("<Leave>", lambda _e: close.config(fg=P.faint))

        body = tk.Frame(top, bg=P.bg)
        body.pack(fill="both", expand=True)

        # 제목표시줄이 없으니 머리말을 잡고 끌어 옮긴다
        self._bind_panel_drag(top, head, pad, title_lbl, accent)
        top.bind("<Escape>", lambda _e: top.destroy())
        top.focus_set()
        return top, body

    def _bind_panel_drag(self, top: tk.Toplevel, *widgets: tk.Misc) -> None:
        st = {"x": 0, "y": 0}

        def press(e):
            st["x"] = e.x_root - top.winfo_x()
            st["y"] = e.y_root - top.winfo_y()

        def drag(e):
            top.geometry(f"+{e.x_root - st['x']}+{e.y_root - st['y']}")

        for w in widgets:
            w.bind("<Button-1>", press)
            w.bind("<B1-Motion>", drag)

    def _finalize_panel(self, top: tk.Toplevel, width: int, grab: bool = False) -> None:
        """내용을 다 채운 뒤 크기를 재고 위젯 옆에 띄운다."""
        top.update_idletasks()
        height = top.winfo_reqheight()
        x, y = clamp_to_screen(
            self.root.winfo_x() + 28, self.root.winfo_y() + 28, width, height
        )
        top.geometry(f"{width}x{height}+{x}+{y}")
        top.deiconify()
        round_corners(top)  # 본체와 같은 둥근 모서리
        if grab:
            try:
                top.grab_set()
            except tk.TclError:
                pass

    def _refit_panel(self, top: tk.Toplevel, width: int) -> None:
        """내용이 바뀌어(경고문 표시·행 추가/삭제) 높이가 달라지면 창을 다시 잰다.
        보더리스 고정 크기 창이라 이걸 안 하면 늘어난 내용이 창 밖으로 잘린다.
        아직 안 띄운(withdraw) 상태면 _finalize_panel 이 위치를 잡을 때까지 건드리지 않는다."""
        try:
            if not top.winfo_ismapped():
                return
            top.update_idletasks()
            height = top.winfo_reqheight()
            x, y = clamp_to_screen(top.winfo_x(), top.winfo_y(), width, height)
            top.geometry(f"{width}x{height}+{x}+{y}")
        except tk.TclError:
            pass

    def _themed_button(self, parent, text, command, primary=False) -> tk.Button:
        """팔레트 색을 입힌 납작한 버튼. primary 는 초록 강조."""
        if primary:
            bg, fg, active = P.green, P.bg, P.green
        else:
            bg, fg, active = P.track, P.title, P.line
        return tk.Button(
            parent,
            text=text,
            command=command,
            width=7,
            bg=bg,
            fg=fg,
            activebackground=active,
            activeforeground=fg,
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            padx=10,
            pady=5,
            font=(KR, 9, "bold") if primary else (KR, 9),
        )

    @staticmethod
    def _friendly_time(when: datetime) -> str:
        """'오늘 00:04' / '어제 23:33' / '07/26 14:00' — 사람이 읽는 시각."""
        today = datetime.now().date()
        day = when.date()
        hm = when.strftime("%H:%M")
        if day == today:
            return f"오늘 {hm}"
        if (today - day).days == 1:
            return f"어제 {hm}"
        return when.strftime("%m/%d ") + hm

    def open_ping_log(self):
        """실행 기록 — 로그 원문 대신 성공/실패 점과 사람이 읽는 시각으로 보여 준다."""
        try:
            entries = cooldown_ping.read_log_entries(40)
            top, body = self._open_panel("실행 기록")
            wrap = tk.Frame(body, bg=P.bg)
            wrap.pack(fill="both", expand=True, padx=PANEL_PAD, pady=(4, PANEL_PAD))

            if not entries:
                tk.Label(
                    wrap,
                    text="아직 실행된 적이 없어요.",
                    bg=P.bg,
                    fg=P.faint,
                    font=(KR, 9),
                ).pack(anchor="w", pady=16)
            else:
                shown = list(reversed(entries))[:14]
                for when, ok, detail in shown:
                    r = tk.Frame(wrap, bg=P.bg)
                    r.pack(fill="x", pady=3)
                    tk.Label(
                        r,
                        text="●",
                        bg=P.bg,
                        fg=(P.green if ok else P.red),
                        font=(KR, 8),
                    ).pack(side="left", padx=(0, 9))
                    tk.Label(
                        r,
                        text=self._friendly_time(when),
                        bg=P.bg,
                        fg=P.title,
                        font=(KR, 9),
                        width=11,
                        anchor="w",
                    ).pack(side="left")
                    tk.Label(
                        r,
                        text="실행됨" if ok else cooldown_ping.friendly_error(detail),
                        bg=P.bg,
                        fg=(P.sub if ok else P.red),
                        font=(KR, 9),
                        anchor="w",
                    ).pack(side="left")
                if len(entries) > 14:
                    tk.Label(
                        wrap,
                        text="· 최근 14개만 표시",
                        bg=P.bg,
                        fg=P.faint,
                        font=(KR, 8),
                    ).pack(anchor="w", pady=(8, 0))
            self._finalize_panel(top, 300)
        except Exception:  # noqa: BLE001
            pass

    def open_ping_times(self):
        """시각 설정 — 알람처럼 시:분 스테퍼(▲▼·스크롤)로 조절, 추가/삭제(✕).
        시각들은 5시간 1분 이상 벌어져 있어야 저장된다."""
        W = 300
        try:
            top, body = self._open_panel("모닝 스타터 · 시각")
            tk.Label(
                body,
                text="이 시각마다 5시간 자동 시작",
                bg=P.bg,
                fg=P.label,
                font=(KR, 8),
                anchor="w",
            ).pack(fill="x", padx=PANEL_PAD, pady=(0, 2))
            tk.Label(
                body,
                text="간격은 최소 5시간 1분 · 하루 최대 4개",
                bg=P.bg,
                fg=P.faint,
                font=(KR, 8),
                anchor="w",
            ).pack(fill="x", padx=PANEL_PAD, pady=(0, 6))

            # 편집 중인 값 (원본). [[시, 분], ...] — 저장할 때만 정렬한다(편집 중 행이 안 튀게).
            parsed = cooldown_ping.parse_times(self.ping_cfg["times"])
            data = [[t.hour, t.minute] for t in parsed] or [[5, 0]]

            editor = tk.Frame(body, bg=P.bg)
            editor.pack(fill="x", padx=PANEL_PAD)
            # 경고문은 자리를 잡아 두려고 구분선 앞에 붙일 수 있게 미리 만든다.
            warn = tk.Label(
                body, text="", bg=P.bg, fg=P.red, font=(KR, 8), anchor="w",
                wraplength=W - PANEL_PAD * 2, justify="left",
            )
            sep = tk.Frame(body, bg=P.line, height=1)

            def add():
                if len(data) < cooldown_ping.MAX_TIMES:
                    data.append([12, 0])
                    render()

            def render():
                for w in editor.winfo_children():
                    w.destroy()
                for i in range(len(data)):
                    self._build_time_row(editor, data, i, render)
                # ＋ 버튼은 최대 개수 미만일 때만 보인다 (규칙을 버튼 유무로 알린다)
                if len(data) < cooldown_ping.MAX_TIMES:
                    add_btn = tk.Label(
                        editor, text="＋ 시각 추가", bg=P.bg, fg=P.green,
                        font=(KR, 9), cursor="hand2",
                    )
                    add_btn.pack(anchor="w", pady=(6, 0))
                    add_btn.bind("<Button-1>", lambda _e: add())
                self._refit_panel(top, W)  # 행이 늘거나 줄면 창 높이를 다시 잡는다

            def warn_show(text):
                warn.config(text=text)
                warn.pack(fill="x", padx=PANEL_PAD, pady=(4, 0), before=sep)
                self._refit_panel(top, W)  # 경고문이 잘리지 않게 창을 늘린다

            def save(_evt=None):
                items = sorted({f"{h:02d}:{m:02d}" for h, m in data})
                if not cooldown_ping.parse_times(items):
                    warn_show("시각을 하나 이상 남겨 주세요.")
                    return
                msg = cooldown_ping.gap_error(items)
                if msg:
                    warn_show(msg)
                    return
                self.ping_cfg["times"] = items
                cooldown_ping.save_cfg(self.ping_cfg)
                top.destroy()

            render()

            sep.pack(fill="x", padx=PANEL_PAD, pady=(12, 0))
            foot = tk.Frame(body, bg=P.bg)
            foot.pack(fill="x", padx=PANEL_PAD, pady=(10, 14))
            self._themed_button(foot, "저장", save, primary=True).pack(side="right")
            self._themed_button(foot, "취소", top.destroy).pack(side="right", padx=(0, 8))
            top.bind("<Return>", save)  # 엔터로도 저장 (버튼이 유일 경로가 아니게)
            self._finalize_panel(top, W, grab=True)
        except Exception:  # noqa: BLE001
            pass

    def _build_time_row(self, parent, data, i, render) -> None:
        """시각 한 줄 — 시:분을 스핀박스로. 숫자를 직접 타이핑, 화살표 클릭,
        화살표를 길게 누르면 빠르게, 숫자 위에서 스크롤 — 네 방법 다 된다."""
        row = tk.Frame(parent, bg=P.track)
        row.pack(fill="x", pady=3, ipady=4)

        def field(idx, hi):
            var = tk.StringVar(value=f"{data[i][idx]:02d}")

            def commit(*_a):
                # 타이핑/화살표/스크롤 무엇으로 바뀌든 data 에 반영. 범위 밖은 감는다.
                try:
                    v = int(var.get())
                except (ValueError, TypeError):
                    v = data[i][idx]  # 비었거나 숫자가 아니면 이전 값 유지
                data[i][idx] = v % (hi + 1)

            var.trace_add("write", commit)
            sb = tk.Spinbox(
                row,
                from_=0,
                to=hi,
                wrap=True,           # 23→00, 59→00 순환
                increment=1,
                textvariable=var,
                width=2,
                format="%02.0f",     # 화살표로 바꾸면 두 자리로
                justify="center",
                font=(NUM, 16, "bold"),
                bg=P.track,
                fg=P.title,
                buttonbackground=P.track,
                readonlybackground=P.track,
                disabledbackground=P.track,
                insertbackground=P.title,  # 커서 색
                relief="flat",
                bd=0,
                highlightthickness=0,
                repeatdelay=400,     # 길게 누르면
                repeatinterval=60,   # 이 간격으로 빠르게 반복
            )

            def reformat(_e=None):
                var.set(f"{data[i][idx]:02d}")  # 포커스 벗어나면 두 자리로 정돈

            sb.bind("<FocusOut>", reformat)
            sb.bind("<Return>", reformat)
            # 숫자 위에서 스크롤해도 오르내린다
            sb.bind(
                "<MouseWheel>",
                lambda e: sb.invoke("buttonup" if e.delta > 0 else "buttondown"),
            )
            return sb

        field(0, 23).pack(side="left", padx=(12, 0))
        tk.Label(row, text=":", bg=P.track, fg=P.faint, font=(NUM, 15, "bold")).pack(
            side="left", padx=3
        )
        field(1, 59).pack(side="left")

        # 삭제 (한 줄만 남으면 숨긴다 — 최소 한 개는 있어야 한다)
        if len(data) > 1:
            x = tk.Label(row, text="✕", bg=P.track, fg=P.faint, font=(KR, 10), cursor="hand2")
            x.pack(side="right", padx=12)
            x.bind("<Button-1>", lambda _e: (data.pop(i), render()))
            x.bind("<Enter>", lambda _e: x.config(fg=P.red))
            x.bind("<Leave>", lambda _e: x.config(fg=P.faint))

    def run(self):
        self.show_window()
        self.root.mainloop()


if __name__ == "__main__":
    # 두 번 실행해도 위젯이 둘로 늘지 않는다 — 이미 떠 있으면 그쪽을 앞으로 부른다.
    # (시작 프로그램 + 바로가기 + .bat 이 겹쳐 눌리기 쉽다)
    # 로그는 이 판정 뒤에 연다 — 겹쳐 눌린 프로세스가 로그를 어지럽히지 않게.
    if already_running():
        summon_running_instance()
        sys.exit(0)
    install_crash_log()
    applog("시작")
    App().run()
    applog("종료 — 창이 닫힘")  # quit() 을 안 거치고 mainloop 이 끝난 길
