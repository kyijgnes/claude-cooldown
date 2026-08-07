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
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
WIN = os.path.join(ROOT, "windows")
ICON = os.path.join(WIN, "앱아이콘.ico")
NAME = "클로드 쿨다운"
# ★★ **버전은 한 곳에서만 적는다 — `android/app/build.gradle.kts` 의 `versionName`.**
#   릴리스 태그(v0.11)·apk·이 exe 이름이 전부 그걸 따른다. 예전에는 exe 이름을 손으로
#   올려서 로컬만 0.31 인데 릴리스는 0.10 인 꼴이 났다(2026-08-04 에 고침).
GRADLE = os.path.join(os.path.dirname(ROOT), "android", "app", "build.gradle.kts")


def version() -> str:
    """gradle 에 적힌 판 번호. 못 읽으면 이름에 번호를 안 붙인다(빌드는 계속)."""
    try:
        with open(GRADLE, encoding="utf-8") as f:
            m = re.search(r'versionName\s*=\s*"([^"]+)"', f.read())
        return m.group(1) if m else ""
    except OSError:
        return ""

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
    "cooldown_login",  # 로그인 상태 확인·잇기
    "cooldown_push",  # 폰으로 보내기 (릴레이 업로드)
    "cooldown_stats",  # 사용량 기록·통계
    "cooldown_update",  # [업데이트 대기] 클로드 업데이트 감시
    "qrcode",  # 폰 연결 QR. 함수 안에서 늦게 import 해 PyInstaller 가 못 찾는다
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

    # **판 번호를 붙인 이름으로도 둔다** — 자동 실행 바로가기가 가리키는 것이 이 파일이고,
    # 릴리스에 올리는 것도 이 파일이다(이름이 곧 판 번호라 어느 판이 도는지 알 수 있다).
    ver = version()
    if ver:
        named = os.path.join(ROOT, "dist", f"claude-cooldown-v{ver}.exe")
        try:
            shutil.copy2(exe, named)
            print(f"판 번호 붙인 것: {named}")
        except PermissionError:
            # 같은 판을 다시 빌드했는데 그게 지금 돌고 있으면 못 덮어쓴다
            print(f"! {os.path.basename(named)} 을 못 바꿨다 — 지금 돌고 있는 것 같다.")
            print("  트레이에서 끝내고 다시 돌리거나, 위 파일을 직접 실행할 것.")
    else:
        print("! 판 번호를 못 읽었다 (android/app/build.gradle.kts 의 versionName)")
    print("이 파일 하나만 주면 된다. 파이썬은 필요 없다.")
    shutil.rmtree(os.path.join(ROOT, "build"), ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
