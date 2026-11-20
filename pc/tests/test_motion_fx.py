"""고정 그림 움직임(`움직임.json`·효과 굽기)과 동작별 후보 한도 시험. 화면 없이 돈다.

시험 그림은 코드로 그린 동그라미다(사용자 그림·이름을 저장소에 넣지 않는다).
"""
import json
import os
import sys
import zipfile

import pytest
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cooldown_pack as pack  # noqa: E402

CHAR = "동글이"


def blob(path, color=(220, 120, 90, 255), size=(30, 40)):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse((2, 2, size[0] - 3, size[1] - 3), fill=color)
    im.save(path)
    return path


def moving(path, n=3):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    frames = [Image.new("RGBA", (20, 20), (40 * i, 90, 90, 255)) for i in range(n)]
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=100, loop=0)
    return path


def put_meta(root, motion, meta, raw=None):
    p = os.path.join(root, CHAR, motion, pack.META)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(raw if raw is not None else json.dumps(meta, ensure_ascii=False))


def names(clips):
    return sorted("+".join(os.path.basename(f) for f in c.files) for c in clips)


# ------------------------------------------------ 움직임.json 읽기
def test_no_meta_gives_default_effects(tmp_path):
    root = str(tmp_path)
    blob(os.path.join(root, CHAR, "기절", "a.png"))
    blob(os.path.join(root, CHAR, "서기", "a.png"))
    (faint,) = pack.candidates(CHAR, "기절", root)
    assert faint.effect == "헤롱"             # 기절은 헤롱헤롱 비틀대다 쓰러진다
    assert pack.candidates(CHAR, "서기", root)[0].effect == pack.DEFAULT_FX["서기"][0]


def test_meta_effects_and_groups(tmp_path):
    root = str(tmp_path)
    for n in ("a.png", "b.png", "c.png", "d.png"):
        blob(os.path.join(root, CHAR, "서기", n))
    put_meta(root, "서기", {
        "그림": {"a.png": {"효과": "떨기", "세기": 3}, "c.png": {"효과": "빙글"}},
        "이어 붙이기": [{"이름": "깜빡", "그림": ["b.png", "c.png", "없는.png"], "간격": 0.2,
                     "효과": "통통"}],
    })
    got = {"+".join(os.path.basename(f) for f in c.files): c for c in pack.candidates(CHAR, "서기", root)}
    # a: 적힌 그대로 · c: 묶음에도 있지만 「그림」에 적혀 있어 따로 후보 · b: 묶음에만 → 따로 안 됨
    # d: 어디에도 안 적힘 → 기본 효과로 따로 후보 · 묶음은 있는 파일만(없는.png 뺌)
    assert set(got) == {"a.png", "c.png", "d.png", "b.png+c.png"}
    assert (got["a.png"].effect, got["a.png"].power) == ("떨기", 3)
    assert (got["c.png"].effect, got["c.png"].power) == ("빙글", 2)   # 세기 없으면 2
    assert got["d.png"].effect == pack.DEFAULT_FX["서기"][0]
    g = got["b.png+c.png"]
    assert (g.effect, g.gap) == ("통통", 0.2)


def test_bad_meta_values_ignored(tmp_path):
    root = str(tmp_path)
    blob(os.path.join(root, CHAR, "인사", "a.png"))
    blob(os.path.join(root, CHAR, "인사", "b.png"))
    put_meta(root, "인사", {
        "그림": {"a.png": {"효과": "폭발", "세기": 9}, "../x.png": {"효과": "통통"}, "b.png": "통통"},
        "이어 붙이기": [{"그림": "a.png"}, {"그림": [1, None]}, {"그림": ["a.png", "b.png"],
                                                          "간격": 5, "효과": 3}, "글자"],
    })
    meta = pack.motion_meta(CHAR, "인사", root)
    assert meta["그림"]["a.png"] == {"효과": "없음", "세기": 2}   # 모르는 효과·세기 → 없음·2
    assert "../x.png" not in meta["그림"]
    assert meta["그림"]["b.png"] == {"효과": "없음", "세기": 2}
    (g,) = meta["이어 붙이기"]
    assert g["간격"] == pack.GAP_MAX and g["효과"] == "없음"


@pytest.mark.parametrize("raw", ["{깨짐", "[1, 2]", "", "null"])
def test_broken_meta_file_is_like_none(tmp_path, raw):
    root = str(tmp_path)
    blob(os.path.join(root, CHAR, "걷기", "a.png"))
    put_meta(root, "걷기", None, raw=raw)
    (c,) = pack.candidates(CHAR, "걷기", root)
    assert c.effect == pack.DEFAULT_FX["걷기"][0]


def test_meta_with_bom(tmp_path):
    root = str(tmp_path)
    blob(os.path.join(root, CHAR, "걷기", "a.png"))
    put_meta(root, "걷기", None, raw="﻿" + json.dumps({"그림": {"a.png": {"효과": "좌우"}}}))
    assert pack.candidates(CHAR, "걷기", root)[0].effect == "좌우"


