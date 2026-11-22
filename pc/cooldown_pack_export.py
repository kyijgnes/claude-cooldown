"""
폰으로 보낼 캐릭터팩 만들기 — 바 캐릭터 그림을 폰 앱이 바로 틀 수 있게 구워 zip 하나로 묶는다. Tk 없음.

그림은 서버·저장소·APK 어디에도 안 올린다(저작권). 이 파일을 카톡·USB 등으로 폰에 옮기고
폰 앱 옵션 > 「캐릭터팩 가져오기」에서 고르면 폰 앱 안에만 풀린다.

★ 폰은 효과를 따로 셈하지 않는다. **PC 엔진(`cooldown_pack.load_clip`)으로 장면을 미리 구워** 넣는다.
  그래서 고정 그림의 효과(통통·흔들·헤롱 …)·빌려 온 그림의 효과·움직이는 그림의 장면 길이가 PC 바와 같다.
  동작마다 후보를 장면 묶음 그림(가로세로 칸으로 늘어놓은 webp 한 장) + 장면 길이(ms) 목록으로 담는다.

    <이름>.zip
        폰팩.json   {"형식": 1, "바 캐릭터": "<이름>"|null,
                     "캐릭터": [{"이름": "..", "폴더": "c0", "보는 쪽": "오른쪽",
                                "동작": {"<동작>": [{"그림": "c0/<해시>.webp", "폭": w, "높이": h,
                                                    "열": 칸 수, "ms": [..], "되감기": n}]}}]}
        c0/<해시>.webp ...

- 동작 이름은 PC 폴더 이름 그대로다. 폰은 아는 이름만 쓰고 모르는 이름은 건너뛴다
  (PC 에 동작이 새로 생겨도 폰 앱을 안 고치면 그냥 안 쓰일 뿐이다).
- 담는 동작은 폰이 쓰는 것(`PHONE_MOTIONS`)과 PC 가 아는 것(`cooldown_pack.MOTIONS`)이 겹치는 것만.
  빈 동작은 PC 와 같이 빌려 온다(`pick_clip`). 같은 그림이 여러 동작에 쓰이면 파일은 한 번만 담는다.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import zipfile

import cooldown_pack as pack

FORMAT = 1
MANIFEST = "폰팩.json"
SUFFIX = ".폰캐릭터팩.zip"
HEIGHT = 180          # 구울 높이(px). 폰은 이 그림을 늘이거나 줄여 그린다
MAX_SHEET = 4096      # 장면 묶음 그림 한 변 (폰 Bitmap 한도 안쪽)
MAX_FRAMES = 96       # 후보 하나의 장면 수 (넘으면 앞에서부터)
PER_MOTION = 6        # 동작 하나에 담는 후보 수 (평소 동작은 PC 가 16까지 둔다. 폰은 이만큼)
QUALITY = 88
# 폰이 쓰는 동작 (android `wallpaper/Buddy.kt` 의 `MOTIONS` 와 같게 둔다)
PHONE_MOTIONS = ("서기", "딴짓", "걷기", "인사", "뛰기", "점프",
                 "놀람", "눌림", "짜증", "화남", "포기", "기절", "깡충", "깸",
                 "허둥", "잠", "축하", "자리비움")


class ExportError(ValueError):
    """만들지 못한 까닭 (화면에 한 줄로 그대로 보여 준다)."""


def motions() -> list[str]:
    known = set(pack.MOTIONS)
    return [m for m in PHONE_MOTIONS if m in known]


def clips_for(char: str, motion: str, root: str = pack.PACK_DIR) -> list:
    """폰에 담을 그 동작의 후보들. 제 것이 있으면 제 것(`PER_MOTION` 까지), 없으면 빌린 것 하나."""
    own = pack.candidates(char, motion, root)
    if own:
        return own[:PER_MOTION]
    got = pack.pick_clip(char, motion, root, stable=True)
    return [got] if got else []


def sheet(frames) -> tuple[bytes, dict]:
    """[(RGBA, ms)] → (webp 바이트, 정보). 장면을 왼쪽 위부터 가로로 늘어놓는다."""
    from PIL import Image

    frames = frames[:MAX_FRAMES]
    w = max(f.width for f, _ in frames)
    h = max(f.height for f, _ in frames)
    cols = max(1, min(len(frames), MAX_SHEET // w))
    rows = math.ceil(len(frames) / cols)
    if rows * h > MAX_SHEET:  # 너무 길다: 들어가는 만큼만
        frames = frames[:cols * (MAX_SHEET // h)]
        rows = math.ceil(len(frames) / cols)
    out = Image.new("RGBA", (cols * w, rows * h), (0, 0, 0, 0))
    for i, (f, _ms) in enumerate(frames):
        # 바닥 가운데에 맞춰 놓는다 (fit_frames 가 이미 같은 크기로 맞춰 오지만 혹시 몰라)
        out.paste(f, ((i % cols) * w + (w - f.width) // 2, (i // cols) * h + h - f.height))
    buf = io.BytesIO()
    out.save(buf, "WEBP", quality=QUALITY, method=4)
    info = {"폭": w, "높이": h, "열": cols, "ms": [int(ms) for _f, ms in frames]}
    return buf.getvalue(), info


def bake_clip(clip, height: int = HEIGHT) -> tuple[bytes, dict] | None:
    """후보 하나 → (webp, 정보) . 못 읽는 그림이면 None."""
    try:
        frames, loop_from = pack.load_clip(clip, height)
    except Exception:
        return None
    if not frames:
        return None
    data, info = sheet(frames)
    info["되감기"] = loop_from if 0 <= loop_from < len(info["ms"]) else 0
    return data, info


def build(chars: list[str], root: str = pack.PACK_DIR, progress=None) -> tuple[dict, dict]:
    """(폰팩.json 내용, {zip 안 이름: 바이트}). `progress(한 일, 할 일)` 을 이따금 부른다."""
    todo = [(c, m) for c in chars for m in motions()]
    files: dict[str, bytes] = {}
    out_chars = []
    done = 0
    for i, char in enumerate(chars):
        folder = f"c{i}"
        table: dict[str, list] = {}
        for m in motions():
            entries = []
            for clip in clips_for(char, m, root):
                got = bake_clip(clip)
                if not got:
                    continue
                data, info = got
                name = f"{folder}/{hashlib.sha1(data).hexdigest()[:16]}.webp"
                files.setdefault(name, data)
                entries.append(dict(info, 그림=name))
            if entries:
                table[m] = entries
            done += 1
            if progress:
                progress(done, len(todo))
        if table:
            out_chars.append({"이름": char, "폴더": folder,
                              "보는 쪽": "오른쪽" if pack.faces_right(char, root) else "왼쪽",
                              "동작": table})
    if not out_chars:
        raise ExportError("그림 없는 캐릭터")
    now = pack.active(root)
    manifest = {"형식": FORMAT, "바 캐릭터": now if now in [c["이름"] for c in out_chars] else None,
                "캐릭터": out_chars}
    return manifest, files


def export(dest: str, chars: list[str] | None = None, root: str = pack.PACK_DIR, progress=None) -> str:
    """폰으로 보낼 팩을 `dest` 에 저장한다. `chars` 가 없으면 넣어 둔 캐릭터 전부."""
    have = pack.characters(root)
    chars = have if chars is None else [c for c in chars if c in have]
    if not chars:
        raise ExportError("넣어 둔 캐릭터 없음")
    manifest, files = build(chars, root, progress)
    tmp = dest + ".쓰는중"
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED) as z:  # webp 는 이미 눌려 있다
            z.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=1))
            for name, data in sorted(files.items()):
                z.writestr(name, data)
        os.replace(tmp, dest)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return dest


def default_name(chars: list[str] | None, root: str = pack.PACK_DIR) -> str:
    """저장 창에 미리 넣을 이름: 한 명이면 그 이름, 여럿이면 「캐릭터 전부」."""
    chars = pack.characters(root) if chars is None else chars
    return (chars[0] if len(chars) == 1 else "캐릭터 전부") + SUFFIX


if __name__ == "__main__":
    import sys
    import time

    dest = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.getcwd(), default_name(None))
    t0 = time.time()
    export(dest, progress=lambda a, b: print(f"\r{a}/{b}", end="", flush=True))
    print(f"\n{dest} · {os.path.getsize(dest) / 1024 / 1024:.1f}MB · {time.time() - t0:.1f}초")
