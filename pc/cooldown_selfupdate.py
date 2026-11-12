"""
클로드 쿨다운 — 쿨다운 **자기 자신의** 자동 업데이트 (순수 로직, Tk 없음)
======================================================================
2026-11-12 사용자 지시. v0.41 을 올렸는데 사용자 PC 위젯은 v0.39 그대로였다 — 알리기만 하고
받기·깔기는 사람이 해야 했기 때문이다. 이제 받고, 옆에 풀고, 바꿔 켠다.

순서
1. `cooldown_newver.release()` 로 최신 릴리스의 `claude-cooldown-v<버전>.zip` 자산(주소·크기·sha256)을 안다.
2. `fetch()` : `%TEMP%` 로 받아 **크기와 `digest`(sha256)를 맞춰 보고**, 지금 도는 폴더
   (`…\\클로드 쿨다운 v0.41\\`) **옆**에 `클로드 쿨다운 v0.42\\` 로 푼다. 도는 폴더는 붙잡혀 있어 덮어쓰지 않는다.
   푸는 것은 `… v0.42.part` 에 먼저 풀고 다 풀린 뒤 이름을 바꾼다 — 반쯤 풀린 폴더가 '받아 둠' 으로 보이지 않게.
3. 바꿔 켜기(앱이 한다): 내 뮤텍스를 **먼저 놓고** 새 exe 를 띄운 뒤(`launch`), 새 것이 뮤텍스를
   잡는 걸 보고서야(`wait_mutex`) 끝낸다. 놓고 띄우므로 새 것이 '이미 떠 있음' 으로 끝나지 않고,
   이 방식은 **새 버전이 이 업데이트를 몰라도**(v0.41 처럼) 된다. 못 보면 뮤텍스를 다시 잡고 남는다.
   새 것에는 `--after-update <옛 pid>` 를 준다. 새 것은 뮤텍스를 잡은 뒤 옛 것이 끝날 때까지
   몇 초 기다렸다(`wait_exit`) 설정을 읽는다 — 옛 것이 끝나며 저장하는 자리·설정을 이어받게.
4. `cleanup()` : 새 버전이 뜬 뒤(다음 시작 때) 옛 형제 폴더를 지운다. 지금 도는 폴더·바로 앞 버전 하나·
   더 새 버전은 남기고, **이름이 정확히 `클로드 쿨다운 v<숫자>` 꼴인 것만.** 지우기 전에 이름을 바꿔 보아
   (돌고 있는 폴더는 이름이 안 바뀐다) 쓰는 중인 폴더는 건드리지 않는다.

- ★ **소스(python)로 돌 때는 하지 않는다**(`can_self_update`). 버전 표시와 알림만.
- ★ 원격 대기(`claude rc`)는 위젯이 끝나도 안 죽고 새 위젯이 PID 파일로 이어받는다(`Remote.adopt`).
  그래서 바꿔 켜는 잣대는 세션 조용함이 아니라 **사람 입력이 `IDLE_MIN` 분 없음** 하나다
  (위젯이 보고 있는 눈앞에서 사라졌다 뜨지 않게).
- 시험용 환경변수 `CLAUDE_COOLDOWN_RELEASE_API`(=`cooldown_newver.API_ENV`): 릴리스 정보를 그 주소에서
  읽고, 시험이므로 기다리는 시간을 줄인다(`TEST`). 사용자 PC 에서는 비어 있다.

확인: `python pc/cooldown_selfupdate.py` (받을 것·지울 것만 보여 준다. 아무것도 안 바꾼다)
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

import requests

import cooldown_env
import cooldown_job
import cooldown_newver

FOLDER = "클로드 쿨다운 v{ver}"  # build_exe.py 가 짓는 폴더 이름
EXE = "클로드 쿨다운.exe"
ARG = "--after-update"  # 바꿔 켠 새 프로세스에 붙는다: --after-update <옛 pid>
_FOLDER_RE = re.compile(r"^클로드 쿨다운 v(\d+(?:\.\d+)*)$")
_LEFT_RE = re.compile(r"^클로드 쿨다운 v\d+(?:\.\d+)*\.(?:part|del)$")  # 내가 남긴 반쯤 된 것

TEST = bool(os.environ.get(cooldown_newver.API_ENV))
IDLE_MIN = 0.0 if TEST else 20.0  # 사람 입력이 이만큼 없어야 알아서 바꿔 켠다 (분)
MANUAL_FLOOR = 60  # [업데이트 확인] 연타 하한 (초). GitHub 익명 한도가 시간당 60번
WAIT_UP = 60  # 새 것이 뮤텍스를 잡을 때까지 기다리는 한도 (초). 처음 켜는 exe 는 디펜더가 훑느라 느리다
OLD_EXIT_WAIT = 20  # 새 것이 옛 것이 끝나길 기다리는 한도 (초)
_DETACHED = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP


def can_self_update() -> bool:
    """스스로 바꿔 끼울 수 있나 — exe 로 묶였고, 버전 붙은 폴더에서 돌 때만."""
    if not getattr(sys, "frozen", False):
        return False
    return bool(_FOLDER_RE.match(os.path.basename(here())))


def here() -> str:
    """지금 도는 버전 폴더."""
    return os.path.dirname(os.path.abspath(sys.executable))


def folder_for(ver: str) -> str:
    return os.path.join(os.path.dirname(here()), FOLDER.format(ver=ver))


def ready(ver: str) -> str | None:
    """그 버전이 옆에 다 풀려 있으면 exe 경로."""
    d = folder_for(ver)
    exe = os.path.join(d, EXE)
    try:
        with open(os.path.join(d, cooldown_newver.VERSION_FILE), encoding="utf-8") as f:
            ok = f.read().strip() == ver
    except OSError:
        return None
    return exe if ok and os.path.isfile(exe) else None


# ---------------------------------------------------------------- 받기·풀기


def fetch(rel: cooldown_newver.Release) -> tuple[str | None, str]:
    """받아서 맞춰 보고 옆에 푼다. (exe 경로, 못 했으면 까닭 — 짧은 명사형)"""
    exe = ready(rel.version)
    if exe:
        return exe, ""
    if not rel.url:
        return None, "릴리스에 zip 없음"
    fd, tmp = tempfile.mkstemp(prefix="claude-cooldown-", suffix=".zip")
    os.close(fd)
    try:
        why = _download(rel, tmp)
        if why:
            return None, why
        why = _extract(tmp, rel.version)
        if why:
            return None, why
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    exe = ready(rel.version)
    return (exe, "") if exe else (None, "풀었는데 exe 없음")


def _download(rel: cooldown_newver.Release, path: str) -> str:
    h = hashlib.sha256()
    n = 0
    try:
        with requests.get(rel.url, stream=True, timeout=(10, 60),
                          headers={"User-Agent": "claude-cooldown"}) as r:
            if r.status_code != 200:
                return f"받기 실패 HTTP {r.status_code}"
            with open(path, "wb") as f:
                for chunk in r.iter_content(1 << 16):
                    f.write(chunk)
                    h.update(chunk)
                    n += len(chunk)
    except (requests.RequestException, OSError) as e:
        return f"받기 실패 {type(e).__name__}"
    if rel.size and n != rel.size:
        return f"크기 다름 ({n} / {rel.size})"
    if rel.sha256 and h.hexdigest() != rel.sha256:
        return "sha256 다름"
    return ""


def _extract(zip_path: str, ver: str) -> str:
    """zip 맨 위 폴더가 `클로드 쿨다운 v<ver>` 하나뿐이어야 한다. 그 밖으로 나가는 이름은 거절."""
    top = FOLDER.format(ver=ver)
    parent = os.path.dirname(here())
    part = os.path.join(parent, top + ".part")
    final = os.path.join(parent, top)
    try:
        with zipfile.ZipFile(zip_path) as z:
            names = z.namelist()
            for name in names:
                parts = name.replace("\\", "/").split("/")
                if parts[0] != top or ".." in parts or ":" in name or name.startswith("/"):
                    return "zip 안 이름이 이상함"
            shutil.rmtree(part, ignore_errors=True)
            os.makedirs(part)
            for info in z.infolist():
                rel = info.filename.replace("\\", "/").split("/", 1)
                if len(rel) < 2 or not rel[1]:
                    continue
                dest = os.path.join(part, *rel[1].split("/"))
                if info.is_dir():
                    os.makedirs(dest, exist_ok=True)
                    continue
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with z.open(info) as src, open(dest, "wb") as out:
                    shutil.copyfileobj(src, out, 1 << 16)
        if os.path.isdir(final):  # 반쯤 된 옛것(버전 파일이 안 맞아 ready 가 아니었다)
            shutil.rmtree(final)
        os.rename(part, final)
    except (OSError, zipfile.BadZipFile) as e:
        shutil.rmtree(part, ignore_errors=True)
        return f"풀기 실패 {type(e).__name__}"
    return ""


# ---------------------------------------------------------------- 바꿔 켜기


def launch(exe: str, argv: list[str]) -> subprocess.Popen:
    """새 버전을 띄운다. 환경은 걷어낸 사본(`clean_env`)을 준다.

    ★ 탐색기를 거치지 않고 바로 띄운다. 위젯이 클로드 job 밖이면 자식도 따라 밖이다(`cooldown_job`).
      안이면 새 것이 제 job 빠져나오기로 알아서 나간다(그땐 뮤텍스가 비어 있으므로).
      빠져나오려고 다시 뜬 위젯(`--job-escaped`)이면 그 표시를 그대로 물려준다.
    """
    args = [exe, ARG, str(os.getpid())]
    if cooldown_job.MARK in argv[1:]:
        args.append(cooldown_job.MARK)
    return subprocess.Popen(args, cwd=os.path.dirname(exe), env=cooldown_env.clean_env(),
                            close_fds=True, creationflags=_DETACHED)


def wait_mutex(name: str, proc: subprocess.Popen | None, timeout: float = WAIT_UP) -> bool:
    """누군가 그 뮤텍스를 잡을 때까지 기다린다. 띄운 것이 먼저 끝나 버리면 바로 거짓."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cooldown_job.mutex_exists(name):
            return True
        if proc is not None and proc.poll() is not None:
            # 끝났더라도 그 사이 잡았을 수 있다(job 빠져나오기로 다시 뜬 경우) — 한 번 더 본다
            time.sleep(1.0)
            return cooldown_job.mutex_exists(name)
        time.sleep(0.2)
    return False


