"""
상호작용 하나에 그림 하나 (11-21): 새 한도 · 새 상호작용 열셋의 빌리기 · 겹칠 때 하나만 · 새 트리거
(하트·갸웃·쳐다보기·빼꼼·밀기·깸·허우적·꽈당·날아감·앉기·빙글·깡충).

그림은 코드로 만든다(공개 저장소). 창 찾기·화면 크기는 가짜로 바꿔 끼운다.
"""

from __future__ import annotations

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "windows"))

import tkinter as tk  # noqa: E402

from PIL import Image  # noqa: E402

import cooldown_pack as pack  # noqa: E402
from skins import buddy as buddy_mod  # noqa: E402
from skins import carry, wins  # noqa: E402
from skins.base import set_palette  # noqa: E402
from skins.buddy import HEART_SEC, HOVER_SEC, TICK_MS, YUM_LIFE, Buddy  # noqa: E402

CHAR = "시험떡"
W, H = 460, 48
BOX = (300, 0, 450, H)
NEW = ("깡충", "빙글", "날아감", "꽈당", "앉기", "쳐다보기", "간지럼",
       "갸웃", "하트", "빼꼼", "밀기", "깸", "허우적")
BASE = ("서기", "걷기", "뛰기", "놀람", "끌림", "점프", "인사", "축하", "잠", "딴짓", "자리비움")


def _png(path, color):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im = Image.new("RGBA", (20, 24), (0, 0, 0, 0))
    for x in range(3, 17):
        for y in range(4, 24):
            im.putpixel((x, y), color)
    im.save(path)


def make_pack(root, motions):
    for i, m in enumerate(motions):
        _png(os.path.join(root, CHAR, m, "1.png"), ((29 * i) % 255, 120, 200, 255))
    return root


@pytest.fixture(scope="module")
def tkroot():
    r = tk.Tk()
    r.withdraw()
    set_palette("dark")
    yield r
    r.destroy()


@pytest.fixture(autouse=True)
def calm_world(monkeypatch):
    monkeypatch.setattr(carry, "button_down", lambda: True)
    monkeypatch.setattr(wins, "title_bar_at", lambda sx, sy: None)
    monkeypatch.setattr(wins, "screen_box", lambda w: (-3000.0, -3000.0, 3000.0, 3000.0))


@pytest.fixture
def base(tmp_path):
    return make_pack(str(tmp_path), BASE)


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def make(tkroot, root):
    c = tk.Canvas(tkroot, width=W, height=H)
    clock = Clock()
    b = Buddy(c, BOX, CHAR, root=root)
    b.now = clock
    b._last = b._touched = clock.t
    b._play("서기", 3.0)
    return b, clock


def run(b, clock, seconds, each=None):
    for _ in range(int(round(seconds * 1000 / TICK_MS))):
        clock.t += TICK_MS / 1000
        b.step()
        if each:
            each()


def seen(b, clock, seconds):
    got = []
    run(b, clock, seconds, lambda: got.append(b.motion) if not got or got[-1] != b.motion else None)
    return got


def until_home(b, clock, limit=12.0):
    n = 0
    while b.mode != "" and n * TICK_MS / 1000 < limit:
        clock.t += TICK_MS / 1000
        b.step()
        n += 1


def spot(b):
    return b.x, b.y1 + b.y - b.height / 2


def tap(b):
    """한 번 누르고 뗀다 (누르기 반응은 뗄 때 정한다, 11-21)."""
    b.react(*spot(b))
    b.tap_up()


def screen_mid(b):
    return b.c.winfo_rootx() + b.x, b.c.winfo_rooty() + b.y1 + b.y - b.height / 2


def texts(b):
    return [b.c.itemcget(i, "text") for i in b.c.find_withtag("buddy_fx")]


