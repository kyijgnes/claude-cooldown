r"""
클로드가 강제로 닫힌 뒤 **다시 안 켜지는 것** 풀기 — 순수 로직, Tk 없음
=====================================================================

**왜 있나.** 2026-09-23 02:14 에 클로드 자체 업데이터가 미뤄 둔 등록을
`ForceApplicationShutdownOption` 으로 적용했다(2.2553.1.0 → 2.2553.13.0). 등록은 4초 만에 끝났는데
**새 판이 한 번도 안 켜졌다** — 업데이터가 곧바로 다시 켠 것(02:14:33)부터 사람이 아침에 누른 것
(05:17~05:22, 일곱 번)까지 전부 `이 파일을 다른 응용 프로그램에서 사용 중입니다` 로 막혔고,
**윈도우를 다시 시작하고서야** 켜졌다.

이벤트 로그 `Microsoft-Windows-AppModel-Runtime/Admin` 이 까닭을 말한다:

- **215** `0x80070020: 작업을 변환하는 동안 오류가 발생하여 … 데스크톱 AppX 컨테이너를 만들 수 없습니다`
- **208** `0x80070020: 런타임을 구성하는 동안 오류가 발생하여 … 프로세스를 만들 수 없습니다 [LaunchProcess]`

여기서 '작업' 은 **job** 이다. 클로드 데스크톱은 MSIX 라 앱 컨테이너(= job) 안에서 돌고,
**클로드 코드 세션과 세션이 띄운 셸·스크립트·개발 서버도 전부 그 job 에 든다**(세션 셸에서
`cooldown_job.job_pids()` 로 실측: 패키지 Claude.exe 14개 + CLI·bash·conhost 16개가 한 목록).
강제 종료는 **패키지 ID 가 있는 것(Claude.exe)만** 죽이고, ID 가 없는 세션 자손은 남을 수 있다.
그것이 하나라도 살아 있으면 옛 컨테이너(job)가 안 닫혀 **새 판 컨테이너를 못 만든다.**
재부팅하면 풀리는 것도 이것과 맞는다(남은 것이 다 죽으니까).

- 패키지 서비스(`cowork-svc.exe`)는 범인이 아니다 — SYSTEM 쪽 제 컨테이너라, 막혀 있던 05:17 에도
  서비스 컨테이너는 새로 잘 만들어졌다(이벤트 210·211). 막힌 것은 **사용자 쪽 앱 컨테이너**뿐이었다.
- 무엇이 남았었는지는 재부팅으로 증거가 사라져 모른다. 그래서 **짐작 대신 기억해 둔다** —
  앱이 떠 있는 동안 그 아래 식구(자손)를 주기적으로 적어 두고, 앱이 사라진 뒤에도 살아 있는
  식구만 남은 것으로 본다(`Watch`). 모르는 프로세스는 절대 안 건드린다.

**언제 치우나 — 둘 중 하나일 때만.** 사람이 일부러 클로드를 닫고 빌드를 돌려 두었을 수도 있으니
앱이 사라졌다는 것만으로는 안 치운다.

1. **업데이트로 닫혔다** — 지금 등록된 판이 사라진 앱의 판과 다르다. 새 판은 어차피 새로 켜야 하고,
   남은 식구가 있는 한 켜지지 않는다.
2. **켜려다 막혔다** — 앱이 사라진 뒤에 208·0x80070020 이 찍혔다(업데이터든 사람이든).

치운 뒤에는 클로드를 다시 켜고, 떠 있는 `사용 중` 알림 창도 닫는다.

확인: `python pc/cooldown_leftover.py` — 지금 클로드 식구와(떠 있으면) 앱이 없다면 남은 것.
"""

from __future__ import annotations

import ctypes
import os
import re
import subprocess
import time
from ctypes import wintypes
from dataclasses import dataclass

import cooldown_update

PKG_MARK = cooldown_update.PKG_MARK.lower()  # 클로드 데스크톱 본체가 앉은 곳
APP_LINK = cooldown_update.APP_LINK
_VER = re.compile(r"\\claude_([\d.]+)_", re.I)

SETTLE = 20  # 앱이 사라진 뒤 이만큼은 기다린다(초) — 세션 CLI 는 부모가 죽으면 스스로 끝난다
UP_WAIT = 60  # 다시 켠 앱이 뜨기를 기다리는 한도(초)
KILL_WAIT = 15  # 죽인 것이 사라지기를 기다리는 한도(초)
ASK_EVERY = 45  # 앱이 없는 동안 '켜려다 막혔나' 를 물어보는 간격(초)

