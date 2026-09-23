r"""
밖으로 띄우는 것에 줄 환경변수 — 내 PyInstaller 런타임을 걷어낸 것
===================================================================

exe(PyInstaller onedir)로 돌면 부트로더가 **제 런타임 자리를 환경변수에 적어 둔다.**

    TCL_LIBRARY = …\클로드 쿨다운 v0.28\_internal\_tcl_data
    TK_LIBRARY  = …\클로드 쿨다운 v0.28\_internal\_tk_data
    PATH        = …\클로드 쿨다운 v0.28\_internal\pywin32_system32;<원래 PATH>
    _PYI_ARCHIVE_FILE · _PYI_PARENT_PROCESS_LEVEL · _PYI_APPLICATION_HOME_DIR

그 환경은 **자식에게 그대로 내려간다.** 위젯이 클로드 데스크톱을 다시 켜면(강제
업데이트 뒤 되살리기, `cooldown_leftover`·`cooldown_update`) 클로드와 그 아래 모든
세션·셸·빌드가 이 값을 물려받아, **남의 파이썬이 쿨다운 폴더에서 Tcl 을 찾다 죽는다.**

    tk.Tk()      → Can't find a usable init.tcl in the following directories: {…쿨다운…}
    PyInstaller  → ERROR: Your platform does not support the splash screen feature,
                          since tkinter is not installed.

2026-09-23 어드민 v2.57 릴리스가 이것으로 멈췄다(파이썬도 tkinter 도 멀쩡했다).
영구 변수가 아니라 **물려받은 것**이라 겉으로 드러나지도 않는다. 게다가 폴더 이름에
판 번호가 박혀 있어, 위젯을 한 판 올리면 물려받은 쪽은 **없어진 자리**를 가리킨다.

**그래서 밖으로 무엇을 띄우든 `clean_env()` 를 준다.**

★ 내 환경(`os.environ`)은 건드리지 않는다. Tcl 은 인터프리터를 만들 때마다
  `TCL_LIBRARY` 를 읽으므로, 내 것을 지우면 다음에 뜨는 내 창이 죽는다.
  걷어내는 것은 **자식에게 주는 사본**뿐이다.

거꾸로, 위젯이 **오염된 셸에서 떠도**(클로드 세션에서 `python cooldown_app.py`) 죽지
않게 `heal_self()` 가 물려받은 남의 값을 골라 지운다. tkinter 보다 먼저 부른다.

확인: `python pc/cooldown_env.py` — 지금 환경에서 무엇이 걷히는지 보여 준다.
"""

from __future__ import annotations

import os
import sys

# PyInstaller 부트로더·런타임 훅이 넣는 것. 자식에게는 하나도 넘기지 않는다.
PYI_VARS = (
    "_MEIPASS2",                   # onefile 부트로더(옛 판)
    "_PYI_APPLICATION_HOME_DIR",
    "_PYI_ARCHIVE_FILE",
    "_PYI_PARENT_PROCESS_LEVEL",
    "_PYI_SPLASH_IPC",
    "PYINSTALLER_RESET_ENVIRONMENT",
)

# Tcl/Tk 자리. 값이 **내 런타임이거나 없어진 자리**일 때만 뺀다
# (사람이 일부러 잡아 둔 멀쩡한 경로는 그대로 둔다).
TK_VARS = {
    "TCL_LIBRARY": "init.tcl",
    "TK_LIBRARY": "tk.tcl",
    "TKPATH": "tk.tcl",
}


def _norm(path: str) -> str:
    try:
        return os.path.normcase(os.path.abspath(path))
    except (OSError, ValueError):
        return ""


def _under(path: str, root: str) -> bool:
    """`path` 가 `root` 이거나 그 아래인가."""
    p, r = _norm(path), _norm(root)
    return bool(p and r and (p == r or p.startswith(r + os.sep)))


def runtime_dirs() -> list[str]:
    """내 PyInstaller 런타임이 앉은 자리들. 파이썬으로 돌면 빈 목록."""
    if not getattr(sys, "frozen", False):
        return []
    dirs = []
    for path in (
        getattr(sys, "_MEIPASS", ""),                 # onedir 이면 exe 옆 `_internal`
        os.environ.get("_PYI_APPLICATION_HOME_DIR", ""),
        os.path.dirname(os.path.abspath(sys.executable)),
    ):
        if path and _norm(path) not in [_norm(d) for d in dirs]:
            dirs.append(path)
    return dirs