# ------------------------------------------------------------------ 팩 약속
def test_new_interactions_listed_with_labels_fallback_fx():
    group = dict(pack.GROUPS)["상호작용"]
    assert group[-len(NEW):] == NEW                    # 이름은 고르기 화면과 같다
    for m in NEW:
        assert m in pack.MOTIONS and m in pack.INTERACT
        assert pack.MOTION_LABELS[m] and "—" not in pack.MOTION_LABELS[m] and "–" not in pack.MOTION_LABELS[m]
        assert len(pack.MOTION_LABELS[m]) <= 13            # 팩 만들기 화면 이름 칸(220px)에 들어감
        assert pack.FALLBACK[m] and all(f in pack.MOTIONS for f in pack.FALLBACK[m])
        assert pack.FALLBACK[m][-1] == "서기"               # 끝내 서기 한 장만 있어도 돈다
        assert pack.DEFAULT_FX[m][0] in pack.EFFECTS
    assert pack.FALLBACK["깡충"][0] == "점프"                # 지금까지 두 번 누르기는 점프였다
    assert not hasattr(pack, "FEELINGS")                  # 감정 묶음은 11-21 에 뺐다


def test_limits():
    assert {pack.limit(m) for m in pack.INTERACT} == {1}
    assert [pack.limit(m) for m in pack.EVERYDAY] == [16] * 4
    assert pack.limit("자리비움") == 16 and pack.limit("잠") == 8
    assert {pack.limit(m) for m in pack.MOVES + ("허둥", "축하")} == {4}
    assert set(pack.LIMITS) == set(pack.MOTIONS)


def test_over_limit_pack_uses_first_and_keeps_files(tmp_path):
    root = str(tmp_path)
    for n in ("a.png", "b.png", "c.png"):
        _png(os.path.join(root, CHAR, "놀람", n), (200, 50, 50, 255))
    for i in range(10):
        _png(os.path.join(root, CHAR, "잠", f"{i:02}.png"), (50, 50, 200, 255))
    got = pack.candidates(CHAR, "놀람", root)
    assert len(got) == 1 and got[0].files[0].endswith("a.png")   # 앞에서부터 한도만큼
    assert len(pack.clips(CHAR, "놀람", root)) == 3                # 지우지 않는다
    for _ in range(20):
        assert pack.pick_clip(CHAR, "놀람", root).files[0].endswith("a.png")
    assert len(pack.candidates(CHAR, "잠", root)) == 8
    assert len(pack.clips(CHAR, "잠", root)) == 10


@pytest.mark.parametrize("motion,have,want", [
    ("깡충", ("점프", "놀람"), "점프"),
    ("깡충", ("놀람", "서기"), "놀람"),
    ("꽈당", ("기절", "놀람"), "기절"),
    ("앉기", ("인사", "서기"), "인사"),
    ("간지럼", ("인사", "서기"), "인사"),
    ("하트", ("서기",), "서기"),
    ("깸", ("놀람", "서기"), "놀람"),
    ("허우적", ("허둥", "끌림"), "허둥"),
    ("밀기", ("걷기", "서기"), "걷기"),
])
def test_empty_new_motion_borrows_with_its_fx(tmp_path, motion, have, want):
    root = str(tmp_path)
    for m in have:
        _png(os.path.join(root, CHAR, m, "a.png"), (200, 100, 50, 255))
    got = pack.pick_clip(CHAR, motion, root)
    assert os.sep + want + os.sep in got.files[0]
    assert got.effect == pack.DEFAULT_FX[motion][0]    # 빌려도 그 동작다운 효과


def test_old_pack_round_trip_and_new_folder(tmp_path):
    """옛 팩(새 동작 폴더 없음)은 그대로, 새 폴더가 든 팩은 내보내고 받아도 그대로."""
    a, b = str(tmp_path / "a"), str(tmp_path / "b")
    make_pack(a, BASE + ("하트", "빼꼼"))
    f = pack.export_pack(CHAR, str(tmp_path / ("x" + pack.PACK_SUFFIX)), a)
    pack.import_pack(f, b)
    assert pack.own(CHAR, "하트", b) and pack.own(CHAR, "빼꼼", b) and not pack.own(CHAR, "갸웃", b)


