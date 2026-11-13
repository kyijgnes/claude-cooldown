"""
스킨 렌더 확인용 (개발 도구) — 창을 띄워 PNG 로 저장하고 바로 끝난다.

    python _shot_skin.py card ok   out.png    정상
    python _shot_skin.py card net  out.png    연결 실패 (값 유지)
    python _shot_skin.py card err  out.png    로그인 막힘 (값 없음)
    python _shot_skin.py card max  out.png    100% · 가장 긴 문자열 (겹침 확인)
    python _shot_skin.py card note out.png    값은 멀쩡 + 자동 시작 알림

뒤에 light / dark 를 붙이면 그 테마로 그린다 (없으면 윈도우 설정을 따른다).
    python _shot_skin.py card ok out.png light
크기 배율은 zoom=1.25 처럼 준다 (작업표시줄 바는 늘 100%).
    python _shot_skin.py arc note out.png "새 버전 0.47" zoom=1.5

★ 창을 앞으로 띄우지 않는다. 화면 안에 거의 투명(알파 0.01)하게 두고 PrintWindow 로
  창 그림만 받아 온다(화면 밖 창은 Tk 바탕이 안 그려져 그림이 깨진다, 11-12 실측).
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import cooldown_env  # noqa: E402

cooldown_env.heal_self()  # ★ tkinter 보다 먼저 — 물려받은 남의 Tcl 경로를 걷어낸다

import time  # noqa: E402
import tkinter as tk  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402

from cooldown_core import Limit, Usage  # noqa: E402

import skins  # noqa: E402
from skins.base import P, set_palette, set_zoom  # noqa: E402

STAMP = "03:07"


def demo(extreme: bool = False) -> Usage:
    now = datetime.now(timezone.utc)
    if extreme:
        return Usage(
            five=Limit("5시간", 100.0, now + timedelta(hours=4, minutes=59)),
            week=Limit("주간", 100.0, now + timedelta(days=6, hours=23)),
            scoped=[Limit("Claude Opus", 99.0, None)],
            fetched_at=now,
        )
    return Usage(
        five=Limit("5시간", 17.0, now + timedelta(hours=4, minutes=12)),
        week=Limit("주간", 56.0, now + timedelta(days=2, hours=7)),
        scoped=[Limit("Fable", 7.0, None)],
        fetched_at=now,
    )


def _grab(root: tk.Tk):
    """창 그림을 PrintWindow 로 받는다 (앞으로 띄우지 않으므로 다른 창에 가려도 된다)."""
    import win32gui
    import win32ui
    from PIL import Image

    hwnd = int(root.wm_frame(), 16)
    w, h = root.winfo_width(), root.winfo_height()
    src = win32gui.GetWindowDC(hwnd)
    dc = win32ui.CreateDCFromHandle(src)
    mem = dc.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(dc, w, h)
    mem.SelectObject(bmp)
    import ctypes

    ctypes.windll.user32.PrintWindow(hwnd, mem.GetSafeHdc(), 2)  # PW_RENDERFULLCONTENT
    info = bmp.GetInfo()
    im = Image.frombuffer("RGB", (info["bmWidth"], info["bmHeight"]),
                          bmp.GetBitmapBits(True), "raw", "BGRX", 0, 1)
    win32gui.DeleteObject(bmp.GetHandle())
    mem.DeleteDC()
    dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, src)
    return im


def main() -> None:
    key, mode, out = sys.argv[1], sys.argv[2], sys.argv[3]
    # 넷째 인자는 테마(light/dark/auto) 아니면 note 문구다. 둘 다 줄 때는 테마를 다섯째에.
    extra = sys.argv[4:]
    theme = next((a for a in extra if a in ("light", "dark", "auto")), "auto")
    zoom = next((float(a[5:]) for a in extra if a.startswith("zoom=")), 1.0)
    words = [a for a in extra if a not in ("light", "dark", "auto") and not a.startswith("zoom=")]
    set_palette(theme)

    skin = skins.make(key)
    if skin.key != key:
        raise SystemExit(f"'{key}' 스킨을 찾을 수 없습니다 (있는 것: "
                         f"{[c.key for c in skins.SKINS]})")

    set_zoom(1.0 if skin.dockable else zoom)
    root = tk.Tk()
    root.withdraw()
    root.configure(bg=P.bg)
    body = tk.Frame(root, bg=P.bg)
    body.pack(fill="both", expand=True)
    skin.build(body)

    if mode == "ok":
        skin.show(demo(), STAMP)
    elif mode == "max":
        skin.show(demo(extreme=True), STAMP)
    elif mode == "note":
        # 값은 멀쩡한데 알릴 것이 있는 상태 — 앱이 show() 바로 뒤에 notice() 를 부른다
        # 넷째 인자로 문구를 넘기면 그걸 쓴다 (새 알림 문구의 폭을 재 볼 때)
        skin.show(demo(), STAMP)
        skin.notice(words[0] if words else "20:03 시작 실패")
    elif mode == "net":
        skin.show(demo(), STAMP)
        skin.show_error("연결 실패", True, STAMP)
    else:
        skin.show_error(words[0] if words else "눌러서 다시 연결", False, STAMP)

    root.overrideredirect(True)
    root.attributes("-alpha", 0.01)
    root.update_idletasks()
    root.geometry(f"{skin.width}x{root.winfo_reqheight()}+40+40")
    root.deiconify()
    root.lower()
    # 번갈아 칸(슬림 바)이 알림을 앉히는 움직임까지 돌게 잠깐 돌린다
    end = time.time() + 0.9
    while time.time() < end:
        root.update()
        time.sleep(0.02)

    im = _grab(root)
    im.save(out)
    print(f"{out}  {root.winfo_width()}x{root.winfo_height()}")
    root.destroy()
    os._exit(0)


main()
