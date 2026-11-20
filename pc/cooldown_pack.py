"""
바 캐릭터 팩 — 작업표시줄 바의 클로디 자리에 세울 캐릭터들의 그림. Tk 없음.

그림은 저장소에 넣지 않는다. 각자 PC 의 `~/.claude_cooldown_pack/` 폴더에만 둔다
(이 저장소는 공개이고 친구들에게 나눠주므로, 남의 그림이 실려 나가면 안 된다).
캐릭터는 여럿 넣어 둘 수 있고, 바에는 고른 **한 명**(`active`)만 나온다. 고른 게 없으면 클로디.

    ~/.claude_cooldown_pack/
        설정.json                  {"바 캐릭터": "<이름>"}   비었거나 "클로디"면 클로디
        <캐릭터 이름>/              이름은 사용자가 정한다 (폴더 이름 = 캐릭터 이름)
            서기/ 걷기/ 인사/ 놀람/ 눌림/ 허둥/ 잠/ 축하/ 딴짓/
            설정.json              {"보는 쪽": "오른쪽"}  그림 속 캐릭터가 보는 쪽

- 동작 폴더마다 그림(png·gif·webp, 움직이는 것도 됨)을 넣는다. 그 동작을 할 때 후보 하나를 골라 튼다.
  후보 수 한도는 동작마다 다르다(`LIMITS`: 상호작용 2 · 상태 4 · 평소 16).
- 동작 폴더의 `움직임.json`(있으면)이 고정 그림에 효과를 주고 여러 장을 한 후보로 잇는다(`motion_meta`).
      {"그림": {"<파일명>": {"효과": "통통", "세기": 2}},
       "이어 붙이기": [{"이름": "..", "그림": ["a.png", "b.png"], "간격": 0.3, "효과": "없음"}]}
  묶음 하나 = 후보 하나. 묶음에만 쓰인 그림은 따로 후보가 되지 않는다. 어디에도 안 적힌 그림은
  따로 후보이고 동작마다 정한 기본 효과(`DEFAULT_FX`)를 받는다. 효과는 PIL 로 장면을 미리 굽는다(`bake`).
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
MOTIONS = ("서기", "걷기", "인사", "놀람", "눌림", "허둥", "잠", "축하", "딴짓", "기절", "끌림", "자리비움")
MOTION_LABELS = {
    "서기": "가만히 있을 때",
    "걷기": "걸어 다닐 때",
    "인사": "가끔 손 흔들 때",
    "놀람": "눌렀을 때",
    "눌림": "길게 누르는 동안",
    "허둥": "사용량 80% 넘음",
    "잠": "한도 다 참",
    "축하": "한도 풀림",
    "딴짓": "오래 가만있을 때",
    "기절": "여러 번 빨리 눌렀을 때",
    "끌림": "끌어서 옮기는 동안",
    "자리비움": "PC를 한참 안 쓸 때",
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
    "기절": ("잠", "눌림", "서기"),
    "끌림": ("놀람", "허둥", "서기"),
    "자리비움": ("잠", "딴짓", "서기"),
}
MAX_CHARS = 8  # 넣어 둘 수 있는 캐릭터 수 (바에는 한 명만 나온다)
CLAUDI = "클로디"
# 동작 하나에 둘 수 있는 후보 수 (이어 붙이기 묶음은 한 개로 센다). 11-20 사용자:
# 누르면 나오는 상호작용은 1~2개면 충분(직관적이게), 평소 동작은 다채롭게.
INTERACT = ("놀람", "눌림", "기절", "끌림")
STATES = ("허둥", "잠", "축하", "자리비움")
EVERYDAY = ("서기", "걷기", "인사", "딴짓")
LIMITS = {**{m: 2 for m in INTERACT}, **{m: 4 for m in STATES}, **{m: 16 for m in EVERYDAY}}
MAX_PER_MOTION = max(LIMITS.values())  # 옛 이름 (가장 큰 한도)
MAX_FILES_PER_MOTION = 64  # 묶음까지 쳐서 동작 폴더 하나에 둘 그림 파일 수 (팩 넣기 막이)

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


def active(root: str = PACK_DIR) -> str | None:
    """바에 세울 캐릭터 이름. None 이면 클로디.
    ★ 기본은 클로디(11-20 사용자: 설치했을 때는 원래 클로디). 사용자가 「바 캐릭터」에서 고른
    캐릭터만 선다. 팩을 넣거나 만들어도 저절로 바뀌지 않고, 고른 캐릭터가 빠지면 클로디로 돌아간다."""
    name = settings(root).get("바 캐릭터")
    if not name or name == CLAUDI:
        return None
    return name if name in characters(root) else None


def set_active(name: str | None, root: str = PACK_DIR) -> None:
    set_setting("바 캐릭터", name or CLAUDI, root)


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
    """고를 수 있는 캐릭터 (그림이 하나라도 있는 것, 이름 순, `MAX_CHARS` 까지)."""
    return [c for c in all_characters(root) if any(clips(c, m, root) for m in MOTIONS)][:MAX_CHARS]


def signature(root: str = PACK_DIR) -> tuple:
    """팩 폴더 지문(파일 경로·크기·고친 시각). 바뀌었는지만 볼 때 쓴다(앱이 3초마다)."""
    out = []
    if not os.path.isdir(root):
        return ()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith(("_", ".")))
        for name in sorted(filenames):
            p = os.path.join(dirpath, name)
            try:
                st = os.stat(p)
            except OSError:
                continue
            out.append((p, st.st_size, int(st.st_mtime)))
    return tuple(out)


def present(root: str = PACK_DIR) -> bool:
    return bool(characters(root))


def clips(char: str, motion: str, root: str = PACK_DIR) -> list[str]:
    """그 캐릭터·동작 폴더에 바로 들어 있는 그림 파일들 (이름 순)."""
    folder = os.path.join(root, char, motion)
    if not os.path.isdir(folder):
        return []
    return sorted(p for p in glob.glob(os.path.join(folder, "*")) if p.lower().endswith(EXTS))


def pick(char: str, motion: str, root: str = PACK_DIR, avoid: str | None = None) -> str | None:
    """동작 하나에 틀 그림 파일 하나 (옛 약속, 묶음의 첫 장을 준다). 바 캐릭터는 `pick_clip` 을 쓴다."""
    got = pick_clip(char, motion, root, avoid=[avoid] if avoid else ())
    return got.files[0] if got else None


# ---------------------------------------------------------------- 움직임.json · 후보
META = "움직임.json"
EFFECTS = ("없음", "통통", "좌우", "흔들", "떨기", "숨쉬기", "쭈그러짐", "쓰러짐", "빙글")
# 움직임.json 에 안 적힌 고정 그림이 받는 효과 (동작에 알맞게). 기절은 확실하게 쓰러진다.
DEFAULT_FX = {
    "서기": ("숨쉬기", 1), "걷기": ("통통", 1), "인사": ("흔들", 2), "놀람": ("쭈그러짐", 2),
    "눌림": ("쭈그러짐", 1), "허둥": ("떨기", 2), "잠": ("숨쉬기", 2), "축하": ("통통", 3),
    "딴짓": ("좌우", 1), "기절": ("쓰러짐", 3), "끌림": ("흔들", 3), "자리비움": ("숨쉬기", 1),
}
GAP_MIN, GAP_MAX = 0.1, 1.0


class Clip(tuple):
    """후보 하나: (key, files, effect, power, gap). key 는 캐시·같은 것 피하기에 쓰는 이름."""
    __slots__ = ()

    def __new__(cls, key: str, files: tuple, effect: str = "없음", power: int = 2, gap: float = 0.3):
        return super().__new__(cls, (key, tuple(files), effect, power, gap))

    key = property(lambda s: s[0])
    files = property(lambda s: s[1])
    effect = property(lambda s: s[2])
    power = property(lambda s: s[3])
    gap = property(lambda s: s[4])


def _fx(v) -> str | None:
    return v if isinstance(v, str) and v in EFFECTS else None


def _power(v) -> int:
    return v if isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 3 else 2


def clean_meta(got) -> dict:
    """움직임.json 내용을 약속대로 걸러 낸다. 모르는 칸·틀린 값은 버린다(없는 것처럼)."""
    out: dict = {"그림": {}, "이어 붙이기": []}
    if not isinstance(got, dict):
        return out
    pics = got.get("그림")
    if isinstance(pics, dict):
        for name, conf in pics.items():
            if not isinstance(name, str) or clean_name(name) != name or not name.lower().endswith(EXTS):
                continue
            conf = conf if isinstance(conf, dict) else {}
            out["그림"][name] = {"효과": _fx(conf.get("효과")) or "없음", "세기": _power(conf.get("세기"))}
    groups = got.get("이어 붙이기")
    if isinstance(groups, list):
        for i, g in enumerate(groups):
            if not isinstance(g, dict) or not isinstance(g.get("그림"), list):
                continue
            files = [f for f in g["그림"] if isinstance(f, str) and clean_name(f) == f
                     and f.lower().endswith(EXTS)]
            if not files:
                continue
            gap = g.get("간격")
            gap = min(GAP_MAX, max(GAP_MIN, float(gap))) if isinstance(gap, (int, float)) \
                and not isinstance(gap, bool) else 0.3
            name = g.get("이름") if isinstance(g.get("이름"), str) else f"묶음 {i + 1}"
            out["이어 붙이기"].append({"이름": name, "그림": files, "간격": gap,
                                   "효과": _fx(g.get("효과")) or "없음", "세기": _power(g.get("세기"))})
    return out


def motion_meta(char: str, motion: str, root: str = PACK_DIR) -> dict:
    """그 동작 폴더의 움직임.json (걸러 낸 것). 없거나 깨졌으면 빈 약속."""
    return clean_meta(_read_json(os.path.join(root, char, motion, META)))


def write_meta(char: str, motion: str, meta: dict, root: str = PACK_DIR) -> None:
    meta = clean_meta(meta)
    path = os.path.join(root, char, motion, META)
    if not meta["그림"] and not meta["이어 붙이기"]:
        if os.path.isfile(path):
            os.remove(path)
        return
    _write_json(path, meta)


def plan_clips(names: list[str], meta: dict, motion: str, folder: str = "") -> list[Clip]:
    """폴더 안 그림 이름들 + 움직임.json → 후보들. 파일이 없는 묶음 그림은 뺀다."""
    have = set(names)
    out = []
    grouped = set()
    for i, g in enumerate(meta["이어 붙이기"]):
        files = [f for f in g["그림"] if f in have]
        grouped.update(g["그림"])
        if files:
            out.append(Clip(f"{folder}|{i}|{g['이름']}", [os.path.join(folder, f) for f in files],
                            g["효과"], g["세기"], g["간격"]))
    singles = []
    for n in names:
        conf = meta["그림"].get(n)
        if conf is None and n in grouped:
            continue  # 묶음에만 쓰인 그림
        fx, power = (conf["효과"], conf["세기"]) if conf else DEFAULT_FX.get(motion, ("없음", 2))
        singles.append(Clip(os.path.join(folder, n), [os.path.join(folder, n)], fx, power))
    return singles + out


def candidates(char: str, motion: str, root: str = PACK_DIR) -> list[Clip]:
    """그 동작의 후보들 (그림 하나 또는 이어 붙이기 묶음 하나가 후보 하나). 한도까지만."""
    files = clips(char, motion, root)
    if not files:
        return []
    folder = os.path.dirname(files[0])
    got = plan_clips([os.path.basename(p) for p in files], motion_meta(char, motion, root), motion, folder)
    return got[:limit(motion)]


def limit(motion: str) -> int:
    return LIMITS.get(motion, 2)


def pick_clip(char: str, motion: str, root: str = PACK_DIR, avoid=()) -> Clip | None:
    """동작 하나에 틀 후보 하나. 없으면 빌려 오고(FALLBACK), 그래도 없으면 아무 그림이나.
    `avoid` 는 최근에 튼 것들의 key — 남는 게 있으면 그것들을 피한다(평소 동작이 잇달아 같지 않게)."""
    for m in (motion, *FALLBACK.get(motion, ()), *MOTIONS):
        found = candidates(char, m, root)
        if found:
            rest = [c for c in found if c.key not in avoid]
            return random.choice(rest or found)
    return None


# ---------------------------------------------------------------- 사용량 → 분위기
def mood(five: float | None, week: float | None) -> str:
    """사용량 두 개로 캐릭터 기분을 정한다: 여유 · 허둥 · 잠."""
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


# ---------------------------------------------------------------- 고정 그림 움직임 (효과 굽기)
# ★ 효과는 tk 에서 돌리지 않고 PIL 로 장면을 미리 굽는다. 모든 장면이 같은 크기의 판 위에 있어서
#   `fit_frames` 가 장면 전체에 걸친 네모 하나로 잘라 맞추면 바닥이 안 흔들린다.
#   세기 1·2·3 = 폭 0.6·1·1.5 배. `bake` 는 (장면들, 되감을 자리) 를 낸다. 되감을 자리는 쓰러짐처럼
#   한 번 쓰러진 뒤 누운 채로만 도는 효과에 쓴다(처음부터 다시 쓰러지지 않게).
FX_FRAMES = {  # 효과: (장면 수, 한 장면 ms). 쓰러짐·빙글은 아래 셈에서 따로 붙는다
    "통통": (12, 55), "좌우": (16, 80), "흔들": (16, 70), "떨기": (8, 40),
    "숨쉬기": (20, 90), "쭈그러짐": (12, 60),
}
FALL_STEPS, FALL_MS = 7, 45      # 쓰러지는 장면
FALL_BOUNCE = (78, 90, 85, 90)   # 바닥에 닿고 한 번 들썩 (도)
FALL_TAIL, FALL_TAIL_MS = 4, 160  # 누운 채 별이 도는 장면 (여기만 되돌아 돈다)
SPIN_STEPS, SPIN_MS, SPIN_REST = 12, 45, 700
STAR = (255, 213, 74, 255)
STAR_EDGE = (90, 60, 10, 255)


def fx_count(effect: str, power: int = 2) -> int:
    """고정 그림 한 장에 그 효과를 주면 나오는 장면 수 (시험·그림 넣기 창이 쓴다)."""
    if effect in FX_FRAMES:
        return FX_FRAMES[effect][0]
    if effect == "쓰러짐":
        return FALL_STEPS + len(FALL_BOUNCE) + FALL_TAIL
    if effect == "빙글":
        return SPIN_STEPS * (2 if power >= 3 else 1) + 1
    return 1


def _k(power: int) -> float:
    return {1: 0.6, 2: 1.0, 3: 1.5}.get(power, 1.0)


def _pose(img, size, base, angle=0.0, sx=1.0, sy=1.0, dx=0.0, dy=0.0, pivot=None):
    """그림 한 장을 판(size) 위에 놓는다. 쉬는 자리는 바닥 가운데가 `base`. `pivot`(그림 안 좌표)을
    축으로 돌리고(도, 시계 방향) 늘이고 옮긴다. 테두리가 거뭇해지지 않게 곱한 알파(RGBa)로 돌린다."""
    import math

    from PIL import Image

    w, h = img.size
    px, py = pivot if pivot is not None else (w / 2, h)
    cx, cy = base[0] - w / 2 + px + dx, base[1] - h + py + dy
    a = math.radians(angle)
    co, si = math.cos(a), math.sin(a)
    m00, m01, m10, m11 = co / sx, si / sx, -si / sy, co / sy
    data = (m00, m01, px - m00 * cx - m01 * cy, m10, m11, py - m10 * cx - m11 * cy)
    out = img.convert("RGBa").transform(size, Image.AFFINE, data, Image.BICUBIC)
    return out.convert("RGBA")


def _stars(frame, center, rx, ry, r, count, phase):
    """기절한 머리 위를 도는 별."""
    import math

    from PIL import ImageDraw

    d = ImageDraw.Draw(frame)
    for j in range(count):
        a = phase + j * math.tau / count
        x, y = center[0] + math.cos(a) * rx, center[1] + math.sin(a) * ry
        pts = []
        for t in range(10):
            rr = r if t % 2 == 0 else r * 0.45
            b = -math.pi / 2 + t * math.pi / 5
            pts.append((x + math.cos(b) * rr, y + math.sin(b) * rr))
        d.polygon(pts, fill=STAR, outline=STAR_EDGE)
    return frame


def bake(imgs, effect: str, power: int = 2, gap_ms: int = 300):
    """고정 그림(들) → ([(RGBA, ms)], 되감을 자리). 그림이 여럿이면(이어 붙이기) `gap_ms` 마다 갈아 끼우며
    효과를 같이 준다. 그림은 크기가 같아야 한다(`same_height`)."""
    import math

    imgs = list(imgs) if isinstance(imgs, (list, tuple)) else [imgs]
    n_img = len(imgs)
    w = max(im.width for im in imgs)
    h = max(im.height for im in imgs)
    if effect not in FX_FRAMES and effect not in ("쓰러짐", "빙글"):
        if n_img == 1:
            return [(imgs[0], 1000)], 0
        return [(im, gap_ms) for im in imgs], 0
    k = _k(power)
    size = (2 * (w + h), 2 * (w + h))
    base = (size[0] / 2, size[1] * 0.7)

    def img_at(ms_from_start: float):
        return imgs[int(ms_from_start // max(1, gap_ms)) % n_img] if n_img > 1 else imgs[0]

    out = []
    if effect in FX_FRAMES:
        n, ms = FX_FRAMES[effect]
        total = n  # 그림을 갈아 끼우는 한 주기까지 다 돌도록 효과를 되풀이한다
        while n_img > 1 and total * ms < n_img * gap_ms:
            total += n
        for i in range(total):
            p = (i % n) / n
            im = img_at(i * ms)
            iw, ih = im.size
            if effect == "통통":
                s = math.sin(math.pi * p)
                squash = 0.10 * k * (1 - s) ** 3
                f = _pose(im, size, base, sx=1 + squash * 0.6, sy=1 - squash, dy=-0.10 * ih * k * s)
            elif effect == "좌우":
                f = _pose(im, size, base, dx=0.10 * iw * k * math.sin(math.tau * p),
                          angle=2.5 * k * math.sin(math.tau * p))
            elif effect == "흔들":
                f = _pose(im, size, base, angle=8 * k * math.sin(math.tau * p))
            elif effect == "떨기":
                jx = (1, -1, 0.5, -0.5, 1, -1, -0.5, 0.5)[i % 8]
                jy = (0, -0.5, 0.5, 0, -0.5, 0.5, 0, -0.3)[i % 8]
                f = _pose(im, size, base, dx=0.025 * iw * k * jx, dy=0.02 * ih * k * jy,
                          angle=1.5 * k * jx)
            elif effect == "숨쉬기":
                s = math.sin(math.tau * p)
                f = _pose(im, size, base, sx=1 - 0.015 * k * s, sy=1 + 0.04 * k * s)
            else:  # 쭈그러짐
                squash = 0.22 * k * math.sin(math.pi * p)
                f = _pose(im, size, base, sx=1 + squash * 0.7, sy=1 - squash)
            out.append((f, ms))
        return out, 0
    if effect == "쓰러짐":
        t_ms = 0.0
        pivot = (w, h)  # 오른쪽 발끝을 축으로 옆으로 픽
        steps = [90 * ((i + 1) / FALL_STEPS) ** 2 for i in range(FALL_STEPS)] + list(FALL_BOUNCE)
        for j, ang in enumerate(steps):
            ms = FALL_MS if j < FALL_STEPS else 50
            out.append((_pose(img_at(t_ms), size, base, angle=ang, pivot=pivot), ms))
            t_ms += ms
        loop_from = len(out)
        bx, by = base[0] + w / 2, base[1]  # 축(발끝)이 놓인 자리
        count = 2 + power
        for j in range(FALL_TAIL):
            f = _pose(img_at(t_ms), size, base, angle=90, pivot=pivot)
            _stars(f, (bx + h * 0.78, by - w - h * 0.12), h * 0.18 * (0.8 + 0.2 * k),
                   h * 0.06, max(2.0, h * 0.06), count, j * math.tau / FALL_TAIL / count)
            out.append((f, FALL_TAIL_MS))
            t_ms += FALL_TAIL_MS
        return out, loop_from
    # 빙글: 한가운데를 축으로 한 바퀴(세기 3 은 두 바퀴), 그리고 잠깐 쉰다
    steps = SPIN_STEPS * (2 if power >= 3 else 1)
    t_ms = 0.0
    for i in range(steps):
        out.append((_pose(img_at(t_ms), size, base, angle=360 * i / SPIN_STEPS,
                          pivot=(w / 2, h / 2)), SPIN_MS))
        t_ms += SPIN_MS
    out.append((_pose(img_at(t_ms), size, base), SPIN_REST))
    return out, 0


def same_height(imgs, height: int):
    """여러 그림을 투명 테두리를 걷고 같은 높이·같은 폭 판으로 맞춘다(작은 도트 그림은 또렷하게 키운다)."""
    from PIL import Image

    out = []
    for im in imgs:
        box = im.getbbox()
        im = im.crop(box) if box else im
        scale = height / max(1, im.height)
        size = (max(1, round(im.width * scale)), height)
        out.append(im.resize(size, Image.NEAREST if scale > 1 else Image.LANCZOS))
    w = max(im.width for im in out)
    padded = []
    for im in out:
        c = Image.new("RGBA", (w, height), (0, 0, 0, 0))
        c.paste(im, ((w - im.width) // 2, 0))
        padded.append(c)
    return padded


def clip_frames(clip: Clip, work_h: int = 140):
    """후보 하나 → ([(RGBA, ms)], 되감을 자리), 크기는 아직 안 맞춘 것. 움직이는 그림(여러 장)은
    그대로 쓰고 효과는 안 준다. 고정 그림·이어 붙이기는 `work_h` 높이로 맞춘 뒤 굽는다."""
    if len(clip.files) == 1:
        raw = read_frames(clip.files[0])
        if len(raw) > 1 or clip.effect == "없음":
            return raw, 0
        return bake(same_height([raw[0][0]], work_h), clip.effect, clip.power)
    stills = []
    for p in clip.files:
        try:
            raw = read_frames(p)
        except Exception:  # 묶음 안 그림 하나가 깨졌으면 그것만 뺀다
            continue
        if raw:
            stills.append(raw[0][0])
    if not stills:
        return [], 0
    return bake(same_height(stills, work_h), clip.effect, clip.power, int(clip.gap * 1000))


def load_clip(clip: Clip, height: int, width: int | None = None):
    """후보 하나를 바에 세울 크기로: ([(RGBA, ms)], 되감을 자리)."""
    frames, loop_from = clip_frames(clip, max(64, min(160, height * 3)))
    return fit_frames(frames, height, 1.0, width), loop_from


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


def all_candidates(char: str, motion: str, root: str) -> list[Clip]:
    files = clips(char, motion, root)
    if not files:
        return []
    return plan_clips([os.path.basename(p) for p in files], motion_meta(char, motion, root),
                      motion, os.path.dirname(files[0]))


def room_left(char: str, motion: str, root: str = PACK_DIR) -> int:
    """그 동작에 더 넣을 수 있는 후보 수 (묶음은 하나로 센다)."""
    if len(clips(char, motion, root)) >= MAX_FILES_PER_MOTION:
        return 0
    return max(0, limit(motion) - len(all_candidates(char, motion, root)))


def _new_path(char: str, motion: str, ext: str, root: str) -> str:
    if motion not in MOTIONS:
        raise ValueError(motion)
    if room_left(char, motion, root) <= 0:
        raise ValueError(f"{motion} 은 {limit(motion)}개까지")
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


def _named(meta: dict) -> set:
    """움직임.json 에 적힌 그림 이름 전부."""
    return set(meta["그림"]) | {f for g in meta["이어 붙이기"] for f in g["그림"]}


def _forget(meta: dict, names: set) -> dict:
    """움직임.json 에서 지운 그림 이름을 걷어 낸다. 그림이 다 빠진 묶음은 없앤다."""
    meta["그림"] = {k: v for k, v in meta["그림"].items() if k not in names}
    groups = []
    for g in meta["이어 붙이기"]:
        g = dict(g, 그림=[f for f in g["그림"] if f not in names])
        if g["그림"]:
            groups.append(g)
    meta["이어 붙이기"] = groups
    return meta


def delete_clip(path: str, root: str = PACK_DIR) -> None:
    """팩 폴더 안의 그림만 지운다(밖을 가리키면 아무것도 안 함). 움직임.json 의 그 이름도 정리한다."""
    real = os.path.realpath(path)
    if real.startswith(os.path.realpath(root) + os.sep) and os.path.isfile(real):
        os.remove(real)
        _tidy_meta(os.path.dirname(real), {os.path.basename(real)})


def _tidy_meta(folder: str, names: set) -> None:
    path = os.path.join(folder, META)
    if os.path.isfile(path):
        meta = _forget(clean_meta(_read_json(path)), names)
        if meta["그림"] or meta["이어 붙이기"]:
            _write_json(path, meta)
        else:
            os.remove(path)


def delete_candidate(clip: Clip, root: str = PACK_DIR) -> None:
    """후보 하나를 지운다. 묶음이면 그 묶음을 움직임.json 에서 빼고, 다른 후보가 안 쓰는 그림만 지운다."""
    if len(clip.files) == 1 and "|" not in clip.key:
        delete_clip(clip.files[0], root)
        return
    folder = os.path.dirname(clip.files[0])
    real = os.path.realpath(folder)
    if not real.startswith(os.path.realpath(root) + os.sep):
        return
    path = os.path.join(folder, META)
    meta = clean_meta(_read_json(path))
    try:
        idx = int(clip.key.split("|")[1])
    except (IndexError, ValueError):
        return
    if not 0 <= idx < len(meta["이어 붙이기"]):
        return
    mine = set(meta["이어 붙이기"].pop(idx)["그림"])
    keep = _named(meta)
    for name in mine - keep:
        p = os.path.join(folder, name)
        if os.path.isfile(p):
            os.remove(p)
    if meta["그림"] or meta["이어 붙이기"]:
        _write_json(path, meta)
    elif os.path.isfile(path):
        os.remove(path)


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


# ---------------------------------------------------------------- 캐릭터팩 파일 (내보내기·넣기)
# 캐릭터 하나 = zip 하나. 이름은 `<캐릭터>.캐릭터팩.zip` (그냥 zip 이라 어디서나 열리고 이름으로 알아본다).
#     팩.json                {"형식": 1, "캐릭터": "<이름>"}
#     <이름>/설정.json        캐릭터 설정 (보는 쪽 등)
#     <이름>/<동작>/<그림>    동작 폴더마다 그림
# ★ 남이 만든 파일을 받는 길이라 넣을 때 다 의심한다: 경로 탈출(`..`·절대경로·드라이브)·
#   그림 아닌 파일·한도(캐릭터 수·동작당 장수)·지나치게 큰 파일. 하나라도 걸리면 통째로 거절하고
#   팩 폴더에는 아무것도 안 남긴다(임시 폴더 `_넣는 중…` 에 풀어 다 맞으면 이름만 바꿔 옮긴다).
PACK_SUFFIX = ".캐릭터팩.zip"
PACK_FORMAT = 1
PACK_MANIFEST = "팩.json"
PACK_MAX_FILE = 20 * 1024 * 1024  # 팩 파일 자체
PACK_MAX_CLIP = 8 * 1024 * 1024  # 풀었을 때 그림 한 장
PACK_MAX_TOTAL = 60 * 1024 * 1024  # 풀었을 때 전부
PACK_SKIP = {"thumbs.db", "desktop.ini", ".ds_store"}  # 탐색기가 저절로 만드는 것


class PackError(ValueError):
    """팩을 넣지 못한 까닭 (화면에 한 줄로 그대로 보여 준다)."""


def clean_name(name: str) -> str:
    return "".join(ch for ch in name.strip() if ch not in BAD_NAME and ord(ch) >= 32).strip(" .")


def free_name(name: str, root: str = PACK_DIR) -> str:
    """겹치지 않는 캐릭터 이름: `솜구름` 이 있으면 `솜구름 (2)`, `솜구름 (3)` …"""
    taken = {n.casefold() for n in os.listdir(root)} if os.path.isdir(root) else set()
    if name.casefold() not in taken:
        return name
    n = 2
    while f"{name} ({n})".casefold() in taken:
        n += 1
    return f"{name} ({n})"


def export_pack(char: str, dest: str, root: str = PACK_DIR) -> str:
    """캐릭터 하나를 팩 파일 하나로 저장한다. 저장한 경로를 돌려준다."""
    import zipfile

    if char not in all_characters(root):
        raise PackError("없는 캐릭터")
    if not any(clips(char, m, root) for m in MOTIONS):
        raise PackError("그림 없는 캐릭터")
    tmp = dest + ".쓰는중"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(PACK_MANIFEST, json.dumps({"형식": PACK_FORMAT, "캐릭터": char},
                                             ensure_ascii=False, indent=1))
        conf = char_settings(char, root)
        if conf:
            z.writestr(f"{char}/설정.json", json.dumps(conf, ensure_ascii=False, indent=1))
        for m in MOTIONS:
            for p in clips(char, m, root):
                z.write(p, f"{char}/{m}/{os.path.basename(p)}")
            meta = motion_meta(char, m, root)
            if clips(char, m, root) and (meta["그림"] or meta["이어 붙이기"]):
                z.writestr(f"{char}/{m}/{META}", json.dumps(meta, ensure_ascii=False, indent=1))
    os.replace(tmp, dest)
    return dest


PACK_MAX_META = 64 * 1024  # 움직임.json 한 개


def _pack_plan(z) -> tuple[str, dict, list, dict]:
    """zip 을 훑어 (캐릭터 이름, 캐릭터 설정, [(zip 안 이름, 동작, 파일 이름)], {동작: 움직임}) 를 낸다.
    후보 수는 움직임.json 까지 보고 센다(묶음은 하나). 틀리면 PackError."""
    try:
        meta = json.loads(z.read(PACK_MANIFEST).decode("utf-8-sig"))
    except KeyError:
        raise PackError("캐릭터팩 파일이 아님") from None
    except ValueError:
        raise PackError("팩 정보가 깨짐") from None
    if not isinstance(meta, dict) or not isinstance(meta.get("형식"), int):
        raise PackError("팩 정보가 깨짐")
    if meta["형식"] > PACK_FORMAT:
        raise PackError("더 새 버전에서 만든 팩 · 앱 업데이트 필요")
    name = clean_name(str(meta.get("캐릭터") or ""))
    if not name or name.startswith("_"):
        raise PackError("캐릭터 이름이 잘못됨")
    conf, files, total = {}, [], 0
    per_motion: dict[str, list] = {}
    metas: dict[str, dict] = {}
    for info in z.infolist():
        raw = info.filename
        parts = raw.replace("\\", "/").split("/")
        if raw.startswith(("/", "\\")) or ":" in raw or any(p in ("..", ".") for p in parts):
            raise PackError("잘못된 경로가 든 팩")
        if info.is_dir():
            continue
        if raw == PACK_MANIFEST:
            continue
        if parts[-1].casefold() in PACK_SKIP:
            continue
        if info.file_size > PACK_MAX_CLIP:
            raise PackError(f"그림 한 장이 {PACK_MAX_CLIP // 1024 // 1024}MB 넘음")
        total += info.file_size
        if total > PACK_MAX_TOTAL:
            raise PackError(f"풀면 {PACK_MAX_TOTAL // 1024 // 1024}MB 넘음")
        if len(parts) == 2 and parts[1] == "설정.json":
            try:
                got = json.loads(z.read(info).decode("utf-8-sig"))
            except ValueError:
                raise PackError("캐릭터 설정이 깨짐") from None
            conf = {k: v for k, v in got.items() if isinstance(k, str)} if isinstance(got, dict) else {}
            continue
        if len(parts) != 3 or not parts[2]:
            raise PackError("팩 안에 모르는 파일")
        _top, motion, fname = parts
        if fname == META:
            if info.file_size > PACK_MAX_META:
                raise PackError("움직임 설정이 너무 큼")
            try:
                got = json.loads(z.read(info).decode("utf-8-sig"))
            except ValueError:
                raise PackError("움직임 설정이 깨짐") from None
            if motion in MOTIONS:
                metas[motion] = clean_meta(got)
            continue
        if not fname.lower().endswith(EXTS) or clean_name(fname) != fname:
            raise PackError("그림이 아닌 파일이 든 팩")
        if motion not in MOTIONS:
            continue  # 더 새 버전의 동작(이 앱은 모르는 것)은 건너뛴다
        per_motion.setdefault(motion, []).append(fname)
        if len(per_motion[motion]) > MAX_FILES_PER_MOTION:
            raise PackError(f"{motion} 그림이 {MAX_FILES_PER_MOTION}장 넘음")
        files.append((info, motion, fname))
    if not files:
        raise PackError("그림 없는 팩")
    empty = clean_meta({})
    for motion, names in per_motion.items():
        meta = metas.get(motion, empty)
        if len(plan_clips(sorted(names), meta, motion)) > limit(motion):
            raise PackError(f"{motion} 후보가 {limit(motion)}개 넘음")
    # 그림이 없는 동작의 움직임.json 은 버리고, 남은 것은 그 폴더 그림 이름만 남긴다
    metas = {m: _forget(meta, _named(meta) - set(per_motion[m]))
             for m, meta in metas.items() if m in per_motion}
    return name, conf, files, metas


def import_pack(src: str, root: str = PACK_DIR) -> str:
    """팩 파일을 넣는다. 넣은 캐릭터 이름(겹치면 `이름 (2)`)을 돌려준다. 바 캐릭터는 안 바꾼다."""
    import zipfile

    try:
        if os.path.getsize(src) > PACK_MAX_FILE:
            raise PackError(f"팩 파일이 {PACK_MAX_FILE // 1024 // 1024}MB 넘음")
        z = zipfile.ZipFile(src)
    except OSError:
        raise PackError("파일을 못 읽음") from None
    except zipfile.BadZipFile:
        raise PackError("캐릭터팩 파일이 아님") from None
    with z:
        name, conf, files, metas = _pack_plan(z)
        if len(all_characters(root)) >= MAX_CHARS:
            raise PackError(f"캐릭터는 {MAX_CHARS}명까지 · 하나 빼고 넣기")
        os.makedirs(root, exist_ok=True)
        tmp = os.path.join(root, f"_넣는 중 {os.getpid()} {time.time_ns()}")
        try:
            for info, motion, fname in files:
                folder = os.path.join(tmp, motion)
                os.makedirs(folder, exist_ok=True)
                out = os.path.join(folder, fname)
                left = PACK_MAX_CLIP
                with z.open(info) as fin, open(out, "wb") as fout:
                    # 적힌 크기를 믿지 않고 실제로 읽은 만큼 센다(크기를 속인 zip)
                    while chunk := fin.read(65536):
                        left -= len(chunk)
                        if left < 0:
                            raise PackError(f"그림 한 장이 {PACK_MAX_CLIP // 1024 // 1024}MB 넘음")
                        fout.write(chunk)
                try:
                    from PIL import Image

                    with Image.open(out) as im:
                        im.verify()
                except Exception:
                    raise PackError("열리지 않는 그림이 든 팩") from None
            if conf:
                _write_json(os.path.join(tmp, "설정.json"), conf)
            for motion, meta in metas.items():
                if meta["그림"] or meta["이어 붙이기"]:
                    _write_json(os.path.join(tmp, motion, META), meta)
            final = free_name(name, root)
            os.rename(tmp, os.path.join(root, final))
            return final
        except BaseException:
            shutil.rmtree(tmp, ignore_errors=True)
            raise


if __name__ == "__main__":
    # 팩 점검: 캐릭터마다 어느 동작을 제 그림으로 갖고 있는지
    print("팩 폴더:", PACK_DIR, "· 바 캐릭터", active() or CLAUDI)
    for c in characters():
        own = [m for m in MOTIONS if clips(c, m)]
        print(f"  {c}: " + ", ".join(f"{m} {len(clips(c, m))}" for m in own))
    if not present():
        print("  캐릭터 없음 → 클로디")
