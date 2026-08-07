"""
스킨 렌더 확인용 (개발 도구) — 창을 띄워 PNG 로 저장하고 바로 끝난다.

    python _shot_skin.py card ok   out.png    정상
    python _shot_skin.py card net  out.png    연결 실패 (값 유지)
    python _shot_skin.py card err  out.png    로그인 막힘 (값 없음)
    python _shot_skin.py card max  out.png    100% · 가장 긴 문자열 (겹침 확인)
    python _shot_skin.py card note out.png    값은 멀쩡 + 자동 시작 알림

뒤에 light / dark 를 붙이면 그 테마로 그린다 (없으면 윈도우 설정을 따른다).
    python _shot_skin.py card ok out.png light
"""

from __future__ import annotations

import os
import sys
import time
import tkinter as tk
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from cooldown_core import Limit, Usage  # noqa: E402

import skins  # noqa: E402
from skins.base import P, set_palette  # noqa: E402

BACKDROP = "#0b0d10"
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


def _trim(im, key):
    """뒷판 색만으로 채워진 바깥 줄을 잘라낸다 (바탕화면이 섞여 들어오지 않게)."""
    px = im.load()
    w, h = im.size
    top, bot = 0, h
    while bot - top > 1 and all(px[x, bot - 1] == key for x in range(w)):
        bot -= 1
    while bot - top > 1 and all(px[x, top] == key for x in range(w)):
        top += 1
    left, right = 0, w
    while right - left > 1 and all(px[right - 1, y] == key for y in range(top, bot)):
        right -= 1
    while right - left > 1 and all(px[left, y] == key for y in range(top, bot)):
        left += 1
    return im.crop((left, top, right, bot))


def main() -> None:
    key, mode, out = sys.argv[1], sys.argv[2], sys.argv[3]
    set_palette(sys.argv[4] if len(sys.argv) > 4 else "auto")

    skin = skins.make(key)
    if skin.key != key:
        raise SystemExit(f"'{key}' 스킨을 찾을 수 없습니다 (있는 것: "
                         f"{[c.key for c in skins.SKINS]})")

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
        skin.notice(sys.argv[4] if len(sys.argv) > 4 else "20:03 핑 실패")
    elif mode == "net":
        skin.show(demo(), STAMP)
        skin.show_error("연결 실패", True, STAMP)
    else:
        skin.show_error("눌러서 로그인 잇기", False, STAMP)

    root.overrideredirect(True)
    root.update_idletasks()
    root.geometry(f"{skin.width}x{root.winfo_reqheight()}+40+40")
    root.deiconify()
    root.update_idletasks()
    root.update()

    x, y = root.winfo_rootx(), root.winfo_rooty()
    w, h = root.winfo_width(), root.winfo_height()

    pad = 26
    back = tk.Toplevel(root, bg=BACKDROP)
    back.overrideredirect(True)
    back.geometry(f"{w + pad * 2}x{h + pad * 2}+{x - pad}+{y - pad}")
    back.attributes("-topmost", True)
    back.update()
    root.attributes("-topmost", True)
    root.lift()
    root.update()
    time.sleep(0.4)

    from PIL import ImageGrab

    im = ImageGrab.grab(bbox=(x, y, x + w, y + h)).convert("RGB")
    key_rgb = tuple(int(BACKDROP[i:i + 2], 16) for i in (1, 3, 5))
    _trim(im, key_rgb).save(out)
    print(f"{out}  {skin.width}x{h}")
    back.destroy()
    root.destroy()
    os._exit(0)


main()
