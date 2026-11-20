"""캐릭터팩 만들기 창의 「폴더에서 고르기」·효과 고르기·움직이는 미리보기 시험(11-20 셋째).

그림은 임시 폴더에 코드로 그린다(사용자 팩은 안 읽는다). tk 창은 띄우지 않는다(withdraw).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PC = os.path.dirname(HERE)
sys.path.insert(0, PC)
sys.path.insert(0, os.path.join(PC, "windows"))

import tkinter as tk  # noqa: E402

import pytest  # noqa: E402
from PIL import Image  # noqa: E402

import cooldown_pack as pack  # noqa: E402
import cooldown_pack_import as imp  # noqa: E402
from skins.base import set_palette  # noqa: E402

CHAR = "시험떡"


def _pic(path, color, frames=1, size=(30, 36)):
    out = []
    for i in range(frames):
        im = Image.new("RGBA", size, (0, 0, 0, 0))
        for x in range(4, size[0] - 4):
            for y in range(4 + i * 2, size[1]):
                im.putpixel((x, y), color)
        out.append(im)
    if frames > 1:
        out[0].save(path, save_all=True, append_images=out[1:], duration=120, loop=0)
    else:
        out[0].save(path)
    return path


@pytest.fixture
def src(tmp_path):
    folder = tmp_path / "그림"
    folder.mkdir()
    for i, c in enumerate(((250, 80, 80, 255), (80, 200, 80, 255), (80, 80, 250, 255))):
        _pic(str(folder / f"고정{i + 1}.png"), c)
    _pic(str(folder / "움직임.gif"), (200, 160, 40, 255), frames=4)
    (folder / "메모.txt").write_text("그림 아님", encoding="utf-8")
    return str(folder)


@pytest.fixture
def root(tmp_path):
    r = str(tmp_path / "pack")
    pack.add_character(CHAR, r)
    return r


@pytest.fixture
def tkroot():
    r = tk.Tk()
    r.withdraw()
    set_palette("dark")
    yield r
    r.destroy()


def _meta(root, motion):
    with open(os.path.join(root, CHAR, motion, pack.META), encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------------ 팩 함수
def test_folder_pictures_and_moving(src):
    names = [os.path.basename(p) for p in pack.folder_pictures(src)]
    assert names == ["고정1.png", "고정2.png", "고정3.png", "움직임.gif"]   # 그림 아닌 것은 빠짐
    assert pack.is_moving(os.path.join(src, "움직임.gif"))
    assert not pack.is_moving(os.path.join(src, "고정1.png"))
    assert pack.folder_pictures(os.path.join(src, "없는 폴더")) == []


def test_add_file_writes_effect_and_set_clip_fx(src, root):
    path = pack.add_file(CHAR, "서기", os.path.join(src, "고정1.png"), root, effect="빙글", power=3)
    name = os.path.basename(path)
    assert _meta(root, "서기")["그림"][name] == {"효과": "빙글", "세기": 3}
    clip = pack.all_candidates(CHAR, "서기", root)[0]
    assert clip.effect == "빙글" and clip.power == 3
    assert pack.set_clip_fx(clip, "통통", 1, root)
    assert pack.all_candidates(CHAR, "서기", root)[0][2:4] == ("통통", 1)
    assert not pack.set_clip_fx(clip, "없는효과", 1, root)                    # 틀린 값은 안 적음
    outside = pack.Clip(os.path.join(src, "고정2.png"), [os.path.join(src, "고정2.png")])
    assert not pack.set_clip_fx(outside, "통통", 1, root)                     # 팩 밖은 안 건드림
    assert not os.path.exists(os.path.join(src, pack.META))


def test_set_clip_fx_on_group(src, root):
    a = pack.add_file(CHAR, "인사", os.path.join(src, "고정1.png"), root)
    b = pack.add_file(CHAR, "인사", os.path.join(src, "고정2.png"), root)
    names = [os.path.basename(a), os.path.basename(b)]
    pack.write_meta(CHAR, "인사", {"이어 붙이기": [{"이름": "손", "그림": names, "간격": 0.2}]}, root)
    group = [c for c in pack.all_candidates(CHAR, "인사", root) if len(c.files) > 1][0]
    assert pack.set_clip_fx(group, "흔들", 3, root)
    g = _meta(root, "인사")["이어 붙이기"][0]
    assert (g["효과"], g["세기"], g["그림"]) == ("흔들", 3, names)


def test_used_pictures_by_content(src, root):
    pack.add_file(CHAR, "딴짓", os.path.join(src, "고정2.png"), root)
    used = pack.used_pictures(CHAR, root)
    assert used == {pack.file_digest(os.path.join(src, "고정2.png")): "딴짓"}  # 이름이 바뀌어도 알아봄


# ------------------------------------------------------------------ 창
def test_folder_pick_adds_one_marks_used_and_keeps_limit(tkroot, src, root):
    win = imp.PackImport(tkroot, root=root)
    win.char = CHAR
    win._from_folder("놀람", src)                     # 놀람 한도 2
    pick = win.picker
    one = os.path.join(src, "고정1.png")
    pick._select(one)
    pick._set_fx("떨기", 3)
    pick._add(one)
    got = pack.all_candidates(CHAR, "놀람", root)
    assert len(got) == 1 and got[0][2:4] == ("떨기", 3)
    pick._add(one)                                    # 같은 그림은 겹쳐 넣지 않음
    assert len(pack.all_candidates(CHAR, "놀람", root)) == 1
    pick._add(os.path.join(src, "움직임.gif"))        # 움직이는 그림은 효과를 안 적음
    assert len(pack.all_candidates(CHAR, "놀람", root)) == 2
    assert all(n.endswith(".png") for n in _meta(root, "놀람")["그림"])
    pick._add(os.path.join(src, "고정3.png"))         # 한도(2)를 넘지 않음
    assert len(pack.clips(CHAR, "놀람", root)) == 2
    pick._render()
    texts = [w.cget("text") for w in _all(pick.top) if isinstance(w, tk.Label)]
    assert "놀람에 있음" in texts                      # 이미 넣은 그림 표시
    assert not any("넣기" in t for t in texts)          # 묶음째 넣는 단추 같은 것 없음(한 장씩), 꽉 차면 넣기 단추 없음
    win.close()
    assert win.picker is None and not win.anim.items


def test_viewer_effect_writes_meta(tkroot, src, root):
    pack.add_file(CHAR, "서기", os.path.join(src, "고정1.png"), root)
    win = imp.PackImport(tkroot, root=root)
    win.char = CHAR
    clip = pack.all_candidates(CHAR, "서기", root)[0]
    win._select(clip)
    assert win._selected()[1] == clip
    win._set_fx(clip, "쭈그러짐", 1)
    assert pack.all_candidates(CHAR, "서기", root)[0][2:4] == ("쭈그러짐", 1)
    assert win._selected() is not None                 # 효과를 바꿔도 같은 그림이 그대로 크게 보임
    win.close()


def test_preview_frames_match_bar_and_animate(tkroot, src, root):
    pack.add_file(CHAR, "걷기", os.path.join(src, "고정1.png"), root, effect="통통", power=2)
    clip = pack.all_candidates(CHAR, "걷기", root)[0]
    win = imp.PackImport(tkroot, root=root)
    frames, loop_from = win.shelf.bake(clip, imp.BAR_H)
    bar, bar_loop = pack.load_clip(clip, imp.BAR_H, imp.bar_width(clip, imp.BAR_H))
    assert len(frames) == len(bar) > 1 and loop_from == bar_loop       # 바와 같은 장면
    assert [ms for _, ms in frames] == [ms for _, ms in bar]
    assert frames[0][0].height() == bar[0][0].height
    lab = tk.Label(win.win)
    win.anim.show(lab, frames, loop_from)
    assert win.anim.frame_of(lab) == 0
    win.anim.items[str(lab)][4] = 0                     # 이 장면 시간이 다 됨
    win.anim._tick()
    assert win.anim.frame_of(lab) == 1 and lab.cget("image") == str(frames[1][0])
    assert len([k for k in (win.anim._job,) if k]) == 1  # 타이머 하나
    win.close()
    assert win.anim._job is None and not win.anim.items


def test_shelf_bakes_once(tkroot, src, root):
    pack.add_file(CHAR, "서기", os.path.join(src, "고정1.png"), root)
    clip = pack.all_candidates(CHAR, "서기", root)[0]
    win = imp.PackImport(tkroot, root=root)
    calls = []
    real = win.shelf.bake
    win.shelf.bake = lambda *a: calls.append(a) or real(*a)
    labs = [tk.Label(win.win) for _ in range(3)]
    for lab in labs:
        win.shelf.get(clip, 30, lab, lambda f, lf, w=lab: win.anim.show(w, f, lf))
    while win.shelf.queue:
        win.shelf._work()
    assert len([a for a in calls if a[1] == 30]) == 1 and all(lab.cget("image") for lab in labs)
    win.close()


def _all(w):
    out = [w]
    for c in w.winfo_children():
        out += _all(c)
    return out