_TH32CS_SNAPPROCESS = 0x2
_QUERY_LIMITED = 0x1000
_INVALID = ctypes.c_void_p(-1).value
_NO_WINDOW = 0x08000000
_WM_CLOSE = 0x0010
_k32 = None


class _Entry(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


def _kernel32():
    """kernel32 를 따로 연다 — `ctypes.windll.kernel32` 에 argtypes 를 박으면 앱의 다른 곳이 영향받는다."""
    global _k32
    if _k32 is None:
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        k.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_Entry)]
        k.Process32FirstW.restype = wintypes.BOOL
        k.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_Entry)]
        k.Process32NextW.restype = wintypes.BOOL
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.OpenProcess.restype = wintypes.HANDLE
        k.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(ctypes.c_ulonglong)] * 4
        k.GetProcessTimes.restype = wintypes.BOOL
        k.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
        ]
        k.QueryFullProcessImageNameW.restype = wintypes.BOOL
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        _k32 = k
    return _k32


@dataclass(frozen=True)
class Proc:
    pid: int
    ppid: int
    name: str
    ctime: int  # 만든 시각(FILETIME). 못 열었으면 0
    path: str  # 이름이 claude.exe 인 것만 채운다(본체를 가리는 데만 쓴다)

    @property
    def desktop(self) -> bool:
        return PKG_MARK in self.path.lower()


def snapshot() -> dict[int, Proc] | None:
    """지금 떠 있는 프로세스 전부. 못 찍었으면 None."""
    k = _kernel32()
    snap = k.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
    if not snap or snap == _INVALID:
        return None
    rows: list[tuple[int, int, str]] = []
    try:
        e = _Entry()
        e.dwSize = ctypes.sizeof(e)
        ok = k.Process32FirstW(snap, ctypes.byref(e))
        while ok:
            rows.append((int(e.th32ProcessID), int(e.th32ParentProcessID), e.szExeFile))
            ok = k.Process32NextW(snap, ctypes.byref(e))
    finally:
        k.CloseHandle(snap)

    out: dict[int, Proc] = {}
    for pid, ppid, name in rows:
        if pid == 0:
            continue
        ctime, path = 0, ""
        h = k.OpenProcess(_QUERY_LIMITED, False, pid)
        if h:
            try:
                c, x, kt, ut = (ctypes.c_ulonglong() for _ in range(4))
                if k.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(x), ctypes.byref(kt), ctypes.byref(ut)):
                    ctime = int(c.value)
                if name.lower() == "claude.exe":
                    buf = ctypes.create_unicode_buffer(1024)
                    size = wintypes.DWORD(len(buf))
                    if k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                        path = buf.value
            finally:
                k.CloseHandle(h)
        out[pid] = Proc(pid, ppid, name, ctime, path)
    return out


def _parent(p: Proc, procs: dict[int, Proc]) -> Proc | None:
    """진짜 부모(살아 있을 때만). 번호가 다시 쓰였으면(부모가 자식보다 늦게 떴으면) 없는 것으로."""
    q = procs.get(p.ppid)
    if q is None or q.pid == p.pid:
        return None
    if p.ctime and q.ctime and q.ctime > p.ctime:
        return None
    return q


def desktop_version(procs: dict[int, Proc]) -> str:
    """떠 있는 데스크톱 앱의 판. 안 떠 있으면 빈 문자열."""
    for p in procs.values():
        if p.desktop:
            m = _VER.search(p.path)
            if m:
                return m.group(1)
    return ""


def family(procs: dict[int, Proc], me: int) -> dict[int, tuple[int, str]]:
    """데스크톱 앱과 그 아래 자손 전부 `{번호: (만든 시각, 이름)}`. 위젯 자신과 그 아래는 뺀다."""
    out: dict[int, tuple[int, str]] = {}
    for p in procs.values():
        cur: Proc | None = p
        for _hop in range(32):
            if cur is None or cur.pid == me:
                break
            if cur.desktop:
                if p.ctime:  # 못 연 것은 뒤에 같은 것인지 가릴 수 없어 안 적는다
                    out[p.pid] = (p.ctime, p.name)
                break
            cur = _parent(cur, procs)
    return out