# ------------------------------------------------ 효과 굽기
@pytest.mark.parametrize("effect", pack.EFFECTS)
@pytest.mark.parametrize("power", (1, 2, 3))
def test_bake_counts_and_sizes(effect, power):
    im = Image.new("RGBA", (30, 40), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse((2, 2, 27, 37), fill=(200, 100, 100, 255))
    frames, loop_from = pack.bake(pack.same_height([im], 120), effect, power)
    assert len(frames) == pack.fx_count(effect, power)
    assert len({f.size for f, _ in frames}) == 1          # 판 크기가 같아야 바닥이 안 흔들린다
    assert all(ms > 0 for _, ms in frames)
    assert 0 <= loop_from < len(frames)
    fit = pack.fit_frames(frames, 46, 1.0, 80)
    sizes = {f.size for f, _ in fit}
    assert len(sizes) == 1
    (w, h), = sizes
    assert h <= 46 and w <= 80
    if effect != "없음":
        assert len({f.tobytes() for f, _ in frames}) > 1  # 실제로 움직인다


def test_faint_lies_down_and_stays():
    im = Image.new("RGBA", (20, 60), (0, 0, 0, 0))
    ImageDraw.Draw(im).rectangle((0, 0, 19, 59), fill=(90, 90, 200, 255))
    frames, loop_from = pack.bake([im], "쓰러짐", 3)
    first = frames[0][0].getbbox()
    lying = frames[loop_from - 1][0].getbbox()   # 별 없이 누운 마지막 장면
    # 서 있을 땐 키가 크고, 쓰러지면 옆으로 길다
    assert first[3] - first[1] > first[2] - first[0]
    assert lying[2] - lying[0] > 2 * (lying[3] - lying[1])
    assert frames[loop_from][0].getbbox() != frames[loop_from + 1][0].getbbox() or         frames[loop_from][0].tobytes() != frames[loop_from + 1][0].tobytes()   # 별이 돈다
    assert loop_from == pack.FALL_STEPS + len(pack.FALL_BOUNCE)   # 되감으면 누운 채로만 돈다


def test_moving_image_ignores_effect(tmp_path):
    p = moving(str(tmp_path / "m.webp"))
    frames, loop_from = pack.clip_frames(pack.Clip(p, [p], "빙글", 3))
    assert len(frames) == 3 and loop_from == 0


def test_group_clip_frames(tmp_path):
    a = blob(str(tmp_path / "a.png"), (255, 0, 0, 255))
    b = blob(str(tmp_path / "b.png"), (0, 0, 255, 255), size=(60, 20))   # 크기가 달라도 맞춘다
    frames, _ = pack.clip_frames(pack.Clip("g", [a, b], "없음", 2, 0.25))
    assert [ms for _, ms in frames] == [250, 250]
    assert len({f.size for f, _ in frames}) == 1
    fx, _ = pack.clip_frames(pack.Clip("g", [a, b], "통통", 2, 0.25))
    assert len(fx) * pack.FX_FRAMES["통통"][1] >= 2 * 250   # 두 장을 다 돌 만큼 효과를 되풀이


# ------------------------------------------------ 동작별 한도
def test_limits_per_kind():
    assert all(pack.limit(m) == 2 for m in ("놀람", "눌림", "기절", "끌림"))
    assert all(pack.limit(m) == 4 for m in ("허둥", "잠", "축하", "자리비움"))
    assert all(pack.limit(m) == 16 for m in ("서기", "걷기", "인사", "딴짓"))
    assert set(pack.LIMITS) == set(pack.MOTIONS)


def test_room_left_counts_groups_as_one(tmp_path):
    root = str(tmp_path)
    for n in ("a.png", "b.png", "c.png"):
        blob(os.path.join(root, CHAR, "놀람", n))
    assert pack.room_left(CHAR, "놀람", root) == 0      # 셋 > 2: 꽉 참 (넘친 것은 안 튼다)
    assert len(pack.candidates(CHAR, "놀람", root)) == 2
    put_meta(root, "놀람", {"이어 붙이기": [{"그림": ["a.png", "b.png", "c.png"]}]})
    assert len(pack.all_candidates(CHAR, "놀람", root)) == 1
    assert pack.room_left(CHAR, "놀람", root) == 1
    pack.add_file(CHAR, "놀람", blob(str(tmp_path / "x" / "new.png")), root)
    assert pack.room_left(CHAR, "놀람", root) == 0
    with pytest.raises(ValueError):
        pack.add_file(CHAR, "놀람", str(tmp_path / "x" / "new.png"), root)


def test_avoid_recent(tmp_path):
    root = str(tmp_path)
    for i in range(6):
        blob(os.path.join(root, CHAR, "딴짓", f"{i}.png"))
    keys = [c.key for c in pack.candidates(CHAR, "딴짓", root)]
    for _ in range(40):
        got = pack.pick_clip(CHAR, "딴짓", root, avoid=keys[:5])
        assert got.key == keys[5]
    assert pack.pick_clip(CHAR, "딴짓", root, avoid=keys).key in keys   # 다 피하면 아무거나


# ------------------------------------------------ 지우면 움직임.json 도 정리
def test_delete_cleans_meta(tmp_path):
    root = str(tmp_path)
    for n in ("a.png", "b.png", "c.png"):
        blob(os.path.join(root, CHAR, "서기", n))
    put_meta(root, "서기", {"그림": {"a.png": {"효과": "떨기"}},
                          "이어 붙이기": [{"이름": "둘", "그림": ["a.png", "b.png"]},
                                     {"이름": "하나", "그림": ["c.png"]}]})
    pack.delete_clip(os.path.join(root, CHAR, "서기", "a.png"), root)
    meta = pack.motion_meta(CHAR, "서기", root)
    assert "a.png" not in meta["그림"]
    assert [g["그림"] for g in meta["이어 붙이기"]] == [["b.png"], ["c.png"]]
    # 묶음 「하나」 지우기: 그 묶음만 쓰던 c.png 도 지운다
    clip = next(c for c in pack.all_candidates(CHAR, "서기", root) if c.key.endswith("하나"))
    pack.delete_candidate(clip, root)
    assert not os.path.exists(os.path.join(root, CHAR, "서기", "c.png"))
    clip = next(c for c in pack.all_candidates(CHAR, "서기", root) if "|" in c.key)
    pack.delete_candidate(clip, root)
    assert pack.clips(CHAR, "서기", root) == []
    assert not os.path.exists(os.path.join(root, CHAR, "서기", pack.META))   # 비면 파일째 없앤다


# ------------------------------------------------ 팩 내보내기·넣기에 같이 오간다
def test_pack_roundtrip_keeps_meta(tmp_path):
    a, b = str(tmp_path / "a"), str(tmp_path / "b")
    for n in ("a.png", "b.png"):
        blob(os.path.join(a, CHAR, "서기", n))
    put_meta(a, "서기", {"그림": {"a.png": {"효과": "흔들", "세기": 1}},
                       "이어 붙이기": [{"이름": "이음", "그림": ["a.png", "b.png"], "간격": 0.5}]})
    dest = pack.export_pack(CHAR, str(tmp_path / ("x" + pack.PACK_SUFFIX)), a)
    with zipfile.ZipFile(dest) as z:
        assert f"{CHAR}/서기/{pack.META}" in z.namelist()
    got = pack.import_pack(dest, b)
    assert pack.motion_meta(got, "서기", b) == pack.motion_meta(CHAR, "서기", a)
    assert names(pack.candidates(got, "서기", b)) == names(pack.candidates(CHAR, "서기", a))


def _zip(path, entries):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(pack.PACK_MANIFEST, json.dumps({"형식": 1, "캐릭터": "팩"}))
        for name, data in entries:
            z.writestr(name, data)
    return path


def _png_bytes():
    import io

    buf = io.BytesIO()
    Image.new("RGBA", (4, 4), (1, 2, 3, 255)).save(buf, "PNG")
    return buf.getvalue()


def test_import_counts_candidates_with_meta(tmp_path):
    files = [(f"팩/놀람/{i}.png", _png_bytes()) for i in range(5)]
    bad = _zip(str(tmp_path / "bad.zip"), files)
    with pytest.raises(pack.PackError, match="놀람"):
        pack.import_pack(bad, str(tmp_path / "r1"))      # 다섯 장 = 후보 다섯 > 2
    meta = {"이어 붙이기": [{"그림": [f"{i}.png" for i in range(5)]}]}
    ok = _zip(str(tmp_path / "ok.zip"), files + [(f"팩/놀람/{pack.META}", json.dumps(meta))])
    got = pack.import_pack(ok, str(tmp_path / "r2"))      # 묶음 하나 = 후보 하나
    assert len(pack.candidates(got, "놀람", str(tmp_path / "r2"))) == 1


def test_import_rejects_broken_meta(tmp_path):
    z = _zip(str(tmp_path / "z.zip"), [("팩/서기/a.png", _png_bytes()), (f"팩/서기/{pack.META}", "{깨짐")])
    with pytest.raises(pack.PackError, match="움직임"):
        pack.import_pack(z, str(tmp_path / "r"))
    assert not os.path.exists(str(tmp_path / "r" / "팩"))


def test_import_trims_meta_names(tmp_path):
    meta = {"그림": {"a.png": {"효과": "떨기"}, "없는.png": {"효과": "통통"}}}
    z = _zip(str(tmp_path / "z.zip"), [("팩/서기/a.png", _png_bytes()),
                                     (f"팩/서기/{pack.META}", json.dumps(meta)),
                                     (f"팩/잠/{pack.META}", json.dumps(meta))])  # 그림 없는 동작의 것은 버린다
    root = str(tmp_path / "r")
    got = pack.import_pack(z, root)
    assert list(pack.motion_meta(got, "서기", root)["그림"]) == ["a.png"]
    assert not os.path.exists(os.path.join(root, got, "잠", pack.META))
