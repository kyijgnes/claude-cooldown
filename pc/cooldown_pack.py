"""
캐릭터 팩 — 위젯의 클로디 자리에 **내가 고른 그림**을 세운다. Tk 없음.

그림은 저장소에 넣지 않는다. 각자 PC 의 `~/.claude_cooldown_pack/` 폴더에만 둔다
(이 저장소는 공개이고 친구들에게 나눠주므로, 남의 그림이 실려 나가면 안 된다).
폴더가 없으면 지금처럼 클로디가 나온다.

    ~/.claude_cooldown_pack/
        여유/   빠듯/   한도/   초기화/   콕/   꾹/   오류/   심심/
        설정.json   (없어도 된다)

- 상태 폴더마다 그림 파일(png·gif·webp, 움직이는 png·gif 도 된다)을 몇 개든 넣는다.
  파일 하나가 장면 하나이고, 그 상태가 되면 그 안에서 하나를 골라 튼다.
- 비어 있는 상태는 `FALLBACK` 순서로 옆 상태 그림을 빌려 쓴다. **여유 하나만 채워도 돈다.**
- 설정.json: {"높이": 40, "속도": 1.0}  높이는 바에서 그림 키(px), 속도는 움직이는 그림 빠르기 배율.
"""

from __future__ import annotations

import glob
import json
import os
import random

# 시험할 때는 CLAUDE_COOLDOWN_PACK 으로 다른 폴더를 가리킨다(사용자 팩을 안 건드리게)
PACK_DIR = os.environ.get("CLAUDE_COOLDOWN_PACK") or os.path.join(
    os.path.expanduser("~"), ".claude_cooldown_pack")
EXTS = (".png", ".gif", ".webp", ".apng")

# 상태 이름 = 폴더 이름. 앞의 넷은 사용량에서 정하고(mood), 뒤의 넷은 일이 생길 때 잠깐 튼다.
MOODS = ("여유", "빠듯", "한도", "오류")
EVENTS = ("초기화", "콕", "꾹", "심심")
STATES = MOODS + EVENTS

# 그 상태 그림이 없으면 차례로 빌려 올 곳
FALLBACK = {
    "여유": (),
    "빠듯": ("여유",),
    "한도": ("빠듯", "여유"),
    "오류": ("한도", "빠듯", "여유"),
    "초기화": ("여유",),
    "콕": ("여유",),
    "꾹": ("콕", "여유"),
    "심심": ("여유",),
}

TIGHT_AT = 80.0  # 이 이상이면 빠듯
FULL_AT = 99.5  # 이 이상이면 한도
RESET_DROP = 30.0  # 5시간 한도가 이만큼 넘게 한꺼번에 내려가면 초기화로 본다


def present(root: str = PACK_DIR) -> bool:
    """팩이 쓸 만큼 있는가 (어느 상태든 그림이 하나라도 있으면 참)."""
    return any(clips(s, root) for s in STATES)


def clips(state: str, root: str = PACK_DIR) -> list[str]:
    """그 상태 폴더에 바로 들어 있는 그림 파일들 (이름 순)."""
    folder = os.path.join(root, state)
    if not os.path.isdir(folder):
        return []
    out = [p for p in glob.glob(os.path.join(folder, "*")) if p.lower().endswith(EXTS)]
    return sorted(out)


def pick(state: str, root: str = PACK_DIR, avoid: str | None = None) -> str | None:
    """상태 하나에 틀 그림 파일 하나. 없으면 빌려 오고, 그래도 없으면 None.
    `avoid` 는 방금 튼 것 — 고를 게 둘 이상이면 같은 것을 잇달아 안 튼다."""
    for s in (state, *FALLBACK.get(state, ())):
        found = clips(s, root)
        if found:
            if avoid in found and len(found) > 1:
                found = [p for p in found if p != avoid]
            return random.choice(found)
    return None


def settings(root: str = PACK_DIR) -> dict:
    """설정.json. 못 읽으면 빈 dict (BOM 붙은 것도 읽는다)."""
    try:
        with open(os.path.join(root, "설정.json"), encoding="utf-8-sig") as f:
            got = json.load(f)
        return got if isinstance(got, dict) else {}
    except (OSError, ValueError):
        return {}


def mood(five: float | None, week: float | None) -> str:
    """사용량 두 개로 늘 서 있을 상태를 정한다 (여유·빠듯·한도)."""
    worst = max((p for p in (five, week) if p is not None), default=0.0)
    if worst >= FULL_AT:
        return "한도"
    if worst >= TIGHT_AT:
        return "빠듯"
    return "여유"


def was_reset(before: float | None, after: float | None) -> bool:
    """5시간 한도가 초기화됐는가 — 크게 떨어졌을 때만 (작은 오르내림은 무시)."""
    return before is not None and after is not None and before - after >= RESET_DROP


def load_frames(path: str, height: int, speed: float = 1.0, width: int | None = None):
    """그림 파일 하나를 [(PIL.Image RGBA, 보여 줄 ms), ...] 로. 높이(와 폭)에 맞춰 줄인다.
    `width` 를 주면 그 폭도 안 넘게 줄인다(바의 틈이 좁아 옆 숫자를 덮지 않게).

    움직이는 png·gif 는 프레임을 다 꺼낸다. 프레임마다 크기가 달라도(gif 부분 갱신)
    `ImageSequence` 가 덮어 그린 전체 장면을 주므로 그대로 쓴다.
    """
    from PIL import Image, ImageSequence

    out = []
    with Image.open(path) as im:
        for frame in ImageSequence.Iterator(im):
            ms = frame.info.get("duration") or im.info.get("duration") or 100
            rgba = frame.convert("RGBA")
            box = rgba.getbbox()  # 투명 테두리를 걷어 낸다 — 바가 낮아 한 줄도 아깝다
            if box:
                rgba = rgba.crop(box)
            out.append((rgba, ms))
    if not out:
        return []
    # 프레임마다 걷어 낸 크기가 다르면 들썩이므로, 가장 큰 것에 맞춰 바닥 가운데로 다시 앉힌다
    w = max(f.width for f, _ in out)
    h = max(f.height for f, _ in out)
    scale = height / h
    if width:
        scale = min(scale, width / w)
    tw, th = max(1, round(w * scale)), max(1, round(h * scale))
    result = []
    for f, ms in out:
        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        canvas.paste(f, ((w - f.width) // 2, h - f.height))
        result.append((canvas.resize((tw, th), Image.LANCZOS), max(20, int(ms / max(0.1, speed)))))
    return result


if __name__ == "__main__":
    # 팩 점검: 상태마다 무엇을 틀지 보여 준다
    print("팩 폴더:", PACK_DIR, "(있음)" if present() else "(없음 → 클로디)")
    for s in STATES:
        own = clips(s)
        print(f"  {s}: {len(own)}개" + ("" if own else f" → {os.path.basename(os.path.dirname(pick(s) or '')) or '없음'} 빌림"))