def leftovers(
    remembered: dict[int, tuple[int, str]], procs: dict[int, Proc], me: int
) -> list[Proc]:
    """앱이 사라진 뒤에도 살아 있는 옛 식구.

    둘 중 하나면 식구다:
    - 적어 둔 그 프로세스 그대로(번호와 **만든 시각이 둘 다** 같다 — 번호만 같으면 딴 것일 수 있다)
    - 적어 둔 식구가 **적은 뒤에** 낳은 것(마지막으로 적은 뒤에 뜬 백그라운드). 부모가 죽었어도
      자식에게 부모 번호는 남으므로, 그 번호가 적어 둔 식구이고 자식이 그보다 늦게 떴으면 식구다.
    """
    out: list[Proc] = []
    for p in procs.values():
        if p.pid == me or not p.ctime:
            continue
        cur: Proc | None = p
        for _hop in range(32):
            if cur is None or cur.pid == me:
                break
            known = remembered.get(cur.pid)
            if known and known[0] == cur.ctime:
                out.append(p)
                break
            up = _parent(cur, procs)
            if up is None:
                # 원래 부모가 죽었다(번호가 비었거나, 더 늦게 뜬 딴 것이 그 번호를 쓰고 있다).
                # 그 번호가 적어 둔 식구이고 이 프로세스가 그보다 늦게 떴으면 그 자식이다.
                dead = remembered.get(cur.ppid)
                if dead and cur.ctime and dead[0] <= cur.ctime:
                    out.append(p)
                break
            cur = up
    return out


# ---------------------------------------------------------------- 판정 재료

_BLOCKED_PS = r"""
$ErrorActionPreference = 'SilentlyContinue'
$n = @(Get-WinEvent -FilterHashtable @{
        LogName = 'Microsoft-Windows-AppModel-Runtime/Admin'; Id = 208; StartTime = [datetime]'__SINCE__'
      } | Where-Object { $_.Message -match 'Claude_' -and $_.Message -match '0x80070020' }).Count
"n=$n"
"""


def launch_blocked(since: float) -> bool | None:
    """`since`(epoch) 뒤에 클로드 실행이 0x80070020 으로 막힌 적이 있나. 못 물어봤으면 None."""
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(since))
    out = cooldown_update._ps(_BLOCKED_PS.replace("__SINCE__", stamp), timeout=30)
    m = re.search(r"n=(\d+)", out or "")
    if not m:
        return None
    return int(m.group(1)) > 0


def kill(procs: list[Proc]) -> list[Proc]:
    """죽이고, 끝내 안 죽은 것을 돌려준다. 가지째(`/T`) — 그 아래도 같은 job 식구다."""
    for p in procs:
        cooldown_update._run(["taskkill", "/F", "/T", "/PID", str(p.pid)], timeout=15)
    end = time.monotonic() + KILL_WAIT
    left = procs
    while time.monotonic() < end:
        now = snapshot() or {}
        left = [p for p in procs if p.pid in now and now[p.pid].ctime == p.ctime]
        if not left:
            break
        time.sleep(0.5)
    return left


def desktop_up() -> bool:
    return any(p.desktop for p in (snapshot() or {}).values())


def start_desktop() -> bool:
    """탐색기를 거쳐 클로드를 켜고, 뜨는 것을 본다(`UP_WAIT` 초까지)."""
    explorer = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "explorer.exe")
    try:
        subprocess.Popen([explorer, APP_LINK], creationflags=_NO_WINDOW)
    except OSError:
        return False
    end = time.monotonic() + UP_WAIT
    while time.monotonic() < end:
        if desktop_up():
            return True
        time.sleep(1)
    return False


def close_in_use_boxes() -> int:
    r"""떠 있는 `이 파일을 다른 응용 프로그램에서 사용 중입니다` 창을 닫는다. 닫은 개수.

    제목이 클로드 실행 파일 경로(`C:\Program Files\WindowsApps\Claude_…\app\Claude.exe`)인
    대화 상자(`#32770`)만 고른다 — 탐색기가 띄운 알림이라 이렇게밖에 못 가린다.
    """
    user32 = ctypes.WinDLL("user32")
    found: list[int] = []
    proto = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def each(hwnd, _lp):
        cls = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, cls, 64)
        if cls.value == "#32770":
            title = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, title, 512)
            t = title.value.lower()
            if PKG_MARK in t and t.endswith("claude.exe"):
                found.append(hwnd)
        return True

    user32.EnumWindows(proto(each), 0)
    for hwnd in found:
        user32.PostMessageW(hwnd, _WM_CLOSE, 0, 0)
    return len(found)


