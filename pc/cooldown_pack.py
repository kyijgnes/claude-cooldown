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
    "인사": "가끔 손 흔들 때",
    "놀람": "눌렀을 때",
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
MAX_CHARS = 8  # 넣어 둘 수 있는 캐릭터 수 (바에는 한 명만 나온다)
CLAUDI = "클로디"
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
    os.replace(tmp, dest)
    return dest


def _pack_plan(z) -> tuple[str, dict, list]:
    """zip 을 훑어 (캐릭터 이름, 캐릭터 설정, [(zip 안 이름, 동작, 파일 이름)]) 를 낸다. 틀리면 PackError."""
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
    per_motion: dict[str, int] = {}
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
        if not fname.lower().endswith(EXTS) or clean_name(fname) != fname:
            raise PackError("그림이 아닌 파일이 든 팩")
        if motion not in MOTIONS:
            continue  # 더 새 버전의 동작(이 앱은 모르는 것)은 건너뛴다
        per_motion[motion] = per_motion.get(motion, 0) + 1
        if per_motion[motion] > MAX_PER_MOTION:
            raise PackError(f"{motion} 그림이 {MAX_PER_MOTION}장 넘음")
        files.append((info, motion, fname))
    if not files:
        raise PackError("그림 없는 팩")
    return name, conf, files


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
        name, conf, files = _pack_plan(z)
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
