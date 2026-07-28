"""
배포용 exe 만들기
==================
    pip install pyinstaller
    python build_exe.py

결과: dist/클로드 쿨다운.exe  (파이썬이 없는 PC 에서도 더블클릭으로 실행)

받는 사람 조건은 하나 — **그 PC 에 Claude Code 가 깔려 있고 로그인돼 있어야 한다.**
앱은 그 PC 의 ~/.claude/.credentials.json 을 읽어 자기 사용량을 조회한다.
토큰은 밖으로 나가지 않는다.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
WIN = os.path.join(ROOT, "windows")
ICON = os.path.join(WIN, "앱아이콘.ico")
NAME = "클로드 쿨다운"

# skins/__init__.py 가 importlib 로 불러오므로 PyInstaller 가 스스로 못 찾는다.
# 빼먹으면 exe 에 디자인이 하나도 안 들어가고 "쓸 수 있는 스킨이 없습니다" 로 죽는다.
HIDDEN = [
    "skins.base",
    "skins.card",
    "skins.arc",
    "skins.table",
    "skins.slim",
    "cooldown_core",  # 루트 모듈 (--paths 로 찾지만 명시해 확실히)
    "cooldown_ping",  # 자동 핑(모닝 스타터) 로직
    "pystray._win32",
    "win32com.client",
]


def make_icon() -> None:
    """앱 아이콘. 위젯과 같은 모양 — 어두운 판에 초록·노랑 게이지 두 줄."""
    from PIL import Image, ImageDraw

    sizes = (16, 24, 32, 48, 64, 128, 256)
    base = 256
    img = Image.new("RGBA", (base, base), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((8, 8, base - 8, base - 8), radius=52, fill="#15171c")

    left, right = 44, base - 44
    for y, ratio, color in ((96, 0.30, "#3fb950"), (160, 0.72, "#e3b341")):
        d.rounded_rectangle((left, y, right, y + 22), radius=11, fill="#2a3038")
        end = left + (right - left) * ratio
        d.rounded_rectangle((left, y, end, y + 22), radius=11, fill=color)

    img.save(ICON, sizes=[(s, s) for s in sizes])
    print(f"아이콘: {ICON}")


def build() -> int:
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",           # 검은 콘솔 창 없이
        "--clean", "--noconfirm",
        "--name", NAME,
        "--icon", ICON,
        "--paths", ROOT,        # cooldown_core.py
        "--paths", WIN,         # skins 패키지
        os.path.join(WIN, "cooldown_app.py"),
    ]
    for mod in HIDDEN:
        cmd += ["--hidden-import", mod]

    print("빌드 중… (처음이면 1~2분 걸린다)")
    return subprocess.call(cmd, cwd=ROOT)


def main() -> int:
    make_icon()
    code = build()
    if code != 0:
        print("빌드 실패")
        return code

    exe = os.path.join(ROOT, "dist", f"{NAME}.exe")
    size = os.path.getsize(exe) / 1024 / 1024
    print(f"\n완성: {exe}  ({size:.1f} MB)")
    print("이 파일 하나만 주면 된다. 파이썬은 필요 없다.")
    shutil.rmtree(os.path.join(ROOT, "build"), ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