# ---------------------------------------------------------------- 지켜보기


@dataclass
class Result:
    """치운 결과 — 앱이 사람에게 그대로 보여 줄 수 있게."""

    ok: bool  # 다시 켜졌나
    why: str  # 치운 까닭 (`업데이트` · `실행 막힘`)
    names: list[str]  # 치운 것 이름
    stuck: list[str]  # 안 죽은 것 이름


class Watch:
    """앱이 떠 있는 동안 식구를 적어 두고, 사라진 뒤 막혀 있으면 치운다.

    `step()` 을 작업 스레드에서 주기적으로 부른다(한 번에 수 ms, 치울 때만 몇십 초).
    치웠으면 `Result`, 아니면 None 을 준다. **사라질 때마다 한 번만** 치운다 — 치워도 안 켜지면
    되풀이하지 않고 사람에게 넘긴다(되풀이는 2026-08-14 에 밤새 클로드를 죽인 길이다).
    """

    def __init__(self, me: int | None = None):
        self.me = me or os.getpid()
        self.remembered: dict[int, tuple[int, str]] = {}
        self.ver = ""  # 마지막으로 본 데스크톱 판
        self.gone_at: float | None = None  # 데스크톱이 사라진 것을 처음 본 때(epoch)
        self.done = False  # 이번에 사라진 것은 이미 다뤘나
        self._installed = ""  # 사라진 뒤 읽은 등록 판(한 번 읽으면 그대로 쓴다)
        self._asked_at = 0.0  # 실행이 막혔는지 마지막으로 물어본 때(epoch)

    def step(self) -> Result | None:
        procs = snapshot()
        if procs is None:
            return None
        if any(p.desktop for p in procs.values()):
            self.remembered = family(procs, self.me)
            self.ver = desktop_version(procs) or self.ver
            self.gone_at, self.done, self._installed, self._asked_at = None, False, "", 0.0
            return None
        if not self.remembered or self.done:
            return None

        now = time.time()
        if self.gone_at is None:
            self.gone_at = now
        left = leftovers(self.remembered, procs, self.me)
        if not left:
            # 남은 것이 없다 — 켜지든 막히든 이 까닭은 아니다. 적어 둔 것은 이제 쓸모없다.
            self.remembered, self.done = {}, True
            return None
        if now - self.gone_at < SETTLE:
            return None

        why = ""
        if not self._installed:
            self._installed = cooldown_update.installed_version()
        if self._installed and self.ver and cooldown_update._ver(self._installed) != cooldown_update._ver(self.ver):
            why = f"업데이트 {self.ver} → {self._installed}"
        elif now - self._asked_at >= ASK_EVERY:
            # 이벤트 로그는 파워셸이라 0.5초쯤 걸린다 — 사람이 닫아 둔 동안 15초마다 부르지 않는다
            self._asked_at = now
            if launch_blocked(self.gone_at - 5):
                why = "실행 막힘"
        if not why:
            return None  # 사람이 닫은 것일 수 있다 — 켜려다 막히기 전에는 안 건드린다

        self.done = True
        stuck = kill(left)
        ok = start_desktop()
        if ok:
            close_in_use_boxes()
        return Result(
            ok=ok,
            why=why,
            names=sorted({p.name for p in left}),
            stuck=sorted({p.name for p in stuck}),
        )


if __name__ == "__main__":
    ps = snapshot() or {}
    me = os.getpid()
    fam = family(ps, me)
    print("데스크톱 판:", desktop_version(ps) or "안 떠 있음")
    print("식구:", len(fam), "개")
    names: dict[str, int] = {}
    for _c, n in fam.values():
        names[n] = names.get(n, 0) + 1
    print("   ", " · ".join(f"{n} {c}" for n, c in sorted(names.items())))
    # 적어 둔 식구가 앱 없이도 살아 있다고 치고 가려 본다 — 앱이 떠 있으면 본체와 CLI 도 다 나온다
    print("남은 것으로 볼 것:", len(leftovers(fam, ps, me)), "개 (앱이 떠 있으면 식구 수와 같아야 한다)")