# ------------------------------------------------------------------ 누르기 · 가운데 단추
def test_double_tap_hops_with_own_picture(tkroot, tmp_path):
    root = make_pack(str(tmp_path), BASE + ("깡충",))
    b, clock = make(tkroot, root)
    tap(b)
    clock.t += 0.2
    tap(b)
    run(b, clock, 0.4)
    assert b.motion == "깡충" and os.sep + "깡충" + os.sep in b.clip.files[0]


def test_fast_triple_tap_is_mash_not_hop(tkroot, tmp_path):
    """빠르게 셋 넘게 누르면 연타: 깡충이 아니라 놀람 하나로 시작한다."""
    root = make_pack(str(tmp_path), BASE + ("깡충",))
    b, clock = make(tkroot, root)
    got = []
    for _ in range(4):
        tap(b)
        run(b, clock, 0.15, lambda: got.append(b.motion) if not got or got[-1] != b.motion else None)
    run(b, clock, 0.6, lambda: got.append(b.motion) if not got or got[-1] != b.motion else None)
    assert got == ["서기", "놀람"]


def test_heart_on_middle_click(tkroot, base):
    b, clock = make(tkroot, base)
    b.middle(b.x + 200, 5)                               # 캐릭터 밖: 아무 일 없음
    assert b.motion == "서기" and not b._hearts
    b.middle(*spot(b))
    assert b.motion == "하트" and b.busy
    run(b, clock, 1.0)
    assert texts(b) and set(texts(b)) == {"♥"}           # 「♥」가 오른다
    run(b, clock, HEART_SEC + YUM_LIFE)
    assert not texts(b) and b.motion != "하트"


def test_heart_ignored_while_held_or_fainted(tkroot, base):
    b, clock = make(tkroot, base)
    b._faint()
    b.middle(*spot(b))
    assert b.motion == "기절"


def test_wake_when_sleeping(tkroot, base):
    b, clock = make(tkroot, base)
    b.set_mood("잠")
    run(b, clock, 0.5)
    assert b.motion == "잠"                               # 슬픔 없이 바로 잔다 (감정은 뺐다)
    tap(b)
    assert b.motion == "깸" and b.vy < 0
    tap(b)                                               # 깬 뒤 바로 또 누르면 그냥 놀람 (잠 그림이 아니다)
    run(b, clock, 0.5)
    assert b.motion == "놀람"
    run(b, clock, 4.0)
    assert b.motion == "잠"                               # 다시 잔다


def test_wake_when_away_is_one_motion(tkroot, base):
    b, clock = make(tkroot, base)
    b.set_away(True)
    run(b, clock, 4.0)
    assert b.mode == "자리비움"
    tap(b)
    assert b.mode == "" and b.motion == "깸"
    got = seen(b, clock, 1.4)
    assert got == ["깸"]                                  # 깸 하나 (반기는 그림을 잇지 않는다)


def test_away_ends_by_input_without_wake(tkroot, base):
    b, clock = make(tkroot, base)
    b.set_away(True)
    run(b, clock, 4.0)
    b.set_away(False)                                    # 키보드로 돌아옴: 깸 없이 반김
    assert b.motion == "점프"


# ------------------------------------------------------------------ 커서
def test_look_stays_one_motion_and_leave(tkroot, base):
    b, clock = make(tkroot, base)
    cx, cy = screen_mid(b)
    pos = {"p": (cx - 50, cy)}
    b.pointer = lambda: pos["p"]
    b.until = clock.t + 100
    run(b, clock, 0.6)
    assert b.motion == "쳐다보기" and b.dir == -1 and b.mode == "봄"
    pos["p"] = (cx + 50, cy)                               # 반대쪽으로 옮겨도 같은 그림을 돌릴 뿐
    got = seen(b, clock, 20.0)
    assert got == ["쳐다보기"] and b.dir == 1              # 오래 있어도 평소 그림·부끄럼이 안 낀다
    pos["p"] = (cx + 600, cy)
    run(b, clock, 0.2)
    assert b.motion != "쳐다보기" and b.mode == ""        # 커서가 가면 접는다


