"""폰으로 보낼 캐릭터팩(`cooldown_pack_export`) 시험. 화면·tk 없이 돈다. 사용자 팩은 안 건드린다."""
import io
import json
import os
import sys
import zipfile

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cooldown_pack as pack  # noqa: E402
import cooldown_pack_export as ex  # noqa: E402
from PIL import Image  # noqa: E402


def _png(path, color=(200, 80, 80, 255), size=(20, 24)):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.new("RGBA", size, color).save(path)


def _anim(path, durations=(120, 40, 300)):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    frames = [Image.new("RGBA", (30, 30), (40 * i, 90, 160, 255)) for i in range(len(durations))]
    frames[0].save(path, "WEBP", save_all=True, append_images=frames[1:], duration=list(durations),
                   loop=0, lossless=True)


def _read(path):
    z = zipfile.ZipFile(path)
    return z, json.loads(z.read(ex.MANIFEST).decode("utf-8"))


@pytest.fixture
def root(tmp_path):
    r = str(tmp_path / "팩")
    _png(os.path.join(r, "떡", "서기", "a.png"))
    _anim(os.path.join(r, "떡", "놀람", "b.webp"))
    pack._write_json(os.path.join(r, "떡", "설정.json"), {"보는 쪽": "왼쪽"})
    _png(os.path.join(r, "구름", "서기", "a.png"), (10, 200, 10, 255))
    pack.set_active("구름", r)
    return r


def test_exports_every_character_with_phone_motions(root, tmp_path):
    dest = ex.export(str(tmp_path / ("x" + ex.SUFFIX)), root=root)
    z, m = _read(dest)
    assert m["형식"] == ex.FORMAT and m["바 캐릭터"] == "구름"
    names = [c["이름"] for c in m["캐릭터"]]
    assert sorted(names) == ["구름", "떡"]
    ddeok = next(c for c in m["캐릭터"] if c["이름"] == "떡")
    assert ddeok["보는 쪽"] == "왼쪽"
    # 빈 동작도 빌려 와서 폰이 쓰는 동작이 다 찬다 (PC 가 모르는 이름은 안 담는다)
    assert set(ddeok["동작"]) == set(ex.motions())
    assert set(ex.motions()) <= set(pack.MOTIONS)


def test_sheet_matches_info_and_keeps_frame_lengths(root, tmp_path):
    dest = ex.export(str(tmp_path / "x.zip"), ["떡"], root=root)
    z, m = _read(dest)
    surprise = m["캐릭터"][0]["동작"]["놀람"][0]
    assert surprise["ms"] == [120, 40, 300]  # 움직이는 그림은 장면 길이 그대로
    with Image.open(io.BytesIO(z.read(surprise["그림"]))) as im:
        rows = -(-len(surprise["ms"]) // surprise["열"])
        assert im.size == (surprise["폭"] * surprise["열"], surprise["높이"] * rows)
    assert surprise["높이"] == ex.HEIGHT


def test_still_picture_gets_pc_effect(root, tmp_path):
    """고정 그림은 PC 와 같은 효과로 구워진다 (기절은 서기를 빌려 헤롱)."""
    dest = ex.export(str(tmp_path / "x.zip"), ["떡"], root=root)
    _z, m = _read(dest)
    table = m["캐릭터"][0]["동작"]
    assert len(table["서기"][0]["ms"]) == pack.fx_count("숨쉬기")
    assert len(table["기절"][0]["ms"]) == pack.fx_count("헤롱")


def test_same_picture_stored_once(root, tmp_path):
    dest = ex.export(str(tmp_path / "x.zip"), ["떡"], root=root)
    z, m = _read(dest)
    used = {e["그림"] for c in m["캐릭터"] for v in c["동작"].values() for e in v}
    pics = [n for n in z.namelist() if n != ex.MANIFEST]
    assert sorted(used) == sorted(pics)
    assert len(pics) < sum(len(v) for v in m["캐릭터"][0]["동작"].values())  # 빌린 것은 겹친다
    assert all(n.startswith("c0/") and n.isascii() for n in pics)


def test_only_chosen_and_errors(root, tmp_path):
    dest = ex.export(str(tmp_path / "x.zip"), ["구름", "없는애"], root=root)
    _z, m = _read(dest)
    assert [c["이름"] for c in m["캐릭터"]] == ["구름"]
    with pytest.raises(ex.ExportError):
        ex.export(str(tmp_path / "y.zip"), ["없는애"], root=root)
    with pytest.raises(ex.ExportError):
        ex.export(str(tmp_path / "z.zip"), root=str(tmp_path / "빈 팩"))
    assert not os.path.exists(str(tmp_path / "y.zip"))


def test_default_name(root):
    assert ex.default_name(["떡"], root) == "떡" + ex.SUFFIX
    assert ex.default_name(None, root) == "캐릭터 전부" + ex.SUFFIX


def test_user_pack_untouched(root, tmp_path):
    before = {p: os.path.getmtime(os.path.join(dp, p)) for dp, _d, fs in os.walk(root) for p in fs}
    ex.export(str(tmp_path / "x.zip"), root=root)
    after = {p: os.path.getmtime(os.path.join(dp, p)) for dp, _d, fs in os.walk(root) for p in fs}
    assert before == after
