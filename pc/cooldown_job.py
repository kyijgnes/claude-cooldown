r"""
클로드 데스크톱 job 에서 빠져나오기 — 순수 로직, Tk 없음
==========================================================

★★ **클로드 코드 세션(데스크톱 앱)에서 띄운 위젯은 클로드 데스크톱과 한 job 에 든다.**
세션의 CLI·셸은 물론 `Start-Process` 로 떼어 띄운 자식까지 전부 같은 job 이다. 클로드 자체
업데이터가 미뤄 둔 등록을 `ForceApplicationShutdownOption` 으로 적용하면
(AppXDeploymentServer/Operational 9643 `TerminateApplications`) 그 job 이 통째로 끝나,
위젯도 앱 로그에 `종료 —` 줄 없이 사라진다 — 2026-09-14 05:41:58 에 겪었다.
로그온 때 시작 프로그램으로 뜬 위젯은 다른 job 이라 9/11·9/12 강제 업데이트를 살아남았다.

그래서 시작할 때(**뮤텍스를 잡기 전**) 제 job 에 `\WindowsApps\Claude_` 프로세스가 있는지 보고,
있으면 **탐색기에게 바로가기(`~/.claude_cooldown_relaunch.lnk`)를 열게 해** 다시 띄우고 끝낸다.
부모가 탐색기가 되어 클로드 job 밖이고, 환경변수도 탐색기 것이라 세션 환경(`CLAUDECODE=1`·
`CLAUDE_CODE_SESSION_ID`…)이 위젯의 `claude rc`·핑까지 번지지 않는다. 위젯이 띄우는 자식은
부모의 job 을 물려받으므로 위젯이 밖이면 따라 밖이다(손주까지 실측).
바로가기를 거치는 까닭은 아래 표시 인자를 실어 보내기 위해서다 — `explorer.exe "<exe>"` 는 인자를 못 준다.

- ★★ **`CREATE_BREAKAWAY_FROM_JOB` 로는 못 빠져나온다**(2026-09-14 실측 — 되살리지 말 것).
  job 이 두 겹이다: 세션이 든 안쪽 job(`0x800` BREAKAWAY_OK, 23개)이 **바깥 job(`0x0`, 25개)** 안에
  들어 있고, **바깥에도 클로드 데스크톱 본체가 다 들어 있다.** 떼어 띄우면 안쪽에서만 빠지고 바깥에
  남는다(자식의 job 목록에 클로드 13개 그대로). 안쪽 job 의 한도만 보고 '허용된다' 고 믿기 쉽다.
- ★ **새 프로세스가 뮤텍스를 잡는 것을 보고서야 끝낸다.** `WAIT_UP` 안에 못 보면 그 자리에서 그냥
  뜬다 — 위젯이 아예 안 뜨는 것보다 낫다(늦게 뜬 쪽은 뮤텍스를 보고 이쪽을 부르고 끝난다).
- ★ **무한 재실행 막기**: 다시 띄울 때 `--job-escaped` 를 붙인다. 그게 있으면 다시 빠져나가지 않고,
  제가 정말 밖인지 보기만 해서 앱 로그에 적는다.
- ★ **탐색기(바탕화면 셸)가 안 떠 있으면 부르지 않는다**(`GetShellWindow`). 그때 `explorer.exe` 를
  띄우면 셸이 통째로 이 job 안에서 새로 뜬다.
- 판정은 **제 job 의 프로세스 목록**(`QueryInformationJobObject(NULL, JobObjectBasicProcessIdList)`)으로
  한다. 세션 자식에게는 패키지 ID 가 없어 `GetPackageFullName` 으로는 안 보인다.
- `pythonw` 를 PATH 의 별칭(파이썬 설치 관리자)으로 띄우면 진짜 pythonw 는 설치 관리자가 제 job(`0x3000`)에
  넣어 띄워 **처음부터 클로드 job 밖**이다(같은 날 실측). 그 경우엔 빠져나올 일이 없다.
- 못 물어보면(API 실패) '안 들었다' 로 본다 — 없는 걱정으로 다시 띄우지 않는다.

확인: `python pc/cooldown_job.py` — 지금 이 셸이 클로드 job 안인지.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes

import cooldown_env

MARK = "--job-escaped"  # 다시 띄운 프로세스에 붙는 표시
CLAUDE_MARK = "\\windowsapps\\claude_"  # 클로드 데스크톱 본체 경로(소문자로 견줌). cooldown_update.PKG_MARK 와 같은 결
# 다시 띄운 것이 뮤텍스를 잡을 때까지 기다리는 한도 (초). 새 판 exe 를 처음 켤 땐 디펜더가 훑느라 오래 걸린다.
WAIT_UP = 60
LNK_PATH = os.path.join(os.path.expanduser("~"), ".claude_cooldown_relaunch.lnk")

_PID_LIST = 3  # JobObjectBasicProcessIdList
_MORE_DATA = 234  # ERROR_MORE_DATA
_QUERY_LIMITED = 0x1000  # PROCESS_QUERY_LIMITED_INFORMATION
_SYNCHRONIZE = 0x00100000
_k32 = None


def _kernel32():
    """kernel32 를 따로 연다 — `ctypes.windll.kernel32` 에 argtypes 를 박으면 앱의 다른 곳이 영향받는다."""
    global _k32
    if _k32 is None:
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.QueryInformationJobObject.argtypes = [
            wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)
        ]
        k.QueryInformationJobObject.restype = wintypes.BOOL
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.OpenProcess.restype = wintypes.HANDLE
        k.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
        ]
        k.QueryFullProcessImageNameW.restype = wintypes.BOOL
        k.OpenMutexW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
        k.OpenMutexW.restype = wintypes.HANDLE
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        _k32 = k
    return _k32


# ---------------------------------------------------------------- 판정


def job_pids() -> list[int] | None:
    """제가 든 job 의 프로세스 번호들(겹친 job 이면 안쪽 job 과 그 아래). 안 들었거나 못 물어보면 None."""
    k = _kernel32()
    n = 256
    while n <= 1 << 16:

        class Buf(ctypes.Structure):
            _fields_ = [
                ("assigned", wintypes.DWORD),
                ("listed", wintypes.DWORD),
                ("pids", ctypes.c_size_t * n),
            ]

        buf = Buf()
        if k.QueryInformationJobObject(None, _PID_LIST, ctypes.byref(buf), ctypes.sizeof(buf), None):
            return [int(buf.pids[i]) for i in range(buf.listed)]
        if ctypes.get_last_error() != _MORE_DATA:
            return None
        n = max(n * 4, buf.assigned + 16)
    return None


def _image(pid: int) -> str:
    """프로세스 실행 파일 전체 경로. 못 열면 빈 문자열."""
    k = _kernel32()
    h = k.OpenProcess(_QUERY_LIMITED, False, pid)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buf))
        return buf.value if k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)) else ""
    finally:
        k.CloseHandle(h)


def claude_in_my_job() -> bool:
    """클로드 데스크톱과 한 job 에 들었나."""
    try:
        me = os.getpid()
        return any(CLAUDE_MARK in _image(p).lower() for p in job_pids() or () if p != me)
    except Exception:  # noqa: BLE001  못 물어보면 안 든 것으로
        return False


def escaped(argv: list[str]) -> bool:
    """빠져나오려고 다시 띄운 프로세스인가."""
    return MARK in argv[1:]


def mutex_exists(name: str) -> bool:
    """그 이름의 뮤텍스가 있나 — 만들지 않고 열어만 본다."""
    k = _kernel32()
    h = k.OpenMutexW(_SYNCHRONIZE, False, name)
    if h:
        k.CloseHandle(h)
        return True
    return ctypes.get_last_error() == 5  # ERROR_ACCESS_DENIED — 있긴 하다


# ---------------------------------------------------------------- 다시 띄우기


def relaunch_outside(exe: str, args: str, workdir: str, mutex: str) -> tuple[bool, str]:
    """탐색기를 거쳐 클로드 job 밖으로 다시 띄운다. (새 프로세스가 떴나, 못 떴으면 까닭)"""
    try:
        user32 = ctypes.WinDLL("user32")
        user32.GetShellWindow.restype = wintypes.HWND
        if not user32.GetShellWindow():
            return False, "탐색기 안 떠 있음"
    except Exception:  # noqa: BLE001
        return False, "탐색기 확인 못 함"
    try:
        from win32com.client import Dispatch

        link = Dispatch("WScript.Shell").CreateShortCut(LNK_PATH)
        link.TargetPath = exe
        link.Arguments = " ".join(x for x in (args, MARK) if x)
        link.WorkingDirectory = workdir
        link.Save()
        # 이렇게 띄운 explorer.exe 는 떠 있는 셸에게 넘기고 바로 끝난다 — 바로가기를 여는 것은 그 셸이다.
        explorer = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "explorer.exe")
        # ★ 환경은 걷어내고 넘긴다. 지금 내가 오염된 셸에서 떴다면(클로드 세션 아래) 그
        #   값이 다시 뜨는 나에게, 나아가 탐색기 쪽으로까지 번진다(`cooldown_env` 참고).
        subprocess.Popen([explorer, LNK_PATH], env=cooldown_env.clean_env())
    except Exception as e:  # noqa: BLE001
        return False, f"바로가기 못 엶 {e}"
    end = time.monotonic() + WAIT_UP
    while time.monotonic() < end:
        if mutex_exists(mutex):
            return True, ""
        time.sleep(0.1)
    return False, f"{WAIT_UP}초 안에 안 뜸"


if __name__ == "__main__":
    pids = job_pids()
    print("job:", "안 들었음" if pids is None else f"프로세스 {len(pids)}개")
    print("클로드 데스크톱과 한 job:", claude_in_my_job())
    sys.exit(0)
