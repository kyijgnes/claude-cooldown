"""
캐릭터 마당 팩 — 작업표시줄 바 오른쪽 **마당 칸**에서 노는 캐릭터들의 그림. Tk 없음.

그림은 저장소에 넣지 않는다. 각자 PC 의 `~/.claude_cooldown_pack/` 폴더에만 둔다
(이 저장소는 공개이고 친구들에게 나눠주므로, 남의 그림이 실려 나가면 안 된다).
캐릭터가 하나도 없으면 마당 칸 없이 지금처럼 클로디가 나온다.

    ~/.claude_cooldown_pack/
        설정.json                  {"마당 폭": 180}
        <캐릭터 이름>/              이름은 사용자가 정한다 (폴더 이름 = 캐릭터 이름)
            서기/ 걷기/ 인사/ 놀람/ 눌림/ 허둥/ 잠/ 축하/ 딴짓/
            설정.json              {"보는 쪽": "오른쪽"}  그림 속 캐릭터가 보는 쪽

- 동작 폴더마다 그림(png·gif·webp, 움직이는 것도 됨)을 `MAX_PER_MOTION` 장까지 넣는다.
  그 동작을 할 때 그 안에서 하나를 골라 튼다.
- 비어 있는 동작은 `FALLBACK` 으로 빌린다. **서기 한 장만 있어도 캐릭터로 친다.**
- 이름이 `_` 나 `.` 로 시작하는 폴더는 캐릭터가 아니다(잠깐 빼 둔 것).
"""

from __future__ import annotations

import glob
import json
import os
import random
import shutil
import time

# 시험할 때는 CLAUDE_COOLDOWN_PACK 으로 다른 폴더를 가리킨다(사용자 팩을 안 건드리게)
PACK_DIR = os.environ.get("CLAUDE_COOLDOWN_PACK") or os.path.join(
    os.path.expanduser("~"), ".claude_cooldown_pack")
EXTS = (".png", ".gif", ".webp", ".apng")

# 동작 이름 = 폴더 이름
MOTIONS = ("서기", "걷기", "인사", "놀람", "눌림", "허둥", "잠", "축하", "딴짓")
MOTION_LABELS = {
    "서기": "가만히 있을 때",
    "걷기": "걸어 다닐 때",
    "인사": "친구와 마주쳤을 때",
    "놀람": "눌렸을 때·옆 친구가 눌렸을 때",
    "눌림": "길게 누르는 동안",
    "허둥": "사용량 80% 넘음",
    "잠": "한도 다 참",
    "축하": "한도 풀림",
    "딴짓": "오래 가만있을 때",
}
FALLBACK = {
    "서기": (),
    "걷기": ("서기",),
    "인사": ("놀람", "서기"),
    "놀람": ("서기",),
    "눌림": ("놀람", "서기"),
    "허둥": ("걷기", "서기"),
    "잠": ("서기",),
    "축하": ("인사", "서기"),
    "딴짓": ("서기",),
}
YARD_WIDTHS = (120, 180, 240)
YARD_DEFAULT = 180
MAX_CHARS = 5  # 마당이 좁아 이보다 많으면 놀 자리가 없다
MAX_PER_MOTION = 6  # 동작 하나에 넣을 수 있는 그림 수 (★ 한 장씩 골라 넣는다. 묶음째 넣기 없음)

TIGHT_AT = 80.0  # 이 이상이면 허둥
FULL_AT = 99.5  # 이 이상이면 잠
RESET_DROP = 30.0  # 5시간 한도가 이만큼 넘게 한꺼번에 내려가면 초기화로 본다
BAD_NAME = set('\\/:*?"<>|')


