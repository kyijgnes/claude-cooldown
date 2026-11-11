"""
클로드 쿨다운 — 쿨다운 **자기 자신의** 새 버전 알림 (순수 로직, Tk 없음)
=====================================================================
2026-11-11 사용자 지시. 그 전까지는 친구들이 릴리스 페이지를 직접 다시 찾아와야 새 버전을 받았다.

- 하는 일은 **알리기까지만**이다. 받기·깔기는 사람이 한다(릴리스 페이지를 브라우저로 연다).
  돌고 있는 exe 를 스스로 바꿔 끼우면 그 폴더를 붙잡은 채라 실패하기 쉽고, 백신도 싫어한다.
- 최신 버전은 GitHub 공개 API `releases/latest` 의 `tag_name`(v0.39) 한 칸만 읽는다.
  보내는 것은 없다(로그인·키·PC 정보 없음). 익명 한도가 시간당 60번이라 6시간에 한 번이면 넉넉하다.
- 내 버전: exe 는 빌드할 때 폴더에 넣은 `version.txt`(`build_exe.py`), 소스로 돌 때는
  `android/app/build.gradle.kts` 의 `versionName`(버전은 거기 한 곳이다).

확인: `python pc/cooldown_newver.py`
"""

from __future__ import annotations

import os
import re
import sys

import requests

REPO = "kyijgnes/claude-cooldown"
LATEST_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASE_PAGE = f"https://github.com/{REPO}/releases/latest"
VERSION_FILE = "version.txt"   # exe 옆 — build_exe.py 가 넣는다
CHECK_EVERY = 6 * 3600         # 이만큼마다 묻는다 (초)
FIRST_WAIT = 90                # 켜고 이만큼 뒤에 처음 묻는다 — 켜는 순간을 붐비게 하지 않게

_HERE = os.path.dirname(os.path.abspath(__file__))
_GRADLE = os.path.join(os.path.dirname(_HERE), "android", "app", "build.gradle.kts")


def current() -> str:
    """지금 도는 쿨다운의 버전("0.39"). 모르면 빈 문자열 — 그러면 알리지 않는다."""
    try:
        if getattr(sys, "frozen", False):
            with open(os.path.join(os.path.dirname(sys.executable), VERSION_FILE),
                      encoding="utf-8") as f:
                return f.read().strip()
        with open(_GRADLE, encoding="utf-8") as f:
            m = re.search(r'versionName\s*=\s*"([^"]+)"', f.read())
        return m.group(1) if m else ""
    except OSError:
        return ""


def _key(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", v))


def is_newer(latest: str, mine: str) -> bool:
    try:
        return bool(latest and mine) and _key(latest) > _key(mine)
    except ValueError:
        return False


def latest() -> str | None:
    """릴리스에 올라간 최신 버전("0.40"). 못 물어봤으면 None."""
    try:
        r = requests.get(
            LATEST_API,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "claude-cooldown"},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        tag = str(r.json().get("tag_name") or "")
        return tag.lstrip("vV") or None
    except (requests.RequestException, ValueError):
        return None


def check() -> str | None:
    """받을 새 버전이 있으면 그 번호, 없거나 모르면 None."""
    mine = current()
    new = latest()
    return new if new and is_newer(new, mine) else None


if __name__ == "__main__":
    print("내 버전:", current() or "(모름)")
    print("최신:", latest() or "(못 물어봄)")
    print("알릴 것:", check() or "없음")