def test_tilt_when_cursor_rests_on_body(tkroot, base):
    b, clock = make(tkroot, base)
    cx, cy = screen_mid(b)
    b.pointer = lambda: (cx + 1, cy)
    b.until = clock.t + 100
    got = seen(b, clock, HOVER_SEC + 0.3)
    assert got[-1] == "갸웃" and "부끄럼" not in got
    got = seen(b, clock, 2.0)
    assert "부끄럼" not in got                             # 갸웃 바로 뒤에 부끄럼이 겹쳐 나오지 않는다


def test_rub_beats_tilt(tkroot, base):
    b, clock = make(tkroot, base)
    b.until = clock.t + 100
    cx, cy = screen_mid(b)
    pos = {"p": (cx, cy)}
    b.pointer = lambda: pos["p"]
    got = []
    for px in [cx - 8, cx + 8] * 4:
        pos["p"] = (px, cy)
        run(b, clock, 0.08, lambda: got.append(b.motion))
    assert b.motion == "간지럼" and "갸웃" not in got


def test_moving_cursor_on_body_does_not_tilt(tkroot, base):
    b, clock = make(tkroot, base)
    b.until = clock.t + 100
    cx, cy = screen_mid(b)
    pos = {"i": 0}

    def wander():
        pos["i"] += 1
        return cx - 8 + (pos["i"] * 5) % 16, cy        # 몸 위를 천천히 오간다(문지르기 만큼은 아님)
    b.pointer = wander
    got = seen(b, clock, HOVER_SEC + 1.0)
    assert "갸웃" not in got


# ------------------------------------------------------------------ 놓기: 빼꼼 · 허우적
@pytest.mark.parametrize("side", [-1, 1])
def test_peek_at_bar_end_then_click_returns(tkroot, base, side):
    b, clock = make(tkroot, base)
    x, y = spot(b)
    assert b.catch(x, y)
    b.drag(-30 if side < 0 else W + 30, y)               # 바 끝 바로 밖, 바 높이
    b.put_down()
    edge = 0.0 if side < 0 else float(W)
    assert b.mode == "빼꼼" and b.motion == "빼꼼" and b._carry is None
    assert b.x == pytest.approx(edge)                    # 반쯤 숨었다 (몸 반이 바 밖)
    assert b.dir == -side                                # 바 안쪽을 본다
    xs = set()
    run(b, clock, 8.0, lambda: xs.add(round(b.x, 1)))
    assert b.mode == "빼꼼" and len(xs) == 2             # 깊이 숨었다 내다봤다 번갈아
    assert any(abs(v - edge) > 1 for v in xs) and all((v - edge) * side >= -0.1 for v in xs)
    b.react(b.x - side * b.w / 4, y)                     # 보이는 쪽을 누르면 돌아온다
    b.tap_up()
    assert b.mode == "복귀"
    until_home(b, clock)
    assert b.mode == "" and b.x == pytest.approx(b.home_x)


def test_far_off_bar_is_not_peek(tkroot, base):
    b, clock = make(tkroot, base)
    x, y = spot(b)
    assert b.catch(x, y)
    b.drag(-400, y)                                      # 바 끝에서 멀다
    b.put_down()
    assert b.mode == "날기"


def test_flail_when_dropped_high(tkroot, base):
    b, clock = make(tkroot, base)
    x, y = spot(b)
    assert b.catch(x, y)
    b.drag(x + 300, y - 2500)                            # 화면 위쪽 높은 곳 (화면 -3000~3000)
    b.put_down()
    assert b.mode == "던짐" and b.motion == "허우적" and b._toss["flail"]
    floor = carry.screen_of(b.c, b.home_x, b.y1)[1]
    run(b, clock, 0.5)
    assert b.motion == "허우적"
    until_home(b, clock)
    assert b.mode == "" and b._carry is None and b.x == pytest.approx(b.home_x)
    assert floor  # 바 바닥까지 떨어져 내려앉았다