# ---------------------------------------------------------------- 설정 파일
def _read_json(path: str) -> dict:
    try:
        with open(path, encoding="utf-8-sig") as f:  # BOM 붙은 것도 읽는다
            got = json.load(f)
        return got if isinstance(got, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def settings(root: str = PACK_DIR) -> dict:
    return _read_json(os.path.join(root, "설정.json"))


def set_setting(key: str, value, root: str = PACK_DIR) -> None:
    data = settings(root)
    data[key] = value
    _write_json(os.path.join(root, "설정.json"), data)


def yard_width(root: str = PACK_DIR) -> int:
    try:
        w = int(settings(root).get("마당 폭", YARD_DEFAULT))
    except (TypeError, ValueError):
        w = YARD_DEFAULT
    return min(YARD_WIDTHS, key=lambda v: abs(v - w))


def char_settings(char: str, root: str = PACK_DIR) -> dict:
    return _read_json(os.path.join(root, char, "설정.json"))


def set_char_setting(char: str, key: str, value, root: str = PACK_DIR) -> None:
    data = char_settings(char, root)
    data[key] = value
    _write_json(os.path.join(root, char, "설정.json"), data)


def faces_right(char: str, root: str = PACK_DIR) -> bool:
    """그림 속 캐릭터가 오른쪽을 보고 있나 (걷는 쪽에 맞춰 좌우를 뒤집을 때 쓴다)."""
    return char_settings(char, root).get("보는 쪽", "오른쪽") != "왼쪽"


# ---------------------------------------------------------------- 캐릭터·그림 찾기
def all_characters(root: str = PACK_DIR) -> list[str]:
    """그림이 없어도 폴더가 있는 캐릭터까지 (그림 넣기 창이 쓴다)."""
    if not os.path.isdir(root):
        return []
    return sorted(n for n in os.listdir(root)
                  if not n.startswith(("_", ".")) and os.path.isdir(os.path.join(root, n)))


def characters(root: str = PACK_DIR) -> list[str]:
    """마당에 나올 캐릭터 (그림이 하나라도 있는 것, 이름 순, `MAX_CHARS` 까지)."""
    return [c for c in all_characters(root) if any(clips(c, m, root) for m in MOTIONS)][:MAX_CHARS]


def present(root: str = PACK_DIR) -> bool:
    return bool(characters(root))


def clips(char: str, motion: str, root: str = PACK_DIR) -> list[str]:
    """그 캐릭터·동작 폴더에 바로 들어 있는 그림 파일들 (이름 순)."""
    folder = os.path.join(root, char, motion)
    if not os.path.isdir(folder):
        return []
    return sorted(p for p in glob.glob(os.path.join(folder, "*")) if p.lower().endswith(EXTS))


def pick(char: str, motion: str, root: str = PACK_DIR, avoid: str | None = None) -> str | None:
    """동작 하나에 틀 그림 하나. 없으면 빌려 오고(FALLBACK), 그래도 없으면 아무 그림이나.
    `avoid` 는 방금 튼 것 — 고를 게 둘 이상이면 같은 것을 잇달아 안 튼다."""
    for m in (motion, *FALLBACK.get(motion, ()), *MOTIONS):
        found = clips(char, m, root)
        if found:
            if avoid in found and len(found) > 1:
                found = [p for p in found if p != avoid]
            return random.choice(found)
    return None


# ---------------------------------------------------------------- 사용량 → 분위기
def mood(five: float | None, week: float | None) -> str:
    """사용량 두 개로 마당 분위기를 정한다: 여유 · 허둥 · 잠."""
    worst = max((p for p in (five, week) if p is not None), default=0.0)
    if worst >= FULL_AT:
        return "잠"
    if worst >= TIGHT_AT:
        return "허둥"
    return "여유"


def was_reset(before: float | None, after: float | None) -> bool:
    """5시간 한도가 초기화됐는가 — 크게 떨어졌을 때만 (작은 오르내림은 무시)."""
    return before is not None and after is not None and before - after >= RESET_DROP


# ---------------------------------------------------------------- 그림 읽기·맞추기
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
    """[(RGBA, ms)] 의 투명 테두리를 걷고 높이·폭 안에 맞춘다(바닥 가운데 정렬).
    ★ 모든 프레임에 걸친 네모 하나로 자른다 — 프레임마다 따로 자르면 움직일 때 들썩인다."""
    from PIL import Image

    if not frames:
        return []
    boxes = [b for b in (f.getbbox() for f, _ in frames) if b]
    if boxes:
        box = (min(b[0] for b in boxes), min(b[1] for b in boxes),
               max(b[2] for b in boxes), max(b[3] for b in boxes))
        frames = [(f.crop(box), ms) for f, ms in frames]
    w = max(f.width for f, _ in frames)
    h = max(f.height for f, _ in frames)
    scale = height / h
    if width:
        scale = min(scale, width / w)
    tw, th = max(1, round(w * scale)), max(1, round(h * scale))
    out = []
    for f, ms in frames:
        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        canvas.paste(f, ((w - f.width) // 2, h - f.height))
        out.append((canvas.resize((tw, th), Image.LANCZOS), max(20, int(ms / max(0.1, speed)))))
    return out


def load_frames(path: str, height: int, speed: float = 1.0, width: int | None = None):
    return fit_frames(read_frames(path), height, speed, width)


# ---------------------------------------------------------------- 그림 넣기 창이 쓰는 것
SENTINEL = (1, 254, 3)  # 바탕 칠하기 표시 색 (그림에 거의 없는 색)


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
    for p, c in zip(edge, colors):
        if max(abs(a - b) for a, b in zip(c, bg)) <= tol and rgb.getpixel(p) != SENTINEL:
            ImageDraw.floodfill(rgb, p, SENTINEL, thresh=tol)
    diff = ImageChops.difference(rgb, Image.new("RGB", rgb.size, SENTINEL))
    r, g, b = diff.split()
    keep = ImageChops.lighter(ImageChops.lighter(r, g), b).point(lambda v: 255 if v else 0)
    rgba.putalpha(ImageChops.multiply(rgba.getchannel("A"), keep))
    return rgba


def tidy(frames):
    """[(RGBA, ms)] 를 모든 프레임에 걸친 한 네모로 잘라 맞춘다(움직여도 자리가 안 흔들리게)."""
    boxes = [b for b in (f.getbbox() for f, _ in frames) if b]
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


def room_left(char: str, motion: str, root: str = PACK_DIR) -> int:
    return max(0, MAX_PER_MOTION - len(clips(char, motion, root)))


def _new_path(char: str, motion: str, ext: str, root: str) -> str:
    if motion not in MOTIONS:
        raise ValueError(motion)
    if room_left(char, motion, root) <= 0:
        raise ValueError(f"{motion} 은 {MAX_PER_MOTION}장까지")
    folder = os.path.join(root, char, motion)
    os.makedirs(folder, exist_ok=True)
    stem = time.strftime("%m%d_%H%M%S")
    path, n = os.path.join(folder, stem + ext), 2
    while os.path.exists(path):
        path, n = os.path.join(folder, f"{stem}_{n}{ext}"), n + 1
    return path


def save_clip(char: str, motion: str, frames, root: str = PACK_DIR) -> str:
    """따온 그림을 캐릭터·동작 폴더에 저장. 여러 장이면 움직이는 png."""
    frames = tidy(frames)
    path = _new_path(char, motion, ".png", root)
    first, *rest = [f for f, _ in frames]
    if rest:
        first.save(path, save_all=True, append_images=rest,
                   duration=[ms for _, ms in frames], loop=0, disposal=1)
    else:
        first.save(path)
    return path


def add_file(char: str, motion: str, src: str, root: str = PACK_DIR) -> str:
    """그림 파일 한 장을 그대로 복사해 넣는다(움직이는 webp·gif 를 다시 굽지 않는다)."""
    path = _new_path(char, motion, os.path.splitext(src)[1].lower(), root)
    shutil.copy2(src, path)
    return path


def delete_clip(path: str, root: str = PACK_DIR) -> None:
    """팩 폴더 안의 그림만 지운다(밖을 가리키면 아무것도 안 함)."""
    real = os.path.realpath(path)
    if real.startswith(os.path.realpath(root) + os.sep) and os.path.isfile(real):
        os.remove(real)


def add_character(name: str, root: str = PACK_DIR) -> str:
    """새 캐릭터 폴더. 이름에 못 쓰는 글자는 뺀다. 만든(또는 있던) 이름을 돌려준다."""
    clean = "".join(ch for ch in name.strip() if ch not in BAD_NAME).strip(" .")
    if not clean or clean.startswith("_"):
        raise ValueError("이름")
    os.makedirs(os.path.join(root, clean), exist_ok=True)
    return clean


def remove_character(name: str, root: str = PACK_DIR) -> str | None:
    """캐릭터를 지우지 않고 이름 앞에 `_` 를 붙여 빼 둔다. 옮긴 이름을 돌려준다."""
    src = os.path.join(root, name)
    if not os.path.isdir(src) or name.startswith("_"):
        return None
    dst, n = os.path.join(root, "_" + name), 2
    while os.path.exists(dst):
        dst, n = os.path.join(root, f"_{name} {n}"), n + 1
    os.rename(src, dst)
    return os.path.basename(dst)


if __name__ == "__main__":
    # 팩 점검: 캐릭터마다 어느 동작을 제 그림으로 갖고 있는지
    print("팩 폴더:", PACK_DIR, "· 마당 폭", yard_width())
    for c in characters():
        own = [m for m in MOTIONS if clips(c, m)]
        print(f"  {c}: " + ", ".join(f"{m} {len(clips(c, m))}" for m in own))
    if not present():
        print("  캐릭터 없음 → 마당 없이 클로디")
