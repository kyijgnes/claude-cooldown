"""
클로드 쿨다운 — 바탕화면 위젯 + 시작표시줄 아이콘 (Windows)
=============================================================
pip install -r ../requirements.txt

실행:  pythonw cooldown_app.py      (검은 콘솔 창 없이)
확인:  python  ../cooldown_core.py  (응답 원본 JSON)

- 시작표시줄 아이콘을 누르면 위젯이 맨 앞으로 나온다.
- 위젯은 드래그로 옮기고, 위치는 저장된다. 우클릭으로 메뉴.
- 우클릭 > 디자인 에서 모양을 바꾼다 (skins/ 폴더).
- 우클릭 > 앱 설정 > 윈도우 켤 때 자동 실행 을 켜면 시작 프로그램에 등록된다.
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
from tkinter import filedialog, messagebox

import pystray
from PIL import Image, ImageDraw, ImageFont, ImageTk

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from cooldown_core import (  # noqa: E402
    DAY_PP,
    MIN_INTERVAL,
    ConnectionFailed,
    LoginRequired,
    TokenStale,
    Usage,
    UsageError,
    fetch,
    pace,
    token_expiry,
    token_stale,
)

import cooldown_login  # noqa: E402
import cooldown_ping  # noqa: E402
import cooldown_push  # noqa: E402
import cooldown_remote  # noqa: E402
import cooldown_stats  # noqa: E402
import cooldown_update  # noqa: E402  [업데이트 대기] 클로드가 고쳐지면 지운다
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
# [업데이트 대기] 클로드 업데이트가 밀려 있는지 보는 간격. 남의 서버가 아니라 내 PC를
# 보는 것이라 자주 해도 무해하지만, 한 번에 0.6초쯤 걸리므로 5분이면 충분하다.
UPDATE_EVERY = 300
# [업데이트 대기] 자동 적용을 판마다 몇 번까지 · 실패한 뒤 얼마나 띄우고 다시 할지.
# **되풀이를 막는 빗장이자, 한 번 어긋났다고 하루를 버리지 않게 하는 여유다.**
AUTO_TRIES = 3
AUTO_RETRY_GAP = 1800  # 초 (30분)
DRAG_SLOP = 4  # 이만큼 안 움직였으면 '끌었다' 로 치지 않는다 (px)
UNDOCK_SLOP = 120  # 붙여 둔 상태에선 이만큼 넘게 끌어야 떼어 낸다 (그 안이면 클릭으로 보고 제자리로)
MANUAL_FLOOR = 15  # '지금 새로고침' 을 연타해도 이 간격은 지킨다 (초)
REVIVE_GAP = 600  # 토큰이 낡았을 때 조용히 되살려 보는 간격 (초)
REVIVE_TRIES = 2  # 연달아 이만큼 실패하면 자동 시도를 멈춘다 (사람이 누를 때까지)
TICK = 60  # 남은 시간을 다시 그리는 주기 (초)
PING_TICK = 20  # 자동 핑을 쏠 때가 됐는지 보는 주기 (초). 앵커 여유(GRACE_MIN)보다 촘촘히.
REMOTE_TICK = 30  # 원격 대기가 아직 살아 있는지 보는 주기 (초)
# 폰이 '켜 달라' 고 적어 뒀는지 릴레이에 물어보는 주기 (초).
# ★ 줄이지 말 것 — Upstash 무료는 월 50만 명령이고 사용량 중계만으로 이미 29%(20명)를
#   쓴다. 60초로 하면 20명 기준 한도를 넘긴다. 계산은 server/README.md.
REMOTE_POLL = 120
REMOTE_GIVEUP = 3  # 연달아 이만큼 못 붙으면 스스로 끈다 (안 될 일에 계속 프로세스를 띄우지 않는다)
PANEL_PAD = 18  # 팝업창 좌우 여백 (px). 카드 스킨의 PAD 와 맞춰 위젯과 같은 결로.
THEME_TICK = 4  # 윈도우 테마가 바뀌었는지 보는 주기 (초). 'auto' 일 때만 쓴다.
THEMES = (("auto", "윈도우 설정 따름"), ("light", "밝게"), ("dark", "어둡게"))
STAY_TICK = 250  # 붙어 있을 때 다시 맨 앞으로 올리는 주기 (ms). 가려지는 시간이 곧 이 값.
ALPHA = 0.96  # 평소 창 불투명도
BUSY_ALPHA = 0.78  # 새로고침 누른 직후
HOLD_MS = 340  # 이만큼 누르고 있으면 '꾹 누름' — 마스코트가 기를 모으기 시작한다
STATUS_BOX = 18  # 상태 점 + 새로고침 링을 담는 작은 캔버스 한 변 (px)
DOT_R = 2.0  # 상태 점 반지름 — 링(반지름 7) 안쪽에 넉넉히 들어가게 작게

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
        # [업데이트 대기] 조용할 때 알아서 껐다 켤지. **끔이 기본** — 남의 프로세스를
        # 죽이는 일이라 켜는 것은 사람이 정한다.
        "auto_update": False,
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


STABLE_EXE = "클로드 쿨다운.exe"  # build_exe 가 판 번호 없는 이름으로도 늘 남긴다


def stable_twin(exe: str) -> str:
    """옆에 있는 **판 번호 없는 쌍둥이 파일** 경로. 없거나 다른 것이면 준 것 그대로.

    ★ 자동 실행 바로가기가 `claude-cooldown-v0.15.exe` 를 가리키면, 판을 올리며
      그 파일을 지우는 순간 **없는 파일을 가리키는 바로가기**가 된다 — 다음 로그인에
      아무 일도 안 일어나고 오류도 안 뜬다. `repair_autostart` 는 앱이 떠야 도니까
      스스로 못 고친다. 이름이 안 바뀌는 쪽을 등록하면 그 구멍이 없어진다.
    두 파일은 `shutil.copy2` 로 복사한 것이라 크기·수정시각이 정확히 같다 —
    **그럴 때만** 바꾼다(예전에 만들어 두고 잊은 파일을 잘못 가리키지 않게).
    """
    twin = os.path.join(os.path.dirname(exe), STABLE_EXE)
    if os.path.normcase(twin) == os.path.normcase(exe):
        return exe
    try:
        here, there = os.stat(exe), os.stat(twin)
    except OSError:
        return exe
    same = here.st_size == there.st_size and abs(here.st_mtime - there.st_mtime) < 2
    return twin if same else exe


def launch_command() -> tuple[str, str, str]:
    """(실행 파일, 인자, 작업 폴더) — 지금 이 프로그램을 다시 띄우는 방법.

    exe 로 묶으면 파이썬도 스크립트도 없다. 그때는 exe 자신이 곧 실행 파일이다
    (단, 판 번호 없는 쌍둥이가 옆에 있으면 그쪽 — `stable_twin` 참고).
    """
    if getattr(sys, "frozen", False):  # PyInstaller 로 묶인 상태
        exe = os.path.abspath(sys.executable)
        return stable_twin(exe), "", os.path.dirname(exe)
    pyw = sys.executable.replace("python.exe", "pythonw.exe")
    script = os.path.abspath(__file__)
    return pyw, f'"{script}"', os.path.dirname(script)


def autostart_link() -> tuple[str, str] | None:
    """등록된 바로가기의 (가리키는 파일, 인자). 없거나 못 읽으면 None."""
    if not os.path.exists(STARTUP_LNK):
        return None
    try:
        from win32com.client import Dispatch

        link = Dispatch("WScript.Shell").CreateShortCut(STARTUP_LNK)
        return link.TargetPath, link.Arguments
    except Exception:  # noqa: BLE001
        return None


def autostart_points_here() -> bool | None:
    """등록된 바로가기가 지금 이 프로그램을 가리키는가. 없거나 못 읽으면 None."""
    link = autostart_link()
    if link is None:
        return None
    target, args, _ = launch_command()
    same_exe = os.path.normcase(link[0]) == os.path.normcase(target)
    return same_exe and link[1].strip() == args.strip()


def repair_autostart() -> None:
    """자동 실행 바로가기가 고장났으면 지금 것으로 고쳐 쓴다.

    폴더를 옮기거나 판을 올리면 바로가기가 **없어진 파일**을 가리키게 되고,
    재부팅해도 아무 일이 일어나지 않는다 — 오류도 안 뜬다. 켜 둔 사람은
    고장난 줄도 모른다.

    ★ **소스로 돌릴 때는 멀쩡한 exe 등록을 빼앗지 않는다.** 손보느라
      `python cooldown_app.py` 를 한 번 돌리면 바로가기가 조용히
      `pythonw + 스크립트` 로 바뀌어, 그 뒤로는 부팅 때 **exe 가 아니라 소스가**
      뜬다(파이썬을 옮기거나 지우면 그대로 먹통이고, 새 기능도 exe 에는 안 들어간다).
      바꾸는 건 사람이 메뉴로 할 일이다.
    """
    if autostart_points_here() is not False:
        return  # 등록이 아예 없거나(꺼 둠) 이미 맞다
    link = autostart_link()
    dangling = not os.path.exists(link[0] if link else "")
    if dangling or getattr(sys, "frozen", False):
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


def gil_held(lib: str):
    """호출하는 동안 GIL 을 놓지 않는 DLL 핸들 (창을 만지는 Win32 호출 전용).

    ★ 창을 건드리는 Win32 함수(SetWindowPos·EndMenu·DwmSetWindowAttribute…)는
    **부르는 그 자리에서** 창 프로시저로 메시지를 보내고, Tk 는 그 안에서 밀려
    있던 after 콜백을 실행한다. 그런데 `ctypes.windll` 과 pywin32 는 호출하는
    동안 GIL 을 놓으므로, 그 콜백이 **파이썬 스레드 상태가 없는 채로** 들어와
    `Fatal Python error: PyEval_RestoreThread` 로 앱이 통째로 죽는다
    (2026-08-03 02:43 실제 크래시 — 예외 0xC0000409, 로그에 아무 흔적도 안 남는다).
    `PyDLL` 은 GIL 을 안 놓으므로 그 콜백이 정상적으로 돈다.
    """
    dll = _GIL_DLL.get(lib)
    if dll is None:
        import ctypes

        dll = _GIL_DLL[lib] = ctypes.PyDLL(lib)
    return dll


_GIL_DLL: dict = {}


def raise_above_taskbar(root: tk.Tk) -> None:
    """항상 위 창들 중에서도 맨 앞으로 올린다.

    작업표시줄도 '항상 위' 라서, 그냥 topmost 로 두면 작업표시줄이 위에 와서
    붙여 놓은 위젯이 가려진다. 작업표시줄은 조작할 때마다 스스로를 올리므로
    붙어 있는 동안은 주기적으로 다시 올려야 한다.

    ★ 올리는 일은 **Tk 를 통해서** 한다 (`win32gui.SetWindowPos` 로 직접 부르지 말 것).
    pywin32 는 부르는 동안 GIL 을 놓는데, 그 사이 Tk 가 밀린 after 콜백을 실행하다
    앱이 통째로 죽는다 (`gil_held` 주석 참고 — 실제로 났던 크래시다). Tk 의 raise 는
    Tcl 안에서 같은 SetWindowPos 를 부르므로 그 문제가 없다.
    작업표시줄을 이기는 효과는 win32 방식과 같은 것으로 확인했다.
    """
    try:
        root.lift()
    except tk.TclError:
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


def fullscreen_over(root: tk.Tk) -> bool:
    """**전체화면 앱이 위젯이 있는 화면을 덮고 있는가** (영상·게임·발표).

    작업표시줄에 붙어 있으면 위젯도 '항상 위'라, 유튜브를 전체화면으로 켜도 그 위에
    남아 있었다. 그때는 잠시 물러나야 한다(`_stay_above` 가 topmost 를 내린다).

    - 판정은 **맨 앞 창이 제 모니터를 꽉 채우는가**로 한다. 바탕화면·작업표시줄은 뺀다
      (그것들도 화면 전체 크기라 안 빼면 늘 전체화면으로 보인다).
    - **위젯과 같은 모니터일 때만** 참이다 — 두 번째 화면에서 영상을 봐도 이쪽 위젯이
      사라지면 그게 더 이상하다.
    - 여기서 부르는 win32 함수들은 메시지를 돌리지 않으므로 GIL 을 놓아도 안전하다
      (창을 옮기는 `SetWindowPos` 만 위험하다 — `raise_above_taskbar` 주석 참고).
    """
    try:
        import ctypes  # ★ 이 파일은 ctypes 를 **함수 안에서** 들여온다 (모듈 전역에 없다)
        import win32api
        import win32con
        import win32gui

        # ① 윈도우 자신의 판단 — 알림을 띄워도 되는 상태인가.
        #    전체화면 게임(D3D)·발표 모드처럼 창 크기만으로는 못 잡는 것까지 잡아 준다.
        #    2 QUNS_BUSY(전체화면 앱) · 3 D3D 전체화면 · 4 발표 모드
        busy = ctypes.c_int(0)
        if ctypes.windll.shell32.SHQueryUserNotificationState(
                ctypes.byref(busy)) == 0 and busy.value in (2, 3, 4):
            return True

        # ② 맨 앞 창이 제 모니터를 꽉 채우는가 (바탕화면·작업표시줄은 뺀다)
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return False
        if win32gui.GetClassName(hwnd) in (
            "Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
        ):
            return False
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        screen = win32api.GetMonitorInfo(
            win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
        )["Monitor"]
        if (right - left < screen[2] - screen[0]
                or bottom - top < screen[3] - screen[1]):
            return False
        mine = win32api.MonitorFromPoint(
            (root.winfo_x() + root.winfo_width() // 2,
             root.winfo_y() + root.winfo_height() // 2),
            win32con.MONITOR_DEFAULTTONEAREST,
        )
        return win32api.GetMonitorInfo(mine)["Monitor"] == screen
    except Exception:  # noqa: BLE001  못 물어봤으면 하던 대로 둔다
        return False


def dismiss_menus() -> None:
    """열려 있는 팝업 메뉴를 닫는다.

    Tk 의 메뉴는 윈도우 기본 메뉴 창(#32768)이라 `unpost()` 로는 안 닫힌다.
    주인 창을 감추면 메뉴만 화면에 덩그러니 남으므로 직접 끝내 준다.
    """
    try:
        # 메뉴를 끝내면 그 자리에서 창 프로시저가 돈다 — GIL 을 쥔 채로 부른다
        gil_held("user32").EndMenu()
    except Exception:  # noqa: BLE001
        pass


def round_corners(root: tk.Tk) -> None:
    """윈도우 11 둥근 모서리. 안 되는 환경이면 조용히 넘어간다."""
    try:
        from ctypes import byref, c_int

        root.update_idletasks()
        # 모서리를 바꾸면 비클라이언트 영역이 다시 그려진다 — GIL 을 쥔 채로 부른다
        user32 = gil_held("user32")
        hwnd = user32.GetParent(root.winfo_id()) or root.winfo_id()
        gil_held("dwmapi").DwmSetWindowAttribute(hwnd, 33, byref(c_int(2)), 4)
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------- 앱


class App:
    def __init__(self):
        self.state = load_state()
        self.results: queue.Queue = queue.Queue()
        self.commands: queue.Queue = queue.Queue()
        self.warned = {"five": False, "week": False}
        # [업데이트 대기] 클로드 앱 업데이트가 실행 중인 세션을 죽이기 전에 알린다
        self.update_out: queue.Queue = queue.Queue()
        # ★ 결과도 큐로 돌려받는다. **작업 스레드에서 root.after 를 부르면 안 된다** —
        #   Tk 는 스레드 안전하지 않아 조용히 씹히거나 죽는다(실제로 씹혔다).
        self.update_done: queue.Queue = queue.Queue()
        self._update_pending: cooldown_update.Pending | None = None
        self._update_warned = ""  # 알림을 이미 띄운 대기 판 (판마다 한 번만)
        self._update_busy = False
        # ★ 판마다 **몇 번 해 봤나 · 마지막으로 언제 해 봤나**. 적용은 클로드를 죽이는
        #   일이라 5분마다 되풀이하면 밤새 앱이 사라진다(2026-08-14). 그렇다고 한 번에
        #   손을 떼면 잠깐 어긋난 것 하나로 **하루 종일 안 올라간다**(2026-08-19 에
        #   그랬다 — 09:28 에 한 번 실패하고 그날은 끝이었다). 그래서 사이를 넉넉히
        #   띄우고 몇 번만 한다(`AUTO_TRIES` · `AUTO_RETRY_GAP`).
        self._update_tries: dict[str, int] = {}
        self._update_last: dict[str, float] = {}
        self.height = 0
        self.alive = True
        self.last_usage: Usage | None = None
        self.last_error: Exception | None = None
        self.last_error_stamp = ""
        self.last_manual = 0.0
        self._dragging = False
        self._hold_job = None   # '꾹 누름' 판정 예약
        self._holding = False   # 지금 꾹 누르고 있는가
        self._menu_open = False
        # 지금 창에 걸어 둔 '항상 위' 값 — 전체화면일 때 내렸다가 끝나면 되돌린다
        self._topmost_now: bool | None = None
        self._behind = False    # 전체화면 앞에서 물러나 있는 중인가
        self._panels: list[tk.Toplevel] = []  # 열려 있는 팝업들 (한 번에 하나만 둔다)

        # 자동 핑(모닝 스타터) 상태 — _build_menu 가 참조하므로 그 전에 잡아 둔다
        self.ping_cfg = cooldown_ping.load_cfg()
        self.ping_out: queue.Queue = queue.Queue()
        self._ping_busy = False
        self._last_ping_dt = cooldown_ping._parse_iso(self.ping_cfg.get("last_ping"))
        # 앱이 떠서 처리한 가장 최근 앵커 / 컴퓨터 꺼짐 등으로 놓친 앵커 (자동 시작)
        self._last_anchor_dt = cooldown_ping._parse_iso(self.ping_cfg.get("last_anchor"))
        self._missed_dt = cooldown_ping._parse_iso(self.ping_cfg.get("last_missed"))
        # 마지막 자동 시작 실패 (시각, 까닭). 다음 성공·기능 끄기·실행 기록 열기로 지운다.
        # 껐다 켜면 사라진다 — 지난 실패는 '실행 기록' 이 갖고 있다.
        self._ping_fail: tuple[datetime, str] | None = None

        # 로그인(토큰) 되살리기 — 토큰은 발급 8시간 뒤 만료되고, 새로 발급하는 건
        # 클로드 코드 CLI 뿐이다. 낡으면 조용히 되살려 보고, 안 되면 클릭 한 번으로.
        self.login_out: queue.Queue = queue.Queue()
        self._revive_busy = False
        self._revive_at = 0.0  # 마지막 자동 시도 (monotonic)
        self._revive_fails = 0  # 연달아 실패한 횟수 — 쌓이면 자동 시도를 멈춘다
        self._login_state = ""  # cooldown_login 의 상태 낱말 (모르면 빈 문자열)
        self._login_account = ""  # 로그인된 계정 (알아냈을 때만)
        self._login_render = None  # 로그인 팝업이 떠 있으면 그걸 다시 그리는 함수

        # 폰으로 보내기 — 조회에 성공할 때마다 퍼센트만 릴레이 서버로 올린다
        self.push_cfg = cooldown_push.load_cfg()
        self.push_out: queue.Queue = queue.Queue()
        self._push_busy = False
        self.push_error = ""  # 마지막 전송 실패 사유 (성공하면 비운다)

        # 원격 대기 — 폰·웹에서 이 PC 에 새 세션을 열려면 `claude rc` 가 상주해야 한다.
        # 그러자고 검은 창을 하루 종일 켜 둘 까닭이 없어서 위젯이 대신 들고 있는다.
        self.remote_cfg = cooldown_remote.load_cfg()
        self.remote = cooldown_remote.Remote()
        self.remote_error = ""  # 마지막 실패 까닭 (성공하면 비운다)
        self._remote_fails = 0  # 연달아 못 붙은 횟수 — REMOTE_GIVEUP 이면 스스로 끈다
        # 폰에서 켜고 끄기 — 릴레이에 적힌 '원하는 상태' 를 REMOTE_POLL 마다 읽어 따라간다
        self.remote_out: queue.Queue = queue.Queue()
        self._remote_busy = False
        self._remote_poll_at = 0.0  # 마지막 물어본 때 (monotonic)
        self._remote_said = ""  # 릴레이에 마지막으로 적어 둔 상태 (같으면 다시 안 적는다)

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
        cooldown_stats.trim()  # 오래된 기록 덜어내기 — 켤 때 한 번이면 된다

        self.body: tk.Frame | None = None
        self.skin = skins.make(self.state["skin"])
        self._build_body()
        self._build_menu()

        self.poller = Poller(self.results)
        self.poller.start()
        self.tray = self._build_tray()
        threading.Thread(target=self.tray.run, daemon=True).start()
        # [업데이트 대기] 사용량 조회와 무관하므로 폴러에 얹지 않고 따로 돈다
        threading.Thread(target=self._update_watch, daemon=True).start()

        self.root.after(200, self._pump)
        self.root.after(STAY_TICK, self._stay_above)
        self.root.after(TICK * 1000, self._tick)
        self.root.after(THEME_TICK * 1000, self._theme_watch)
        self.root.after(3000, self._ping_tick)  # 첫 조회가 들어올 시간을 준 뒤 시작
        # 원격 대기는 사용량과 무관하므로 곧바로 — 켜 두기로 했으면 여기서 되살아난다
        self.root.after(1500, self._remote_tick)

    # -------------------------------------------------- 본체(스킨) 그리기
    def _build_body(self) -> None:
        if self.body is not None:
            self.body.destroy()
        self.body = tk.Frame(self.root, bg=P.bg)
        self.body.pack(fill="both", expand=True)
        self.skin.build(self.body)
        # ★★ 드래그·우클릭은 **창(toplevel)에만** 건다. tk 이벤트는 자식에서 창으로
        #   올라오므로 이것만으로 어느 자식을 눌러도 잡힌다 — 자식마다 또 걸면
        #   **한 번 누른 게 두 번 처리된다**(마스코트가 두 배로 튀고, 기절 누적도 두 배로
        #   쌓이고, 클릭 한 번에 반짝이가 터졌다. 2026-08-03 에 실제로 그러고 있었다).
        self._bind_drag(self.root)
        # 상태 점은 스킨 위에 얹는 별도 캔버스라 스킨을 다시 그릴 때마다 자리를 다시 잡는다.
        # (root 의 자식이라 _bind_drag 가 못 걸지만, 이벤트가 root 로 올라가 똑같이 동작한다)
        self._sync_status()

    def _bind_drag(self, widget: tk.Misc) -> None:
        """드래그·우클릭을 건다. **창에만 걸 것** — 자식에도 걸면 두 번 처리된다."""
        widget.bind("<Button-1>", self._press)
        widget.bind("<B1-Motion>", self._drag)
        widget.bind("<ButtonRelease-1>", self._release)
        widget.bind("<Button-3>", self._popup)

    def switch_skin(self, key: str) -> None:
        self._close_panels()  # 디자인을 바꾸면 옛 팝업(옛 색·자리)이 떠돌지 않게 닫는다
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
        self._close_panels()  # 밝기를 바꾸면 옛 색 팝업이 떠돌지 않게 닫는다
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
        self._apply_notice()

    # -------------------------------------------------- 메뉴
    def _build_menu(self) -> None:
        self.var_topmost = tk.BooleanVar(self.root, bool(self.state["topmost"]))
        self.var_autostart = tk.BooleanVar(self.root, autostart_enabled())
        self.var_skin = tk.StringVar(self.root, self.skin.key)
        self.var_theme = tk.StringVar(self.root, self.state["theme"])
        self.var_ping = tk.BooleanVar(self.root, bool(self.ping_cfg.get("enabled")))
        self.var_push = tk.BooleanVar(self.root, bool(self.push_cfg.get("enabled")))
        self.var_remote = tk.BooleanVar(self.root, bool(self.remote_cfg.get("enabled")))
        # [업데이트 대기]
        self.var_auto_update = tk.BooleanVar(
            self.root, bool(self.state.get("auto_update"))
        )

        # 메인 메뉴는 **갈래(하위 메뉴)로만** 이룬다 — 하나의 앱이지만 기능은 직관적으로 분리.
        #   · 사용량: 지금 이 창의 속도 · 쌓인 날들의 통계 (읽는 쪽)
        #   · 디자인: 스킨 넷을 곧바로 + 밝기·항상 위 (옛 이름 '쿨다운 (사용량 표시)')
        #   · 클로드 모닝 스타터: 5시간 창을 앵커 시각에 맞춰 여는 기능
        #   · 모바일: 릴레이 전송·페어링
        #   · 앱 설정: 로그인·자동 적용·자동 실행 (앱 전체에 걸리는 것)
        # 맨 아래 종료만 메인에 둔다.
        # ★ **갈래 이름에 괄호를 달지 않는다.** '쿨다운 (사용량 표시)' 처럼 이름이 안 통해서
        #   괄호로 풀어 줘야 한다면, 괄호를 붙일 게 아니라 **이름을 하는 일로 바꾼다**
        #   (폴더 전체 규칙: 설명이 필요하면 화면을 고친다).
        self.menu = tk.Menu(self.root, tearoff=0)

        # ---- 사용량 ----
        # 같은 물음('얼마나 썼나')에 답이 둘이라 한 갈래로 묶는다 —
        # 속도는 **지금 이 창**을, 통계는 **쌓인 날들**을 본다.
        used = tk.Menu(self.menu, tearoff=0)
        # 게이지의 '적정선' 눈금이 무슨 뜻인지, 숫자와 판정까지 여기서 다 본다.
        used.add_command(label="이번 주 사용 속도…", command=self.open_pace)
        # 지나간 기록으로 보는 쪽 — 날짜별·시간대별·5시간 창별
        used.add_command(label="사용량 통계…", command=self.open_stats)
        self.menu.add_cascade(label="사용량", menu=used)
        self.menu.add_separator()

        # ---- 디자인 ----
        # '지금 새로고침' 항목은 뺀다 — 위젯을 클릭하면 새로고침되고 스피너가 돈다.
        # ★ 스킨은 **이 갈래에 곧바로** 놓는다 — 안에 또 `디자인` 갈래를 두면
        #   `디자인 > 디자인 > 카드형` 이 되어 한 단계가 헛돈다.
        cool = tk.Menu(self.menu, tearoff=0)

        for cls in skins.SKINS:
            cool.add_radiobutton(
                label=cls.name,
                value=cls.key,
                variable=self.var_skin,
                command=lambda k=cls.key: self.switch_skin(k),
            )
        cool.add_separator()

        theme = tk.Menu(cool, tearoff=0)
        for key, label in THEMES:
            theme.add_radiobutton(
                label=label,
                value=key,
                variable=self.var_theme,
                command=lambda k=key: self.switch_theme(k),
            )
        cool.add_cascade(label="밝기", menu=theme)

        # '작업표시줄에 붙이기' 는 따로 두지 않는다 — 여기서 '작업표시줄 슬림 바' 를 고르면
        # 바로 작업표시줄에 붙고, 끌어 옮기면 그 자리에 남는다.
        cool.add_checkbutton(
            label="항상 위에 표시", variable=self.var_topmost, command=self.toggle_topmost
        )
        self.menu_cool = cool
        self.menu.add_cascade(label="디자인", menu=cool)

        # ---- 클로드 모닝 스타터 ----
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
        self.menu.add_cascade(label="클로드 모닝 스타터", menu=ping)

        # ---- 모바일 ----
        # 조회에 성공할 때마다 퍼센트만 릴레이 서버로 올린다. 폰 앱이 그걸 읽는다.
        phone = tk.Menu(self.menu, tearoff=0)
        phone.add_checkbutton(
            label="폰으로 보내기", variable=self.var_push, command=self.toggle_push
        )
        phone.add_separator()
        phone.add_command(label="폰 연결…", command=self.open_phone_link)
        self.menu.add_cascade(label="모바일", menu=phone)

        # ---- 클로드 코드 원격 ----
        # 폰이나 claude.ai/code 에서 **이 PC 에 새 세션을 열려면** `claude rc` 가
        # 상주해 있어야 한다. 그러자고 검은 창을 켜 둘 까닭이 없어 위젯이 들고 있는다.
        # 값(폴더·마지막 실패)은 메뉴에 나열하지 않는다 — 폴더 창과 알림에서 본다.
        rc = tk.Menu(self.menu, tearoff=0)
        rc.add_checkbutton(
            label="폰·웹에서 이 PC 에 세션 열기",
            variable=self.var_remote,
            command=self.toggle_remote,
        )
        rc.add_separator()
        rc.add_command(label="작업 폴더…", command=self.open_remote_folder)
        self.menu.add_cascade(label="클로드 코드 원격", menu=rc)

        # ---- 앱 설정 ----
        # 앱 전체에 걸리는 것들 — 위젯 모양(쿨다운)이 아니라 '이 프로그램이 어떻게 도는가'.
        conf = tk.Menu(self.menu, tearoff=0)
        # 위젯이 사용량을 읽을 수 있는지 · 막혔으면 여기서 잇는다
        conf.add_command(label="로그인 상태…", command=self.open_login)
        conf.add_separator()
        # [업데이트 대기] 이름은 **언제 도는지**까지만 — 몇 분인지는 안 적는다.
        # 옛 이름은 `작업 없고 자리 비면 … (45분·20분)` 이었는데 메뉴 한 줄이 너무 길었다.
        conf.add_checkbutton(
            label="자리 비면 클로드 업데이트 자동 적용",
            variable=self.var_auto_update,
            command=self.toggle_auto_update,
        )
        conf.add_checkbutton(
            label="윈도우 켤 때 자동 실행",
            variable=self.var_autostart,
            command=self.toggle_autostart,
        )
        self.menu_conf = conf
        self.menu.add_cascade(label="앱 설정", menu=conf)

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
                # [업데이트 대기] 대기 중일 때만 나타난다. 평소엔 없는 항목이다.
                pystray.MenuItem(
                    lambda item: self._update_menu_label(),
                    lambda: self.commands.put("apply_update"),
                    visible=lambda item: self._update_pending is not None,
                ),
                pystray.MenuItem("지금 새로고침", lambda: self.refresh_now()),
                pystray.MenuItem(
                    "이번 주 사용 속도", lambda: self.commands.put("pace")
                ),
                pystray.MenuItem("사용량 통계", lambda: self.commands.put("stats")),
                pystray.MenuItem("로그인 상태", lambda: self.commands.put("login")),
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
        self._close_panels()  # 위젯을 누르면(새로고침·드래그) 떠 있던 팝업을 닫는다
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
        # 그대로 누르고 있으면 '꾹 누름'으로 넘긴다 (마스코트가 기를 모은다)
        self._hold_job = self.root.after(
            HOLD_MS, lambda x=self._dx, y=self._dy: self._begin_hold(x, y)
        )

    def _begin_hold(self, x, y):
        self._hold_job = None
        if self._holding or not self._dragging:
            return
        self._holding = True
        try:
            self.skin.hold(x, y)
        except Exception:  # noqa: BLE001
            pass

    def _end_hold(self):
        """누르기가 끝났거나(뗌) 끌기로 바뀌었다 — 꾹 누름을 접는다."""
        if getattr(self, "_hold_job", None) is not None:
            try:
                self.root.after_cancel(self._hold_job)
            except (tk.TclError, ValueError):
                pass
            self._hold_job = None
        if getattr(self, "_holding", False):
            self._holding = False
            try:
                self.skin.let_go()
            except Exception:  # noqa: BLE001
                pass

    def _drag(self, e):
        # 끌기 시작한 순간 꾹 누름은 접는다 (옮기려던 것이지 놀려던 게 아니다)
        start = getattr(self, "_from", (e.x_root, e.y_root))
        if max(abs(e.x_root - start[0]), abs(e.y_root - start[1])) > DRAG_SLOP:
            self._end_hold()
        self.root.geometry(f"+{e.x_root - self._dx}+{e.y_root - self._dy}")

    def _release(self, e):
        self._end_hold()
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
            # ★ **마스코트를 두드린 것은 새로고침이 아니다.** 박자 놀이로 수십 번을
            #   누르는데 그때마다 조회를 부르면(15초에 한 번씩이라도) 문서화도 안 된
            #   엔드포인트를 괜히 두드리게 된다. 마스코트 밖을 누르면 그대로 새로고침.
            try:
                played = self.skin.absorbed()
            except Exception:  # noqa: BLE001
                played = False
            if played:
                return
            # ★ 로그인이 막혀 있으면 새로고침은 어차피 헛일이다 (토큰이 낡은 걸
            #   이미 안다) — 그 클릭을 **고칠 수 있는 곳**으로 보낸다. 그래서
            #   위젯이 '눌러서 로그인 잇기' 라고 적어 둘 수 있다.
            if isinstance(self.last_error, LoginRequired):
                self.open_login()
            else:
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

    # ---- 상태 점 + 새로고침 링 (한 자리를 나눠 쓴다) ----
    # 스킨이 `status_spot()` 으로 자리를 알려 주면 그 한가운데에 **상태 점**을 늘 띄우고,
    # 새로고침을 누르면 **그 점 둘레로 링이 한 바퀴** 돈다. 둘을 한 캔버스에 그려야
    # 겹쳐도 따로 놀지 않는다 (tk 위젯은 투명이 안 돼 포개면 아래가 가려진다).
    def _sync_status(self):
        """스킨이 바뀌거나 값·오류·테마가 바뀔 때 상태 캔버스를 제자리에 다시 놓는다."""
        try:
            spot = self.skin.status_spot()
        except Exception:  # noqa: BLE001
            spot = None
        box = getattr(self, "_status", None)
        if box is None:
            box = self._status = tk.Canvas(
                self.root, width=STATUS_BOX, height=STATUS_BOX,
                highlightthickness=0, bd=0,
            )
        self._status_dot = spot is not None
        try:
            if spot is None:
                # 점을 안 쓰는 스킨 — 링만 옛날처럼 오른쪽 위 구석에 잠깐 뜬다
                box.configure(bg=P.bg)
                box.place_forget()
            else:
                x, y, bg = spot
                box.configure(bg=bg)
                box.place(x=int(x), y=int(y), anchor="center")
                self._draw_status()
        except tk.TclError:
            pass

    def _draw_status(self, spin: int | None = None):
        """점(있으면)과 도는 링(새로고침 중일 때)을 한 캔버스에 그린다."""
        box = getattr(self, "_status", None)
        if box is None:
            return
        mid = STATUS_BOX / 2
        ring = STATUS_BOX / 2 - 2
        box.delete("all")
        if spin is not None:
            box.create_oval(
                mid - ring, mid - ring, mid + ring, mid + ring,
                outline=P.track, width=2,  # 배경 링
            )
            box.create_arc(
                mid - ring, mid - ring, mid + ring, mid + ring,
                start=(90 - spin * 30) % 360, extent=110,
                style="arc", outline=P.title, width=2,  # 도는 조각(밝게)
            )
        if not self._status_dot:
            return
        if self.last_error is not None:
            color = P.red
        elif self.last_usage is None:
            color = P.faint  # 아직 한 번도 못 받았다
        else:
            color = P.green
        box.create_oval(
            mid - DOT_R, mid - DOT_R, mid + DOT_R, mid + DOT_R, fill=color, width=0
        )

    def _spin_once(self):
        """새로고침을 눌렀다는 표시 — 상태 점 둘레로 링이 한 바퀴 돈다.
        점을 안 쓰는 스킨에서는 오른쪽 위 구석에 링만 잠깐 뜬다."""
        try:
            box = getattr(self, "_status", None)
            if box is None:
                self._sync_status()
                box = self._status
            if not self._status_dot:  # 구석에 잠깐 띄우는 옛 방식
                box.configure(bg=P.bg)
                box.place(relx=1.0, rely=0.0, x=-6, y=6, anchor="ne")
            if getattr(self, "_spinning", False):
                return  # 이미 도는 중이면 겹쳐 시작하지 않는다
            self._spinning = True
            frames = 12  # 12칸 × 42ms ≈ 0.5초에 한 바퀴

            def step(n):
                if not self.alive:
                    return
                try:
                    self._draw_status(spin=n)
                except tk.TclError:
                    self._spinning = False
                    return
                if n < frames:
                    self.root.after(42, lambda: step(n + 1))
                else:
                    self._spinning = False
                    try:
                        if self._status_dot:
                            self._draw_status()  # 링만 걷고 점은 남긴다
                        else:
                            box.place_forget()
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
        self._topmost_now = None   # 손으로 건드렸다 — 다음 tick 이 다시 맞춘다
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
            self.menu_conf.entryconfig("윈도우 켤 때 자동 실행", state="disabled")
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
        self._topmost_now = None   # 손으로 건드렸다 — 다음 tick 이 다시 맞춘다
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
        # ★ 원격 대기(claude rc)는 **일부러 안 끈다.** 폰에서 열어 둔 세션이 돌고 있을 수
        #   있어서, 위젯을 닫았다고 그걸 죽이면 사고다. 앱을 다시 켜면 PID 파일을 보고
        #   그 놈을 이어받는다(`Remote.adopt`). 끄는 것은 메뉴에서 사람이 정한다.
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
                "stats": self.open_stats,
                "login": self.open_login,
                "apply_update": self.apply_update,  # [업데이트 대기]
            }[cmd]()
            if cmd == "quit":
                return

        # [업데이트 대기] 감시 스레드가 넣어 둔 판정을 받는다
        while True:
            try:
                pending = self.update_out.get_nowait()
            except queue.Empty:
                break
            self._on_update_state(pending)

        # 폰이 릴레이에 적어 둔 '원하는 상태' — 물어본 스레드가 넣어 둔다
        while True:
            try:
                got = self.remote_out.get_nowait()
            except queue.Empty:
                break
            self._on_want(got)

        while True:
            try:
                auto, ok, detail, target = self.update_done.get_nowait()
            except queue.Empty:
                break
            self._on_update_done(auto, ok, detail, target)

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
                ok, state, account = self.login_out.get_nowait()
            except queue.Empty:
                break
            self._on_revive_result(ok, state, account)

        while True:
            try:
                self.push_error = self.push_out.get_nowait()
            except queue.Empty:
                break

    @staticmethod
    def _stamp(usage: Usage) -> str:
        return usage.fetched_at.astimezone().strftime("%H:%M")

    def _error_text(self, err: Exception) -> str:
        """위젯에 뜰 오류 한 마디. cooldown_core 가 이미 짧은 명사형으로 던진다 —
        '연결 실패' / '요청 과다' / '형식 변경'.

        **로그인 쪽만 여기서 갈아 끼운다** — 무엇이 잘못됐는지가 아니라 **무엇을 하면
        되는지**를 쓴다. 토큰이 낡은 건 로그아웃이 아니라 '한 번 이어 주면 되는' 일이라,
        옛 문구 '로그인 만료'(로그아웃된 줄 안다)를 되살리지 말 것.
        """
        if isinstance(err, LoginRequired):
            if self._revive_busy:
                return "로그인 잇는 중"
            if self._login_state == cooldown_login.NO_CLI:
                return "클로드 코드 없음"
            if self._login_state == cooldown_login.LOGGED_OUT:
                return "클로드 코드 로그인 필요"
            if isinstance(err, TokenStale):
                return "눌러서 로그인 잇기"
            return "클로드 코드 로그인 필요"
        return str(err) or "알 수 없는 오류"

    def _tick(self):
        """1분마다 마지막 값으로 다시 그린다. 남은 시간이 조회 시점에 굳어
        '1분 후' 라고 떠 있는 동안 이미 초기화가 끝나 있는 일을 막는다.

        ★ 로그인이 막혀 있는 동안에는 **토큰이 되살아났는지도 여기서 본다.** 자격
        파일을 읽는 것뿐이라 공짜고(조회를 안 한다), 사용자가 클로드 코드를 한 번
        쓰면 **1분 안에 저절로 이어진다.** 이게 없으면 되살리기가 한 번 실패한 뒤
        폴링 간격(300초)·재시도 간격(600초)을 다 기다려야 해서, 정작 사람이 직접
        고쳐 놓은 뒤에도 위젯만 한참 멎어 있었다.
        """
        try:
            if isinstance(self.last_error, LoginRequired) and token_stale() is False:
                self.poller.refresh_now()
            elif self.last_usage is not None and self.last_error is None:
                self.skin.show(self.last_usage, self._stamp(self.last_usage))
                self._apply_notice()
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

        ★ **전체화면 앱이 이 화면을 덮으면 잠시 물러난다** — 영상을 전체화면으로 보는데
          위젯만 맨 앞에 남아 있었다. '항상 위'를 내리는 것으로 충분하다(창을 감추면
          돌아올 때 자리·모양을 다시 잡아야 한다). 끝나면 원래대로 되돌린다.
        """
        try:
            docked = self.state["dock"] and self.skin.dockable
            behind = fullscreen_over(self.root)
            want = False if behind else (docked or bool(self.state["topmost"]))
            if want != self._topmost_now:
                self._topmost_now = want
                self.root.attributes("-topmost", want)
            if behind != self._behind:
                self._behind = behind
                applog("전체화면 — 물러남" if behind else "전체화면 끝 — 돌아옴")
                if behind:
                    # ★ '항상 위'를 내리는 것만으로는 모자란다 — 방금 위젯을 눌렀다면
                    #   그 자리에서 여전히 영상 위에 있다. 한 번 **맨 뒤로 내린다.**
                    #   (Tk 의 lower 는 Tcl 안에서 SetWindowPos 를 부르므로 GIL 문제가 없다)
                    self.root.lower()
            if not behind and docked and not self._menu_open and not popup_menu_open():
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

    # ---------------------------------------------------- [업데이트 대기]
    # 클로드 앱은 새 버전을 받아 두고 나중에 **실행 중인 세션을 죽이면서** 갈아끼운다.
    # 대기 중인지 미리 알려 주면 편할 때 껐다 켜서 피할 수 있다.
    # 판정은 cooldown_update 에만 있다. 클로드가 고쳐지면 이 블록째로 지운다.

    def _update_watch(self) -> None:
        """UPDATE_EVERY 마다 대기 여부를 물어 큐에 넣는다. 조회는 0.6초쯤 걸린다."""
        while self.alive:
            try:
                self.update_out.put(cooldown_update.check())
            except Exception:  # noqa: BLE001  못 물어봤으면 다음 차례에 다시
                pass
            time.sleep(UPDATE_EVERY)

    def _update_menu_label(self) -> str:
        """트레이 메뉴 항목 이름 = 하는 일 + 지금 값."""
        p = self._update_pending
        if p is None:
            return "클로드 껐다 켜서 업데이트 끝내기"
        return f"클로드 껐다 켜서 업데이트 끝내기 ({p.target} 대기)"

    def toggle_auto_update(self) -> None:
        self.state["auto_update"] = not bool(self.state.get("auto_update"))
        self.var_auto_update.set(bool(self.state["auto_update"]))
        save_state(self.state)

    def _on_update_state(self, pending: cooldown_update.Pending | None) -> None:
        was = self._update_pending
        self._update_pending = pending

        if pending is None:
            self._update_warned = ""
        elif self._update_warned != pending.target:
            # ★★ **판마다 딱 한 번**이다. 예전엔 적용이 끝날 때마다 이 표시를 지워서,
            #   적용이 안 먹히면 5분마다 같은 알림이 다시 떴다 — 하룻밤에 100통이
            #   쌓였다(2026-08-14). 새 판이 나오기 전에는 다시 알리지 않는다.
            # 자동으로 갈 수 있는 것만 자동이라고 말한다 — 자동 적용은 윈도우가 실제로
            # 등록을 미뤄 뒀을 때(`staged`)만 돈다(`_auto_update_try`).
            auto_will = bool(self.state.get("auto_update")) and pending.staged
            hint = (
                "작업이 없고 자리를 비우면 알아서 적용합니다"
                if auto_will
                else "트레이 아이콘 > 클로드 껐다 켜서 업데이트 끝내기"
            )
            self.tray.notify(
                f"{pending.line}\n"
                "그대로 두면 작업 도중 클로드가 강제로 닫힙니다.\n" + hint,
                "클로드 쿨다운",
            )
            self._update_warned = pending.target

        # 문구가 실제로 바뀌었을 때만 다시 그린다
        if (was.target if was else None) != (pending.target if pending else None):
            self._redraw()

        if pending is not None and self.state.get("auto_update"):
            self._auto_update_try(pending)

    def _auto_update_try(self, pending: cooldown_update.Pending) -> None:
        """조용하면 묻지 않고 적용한다. 아니면 다음 차례(5분 뒤)에 다시 본다.

        ★★ **되풀이하지 않는다.** 적용은 클로드를 죽이는 일이라, 안 끝난 것을 5분마다
        다시 하면 **밤새 클로드가 5분마다 사라진다**(2026-08-14 03:53~13:09 에 실제로
        그랬다 — 원격 대기까지 같이 죽었다). 그래서 판마다 `AUTO_TRIES`(3번)까지,
        실패하면 `AUTO_RETRY_GAP`(30분) 띄우고 다시 한다. 그 뒤로는 손 떼고 사람이
        메뉴에서 부르기를 기다린다.
        """
        if self._update_busy:
            return
        if self._update_tries.get(pending.target, 0) >= AUTO_TRIES:
            return
        last = self._update_last.get(pending.target, 0.0)
        if last and time.time() - last < AUTO_RETRY_GAP:
            return
        # ★ 윈도우가 실제로 등록을 미뤄 뒀을 때만 자동으로 한다(이벤트 658).
        #   업데이터가 새 판을 '봤다' 는 것뿐이면 껐다 켜도 끝낼 것이 없다.
        if not pending.staged:
            return
        ok, _why = cooldown_update.safe_now()
        if not ok:
            return

        self._update_busy = True
        target = pending.target

        def worker():
            # 판정과 실행 사이에 작업이 시작됐을 수 있다 — 죽이기 직전에 한 번 더 본다
            still, why = cooldown_update.safe_now()
            if not still:
                applog(f"업데이트 자동 적용 접음 — {why}")
                self.update_done.put((True, True, "", target))  # 조용히 물러난다
                return
            ok, detail = False, ""
            try:
                ok, detail = cooldown_update.apply(target=target)
                # 다시 판정도 여기서(작업 스레드에서) 한다 — 0.6초 걸려 화면을 붙잡으면 안 된다
                self.update_out.put(cooldown_update.check())
            except Exception as e:  # noqa: BLE001
                ok, detail = False, str(e)
            finally:
                # ★ 무슨 일이 있어도 **결과를 돌려준다.** 여기서 빠져나가면 `_update_busy`
                #   가 True 로 굳어 자동 적용이 그날 이후로 영영 안 돈다.
                self.update_done.put((True, ok, detail, target))

        threading.Thread(target=worker, daemon=True).start()

    def apply_update(self) -> None:
        """클로드를 껐다 켜서 미뤄둔 등록을 지금 끝낸다. 되돌릴 수 없어 한 번 묻는다."""
        if self._update_busy:
            return
        p = self._update_pending
        if p is None:
            messagebox.showinfo(
                "클로드 쿨다운", "대기 중인 업데이트가 없습니다.", parent=self.root
            )
            return

        when = f"\n내려받은 시각   {p.since:%m/%d %H:%M}" if p.since else ""
        if not messagebox.askyesno(
            "클로드 껐다 켜서 업데이트 끝내기",
            f"지금 버전   {p.current}\n"
            f"대기 버전   {p.target}{when}\n\n"
            "클로드를 지금 닫고 새 버전으로 다시 켭니다.\n"
            "돌고 있는 작업은 여기서 중단됩니다 (대화 기록은 남습니다).\n\n"
            "계속할까요?",
            parent=self.root,
        ):
            return

        self._update_busy = True

        target = p.target

        def worker():
            ok, detail = False, ""
            try:
                ok, detail = cooldown_update.apply(target=target)
                # 다시 판정도 여기서(작업 스레드에서) 한다 — 0.6초 걸려 화면을 붙잡으면 안 된다
                self.update_out.put(cooldown_update.check())
            except Exception as e:  # noqa: BLE001
                ok, detail = False, str(e)
            finally:
                self.update_done.put((False, ok, detail, target))

        threading.Thread(target=worker, daemon=True).start()

    def _on_update_done(self, auto: bool, ok: bool, detail: str, target: str) -> None:
        self._update_busy = False
        if detail:
            applog(f"업데이트 {'자동 ' if auto else ''}적용 — {target} — {detail}")
            # ★ **자동은 성공만 알린다.** 자리를 비운 사이에 실패해서 뜬 오류 알림은
            #   돌아와 볼 때 할 일이 없는 잔소리다 — 어차피 30분 뒤에 다시 한다.
            #   실패는 로그(`~/.claude_cooldown_app.log`)에만 남는다.
            if ok:
                head = "조용해서 자동으로 적용했습니다\n" if auto else ""
                self.tray.notify(head + detail, "클로드 쿨다운")
            elif not auto:
                self.tray.notify(detail, "클로드 쿨다운")
        if auto and target and detail:
            # 물러난 것(detail 이 빈 것)은 시도로 세지 않는다 — 죽인 적이 없다.
            # ★★ **죽였으면 센다 — 됐든 안 됐든.** 실패했을 때만 세면, 안 끝났는데 끝났다고
            #    돌아온 한 번이 빗장을 통째로 지나가 **30분마다 밤새** 클로드를 죽인다
            #    (2026-08-14 사고가 주기만 늘려 되살아나는 길이다). 진짜로 끝났으면 대기가
            #    사라져 여기 다시 안 오므로, 성공을 세도 잃는 것이 없다.
            self._update_last[target] = time.time()
            n = self._update_tries.get(target, 0) + 1
            self._update_tries[target] = n
            if not ok and n >= AUTO_TRIES:
                applog(f"업데이트 자동 적용 그만둠 — {target} (이제 사람이 눌러야 함)")
        if not ok and not auto:
            messagebox.showwarning(
                "클로드 쿨다운", detail or "적용하지 못했습니다", parent=self.root
            )

    # ------------------------------------------------ [업데이트 대기] 끝

    def _notice_text(self) -> str:
        """위젯에 얹을 알림 문구 (값은 멀쩡할 때) — 자동 시작이 실패했거나 놓쳤을 때.

        위젯 자리가 좁아 **여기서만은 '핑' 으로 짧게 쓴다**(메뉴·팝업·트레이는 그대로
        '자동 시작'). 시각을 앞세우고 **까닭은 붙이지 않는다** — 까닭은 트레이 알림과
        실행 기록에 있다.
        """
        # [업데이트 대기] 핑보다 앞선다 — 이건 놓치면 작업이 통째로 날아간다
        if self._update_pending is not None:
            return self._update_pending.short
        if self.ping_cfg.get("enabled"):
            if self._ping_fail is not None:  # 실패가 놓침보다 급하다 (지금 안 열린 것)
                return f"{self._ping_fail[0]:%H:%M} 핑 실패"
            if self._missed_dt is not None:
                return f"{self._missed_dt:%H:%M} 핑 놓침"
        # 원격 대기는 맨 뒤다 — 지금 잃는 것은 없고 폰에서 새 세션만 못 연다.
        # 여기서도 **까닭은 붙이지 않는다**(자리가 없다. 까닭은 트레이 알림에 있다).
        if self.remote_error:
            return "원격 대기 끊김"
        return ""

    def _apply_notice(self) -> None:
        """스킨에 알림 문구를 얹는다. 오류가 떠 있으면(자리가 겹친다) 얹지 않는다."""
        try:
            self.skin.notice("" if self.last_error is not None else self._notice_text())
        except Exception:  # noqa: BLE001
            pass

    def _redraw(self) -> None:
        """마지막 값으로 화면을 다시 그리고 알림을 다시 얹는다.
        알림이 사라질 때 스킨의 그 자리를 정상값으로 되돌리려면 show() 를 한 번 태워야 한다."""
        try:
            if self.last_usage is not None and self.last_error is None:
                self.skin.show(self.last_usage, self._stamp(self.last_usage))
            self._apply_notice()
        except Exception:  # noqa: BLE001
            pass

    def _show(self, usage: Usage):
        self.last_usage = usage
        self.last_error = None
        # 조회가 됐다 = 로그인이 멀쩡하다. 되살리기 예산을 되돌려 놓는다 —
        # 안 그러면 며칠에 걸쳐 실패가 쌓여 자동 되살리기가 영영 멈춘다.
        self._revive_fails = 0
        self._revive_at = 0.0
        self._login_state = ""
        self._clear_busy()
        self.skin.show(usage, self._stamp(usage))
        self._apply_notice()
        self._sync_status()  # 상태 점을 초록으로 (바탕색도 정상으로 돌아왔다)
        self._reassert_dock()
        export(usage)
        cooldown_stats.record(usage)  # 통계용 기록 (값이 그대로면 안 쌓인다)
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
            parts.append(f"이번 주 적정선 {p.due:.0f}%  ·  {p.verdict}")
        if self.ping_cfg.get("enabled"):
            if self._missed_dt is not None:
                parts.append(f"자동 시작 놓침 {self._missed_dt:%H:%M} (컴퓨터 꺼짐 등)")
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
        if isinstance(err, TokenStale):
            # 토큰만 낡았다 — 사용량을 안 쓰는 길로 조용히 되살려 본다.
            # (문구는 되살리기가 시작되면 '로그인 잇는 중' 으로 바뀐다)
            self._maybe_revive()
        elif not isinstance(err, LoginRequired):
            self._login_state = ""  # 로그인 문제가 아니면 옛 판정을 붙들지 않는다
        text = self._error_text(err)
        self.skin.show_error(text, keep, self.last_error_stamp)
        self._sync_status()  # 상태 점을 빨강으로 (붉은 바탕에 맞춰 자리도 다시)
        self.tray.icon = draw_icon(None)
        detail = f"{type(err).__name__}: {err}" if not str(err) else text
        self.tray.title = f"클로드 쿨다운 — {detail}"[:127]

    # -------------------------------------------------- 로그인(토큰) 잇기
    # 위젯이 쓰는 accessToken 은 **발급 8시간 뒤 만료**되고, 새로 발급할 수 있는 건
    # 클로드 코드 CLI 뿐이다 — 그래서 클로드 코드를 하룻밤 안 쓰면 로그인은 멀쩡한데
    # 위젯만 멎는다. 위젯이 직접 재발급하지 않는 까닭은 cooldown_login 머리말 참고.
    def _five_open(self) -> bool:
        """지금 5시간 창이 열려 있나 (마지막으로 받은 값 기준).
        열려 있으면 핑을 보내도 경계가 안 밀리므로, 되살리기에 써도 잃는 게 없다."""
        when = self._five_resets_local()
        return when is not None and when > datetime.now()

    def _maybe_revive(self) -> None:
        """조용한 자동 되살리기. 사용량을 쓰지 않는 길만 밟는다 —
        다만 5시간 창이 이미 열려 있으면 핑까지 밟는다(그 창에는 경계가 안 밀린다).

        실패가 REVIVE_TRIES 만큼 쌓이면 멈춘다 — 안 될 일에 5분마다 프로세스를
        띄우지 않는다. 그 뒤로는 사람이 '지금 잇기' 를 누를 때 다시 시도한다.
        """
        if self._revive_busy or self._revive_fails >= REVIVE_TRIES:
            return
        now = time.monotonic()
        if self._revive_at and now - self._revive_at < REVIVE_GAP:
            return
        self._revive_at = now
        self._start_revive(paid=self._five_open())

    def _start_revive(self, paid: bool = False) -> None:
        """되살리기를 백그라운드에서 시작한다 (CLI 를 부르므로 Tk 를 막으면 안 된다).

        `paid` 가 참이면 공짜 계단이 다 실패했을 때 `claude -p` 핑까지 간다 —
        **5시간 창이 닫혀 있었다면 그 순간 열린다.** 그래서 자동으로는 창이 이미
        열려 있을 때만 참이고, 닫혀 있을 땐 사람이 그 버튼을 눌렀을 때만 참이다.
        """
        if self._revive_busy:
            return
        self._revive_busy = True
        cfg = dict(self.ping_cfg)
        self._refresh_error_text()  # '로그인 잇는 중' 으로 바꿔 단다
        self._render_login()

        def worker():
            try:
                ok = cooldown_login.revive_free()
                if not ok and paid:
                    # ★★ '핑이 나갔다' 와 '토큰이 새로 나왔다' 는 다른 말이다.
                    #   보내고 나서 자격 파일을 다시 본다 — 안 그러면 갱신이 안 됐는데도
                    #   성공으로 쳐서 예산이 되돌아가고, **10분마다 핑이 나가며 한도만
                    #   깎는다**(2026-08-14 오전 08:05~09:56 에 열두 번 그랬다).
                    ok = cooldown_ping.send_ping(cfg)[0] and token_stale() is False
                if ok:
                    self.login_out.put((True, cooldown_login.OK, ""))
                    return
                # 왜 안 됐는지는 CLI 가 안다 — 로그아웃인지, 아예 없는지.
                status = cooldown_login.auth_status()
                self.login_out.put(
                    (False, cooldown_login.state(status), cooldown_login.account(status))
                )
            except Exception as e:  # noqa: BLE001
                applog(f"스레드 오류 (로그인 잇기)\n{e}")
                self.login_out.put((False, cooldown_login.UNKNOWN, ""))

        threading.Thread(target=worker, daemon=True).start()

    def _on_revive_result(self, ok: bool, state: str, account: str) -> None:
        self._revive_busy = False
        self._login_state = "" if ok else state
        if account:
            self._login_account = account
        if ok:
            self._revive_fails = 0
            self.poller.refresh_now()  # 토큰이 새로 나왔으니 곧바로 다시 조회
        else:
            self._revive_fails += 1
        self._refresh_error_text()
        self._render_login()

    def _refresh_error_text(self) -> None:
        """오류가 떠 있는 채로 로그인 상태만 바뀌었을 때 그 한 줄만 다시 단다."""
        try:
            if self.last_error is not None:
                self.skin.show_error(
                    self._error_text(self.last_error),
                    self.last_usage is not None,
                    self.last_error_stamp,
                )
        except Exception:  # noqa: BLE001
            pass

    def _render_login(self) -> None:
        """로그인 팝업이 떠 있으면 내용을 다시 그린다 (안 떠 있으면 아무것도 안 한다)."""
        render = self._login_render
        if render is None:
            return
        try:
            render()
        except tk.TclError:
            self._login_render = None

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
                and self.last_usage is not None  # 창 상태를 모르면 함부로 쏘지 않는다
            ):
                now = datetime.now()
                times = cooldown_ping.parse_times(cfg["times"])
                resets_local = self._five_resets_local()
                # 이 앵커의 여유 구간에 앱이 떠 있으면 '처리 중'으로 기록 — 놓침에서 제외.
                # (핑을 쏘든, 창이 활성이라 건너뛰든, 떠 있었다는 사실만으로 놓침이 아니다)
                in_grace = cooldown_ping.anchor_in_grace(now, times)
                if in_grace is not None:
                    self._note_anchor_handled(in_grace)
                if not self._ping_busy and cooldown_ping.should_ping_now(
                    now, times, resets_local, self._last_ping_dt
                ):
                    self._start_ping(anchor_now=now)
                # 컴퓨터가 꺼져 있던 등으로 앵커를 놓쳤으면 위젯·트레이에 표시
                self._detect_missed(now, times, resets_local)
        except Exception:  # noqa: BLE001
            pass
        finally:
            if self.alive:
                self.root.after(PING_TICK * 1000, self._ping_tick)

    def _note_anchor_handled(self, anchor: datetime) -> None:
        """앱이 떠서 이 앵커를 처리했다고 기록한다 (놓침 판정에서 제외)."""
        if self._last_anchor_dt is not None and anchor <= self._last_anchor_dt:
            return
        self._last_anchor_dt = anchor
        self.ping_cfg["last_anchor"] = anchor.isoformat()
        cooldown_ping.save_cfg(self.ping_cfg)

    def _detect_missed(self, now: datetime, times, resets_local: datetime | None) -> None:
        """컴퓨터 꺼짐 등으로 놓친 앵커가 있으면 붙잡아 위젯에 표시하고 한 번 알린다."""
        anchor = cooldown_ping.missed_since(
            now, times, resets_local, self._last_ping_dt, self._last_anchor_dt
        )
        if anchor is None:
            return
        # 이 기능을 켜고 처음 도는 순간(핑·처리 기록이 아예 없음)엔 놓친 걸로 치지 않는다 —
        # 지금 이후부터 지켜보도록 기준점만 잡는다.
        if self._last_ping_dt is None and self._last_anchor_dt is None:
            self._note_anchor_handled(anchor)
            return
        if self._missed_dt is not None and anchor <= self._missed_dt:
            return  # 이미 붙잡아 알린 놓침
        self._missed_dt = anchor
        # 알린 앵커는 '처리함'으로 올려, 다음(더 최근) 놓침만 새로 잡히게 한다
        self._last_anchor_dt = anchor
        self.ping_cfg["last_missed"] = anchor.isoformat()
        self.ping_cfg["last_anchor"] = anchor.isoformat()
        cooldown_ping.save_cfg(self.ping_cfg)
        self._apply_notice()
        try:
            self.tray.notify(
                f"{anchor:%H:%M} 자동 시작을 놓쳤어요 (컴퓨터 꺼짐 등)", "클로드 쿨다운"
            )
        except Exception:  # noqa: BLE001
            pass

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
        if ok and self._missed_dt is not None:
            # 핑이 나갔으니 창이 그 앵커에 다시 정렬됐다 — 놓침 표시를 지운다
            self._missed_dt = None
            self.ping_cfg["last_missed"] = None
        cooldown_ping.save_cfg(self.ping_cfg)
        if ok:
            self._ping_fail = None
            self._redraw()  # 실패·놓침 표시가 있었으면 곧바로 지운다
            self.poller.refresh_now()  # 창이 열렸으니 위젯 숫자를 곧바로 갱신
        else:
            reason = cooldown_ping.friendly_error(detail)
            self._ping_fail = (when, reason)
            self._redraw()  # 위젯 오른쪽 칸에도 띄운다 (트레이 알림은 놓치기 쉽다)
            try:
                self.tray.notify(f"자동 시작 실패 · {reason}", "클로드 쿨다운")
            except Exception:  # noqa: BLE001
                pass

    def toggle_ping(self):
        self.ping_cfg["enabled"] = not self.ping_cfg.get("enabled")
        if self.ping_cfg["enabled"]:
            # 켠 순간 이전에 지나간 앵커를 놓친 걸로 잘못 잡지 않게 기준점을 지금에 맞춘다
            now = datetime.now()
            times = cooldown_ping.parse_times(self.ping_cfg["times"])
            base = cooldown_ping.last_due_anchor(now, times)
            if base is not None:
                self._last_anchor_dt = base
                self.ping_cfg["last_anchor"] = base.isoformat()
        else:
            # 껐으면 실패·놓침 표시도 지운다 (더는 지킬 게 없다)
            self._missed_dt = None
            self._ping_fail = None
            self.ping_cfg["last_missed"] = None
        cooldown_ping.save_cfg(self.ping_cfg)
        self.var_ping.set(bool(self.ping_cfg["enabled"]))
        self._redraw()

    def send_ping_now(self):
        """지금 한 번 쏜다 (테스트/즉시 창 열기). 앵커 정렬과 무관."""
        self._start_ping(manual=True)

    # -------------------------------------------------- 클로드 코드 원격
    def _tray_say(self, text: str) -> None:
        try:
            self.tray.notify(text, "클로드 쿨다운")
        except Exception:  # noqa: BLE001 — 트레이가 아직 없거나 알림이 막혀 있을 수 있다
            pass

    def toggle_remote(self):
        """폰·웹에서 이 PC 에 세션을 열 수 있게 `claude rc` 를 창 없이 띄워 둔다."""
        want = not self.remote_cfg.get("enabled")
        self.remote_cfg["enabled"] = want
        cooldown_remote.save_cfg(self.remote_cfg)
        self.var_remote.set(want)
        self._remote_fails = 0
        if want:
            ok, msg = self.remote.start(self.remote_cfg["folder"])
            self.remote_error = "" if ok else cooldown_remote.friendly_error(msg)
            if not ok:
                self._tray_say(f"원격 대기 실패 · {self.remote_error}")
        else:
            self.remote.stop()
            self.remote_error = ""
        self._say_state("on" if (want and not self.remote_error) else "off")
        self._apply_notice()

    def _remote_tick(self):
        """켜 두기로 했으면 살아 있는지 REMOTE_TICK 마다 보고, 죽었으면 다시 살린다.
        다만 **붙지 못하는 상태**(로그인·폴더 신뢰)라면 되살려 봐야 소용없으므로
        REMOTE_GIVEUP 번 연달아 실패하면 스스로 끄고 알린다 — 안 될 일에 30초마다
        프로세스를 띄우지 않는다(자동 되살리기와 같은 결)."""
        try:
            self._remote_once()
        except Exception:  # noqa: BLE001
            pass
        finally:
            if self.alive:
                try:
                    self.root.after(REMOTE_TICK * 1000, self._remote_tick)
                except tk.TclError:  # 종료 중
                    pass

    def _remote_once(self):
        self._remote_ask()  # 폰이 켜 달라고 적어 뒀는지 먼저 본다 (꺼져 있어도 물어봐야 켤 수 있다)
        if not self.remote_cfg.get("enabled"):
            self._say_state("off")
            return
        if self.remote.running():
            if self.remote_error:  # 되살아났다
                self.remote_error = ""
                self._remote_fails = 0
                self._apply_notice()
            self._say_state("on")
            return

        why = self.remote.died()  # 아직 한 번도 안 띄웠으면 None
        if why == cooldown_remote.ERR_DROPPED:
            # ★★ 잘 돌다 끊긴 것은 **못 붙은 게 아니다** — 밖에서 죽인 것이니 그냥 다시
            #   띄운다(아래로 내려간다). 이걸 실패로 세면 세 번 만에 스스로 꺼져 폰에서
            #   세션을 못 연다 — 2026-08-14 새벽에 업데이트 자동 적용이 `claude.exe` 를
            #   싹 죽이는 바람에 그렇게 꺼졌다(그쪽도 고쳤다: cooldown_update.PKG_MARK).
            applog("원격 대기 끊김 — 다시 띄움")
            self.remote_error = ""
        elif why:
            self._remote_fails += 1
            self.remote_error = cooldown_remote.friendly_error(why)
            if self._remote_fails >= REMOTE_GIVEUP:
                self.remote_cfg["enabled"] = False
                cooldown_remote.save_cfg(self.remote_cfg)
                self.var_remote.set(False)
                self._tray_say(f"원격 대기 꺼짐 · {self.remote_error}")
                self._say_state("fail")  # 폰에도 '안 됐다' 가 보이게
                self._apply_notice()
                return
        elif self.remote.adopt():
            # 앱만 다시 뜬 경우 — 지난번에 띄워 둔 놈이 아직 돌고 있으면 이어받는다.
            # (모르고 또 띄우면 같은 폴더에 원격이 둘 붙어 폰에 두 번 뜬다)
            self.remote_error = ""
            self._apply_notice()
            return

        ok, msg = self.remote.start(self.remote_cfg["folder"])
        if ok:
            self.remote_error = ""  # 실제로 붙었는지는 다음 tick 이 본다
        else:
            self._remote_fails += 1
            self.remote_error = cooldown_remote.friendly_error(msg)
        self._apply_notice()

    def _remote_ask(self) -> None:
        """폰이 릴레이에 적어 둔 '원하는 상태' 를 REMOTE_POLL 마다 물어본다.
        네트워크는 별도 스레드 — Tk 를 붙잡으면 위젯이 언다(핑·푸시와 같은 결).

        ★★ **평소에는 아예 안 물어본다** — 사용량을 올릴 때(5분) 그 응답에 want 가 얹혀
        오기 때문이다(`_start_push`). 이 폴링이 무료 한도의 60%를 먹던 항목이었다.
        남겨 둔 건 **'폰으로 보내기'를 꺼 둔 채 짝만 지어 둔 경우** 하나뿐이다 —
        그때는 올리는 요청 자체가 없어서 얹어 받을 자리가 없다.
        """
        if self._remote_busy or not cooldown_remote.relay_ready(self.push_cfg):
            return  # 폰과 짝지어져 있지 않으면 아예 안 물어본다 (무료 한도를 안 쓴다)
        if cooldown_push.ready(self.push_cfg):
            return  # 올릴 때 같이 받는다 — 따로 물어볼 까닭이 없다
        now = time.monotonic()
        if now - self._remote_poll_at < REMOTE_POLL:
            return
        self._remote_poll_at = now
        self._remote_busy = True

        def worker():
            try:
                self.remote_out.put(cooldown_remote.fetch_want(self.push_cfg))
            except Exception:  # noqa: BLE001
                self.remote_out.put(None)
            finally:
                self._remote_busy = False

        threading.Thread(target=worker, daemon=True).start()

    def _on_want(self, got) -> None:
        """폰이 원한 상태를 따라간다. `_pump_once` 가 큐에서 꺼내 부른다
        (★ 작업 스레드에서 Tk 를 건드리면 조용히 씹힌다 — 이 저장소의 규칙)."""
        if not got:
            return
        want, at = got
        # 같은 것을 두 번 따르지 않는다 — 안 그러면 사흘 전 폰에서 켠 것이
        # PC 에서 끌 때마다 되살아난다.
        if at == (self.remote_cfg.get("last_want_at") or ""):
            return
        self.remote_cfg["last_want_at"] = at
        on = want == "on"
        if on != bool(self.remote_cfg.get("enabled")):
            self.remote_cfg["enabled"] = on
            self.var_remote.set(on)
            self._remote_fails = 0
            if on:
                ok, msg = self.remote.start(self.remote_cfg["folder"])
                self.remote_error = "" if ok else cooldown_remote.friendly_error(msg)
            else:
                self.remote.stop()
                self.remote_error = ""
            self._tray_say("폰에서 원격 대기 " + ("켬" if on else "끔"))
            self._apply_notice()
        cooldown_remote.save_cfg(self.remote_cfg)
        # 결과를 **여기서 바로** 알린다 — 다음 tick(30초)까지 미루면 누른 사람 화면에는
        # 그동안 '전하는 중' 이 남아, 됐는지 안 됐는지 모른 채 기다리게 된다.
        self._say_state(
            "on" if self.remote.running() else ("fail" if self.remote_error else "off")
        )

    def _say_state(self, state: str) -> None:
        """지금 상태를 릴레이에 적어 둔다 — 폰이 켜졌는지 보고 알 수 있게.
        **바뀌었을 때만** 적는다(주기마다 적으면 무료 한도를 그냥 태운다)."""
        if state == self._remote_said or not cooldown_remote.relay_ready(self.push_cfg):
            return
        self._remote_said = state
        threading.Thread(
            target=cooldown_remote.publish_state,
            args=(self.push_cfg, state),
            daemon=True,
        ).start()

    def open_remote_folder(self):
        """`claude rc` 는 **폴더 하나**에 붙는다 — 거기서 열린 세션만 폰에서 쓸 수 있다.
        붙은 뒤에는 폴더를 못 바꾸므로, 바꾸면 껐다 다시 띄운다."""
        now = self.remote_cfg.get("folder") or cooldown_remote.default_folder()
        picked = filedialog.askdirectory(title="원격으로 열 폴더", initialdir=now)
        if not picked:
            return
        picked = os.path.normpath(picked)
        if picked == os.path.normpath(now):
            return
        self.remote_cfg["folder"] = picked
        cooldown_remote.save_cfg(self.remote_cfg)
        if self.remote_cfg.get("enabled"):
            self.remote.stop()
            self._remote_fails = 0
            ok, msg = self.remote.start(picked)
            self.remote_error = "" if ok else cooldown_remote.friendly_error(msg)
            self._apply_notice()

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
                data = cooldown_push.push(usage, self.push_cfg)
                # 올린 응답에 폰이 원한 상태가 얹혀 온다 — 그것 하나 때문에 2분마다
                # 따로 물어보던 요청이 사라졌다(무료 한도 절약. `_remote_ask` 참고).
                self.remote_out.put(cooldown_remote.want_of(data))
                self.push_out.put("")
            except Exception as e:  # noqa: BLE001
                self.push_out.put(str(e) or "전송 실패")
            finally:
                self._push_busy = False

        threading.Thread(target=worker, daemon=True).start()

    def open_phone_link(self):
        """폰 연결 — 서버 주소를 넣고, 폰 앱이 찍을 QR 을 본다."""
        try:
            top, body = self._open_panel("폰 연결", click_away=False)
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

    # -------------------------------------------------- 로그인 상태
    def open_login(self):
        """로그인 상태 — 위젯이 사용량을 읽을 수 있는지, 막혔으면 여기서 잇는다.

        말로 설명하지 않는다. **두 줄이 곧 설명**이다:
        `클로드 코드`(로그인돼 있나) · `사용량 읽기`(위젯이 읽을 수 있나, 언제까지).
        고칠 게 있을 때만 버튼이 뜨고, **버튼 이름이 그 값을 치른다는 뜻까지 담는다**
        (`5시간 창 열고 잇기`) — 그래야 툴팁으로 부연할 일이 없다.
        """
        W = 300
        try:
            top, body = self._open_panel("로그인 상태")
            wrap = tk.Frame(body, bg=P.bg)
            wrap.pack(fill="both", expand=True, padx=PANEL_PAD, pady=(2, PANEL_PAD))

            def render():
                for w in wrap.winfo_children():
                    w.destroy()

                stale = token_stale()
                busy = self._revive_busy
                st = self._login_state
                expiry = token_expiry()

                # ---- 클로드 코드: 로그인돼 있나
                # 아직 안 알아본 상태(빈 문자열)에서 '로그인됨' 이라고 적지 않는다 —
                # 확인하기 전에는 확인 중이라고만 쓴다.
                if st == cooldown_login.NO_CLI:
                    account, color = "설치 안 됨", P.red
                elif st == cooldown_login.LOGGED_OUT:
                    account, color = "로그아웃됨", P.red
                elif st == cooldown_login.UNKNOWN and not busy:
                    account, color = "확인 실패", P.amber
                elif stale and not st:
                    account, color = "확인 중…", P.faint
                else:
                    account = self._login_account or "로그인됨"
                    color = P.green
                self._pair(wrap, "클로드 코드", account, color)

                # ---- 사용량 읽기: 위젯이 지금 읽을 수 있나, 언제까지
                if stale is False:
                    when = f"{expiry.astimezone():%H:%M} 까지" if expiry else "됨"
                    self._pair(wrap, "사용량 읽기", when, P.green)
                else:
                    since = f"{expiry.astimezone():%H:%M} 부터 막힘" if expiry else "막힘"
                    self._pair(wrap, "사용량 읽기", since, P.red)

                if stale is False and not busy:
                    tk.Label(
                        wrap, text="이어져 있어요.", bg=P.bg, fg=P.faint,
                        font=(KR, 9), anchor="w",
                    ).pack(fill="x", pady=(10, 2))
                    self._refit_panel(top, W)
                    return

                tk.Frame(wrap, bg=P.line, height=1).pack(fill="x", pady=(12, 0))

                if busy:
                    tk.Label(
                        wrap, text="잇는 중…", bg=P.bg, fg=P.sub, font=(KR, 9), anchor="w"
                    ).pack(fill="x", pady=(10, 2))
                    self._refit_panel(top, W)
                    return

                if st == cooldown_login.LOGGED_OUT or st == cooldown_login.NO_CLI:
                    # 여기서부터는 사람이 해야 한다 — 위젯이 자격 증명을 대신 넣지 않는다.
                    tk.Label(
                        wrap,
                        text=(
                            "클로드 코드를 설치해 주세요."
                            if st == cooldown_login.NO_CLI
                            else f"{cooldown_login.login_command()} 을 실행해 주세요."
                        ),
                        bg=P.bg, fg=P.sub, font=(KR, 9), anchor="w",
                        wraplength=W - PANEL_PAD * 2, justify="left",
                    ).pack(fill="x", pady=(10, 8))
                    if st == cooldown_login.LOGGED_OUT:
                        self._themed_button(
                            wrap, "로그인 창 열기",
                            cooldown_login.open_login_console,
                            primary=True, width=0,
                        ).pack(anchor="e")
                    self._refit_panel(top, W)
                    return

                # 낡았다 — 사용량을 안 쓰는 되살리기가 먼저다.
                # ★ 버튼은 **늘 하나**다. '지금 잇기' 와 '5시간 창 열고 잇기' 를 나란히
                #   놓아 봤더니, 앞엣것은 어차피 또 실패할 길인데 둘 중 뭘 눌러야 하는지가
                #   화면에서 안 보였다. 다음에 밟을 계단 하나만 내놓고, **값을 치르는
                #   계단이면 버튼 이름이 그걸 말한다.**
                tried = self._revive_fails > 0
                costs_window = tried and not self._five_open()
                tk.Label(
                    wrap,
                    text=(
                        "클로드 코드를 한 번 쓰면 저절로 이어져요."
                        if tried
                        else "클로드 코드가 열쇠를 새로 내주면 이어져요."
                    ),
                    bg=P.bg, fg=P.sub, font=(KR, 9), anchor="w",
                    wraplength=W - PANEL_PAD * 2, justify="left",
                ).pack(fill="x", pady=(10, 8))
                self._themed_button(
                    wrap,
                    "5시간 창 열고 잇기" if costs_window else "지금 잇기",
                    lambda paid=costs_window or self._five_open(): self._start_revive(paid=paid),
                    primary=True,
                    width=0 if costs_window else 7,
                ).pack(anchor="e")
                self._refit_panel(top, W)

            # 막혀 있는데 아직 까닭을 안 알아봤으면(앱을 막 켰다 등) 여기서 알아본다.
            # `_login_render` 를 아직 안 걸어 둔 자리라 다시 그리기가 겹치지 않는다.
            if token_stale() and not self._login_state and not self._revive_busy:
                self._start_revive(paid=self._five_open())

            render()
            self._login_render = render
            top.bind(
                "<Destroy>",
                lambda e, t=top: setattr(self, "_login_render", None) if e.widget is t else None,
                add="+",
            )
            self._finalize_panel(top, W)
            # 팝업을 여는 사이에 토큰이 되살아나 있었으면(클로드 코드를 그새 썼다)
            # 굳이 기다리게 하지 않고 곧바로 다시 조회한다.
            if token_stale() is False and self.last_error is not None:
                self.poller.refresh_now()
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

            # 판정을 한 줄로 풀어 준다 — 적정선(고르게 쓸 때)보다 얼마나 앞섰나/뒤졌나.
            tk.Label(
                wrap, text=self._gap_sentence(p), bg=P.bg, fg=P.sub, font=(KR, 10),
            ).pack(anchor="w", pady=(3, 0))

            # 채운 색 = 지금까지 쓴 양, 눈금 = 적정선. 색이 눈금을 앞질렀으면 빨리 쓰는 중.
            bar = tk.Canvas(
                wrap, width=inner, height=10, bg=P.bg, highlightthickness=0, bd=0
            )
            bar.pack(fill="x", pady=(12, 12))
            bar.create_rectangle(0, 0, inner, 10, fill=P.track, width=0)
            bar.create_rectangle(0, 0, inner * p.used / 100, 10, fill=tone(p.used), width=0)
            x = mark_x(p.due, inner)
            bar.create_rectangle(x, 0, x + MARK_W, 10, fill=P.title, width=0)

            self._pair(wrap, "지금까지 사용", f"{p.used:.0f}%", tone(p.used))
            # 괄호로 `(고르게 쓸 때)` 를 달지 않는다 — 바로 위 `_gap_sentence` 가
            # `고르게 쓸 때보다 N%p 덜 썼어요` 로 이미 말했다. 이름은 어디서나 `적정선`.
            self._pair(wrap, "적정선", f"{p.due:.0f}%", P.sub)

            tk.Frame(wrap, bg=P.line, height=1).pack(fill="x", pady=(10, 8))

            # 이대로 계속 쓰면 초기화 시점에 몇 %가 되는가 (지금 속도를 창 끝까지 늘린 값).
            if p.projected is not None:
                self._pair(
                    wrap, "이대로 계속 쓰면",
                    f"초기화 때 {min(999, p.projected):.0f}%",
                    pace_color(p.level),
                )
            # 초기화까지 남은 예산을 남은 날로 나눈 값 — 하루에 이만큼씩 쓰면 딱 맞는다.
            per = p.per_day
            if per is not None:
                self._pair(wrap, "하루 이만큼까지 OK", f"{per:.0f}%", P.sub)
            else:
                self._pair(wrap, "남은 양", f"{max(0.0, 100 - p.used):.0f}%", P.sub)
            if p.runout is not None:
                self._pair(wrap, "이대로면 다 쓰는 때", self._when_text(p.runout), P.red)
            reset = self.last_usage.week.resets_at
            if reset is not None:
                self._pair(wrap, "초기화", self._when_text(reset), P.sub)

            self._finalize_panel(top, W)
        except Exception:  # noqa: BLE001
            pass

    # -------------------------------------------------- 사용량 통계
    def open_stats(self):
        """쌓아 둔 기록에서 '언제 얼마나 썼나' 를 셈해 보여 준다.

        사용량 단위는 **주간 한도 %p** — 5시간 퍼센트는 5시간마다 0으로 돌아가
        더할 수가 없고, 주간 퍼센트가 오른 만큼이 곧 그 사이에 쓴 양이다.
        셈은 전부 `cooldown_stats` 가 하고, 여기서는 그리기만 한다.
        """
        W = 344
        try:
            rep = cooldown_stats.analyze(cooldown_stats.read_samples(days=30))
            top, body = self._open_panel("사용량 통계")
            wrap = tk.Frame(body, bg=P.bg)
            wrap.pack(fill="both", expand=True, padx=PANEL_PAD, pady=(2, PANEL_PAD))
            inner = W - PANEL_PAD * 2

            if rep.samples < 2:
                tk.Label(
                    wrap, text="쌓인 기록 없음", bg=P.bg, fg=P.title, font=(KR, 12, "bold")
                ).pack(anchor="w", pady=(6, 2))
                tk.Label(
                    wrap, text="위젯이 떠 있는 동안 5분마다 쌓임",
                    bg=P.bg, fg=P.faint, font=(KR, 9),
                ).pack(anchor="w", pady=(0, 10))
                self._finalize_panel(top, W)
                return

            tk.Label(
                wrap,
                text=f"기록 {rep.span_days:.0f}일 · 표본 {rep.samples}개",
                bg=P.bg, fg=P.faint, font=(KR, 8), anchor="w",
            ).pack(fill="x", pady=(0, 8))

            # ---- 일별 ----
            self._section(wrap, "일별 사용량", "주간 한도 기준")
            self._chart_days(wrap, rep.days, inner)
            self._pair(
                wrap, "오늘", f"{rep.today:.0f}%p", pace_color(self._day_level(rep.today))
            )
            self._pair(wrap, "어제", f"{rep.yesterday:.0f}%p", P.sub)
            self._pair(wrap, "하루 평균 (최근 이레)", f"{rep.avg_day:.0f}%p", P.sub)
            if rep.busiest is not None:
                day, value = rep.busiest
                self._pair(
                    wrap, "가장 많이 쓴 날",
                    f"{day.month}/{day.day:02d}({'월화수목금토일'[day.weekday()]}) "
                    f"{value:.0f}%p",
                    P.sub,
                )

            tk.Frame(wrap, bg=P.line, height=1).pack(fill="x", pady=(12, 10))

            # ---- 시간대 ----
            self._section(wrap, "시간대", "0~23시")
            self._chart_hours(wrap, rep.hours, inner)
            if rep.peak_hour is not None:
                self._pair(
                    wrap, "가장 많이 쓰는 때",
                    f"{rep.peak_hour:02d}~{(rep.peak_hour + 1) % 24:02d}시", P.sub,
                )

            # ---- 5시간 창 ----
            if rep.windows:
                tk.Frame(wrap, bg=P.line, height=1).pack(fill="x", pady=(12, 10))
                self._section(wrap, "5시간 창 최고", f"최근 {len(rep.windows)}개")
                self._chart_windows(wrap, rep.windows, inner)
                self._pair(
                    wrap, "평균 최고", f"{rep.win_avg:.0f}%", tone(rep.win_avg)
                )
                self._pair(
                    wrap, "90% 넘긴 창", f"{rep.win_full}개",
                    P.red if rep.win_full else P.sub,
                )

            self._finalize_panel(top, W)
        except Exception:  # noqa: BLE001
            pass

    @staticmethod
    def _section(parent: tk.Misc, title: str, note: str = "") -> None:
        """작은 제목 한 줄 — 왼쪽 이름, 오른쪽에 무엇을 재는지."""
        row = tk.Frame(parent, bg=P.bg)
        row.pack(fill="x", pady=(0, 5))
        tk.Label(row, text=title, bg=P.bg, fg=P.title, font=(KR, 9, "bold")).pack(
            side="left"
        )
        if note:
            tk.Label(row, text=note, bg=P.bg, fg=P.faint, font=(KR, 8)).pack(side="right")

    @staticmethod
    def _day_level(value: float) -> int:
        """하루 사용량을 적정선(DAY_PP)과 견준 등급 — 0 여유 · 1 조금 빠름 · 2 많이 빠름.
        주간 판정(cooldown_core.pace)과 같은 잣대라 색이 서로 어긋나지 않는다."""
        if value <= DAY_PP:
            return 0
        return 1 if value <= DAY_PP * 1.5 else 2

    @staticmethod
    def _chart_days(parent: tk.Misc, days: list, width: int, height: int = 62) -> None:
        """날짜별 막대 + 하루 적정선(점선). 막대 색은 적정선과 견준 결과다 —
        게이지의 초록/노랑/빨강과 같은 뜻(여유·조금 빠름·많이 빠름)."""
        c = tk.Canvas(
            parent, width=width, height=height + 13, bg=P.bg, highlightthickness=0, bd=0
        )
        c.pack(fill="x", pady=(0, 8))
        n = max(1, len(days))
        pitch = width / n
        bar_w = max(3.0, pitch - 4)
        # 눈금(적정선)이 늘 보이도록 꼭대기는 적정선보다 반드시 높게 잡는다
        top_v = max([v for _d, v in days] + [DAY_PP]) * 1.15
        today = datetime.now().date()
        for i, (day, value) in enumerate(days):
            x = i * pitch + (pitch - bar_w) / 2
            h = value / top_v * height if top_v > 0 else 0
            if value <= 0:  # 안 쓴 날도 자리는 남긴다 (기록이 없는 것과 구분)
                c.create_rectangle(
                    x, height - 2, x + bar_w, height, fill=P.track, width=0
                )
            else:
                c.create_rectangle(
                    x, height - max(2.0, h), x + bar_w, height,
                    fill=pace_color(App._day_level(value)), width=0,
                )
            c.create_text(
                x + bar_w / 2, height + 7,
                text="월화수목금토일"[day.weekday()],
                font=(KR, 7), fill=P.title if day == today else P.faint,
            )
        y = height - DAY_PP / top_v * height
        c.create_line(0, y, width, y, fill=P.title, width=1, dash=(3, 3))

    @staticmethod
    def _chart_hours(parent: tk.Misc, hours: list, width: int, height: int = 40) -> None:
        """0~23시 막대 — 하루 중 언제 쓰는지. 가장 많은 때만 밝게."""
        c = tk.Canvas(
            parent, width=width, height=height + 13, bg=P.bg, highlightthickness=0, bd=0
        )
        c.pack(fill="x", pady=(0, 8))
        top_v = max(hours) or 1.0
        peak = max(range(24), key=lambda h: hours[h])
        pitch = width / 24
        bar_w = max(3.0, pitch - 3)
        for h in range(24):
            x = h * pitch + (pitch - bar_w) / 2
            bar_h = hours[h] / top_v * height
            c.create_rectangle(
                x, height - max(2.0, bar_h), x + bar_w, height,
                fill=(P.title if h == peak and hours[h] > 0 else P.label)
                if hours[h] > 0 else P.track,
                width=0,
            )
            if h % 6 == 0:
                c.create_text(
                    x + bar_w / 2, height + 7, text=f"{h}", font=(NUM, 7), fill=P.faint
                )

    @staticmethod
    def _chart_windows(parent: tk.Misc, windows: list, width: int,
                       height: int = 40) -> None:
        """5시간 창마다 '어디까지 찼나' — 0~100% 고정 눈금이라 창끼리 바로 견준다."""
        c = tk.Canvas(
            parent, width=width, height=height + 13, bg=P.bg, highlightthickness=0, bd=0
        )
        c.pack(fill="x", pady=(0, 8))
        n = max(1, len(windows))
        pitch = width / n
        bar_w = max(4.0, pitch - 5)
        for i, w in enumerate(windows):
            x = i * pitch + (pitch - bar_w) / 2
            c.create_rectangle(x, 0, x + bar_w, height, fill=P.track, width=0)
            filled = w.peak / 100 * height
            c.create_rectangle(
                x, height - max(2.0, filled), x + bar_w, height,
                fill=tone(w.peak), width=0,
            )
            # 창이 열린 시각 — 하루 경계가 헷갈리지 않게 시(時)만 적는다
            c.create_text(
                x + bar_w / 2, height + 7, text=f"{w.start.hour}",
                font=(NUM, 7), fill=P.faint,
            )

    @staticmethod
    def _gap_sentence(p) -> str:
        """판정을 한 줄로 — 적정선(고르게 쓸 때)보다 얼마나 앞섰나/뒤졌나."""
        if p.used >= 99.5:
            return "이번 주 한도를 거의 다 썼어요"
        d = p.over  # 지금까지 사용 − 적정선
        if d <= -1:
            return f"고르게 쓸 때보다 {abs(d):.0f}%p 덜 썼어요"
        if d >= 1:
            return f"고르게 쓸 때보다 {d:.0f}%p 더 썼어요"
        return "고르게 쓰는 속도와 거의 같아요"

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
    def _open_panel(self, title: str, click_away: bool = True):
        """(top, body) 를 돌려준다. body 에 내용을 채운 뒤 _finalize_panel(top, w) 호출.

        새 팝업을 열면 먼저 떠 있던 팝업은 닫는다(한 번에 하나). `click_away` 가 참이면
        팝업 밖(위젯·바탕화면·다른 앱)을 누르면 저절로 닫힌다 — 읽기 전용 팝업용.
        편집 팝업(시각 설정·폰 연결)은 타이핑 중 사라지지 않게 False 로 연다."""
        self._close_panels()
        top = tk.Toplevel(self.root)
        top.withdraw()
        top.overrideredirect(True)
        top.configure(bg=P.bg)
        top.attributes("-topmost", True)
        top._click_away = click_away  # _finalize 가 이 값을 보고 포커스를 잡는다
        self._panels.append(top)
        top.bind("<Destroy>", lambda e, t=top: self._forget_panel(t) if e.widget is t else None)
        if click_away:
            top.bind("<FocusOut>", lambda _e, t=top: self._panel_focus_out(t))

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
        elif getattr(top, "_click_away", False):
            # 포커스를 쥐어야 '밖을 누르면 포커스가 빠져나가 닫힌다'가 동작한다
            try:
                top.focus_force()
            except tk.TclError:
                pass

    def _close_panels(self) -> None:
        """열려 있는 팝업을 모두 닫는다 (디자인·밝기 바꾸거나 위젯을 누를 때)."""
        for top in list(self._panels):
            try:
                top.destroy()
            except tk.TclError:
                pass
        self._panels.clear()

    def _forget_panel(self, top: tk.Toplevel) -> None:
        if top in self._panels:
            self._panels.remove(top)

    def _panel_focus_out(self, top: tk.Toplevel) -> None:
        """팝업이 포커스를 잃으면(밖을 누름) 닫는다. 포커스가 팝업 안에 그대로 있으면 둔다.
        포커스가 옮겨가 자리 잡을 틈을 주려 조금 뒤에 확인한다."""
        def check():
            try:
                if not top.winfo_exists():
                    return
                foc = top.focus_displayof()
            except (KeyError, tk.TclError):
                foc = None
            if foc is None or foc.winfo_toplevel() is not top:
                try:
                    top.destroy()
                except tk.TclError:
                    pass
        try:
            top.after(120, check)
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

    def _themed_button(self, parent, text, command, primary=False, width=7) -> tk.Button:
        """팔레트 색을 입힌 납작한 버튼. primary 는 초록 강조.

        `width` 는 **글자 수**라 7 을 넘는 이름은 그대로 잘린다 (`5시간 창 열고 잇기` 가
        `간 창 열고 잇` 으로 보였다). 긴 이름은 `width=0` 으로 넘겨 글자에 맞춰 늘린다.
        """
        if primary:
            bg, fg, active = P.green, P.bg, P.green
        else:
            bg, fg, active = P.track, P.title, P.line
        return tk.Button(
            parent,
            text=text,
            command=command,
            width=width,
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
        """실행 기록 — 성공은 점+시각만(글자 없이), 실패만 이유를 붙여 짧게 보여 준다.
        '실행됨'을 줄마다 반복하면 영수증처럼 늘어져 보여, 성공 줄에서는 뺀다."""
        try:
            entries = cooldown_ping.read_log_entries(40)
            # 여기서 까닭까지 봤으니 위젯의 '자동 시작 실패' 표시는 내린다
            if self._ping_fail is not None:
                self._ping_fail = None
                self._redraw()
            top, body = self._open_panel("실행 기록")
            wrap = tk.Frame(body, bg=P.bg)
            wrap.pack(fill="both", expand=True, padx=PANEL_PAD, pady=(2, PANEL_PAD))

            if not entries:
                tk.Label(
                    wrap, text="아직 실행된 적이 없어요.", bg=P.bg, fg=P.faint, font=(KR, 9)
                ).pack(anchor="w", pady=16)
                self._finalize_panel(top, 300)
                return

            shown = list(reversed(entries))[:8]  # 최근 8번만 (그 위는 접는다)
            fails = sum(1 for _w, ok, _d in shown if not ok)
            summary = f"최근 {len(shown)}번" + (
                f" · 실패 {fails}" if fails else " · 모두 실행됨"
            )
            tk.Label(
                wrap, text=summary, bg=P.bg, fg=P.faint, font=(KR, 8), anchor="w"
            ).pack(fill="x", pady=(0, 7))

            for when, ok, detail in shown:
                r = tk.Frame(wrap, bg=P.bg)
                r.pack(fill="x", pady=2)
                tk.Label(
                    r, text="●", bg=P.bg, fg=(P.green if ok else P.red), font=(KR, 7)
                ).pack(side="left", padx=(0, 9))
                tk.Label(
                    r, text=self._friendly_time(when), bg=P.bg,
                    fg=(P.sub if ok else P.title), font=(KR, 9), anchor="w",
                ).pack(side="left")
                # 성공은 시각만으로 충분하다 — 실패일 때만 이유를 붙인다
                if not ok:
                    tk.Label(
                        r, text="  " + cooldown_ping.friendly_error(detail),
                        bg=P.bg, fg=P.red, font=(KR, 9), anchor="w",
                    ).pack(side="left")

            if len(entries) > len(shown):
                tk.Label(
                    wrap, text=f"이전 {len(entries) - len(shown)}번 더",
                    bg=P.bg, fg=P.faint, font=(KR, 8),
                ).pack(anchor="w", pady=(7, 0))
            self._finalize_panel(top, 300)
        except Exception:  # noqa: BLE001
            pass

    def open_ping_times(self):
        """시각 설정 — 알람처럼 시:분 스테퍼(▲▼·스크롤)로 조절, 추가/삭제(✕).
        시각들은 5시간 1분 이상 벌어져 있어야 저장된다."""
        W = 300
        try:
            top, body = self._open_panel("모닝 스타터 · 시각", click_away=False)
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