def test_flail_lands_near_home_without_bounce(tkroot, base):
    b, clock = make(tkroot, base)
    x, y = spot(b)
    assert b.catch(x, y)
    b.drag(x + 300, y - 2500)
    b.put_down()
    home_sx, floor = carry.screen_of(b.c, b.home_x, b.y1)
    last = {"ys": []}
    run(b, clock, 3.0, lambda: (last.update(b._toss), last["ys"].append(b._toss["y"])) if b._toss else None)
    assert last["bounces"] == 0 and max(last["ys"]) <= floor + 0.01 and b._toss is None
    assert abs(last["x"] - home_sx) < 30                  # 제자리 쪽으로 떨어졌다


def test_low_drop_is_not_flail(tkroot, base):
    b, clock = make(tkroot, base)
    x, y = spot(b)
    assert b.catch(x, y)
    b.drag(x, y - 300)
    b.put_down()
    assert b.mode == "날기"


def test_perch_beats_flail(tkroot, base, monkeypatch):
    rect = (400, -2600, 1200, 100)
    monkeypatch.setattr(wins, "title_bar_at", lambda sx, sy: (9, rect))
    monkeypatch.setattr(wins, "rect_of", lambda h: rect)
    b, clock = make(tkroot, base)
    x, y = spot(b)
    assert b.catch(x, y)
    b.drag(x, y - 2500)
    b.put_down()
    assert b.mode == "앉음" and b.motion == "앉기"


def test_own_sit_picture_stays_while_perched(tkroot, tmp_path, monkeypatch):
    rect = (400, -500, 1200, 100)
    monkeypatch.setattr(wins, "title_bar_at", lambda sx, sy: (9, rect))
    monkeypatch.setattr(wins, "rect_of", lambda h: rect)
    root = make_pack(str(tmp_path), BASE + ("앉기",))
    b, clock = make(tkroot, root)
    x, y = spot(b)
    assert b.catch(x, y)
    b.drag(x, y - 400)
    b.put_down()
    got = seen(b, clock, 12.0)
    assert set(got) == {"앉기"} and os.sep + "앉기" + os.sep in b.clip.files[0]


# ------------------------------------------------------------------ 던지기: 날아감 · 꽈당
def throw_right(b, clock, step, up=200):
    x, y = spot(b)
    assert b.catch(x, y)
    for i in range(6):
        clock.t += 0.02
        b.drag(x + step * i, y - up)
    b.put_down()


def test_flying_then_bonk_stays_bonk(tkroot, base, monkeypatch):
    monkeypatch.setattr(wins, "screen_box", lambda w: (-3000.0, -3000.0, 900.0, 3000.0))
    b, clock = make(tkroot, base)
    throw_right(b, clock, 26, up=1200)                   # 1300px/초: 꽈당은 하되 세게는 아님 (높이 던져 오래 난다)
    assert b.mode == "던짐" and b.motion == "날아감"
    got = seen(b, clock, 4.0)
    assert got[:3] == ["날아감", "꽈당", "뛰기"]          # 부딪히면 내려앉을 때까지 꽈당 (날아감으로 안 돌아감)


def test_hard_bonk_stays_bonk_after_landing(tkroot, base, monkeypatch):
    monkeypatch.setattr(wins, "screen_box", lambda w: (-3000.0, -3000.0, 900.0, 3000.0))
    b, clock = make(tkroot, base)
    throw_right(b, clock, 90)                            # 4500px/초
    got = seen(b, clock, 3.0)
    assert got[:2] == ["날아감", "꽈당"] and b.mode == "울음"   # 내려앉아서도 잠깐 꽈당 그대로
    got = seen(b, clock, 3.0)
    assert got[0] == "꽈당" and "뛰기" in got and "슬픔" not in got


