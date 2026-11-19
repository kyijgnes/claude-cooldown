"""캐릭터팩 기본값·내보내기·넣기(`cooldown_pack`) 시험. 화면·tk 없이 돈다. 사용자 팩은 안 건드린다."""
import json
import os
import sys
import zipfile

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cooldown_pack as pack  # noqa: E402
from PIL import Image  # noqa: E402


def _png(path, color=(200, 80, 80, 255), size=(20, 24)):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.new("RGBA", size, color).save(path)


def _char(root, name="솜구름", motions=("서기", "걷기", "잠"), per=2):
    for i, m in enumerate(motions):
        for j in range(per):
            _png(os.path.join(root, name, m, f"{j}.png"), (10 * i, 20 * j, 90, 255))
    pack.set_char_setting(name, "보는 쪽", "왼쪽", root)
    return name


def _tree(root):
    """팩 폴더의 (상대 경로 → 내용) 전부."""
    out = {}
    for dp, _dn, fn in os.walk(root):
        for f in fn:
            p = os.path.join(dp, f)
            with open(p, "rb") as fh:
                out[os.path.relpath(p, root)] = fh.read()
    return out


def _zip(path, entries, manifest=None):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(pack.PACK_MANIFEST, json.dumps(manifest or {"형식": 1, "캐릭터": "나쁜"}))
        for name, data in entries:
            z.writestr(name, data)
    return path


def _png_bytes():
    import io

    buf = io.BytesIO()
    Image.new("RGBA", (4, 4), (1, 2, 3, 255)).save(buf, "PNG")
    return buf.getvalue()


# ------------------------------------------------ ① 기본값 클로디
def test_empty_pack_is_claudi(tmp_path):
    assert pack.active(str(tmp_path)) is None
    assert pack.active(str(tmp_path / "없는 폴더")) is None


def test_chars_but_never_chosen_is_claudi(tmp_path):
    root = str(tmp_path)
    _char(root)
    assert pack.characters(root) == ["솜구름"]
    assert pack.active(root) is None


def test_chosen_char_stands_and_gone_char_falls_back(tmp_path):
    root = str(tmp_path)
    _char(root)
    pack.set_active("솜구름", root)
    assert pack.active(root) == "솜구름"
    pack.remove_character("솜구름", root)
    assert pack.active(root) is None
    pack.set_active(None, root)
    assert pack.active(root) is None


def test_import_does_not_change_active(tmp_path):
    a, b = str(tmp_path / "a"), str(tmp_path / "b")
    _char(a)
    f = pack.export_pack("솜구름", str(tmp_path / ("솜구름" + pack.PACK_SUFFIX)), a)
    pack.import_pack(f, b)
    assert pack.active(b) is None


# ------------------------------------------------ ② 내보내고 넣으면 같다
def test_export_import_roundtrip(tmp_path):
    a, b = str(tmp_path / "a"), str(tmp_path / "b")
    _char(a)
    dest = str(tmp_path / ("솜구름" + pack.PACK_SUFFIX))
    pack.export_pack("솜구름", dest, a)
    assert zipfile.is_zipfile(dest)
    with zipfile.ZipFile(dest) as z:
        meta = json.loads(z.read(pack.PACK_MANIFEST))
    assert meta == {"형식": pack.PACK_FORMAT, "캐릭터": "솜구름"}
    assert pack.import_pack(dest, b) == "솜구름"
    assert _tree(a) == _tree(b)
    assert not pack.faces_right("솜구름", b)
    for m in pack.MOTIONS:
        assert [os.path.basename(p) for p in pack.clips("솜구름", m, a)] == \
               [os.path.basename(p) for p in pack.clips("솜구름", m, b)]


def test_same_name_gets_number(tmp_path):
    a = str(tmp_path / "a")
    _char(a)
    dest = str(tmp_path / ("솜구름" + pack.PACK_SUFFIX))
    pack.export_pack("솜구름", dest, a)
    assert pack.import_pack(dest, a) == "솜구름 (2)"
    assert pack.import_pack(dest, a) == "솜구름 (3)"
    assert pack.all_characters(a) == ["솜구름", "솜구름 (2)", "솜구름 (3)"]


def test_export_needs_pictures(tmp_path):
    root = str(tmp_path)
    pack.add_character("빈칸", root)
    with pytest.raises(pack.PackError):
        pack.export_pack("빈칸", str(tmp_path / "x.zip"), root)


