r"""
배포용 exe 만들기
==================
    pip install pyinstaller
    python build_exe.py

결과: dist/클로드 쿨다운 v<판>/클로드 쿨다운.exe  (파이썬이 없는 PC 에서도 더블클릭으로 실행)
      dist/claude-cooldown-v<판>.zip            (릴리스에 올리는 것 — 위 폴더를 통째로 담은 것)

★ **onedir 다 — onefile 로 되돌리지 말 것**(2026-09-08). onefile 은 켤 때마다 `%TEMP%\_MEIxxxx` 에
자기 속을 풀어 놓고 거기서 도는데, 윈도우 **저장소 센스**(임시 파일 정리)가 **돌고 있는** exe 의
그 폴더를 비워 버린다. 그러면 인증서(`certifi\cacert.pem`)가 사라져 HTTPS 가 전부 막히고 위젯에
`Could not find a suitable TLS CA certificate bundle` 이 흐른다(마지막 값만 남고 조회가 안 된다).
onedir 은 exe 옆 `_internal\` 에서 그대로 돌아 임시 폴더가 없고, 켜는 것도 빠르다.

폴더 이름에 판 번호가 붙는 까닭: 돌고 있는 판의 `_internal\` 은 잠겨 있어 같은 폴더에 다시
못 짓는다. 판마다 새 폴더에 지으면 옛 판을 끄지 않고도 빌드가 되고, 새 exe 를 한 번 띄우면
자동 실행 바로가기가 새 폴더로 옮겨 앉는다(`repair_autostart`). 그 뒤 옛 폴더를 지운다.

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
import zipfile

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
    "cooldown_remote",  # 클로드 코드 원격 대기 (claude rc 상주)
    "cooldown_stats",  # 사용량 기록·통계
    "cooldown_update",  # [업데이트 대기] 클로드 업데이트 감시
    "cooldown_reboot",  # 윈도우 업데이트 재시작 대기 감시
    "cooldown_job",  # 세션에서 띄워지면 클로드 데스크톱 job 밖으로 다시 뜨기
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
        "--onedir",             # ★ onefile 금지 — 맨 위 설명 참고 (저장소 센스가 임시 폴더를 비운다)
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


def zip_dir(folder: str, out: str) -> None:
    """폴더를 통째로 zip 에 담는다(맨 위에 폴더 이름이 그대로 남게). 이름은 UTF-8 로 적어
    윈도우 탐색기가 한글 그대로 푼다."""
    top = os.path.basename(folder)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for base, _dirs, files in os.walk(folder):
            for name in files:
                full = os.path.join(base, name)
                z.write(full, os.path.join(top, os.path.relpath(full, folder)))


def main() -> int:
    make_icon()
    code = build()
    if code != 0:
        print("빌드 실패")
        return code

    built = os.path.join(ROOT, "dist", NAME)  # PyInstaller 가 지은 폴더 (판 번호 없음)
    ver = version()
    if not ver:
        print("! 판 번호를 못 읽었다 (android/app/build.gradle.kts 의 versionName)")
        print(f"완성: {built}  (판 번호 없는 채로 둔다)")
        shutil.rmtree(os.path.join(ROOT, "build"), ignore_errors=True)
        return 0

    # **판 번호 붙은 폴더**로 옮긴다 — 돌고 있는 옛 판의 폴더와 안 겹치게(맨 위 설명).
    final = os.path.join(ROOT, "dist", f"{NAME} v{ver}")
    if os.path.isdir(final):
        try:
            shutil.rmtree(final)
        except PermissionError:
            print(f"! {os.path.basename(final)} 을 못 바꿨다 — 지금 그 판이 돌고 있다.")
            print("  트레이에서 끝내고 다시 돌릴 것.")
            shutil.rmtree(built, ignore_errors=True)
            return 1
    os.rename(built, final)
    exe = os.path.join(final, f"{NAME}.exe")
    total = sum(
        os.path.getsize(os.path.join(b, f)) for b, _d, fs in os.walk(final) for f in fs
    ) / 1024 / 1024
    print(f"\n완성: {exe}  (폴더 {total:.1f} MB)")

    # 릴리스에 올리는 것은 이 zip 이다(이름이 곧 판 번호). 폴더째 담는다.
    named = os.path.join(ROOT, "dist", f"claude-cooldown-v{ver}.zip")
    zip_dir(final, named)
    print(f"릴리스용: {named}  ({os.path.getsize(named) / 1024 / 1024:.1f} MB)")
    print("받는 사람은 zip 을 풀고 안의 exe 를 더블클릭한다. 파이썬은 필요 없다.")
    print("★ 새 exe 를 한 번 띄워야 자동 실행 바로가기가 이 폴더로 옮겨 앉는다.")
    shutil.rmtree(os.path.join(ROOT, "build"), ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