def after_update(argv: list[str]) -> int | None:
    """바꿔 켜서 뜬 새 프로세스면 옛 pid."""
    try:
        i = argv.index(ARG)
        return int(argv[i + 1])
    except (ValueError, IndexError):
        return None


def wait_exit(pid: int, timeout: float = OLD_EXIT_WAIT) -> bool:
    """그 프로세스가 끝날 때까지 기다린다. 끝났으면(또는 없으면) 참."""
    import ctypes

    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.OpenProcess.restype = ctypes.c_void_p
    k.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    k.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    k.CloseHandle.argtypes = [ctypes.c_void_p]
    h = k.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
    if not h:
        return True
    try:
        return k.WaitForSingleObject(h, int(timeout * 1000)) == 0
    finally:
        k.CloseHandle(h)


# ---------------------------------------------------------------- 옛 폴더 지우기


def stale_folders() -> list[str]:
    """지울 형제 폴더들. 지금 것·바로 앞 버전 하나·더 새 버전은 남긴다."""
    if not can_self_update():
        return []
    cur = os.path.basename(here())
    mine = cooldown_newver._key(_FOLDER_RE.match(cur).group(1))
    parent = os.path.dirname(here())
    older: list[tuple[tuple[int, ...], str]] = []
    left: list[str] = []
    try:
        names = os.listdir(parent)
    except OSError:
        return []
    for name in names:
        full = os.path.join(parent, name)
        if name == cur or not os.path.isdir(full):
            continue
        m = _FOLDER_RE.match(name)
        if m:
            k = cooldown_newver._key(m.group(1))
            if k < mine:
                older.append((k, full))
        elif _LEFT_RE.match(name):
            left.append(full)
    older.sort()
    return [p for _k, p in older[:-1]] + left


def cleanup() -> tuple[list[str], list[str]]:
    """옛 폴더를 지운다. (지운 이름들, 못 지운 이름들). 쓰는 중이면 이름 바꾸기에서 막혀 건너뛴다."""
    done, kept = [], []
    for path in stale_folders():
        name = os.path.basename(path)
        trash = path if name.endswith(".del") else path + ".del"
        try:
            if trash != path:
                os.rename(path, trash)  # 도는 exe 가 있으면 여기서 막힌다
            shutil.rmtree(trash)
            done.append(name)
        except OSError:
            kept.append(name)
    return done, kept


if __name__ == "__main__":
    print("스스로 업데이트 가능:", can_self_update(), "(소스로 돌면 늘 거짓)")
    rel = cooldown_newver.release()
    if rel is None:
        print("최신: (못 물어봄)")
    else:
        print(f"최신: {rel.version}  zip {rel.size} 바이트  sha256 {rel.sha256[:12] or '없음'}…")
        print("  ", rel.url)
    print("지울 옛 폴더:", stale_folders() or "없음")