def _usable(var: str, value: str) -> bool:
    """그 자리에 Tcl/Tk 가 실제로 있나. 없어진 폴더면 거짓."""
    marker = TK_VARS.get(var, "")
    try:
        return os.path.exists(os.path.join(value, marker)) if marker else os.path.isdir(value)
    except (OSError, ValueError):
        return False


def _mine(value: str) -> bool:
    return any(_under(value, d) for d in runtime_dirs())


def _packed(value: str) -> bool:
    """PyInstaller 가 제 속에 싸 둔 Tcl/Tk 자리인가(`…\\_internal\\_tcl_data`).

    폴더가 아직 살아 있어도 **남의 exe 것**이면 쓰면 안 된다. 거기 든 Tcl 은 그 exe 에
    맞춰 싸인 판이라, 다른 파이썬이 끌어다 쓰면 판이 어긋나 창이 안 뜬다.
    """
    p = _norm(value)
    return bool(p) and (
        os.path.basename(p) in ("_tcl_data", "_tk_data")
        or (os.sep + "_internal" + os.sep) in p + os.sep
    )


def _drop(var: str, value: str) -> bool:
    """자식에게(또는 나에게서) 걷어낼 값인가. 사람이 잡아 둔 멀쩡한 경로는 남긴다."""
    return _mine(value) or _packed(value) or not _usable(var, value)


def clean_env(base: dict | None = None) -> dict:
    """자식에게 줄 환경변수. 내 PyInstaller 런타임 자국을 걷어낸 사본을 돌려준다."""
    env = dict(base if base is not None else os.environ)

    for var in PYI_VARS:
        env.pop(var, None)

    for var in TK_VARS:
        value = env.get(var)
        if value and _drop(var, value):
            env.pop(var, None)

    # PyInstaller 가 비윈도우에서 원래 값을 여기 넣어 둔다. 있으면 되돌린다.
    for var in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
        orig = env.pop(var + "_ORIG", None)
        if orig is not None:
            env[var] = orig
        elif var in env and _mine(env[var]):
            env.pop(var, None)

    mine = runtime_dirs()
    if mine and env.get("PATH"):
        kept = [
            part
            for part in env["PATH"].split(os.pathsep)
            if part and not any(_under(part, d) for d in mine)
        ]
        env["PATH"] = os.pathsep.join(kept)

    return env


def heal_self() -> list[str]:
    """**내가** 물려받은 남의 PyInstaller 자국을 지운다. 지운 이름들을 돌려준다.

    ★ tkinter·PIL(ImageTk)보다 **먼저** 부른다. 오염된 셸에서 위젯을 띄우면
      (클로드 세션에서 `python cooldown_app.py`) 그 값으로 Tcl 을 찾다 창이 안 뜬다.
      내 것(`runtime_dirs()` 아래)은 그대로 둔다.
    """
    gone: list[str] = []

    for var in TK_VARS:
        value = os.environ.get(var)
        if value and not _mine(value) and _drop(var, value):
            os.environ.pop(var, None)
            gone.append(var)

    if not getattr(sys, "frozen", False):
        for var in PYI_VARS:        # 파이썬으로 도는데 있으면 전부 물려받은 것
            if os.environ.pop(var, None) is not None:
                gone.append(var)

    path = os.environ.get("PATH", "")
    if path:
        parts = path.split(os.pathsep)
        # 남의 exe 가 물려준 런타임 자리(`…\_internal\pywin32_system32`)를 뺀다. 판 번호가
        # 박혀 있어 그 exe 가 한 판 오르면 없어진 자리를 가리킨 채 남는다. 내 것은 놔둔다.
        kept = [p for p in parts if not (p and _packed(p) and not _mine(p))]
        if len(kept) != len(parts):
            os.environ["PATH"] = os.pathsep.join(kept)
            gone.append("PATH")

    return gone


# ---------------------------------------------------------------- 단독 확인

if __name__ == "__main__":
    print("내 런타임 자리:", runtime_dirs() or "(파이썬으로 도는 중)")
    before, after = dict(os.environ), clean_env()
    for name in sorted(set(before) | set(after)):
        if before.get(name) != after.get(name):
            print(f"  빼는 것 {name} = {before.get(name, '')[:110]}")
    print("내 환경에서 지울 것:", heal_self() or "없음")