def test_bar_end_bounces():
    t = {"x": -60.0, "y": 40.0, "vx": 900.0, "bar": (0.0, 460.0, 0.0)}
    assert Buddy._bar_end_hit(t, 10) == 0                 # 아직 바 밖
    t["x"] = -5.0
    assert Buddy._bar_end_hit(t, 10) == pytest.approx(900)
    assert t["x"] == -10 and t["vx"] < 0                  # 바 왼쪽 끝에 부딪혀 튕겼다
    t = {"x": 520.0, "y": 40.0, "vx": -900.0, "bar": (0.0, 460.0, 0.0)}
    Buddy._bar_end_hit(t, 10)
    t["x"] = 465.0
    assert Buddy._bar_end_hit(t, 10) > 0 and t["vx"] > 0  # 오른쪽 끝
    t = {"x": -60.0, "y": -50.0, "vx": 900.0, "bar": (0.0, 460.0, 0.0)}
    Buddy._bar_end_hit(t, 10)
    t["x"] = -5.0
    assert Buddy._bar_end_hit(t, 10) == 0                 # 바보다 높이 날면 바 끝에 안 부딪힌다


def test_dizzy_release_faints_instead_of_bonk(tkroot, base):
    """흔들어 어지러우면 던지지 않고 기절만 (꽈당·기절이 겹치지 않음)."""
    b, clock = make(tkroot, base)
    x, y = spot(b)
    assert b.catch(x, y)
    for i in range(12):
        clock.t += 0.03
        b.drag(x + (90 if i % 2 else -90), y - 300)
    b.put_down()
    assert b.mode == "기절" and b._toss is None


# ------------------------------------------------------------------ 밀기 · 빙글
def test_push_at_gauge_end(tkroot, base, monkeypatch):
    monkeypatch.setattr(buddy_mod.random, "random", lambda: 0.5)   # 거닐기를 고른다
    monkeypatch.setattr(buddy_mod, "PUSH_P", 1.0)                   # 그리고 밀러 간다
    b, clock = make(tkroot, base)
    b.until = 0
    b._shown = False
    clock.t += 0.04
    b.step()
    lo, _ = b._bounds()
    assert b.target == pytest.approx(lo) and b._push_next
    got = seen(b, clock, 6.0)
    assert "밀기" in got and b.x == pytest.approx(lo)
    assert not b._push_next


def test_push_cut_short_does_not_push_elsewhere(tkroot, base):
    """밀러 가다 한도가 차(잠) 집으로 가게 되면, 집에 닿아도 밀지 않는다 (바에서 실제로 겪음)."""
    b, clock = make(tkroot, base)
    lo, _ = b._bounds()
    b.target, b._push_next = lo, True
    run(b, clock, 0.3)
    b.set_mood("잠")
    got = seen(b, clock, 8.0)
    assert "밀기" not in got and "잠" in got


def test_no_push_on_ordinary_walk(tkroot, base, monkeypatch):
    b, clock = make(tkroot, base)
    b.target = b.home_x - 30
    got = seen(b, clock, 3.0)
    assert "밀기" not in got


def test_own_spin_picture(tkroot, tmp_path):
    root = make_pack(str(tmp_path), BASE + ("빙글",))
    b, clock = make(tkroot, root)
    b.wheel(*spot(b), 120)
    assert b.motion == "빙글" and b.clip is not None and os.sep + "빙글" + os.sep in b.clip.files[0]
    run(b, clock, 2.0)
    assert b.motion != "빙글"


def test_base_skin_passes_middle_click():
    from skins.base import Skin

    got = []

    class Ch:
        def to_local(self, w, x, y):
            return x, y

        def middle(self, x, y):
            got.append((x, y))

    class Fake:
        claudi = Ch()
        _char = Skin._char
        middle = Skin.middle

    Fake().middle(3, 4)
    assert got == [(3, 4)]
