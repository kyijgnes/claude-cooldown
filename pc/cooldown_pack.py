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
    return fit_frames(read_frames(path), height, speed, width)


def read_frames(path: str):
    """그림 파일 → [(RGBA, ms), ...] (크기 그대로)."""
    from PIL import Image, ImageSequence

    out = []
    with Image.open(path) as im:
        for frame in ImageSequence.Iterator(im):
            ms = frame.info.get("duration") or im.info.get("duration") or 100
            out.append((frame.convert("RGBA"), int(ms)))
    return out


def fit_frames(frames, height: int, speed: float = 1.0, width: int | None = None):
    """[(RGBA, ms)] 의 투명 테두리를 걷고 높이·폭 안에 맞춘다(바닥 가운데 정렬)."""
    from PIL import Image

    out = []
    for rgba, ms in frames:
        box = rgba.getbbox()  # 투명 테두리를 걷어 낸다 — 바가 낮아 한 줄도 아깝다
        out.append((rgba.crop(box) if box else rgba, ms))
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


# ---------------------------------------------------------------- 그림 넣기 도구가 쓰는 것
# ★ 한 장씩 골라 넣는 도구다. 묶음째 받거나 다른 프로그램 저장 파일을 뒤지는 기능은 넣지 않는다.
MAX_PER_STATE = 6  # 상태 하나에 넣을 수 있는 그림 수
SENTINEL = (1, 254, 3)  # 배경 칠하기 표시 색 (그림에 거의 없는 색)


def remove_bg(img, tol: int):
    """가장자리에서 이어진 바탕(채팅방 바탕색 등)을 투명하게. tol=0 이면 그대로.

    가장자리 점마다 바탕색과 비슷하면 거기서 물들이기(floodfill)를 해서, **안쪽의
    같은 색(캐릭터 흰 몸)은 안 지운다** — 테두리로 둘러싸여 이어지지 않기 때문.
    """
    from PIL import Image, ImageChops, ImageDraw

    rgba = img.convert("RGBA")
    if tol <= 0:
        return rgba
    rgb = rgba.convert("RGB")
    w, h = rgb.size
    edge = [(x, 0) for x in range(0, w, 3)] + [(x, h - 1) for x in range(0, w, 3)]
    edge += [(0, y) for y in range(0, h, 3)] + [(w - 1, y) for y in range(0, h, 3)]
    colors = [rgb.getpixel(p) for p in edge]
    bg = max(set(colors), key=colors.count)  # 가장자리에 가장 많은 색 = 바탕

    def near(c):
        return max(abs(a - b) for a, b in zip(c, bg)) <= tol

    for p, c in zip(edge, colors):
        if near(c) and rgb.getpixel(p) != SENTINEL:
            ImageDraw.floodfill(rgb, p, SENTINEL, thresh=tol)
    diff = ImageChops.difference(rgb, Image.new("RGB", rgb.size, SENTINEL))
    r, g, b = diff.split()
    keep = ImageChops.lighter(ImageChops.lighter(r, g), b).point(lambda v: 255 if v else 0)
    rgba.putalpha(ImageChops.multiply(rgba.getchannel("A"), keep))
    return rgba


def tidy(frames):
    """[(RGBA, ms)] 를 모든 프레임에 걸친 한 네모로 잘라 맞춘다(움직여도 자리가 안 흔들리게)."""
    boxes = [f.getbbox() for f, _ in frames]
    boxes = [b for b in boxes if b]
    if not boxes:
        return frames
    box = (min(b[0] for b in boxes), min(b[1] for b in boxes),
           max(b[2] for b in boxes), max(b[3] for b in boxes))
    return [(f.crop(box), ms) for f, ms in frames]


def dedupe(frames):
    """잇달아 똑같은 프레임은 하나로 합치고 시간을 더한다(화면에서 담으면 같은 장면이 겹친다)."""
    from PIL import ImageChops

    out = []
    for f, ms in frames:
        if out and ImageChops.difference(out[-1][0], f).getbbox() is None:
            out[-1] = (out[-1][0], out[-1][1] + ms)
        else:
            out.append((f, ms))
    return out


def room_left(state: str, root: str = PACK_DIR) -> int:
    return max(0, MAX_PER_STATE - len(clips(state, root)))


def save_clip(state: str, frames, root: str = PACK_DIR) -> str:
    """상태 폴더에 그림 하나 저장. 여러 장이면 움직이는 png. 저장한 경로를 돌려준다."""
    import time

    if state not in STATES:
        raise ValueError(state)
    if room_left(state, root) <= 0:
        raise ValueError(f"{state} 은 {MAX_PER_STATE}장까지")
    frames = tidy(frames)
    folder = os.path.join(root, state)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, time.strftime("%m%d_%H%M%S") + ".png")
    first, *rest = [f for f, _ in frames]
    if rest:
        first.save(path, save_all=True, append_images=rest,
                   duration=[ms for _, ms in frames], loop=0, disposal=1)
    else:
        first.save(path)
    return path


def delete_clip(path: str, root: str = PACK_DIR) -> None:
    """팩 폴더 안의 그림만 지운다(밖을 가리키면 아무것도 안 함)."""
    real = os.path.realpath(path)
    if real.startswith(os.path.realpath(root) + os.sep) and os.path.isfile(real):
        os.remove(real)

if __name__ == "__main__":
    # 팩 점검: 상태마다 무엇을 틀지 보여 준다
    print("팩 폴더:", PACK_DIR, "(있음)" if present() else "(없음 → 클로디)")
    for s in STATES:
        own = clips(s)
        print(f"  {s}: {len(own)}개" + ("" if own else f" → {os.path.basename(os.path.dirname(pick(s) or '')) or '없음'} 빌림"))
