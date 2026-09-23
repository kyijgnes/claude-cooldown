r"""
클로드 코드(CLI) 새 판 받기 — npm 전역 설치를 늘 최신으로
========================================================

**왜 있나.** 새 모델은 클로드 코드 새 판과 같이 나온다. 그런데 이 PC 의 npm 전역
클로드 코드(`%APPDATA%\npm\claude.cmd`)는 **스스로 안 올라간다** — 클로드 코드의
자동 업데이트는 터미널에서 대화형으로 켰을 때만 도는데, 여기서 이 CLI 를 쓰는 것은
위젯이 띄운 원격 대기(`claude rc`)·그 아래 세션(`--print --sdk-url`)·핑(`claude -p`)
뿐이라 한 번도 그 길을 안 탄다. 2026-09-23 에 Opus 5.5 가 나왔는데 폰에서 연 세션이
옛 판이라 **사람이 알아채고 손으로 올릴 때까지 반나절 넘게** 새 모델을 못 썼다.

그래서 위젯이 `CHECK_EVERY` 마다 npm 에 새 판이 있는지 묻고, 있으면 바로 깐다.

- **npm 전역 설치일 때만 한다.** 네이티브 설치(`~\.local\bin\claude.exe`)는 스스로
  올라가고, 데스크톱 앱 속 클로드 코드는 앱이 챙긴다. 모르는 모양이면 손대지 않는다.
- **클로드 코드의 자동 업데이트를 꺼 둔 사람은 건드리지 않는다** — 끄는 손잡이를
  클로드 코드와 같은 것으로 쓴다(`DISABLE_AUTOUPDATER` · `autoUpdates: false`).
  채널(`autoUpdatesChannel` = latest/stable)도 그 설정을 따른다.
- ★ **돌고 있는 세션을 안 죽인다.** 깔려 있는 `claude.exe` 가 돌고 있어도 npm 은 옛
  폴더를 옆으로 치우고(`.claude-code-XXXX`) 새 것을 놓는다 — 돌던 것은 옛 그림으로
  계속 돌고, **새로 뜨는 세션부터 새 판**이다(원격 대기는 세션을 경로로 띄우므로
  원격 대기를 안 껐다 켜도 된다. 2026-09-23 실측: 13:42 에 올린 뒤 14:09 에 뜬 세션이
  새 판). 옆으로 치운 옛 폴더는 그 exe 가 끝난 뒤에 `sweep()` 이 지운다.

확인: `python pc/cooldown_cli.py` — 깔린 판·나온 판·손댈 수 있나만 보여 준다.
      `python pc/cooldown_cli.py --install` — 새 판이 있으면 실제로 깐다.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass

from cooldown_ping import child_env, find_claude

PKG = "@anthropic-ai/claude-code"
REGISTRY = "https://registry.npmjs.org/@anthropic-ai/claude-code/"  # 뒤에 채널(latest/stable)
CHANNELS = ("latest", "stable")
NET_TIMEOUT = 15
# 내려받는 것이 200MB 넘는 exe 라 넉넉히. 넘기면 실패로 보고 다음 차례에 다시 한다.
INSTALL_TIMEOUT = 600
NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW — 검은 창이 뜨면 안 된다

HOME = os.path.expanduser("~")
SETTINGS_PATH = os.path.join(HOME, ".claude", "settings.json")
GLOBAL_PATH = os.path.join(HOME, ".claude.json")


# ---------------------------------------------------------------- 판 번호


def _ver(s: str) -> tuple[int, ...]:
    """'2.1.280' → (2, 1, 280). 숫자가 아닌 꼬리(-beta 등)는 버린다."""
    parts = []
    for p in (s or "").split("."):
        m = re.match(r"\d+", p)
        parts.append(int(m.group()) if m else 0)
    return tuple(parts)


def newer(a: str, b: str) -> bool:
    """a 가 b 보다 새 판인가."""
    return bool(a and b) and _ver(a) > _ver(b)


# ---------------------------------------------------------------- 어디에 깔려 있나


def package_dir() -> str | None:
    """npm 전역으로 깔린 클로드 코드 폴더. npm 전역이 아니면 None.

    `claude.cmd` 는 npm 이 전역 설치 때 만드는 심(shim)이다 — 그 옆 `node_modules` 에
    패키지가 있다. 네이티브 설치(`claude.exe`)는 여기서 None 이 되어 손대지 않는다.
    """
    claude = find_claude()
    if not claude or os.path.basename(claude).lower() != "claude.cmd":
        return None
    here = os.path.join(os.path.dirname(claude), "node_modules", *PKG.split("/"))
    return here if os.path.isfile(os.path.join(here, "package.json")) else None


def installed() -> str:
    """깔린 판. 모르면 빈 문자열. 파일 하나 읽는 것뿐이라 화면 차례에서 불러도 된다."""
    where = package_dir()
    if not where:
        return ""
    try:
        with open(os.path.join(where, "package.json"), encoding="utf-8") as f:
            return str(json.load(f).get("version") or "")
    except (OSError, ValueError):
        return ""


# ---------------------------------------------------------------- 꺼 둔 사람


def _read_json(path: str) -> dict:
    try:
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _truthy(v) -> bool:
    return str(v or "").strip().lower() not in ("", "0", "false", "no", "off")


def _settings() -> dict:
    return _read_json(SETTINGS_PATH)


def turned_off() -> str:
    """클로드 코드 자동 업데이트를 꺼 두었으면 그 까닭(명사형), 아니면 빈 문자열."""
    if _truthy(os.environ.get("DISABLE_AUTOUPDATER")):
        return "DISABLE_AUTOUPDATER 켜짐"
    env = _settings().get("env")
    if isinstance(env, dict) and _truthy(env.get("DISABLE_AUTOUPDATER")):
        return "settings.json 의 DISABLE_AUTOUPDATER"
    if _read_json(GLOBAL_PATH).get("autoUpdates") is False:
        return "자동 업데이트 꺼 둠 (/config)"
    return ""


def channel() -> str:
    ch = str(_settings().get("autoUpdatesChannel") or "latest").strip().lower()
    return ch if ch in CHANNELS else "latest"


# ---------------------------------------------------------------- 묻기


def latest() -> str:
    """npm 에 나온 판. 못 물어봤으면 빈 문자열. **네트워크를 탄다 — 작업 스레드에서.**"""
    try:
        import requests

        r = requests.get(REGISTRY + channel(), timeout=NET_TIMEOUT)
        if r.status_code != 200:
            return ""
        return str(r.json().get("version") or "")
    except Exception:  # noqa: BLE001 — 못 물어봤으면 다음 차례에 다시
        return ""


@dataclass
class Check:
    current: str  # 깔린 판 (모르면 빈 문자열)
    latest: str  # 나온 판 (못 물어봤으면 빈 문자열)
    skip: str  # 손대지 않는 까닭 (비면 손댈 수 있다)

    @property
    def behind(self) -> bool:
        return not self.skip and newer(self.latest, self.current)


def check() -> Check:
    """깔린 판과 나온 판을 대조한다. **네트워크를 탄다 — 작업 스레드에서.**"""
    if package_dir() is None:
        return Check("", "", "npm 전역 설치 아님")
    off = turned_off()
    if off:
        return Check(installed(), "", off)
    cur = installed()
    new = latest()
    if not new:
        return Check(cur, "", "npm 에 못 물어봄")
    return Check(cur, new, "")


# ---------------------------------------------------------------- 깔기


def _npm() -> str | None:
    path = child_env().get("PATH")
    return shutil.which("npm.cmd", path=path) or shutil.which("npm", path=path)


def _tail(text: str) -> str:
    """npm 출력에서 까닭이 될 만한 마지막 줄 하나."""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    for ln in reversed(lines):
        if "ERR" in ln or "error" in ln.lower():
            return ln[:120]
    return lines[-1][:120] if lines else ""


def install(version: str) -> tuple[bool, str]:
    """그 판을 깐다. (됐나, 결과 문구). **몇 분 걸린다 — 작업 스레드에서.**

    ★ 환경은 `child_env()` 로 준다 — 위젯의 PyInstaller 자국과 장기 토큰을 걷어낸 것.
      npm 이 돌리는 설치 스크립트(`install.cjs`)도 그 환경을 물려받는다.
    """
    npm = _npm()
    if not npm:
        return False, "npm 없음"
    was = installed()
    try:
        r = subprocess.run(
            [npm, "install", "-g", f"{PKG}@{version}", "--no-fund", "--no-audit"],
            env=child_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=INSTALL_TIMEOUT,
            creationflags=NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        return False, "시간 초과"
    except Exception as e:  # noqa: BLE001
        return False, str(e)[:120]
    now = installed()
    if now == version:
        return True, f"{was or '?'} → {now}"
    return False, _tail((r.stdout or "") + "\n" + (r.stderr or "")) or f"코드 {r.returncode}"


def sweep() -> int:
    """npm 이 옆으로 치워 둔 옛 판 폴더(`@anthropic-ai\\.claude-code-XXXX`)를 지운다.

    옛 `claude.exe` 가 돌고 있는 동안에는 못 지운다(그래서 npm 도 남기고 간다).
    새 판을 깐 뒤·원격 대기를 갈아 끼운 뒤에 부른다. 못 지운 것은 다음에 또 해 본다.
    지운 수를 준다.
    """
    where = package_dir()
    if not where:
        return 0
    scope = os.path.dirname(where)  # …\node_modules\@anthropic-ai
    gone = 0
    try:
        names = os.listdir(scope)
    except OSError:
        return 0
    for name in names:
        if not name.startswith(".claude-code-"):
            continue
        path = os.path.join(scope, name)
        shutil.rmtree(path, ignore_errors=True)
        if not os.path.exists(path):
            gone += 1
    return gone


# ---------------------------------------------------------------- 단독 확인

if __name__ == "__main__":
    import sys

    print("깔린 곳 :", package_dir() or "(npm 전역 아님)")
    print("채널    :", channel())
    c = check()
    print(f"깔린 판 : {c.current or '-'}  나온 판: {c.latest or '-'}  까닭: {c.skip or '-'}")
    print("새 판 있음" if c.behind else "올릴 것 없음")
    if "--install" in sys.argv and c.behind:
        print("까는 중…")
        print(install(c.latest))
        print("옛 폴더 지움:", sweep())