# ------------------------------------------------ ③ 나쁜 zip 은 거절, 팩 폴더는 그대로
BAD = {
    "dotdot": [("../../밖.png", _png_bytes())],
    "dotdot_mid": [("나쁜/서기/../../../밖.png", _png_bytes())],
    "absolute": [("/abs/서기/a.png", _png_bytes())],
    "drive": [("C:/Windows/서기/a.png", _png_bytes())],
    "backslash": [("..\\..\\밖.png", _png_bytes())],
    "exe": [("나쁜/서기/a.exe", b"MZ")],
    "not_image": [("나쁜/서기/a.png", b"just text")],
    "too_many": [(f"나쁜/서기/{i}.png", _png_bytes()) for i in range(pack.MAX_PER_MOTION + 1)],
    "too_deep": [("나쁜/서기/더/a.png", _png_bytes())],
    "empty": [],
}


@pytest.mark.parametrize("kind", sorted(BAD))
def test_bad_zip_rejected_and_clean(tmp_path, kind):
    root = str(tmp_path / "pack")
    _char(root)
    before = _tree(root)
    f = _zip(str(tmp_path / "bad.zip"), BAD[kind])
    with pytest.raises(pack.PackError):
        pack.import_pack(f, root)
    assert _tree(root) == before
    assert os.listdir(root) == ["솜구름"]  # 임시 폴더(`_넣는 중…`)도 안 남는다
    assert not os.path.exists(str(tmp_path / "밖.png"))


def test_big_clip_rejected(tmp_path, monkeypatch):
    root = str(tmp_path / "pack")
    monkeypatch.setattr(pack, "PACK_MAX_CLIP", 100)
    f = _zip(str(tmp_path / "big.zip"), [("나쁜/서기/a.png", _png_bytes() + b"\0" * 500)])
    with pytest.raises(pack.PackError):
        pack.import_pack(f, root)
    assert not os.path.exists(root) or os.listdir(root) == []


def test_big_file_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(pack, "PACK_MAX_FILE", 10)
    f = _zip(str(tmp_path / "big.zip"), [("나쁜/서기/a.png", _png_bytes())])
    with pytest.raises(pack.PackError):
        pack.import_pack(f, str(tmp_path / "pack"))


def test_not_a_zip_and_no_manifest(tmp_path):
    p = tmp_path / "x.zip"
    p.write_bytes(b"nope")
    with pytest.raises(pack.PackError):
        pack.import_pack(str(p), str(tmp_path / "pack"))
    q = str(tmp_path / "plain.zip")
    with zipfile.ZipFile(q, "w") as z:
        z.writestr("a/서기/a.png", _png_bytes())
    with pytest.raises(pack.PackError):
        pack.import_pack(q, str(tmp_path / "pack"))


def test_newer_format_rejected(tmp_path):
    f = _zip(str(tmp_path / "new.zip"), [("나쁜/서기/a.png", _png_bytes())],
             manifest={"형식": pack.PACK_FORMAT + 1, "캐릭터": "새것"})
    with pytest.raises(pack.PackError):
        pack.import_pack(f, str(tmp_path / "pack"))


def test_char_limit(tmp_path):
    root = str(tmp_path / "pack")
    for i in range(pack.MAX_CHARS):
        _char(root, f"c{i}", motions=("서기",), per=1)
    before = _tree(root)
    f = _zip(str(tmp_path / "ok.zip"), [("나쁜/서기/a.png", _png_bytes())])
    with pytest.raises(pack.PackError):
        pack.import_pack(f, root)
    assert _tree(root) == before


def test_unknown_motion_skipped_and_explorer_junk_ok(tmp_path):
    root = str(tmp_path / "pack")
    f = _zip(str(tmp_path / "ok.zip"), [("나쁜/서기/a.png", _png_bytes()),
                                        ("나쁜/새동작/b.png", _png_bytes()),
                                        ("나쁜/서기/Thumbs.db", b"x")])
    assert pack.import_pack(f, root) == "나쁜"
    assert [os.path.basename(p) for p in pack.clips("나쁜", "서기", root)] == ["a.png"]
    assert not os.path.exists(os.path.join(root, "나쁜", "새동작"))
