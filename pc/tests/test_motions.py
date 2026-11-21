"""동작 열일곱 가지(11-20 둘째) 시험. 가짜 시계·가짜 입력으로 돈다.

빈 동작 빌리기 · 자꾸 누르기 → 짜증·화남·포기 → 회복 · 끌며 흔들기 → 헤롱 기절 · 곧은 줄 복귀 ·
평소 그림 쉼·천천히·「다음」 따르기 · 「다음」 정리(지우기·팩 오가기).
그림은 임시 폴더에 코드로 그린다(사용자 팩은 안 읽는다). tk 창은 띄우지 않는다(withdraw).
"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PC = os.path.dirname(HERE)
sys.path.insert(0, PC)
sys.path.insert(0, os.path.join(PC, "windows"))

import tkinter as tk  # noqa: E402

import pytest  # noqa: E402
from PIL import Image  # noqa: E402

import cooldown_pack as pack  # noqa: E402
from skins import carry, wins  # noqa: E402
from skins.base import ANNOY_COOL, ANNOY_STEPS, Annoy, Shake, ShakeMeter, set_palette  # noqa: E402
from skins.buddy import FADE, FADE_MS, GIVEUP_SEC, REST_MAX, TICK_MS, Buddy  # noqa: E402
from skins.claudi import FAINT_FRAMES, Claudi  # noqa: E402

CHAR = "시험떡"
W, H = 460, 48
BOX = (300, 0, 450, H)


def _png(path, color, size=(20, 24), frames=1):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out = []
    for i in range(frames):
        im = Image.new("RGBA", size, (0, 0, 0, 0))
        for x in range(3, size[0] - 3):
            for y in range(4 + i, size[1]):
                im.putpixel((x, y), color)
        out.append(im)
    if frames > 1:
        out[0].save(path, save_all=True, append_images=out[1:], duration=200, loop=0)
    else:
        out[0].save(path)
    return path


def _meta(root, motion, data):
    with open(os.path.join(root, CHAR, motion, pack.META), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


@pytest.fixture(scope="module")
def tkroot():
    r = tk.Tk()
    r.withdraw()
    set_palette("dark")
    yield r
    r.destroy()


@pytest.fixture(autouse=True)
def no_perch(monkeypatch):
    """시험 화면 뒤의 진짜 창 제목 줄에 걸터앉지 않게."""
    monkeypatch.setattr(wins, "title_bar_at", lambda sx, sy: None)


@pytest.fixture
def pressed(monkeypatch):
    monkeypatch.setattr(carry, "button_down", lambda: True)


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def make_buddy(tkroot, root):
    c = tk.Canvas(tkroot, width=W, height=H)
    clock = Clock()
    b = Buddy(c, BOX, CHAR, root=root)
    b.now = clock
    b._last = b._touched = clock.t
    b._play("서기", 3.0)
    return b, clock


def run(b, clock, seconds, each=None):
    for _ in range(int(seconds * 1000 / TICK_MS)):
        clock.t += TICK_MS / 1000
        b.step()
        if each:
            each()


def spot(b):
    return b.x, b.y1 + b.y - b.height / 2


@pytest.fixture
def basic(tmp_path):
    """서기·걷기·놀람·끌림만 있는 캐릭터 (나머지는 빌린다)."""
    root = str(tmp_path)
    for i, m in enumerate(("서기", "걷기", "놀람", "끌림")):
        _png(os.path.join(root, CHAR, m, "1.png"), (50 * i, 120, 200, 255))
    return root


# ------------------------------------------------------------------ 약속
def test_seventeen_motions():
    """열일곱 + 상호작용 열다섯(어질·헤롱 포함) = 서른둘 (11-21, 감정 여섯은 뺐다)."""
    assert len(pack.MOTIONS) == 32 and len(set(pack.MOTIONS)) == 32
    assert sum(len(ms) for _, ms in pack.GROUPS) == 32
    assert [g for g, _ in pack.GROUPS] == ["평소", "이동", "상호작용", "상태"]
    for m in pack.MOTIONS:
        assert pack.MOTION_LABELS[m] and m in pack.FALLBACK and m in pack.DEFAULT_FX
        assert "\n" not in pack.MOTION_LABELS[m] and "—" not in pack.MOTION_LABELS[m]
        assert all(f in pack.MOTIONS for f in pack.FALLBACK[m])
    assert [pack.limit(m) for m in ("서기", "뛰기", "짜증", "자리비움")] == [16, 4, 1, 16]
    assert "헤롱" in pack.EFFECTS and pack.DEFAULT_FX["기절"][0] == "헤롱"


@pytest.mark.parametrize("motion,have,want", [
    ("뛰기", ("걷기", "서기"), "걷기"),
    ("뛰기", ("서기",), "서기"),
    ("점프", ("축하", "놀람"), "축하"),
    ("점프", ("놀람", "서기"), "놀람"),
    ("짜증", ("놀람", "서기"), "놀람"),
    ("화남", ("짜증", "놀람"), "짜증"),
    ("화남", ("놀람",), "놀람"),
    ("포기", ("잠", "눌림"), "잠"),
    ("포기", ("눌림", "서기"), "눌림"),
    ("기절", ("잠", "눌림"), "잠"),
    ("기절", ("서기",), "서기"),
])
def test_empty_motion_borrows(tmp_path, motion, have, want):
    root = str(tmp_path)
    for m in have:
        _png(os.path.join(root, CHAR, m, "a.png"), (200, 100, 50, 255))
    got = pack.pick_clip(CHAR, motion, root)
    assert os.sep + want + os.sep in got.files[0]
    assert got.effect == pack.DEFAULT_FX[motion][0]  # 빌린 동작의 기본 효과 (기절은 헤롱)
    assert got.key != pack.candidates(CHAR, want, root)[0].key  # 제 것과 캐시가 안 겹친다


def test_dizzy_bake_shape():
    im = Image.new("RGBA", (30, 40), (0, 0, 0, 0))
    for x in range(5, 25):
        for y in range(4, 40):
            im.putpixel((x, y), (90, 160, 230, 255))
    frames, loop_from = pack.bake([im], "헤롱", 3)
    assert len(frames) == pack.fx_count("헤롱", 3) and loop_from == 0
    assert len({f.size for f, _ in frames}) == 1
    total = sum(ms for _, ms in frames)
    assert 2.5 <= total / 1000 <= 3.6
    # 별이 돈다 (노란 점이 있다) · 끝 장면은 똑바로 서 있다 (처음과 같은 높이)
    def yellow(f):
        px = f.tobytes()
        return sum(1 for i in range(0, len(px), 4)
                   if px[i + 3] and px[i] > 200 and px[i + 1] > 170 and px[i + 2] < 120)
    assert yellow(frames[0][0]) > 0
    first, last = frames[0][0].getbbox(), frames[-1][0].getbbox()
    tall = im.getbbox()[3] - im.getbbox()[1]
    assert abs((last[3] - last[1]) - tall) <= 2 and (first[3] - first[1]) > tall  # 처음엔 별까지 높다


# ------------------------------------------------------------------ 자꾸 누르기
def test_annoy_steps_up_and_down():
    a = Annoy()
    t = 0.0
    got = []
    for _ in range(60):
        got.append(a.tap(t))
        t += 0.25
        if got[-1] == 3:
            break
    assert got[0] == 0 and 1 in got and 2 in got and got[-1] == 3   # 짜증 → 화남 → 포기
    assert got == sorted(got)
    a = Annoy()
    for i in range(20):
        a.tap(i * 0.1)
    assert a.level(2.0) == 2                                        # 화남
    t_down = (a.heat - ANNOY_STEPS[1]) / ANNOY_COOL
    assert a.level(2.0 + t_down + 0.2) == 1                         # 서서히 짜증으로
    assert a.level(2.0 + 60) == 0                                    # 한참 두면 괜찮아진다
    a = Annoy()
    assert all(a.tap(i * 2.0) == 0 for i in range(30))              # 2초에 한 번(새로고침)은 안 쌓인다


def tap(b):
    """한 번 누르고 뗀다 (누르기 반응은 뗄 때 정한다, 11-21)."""
    b.react(*spot(b))
    b.tap_up()


def test_buddy_click_stages_giveup_and_recover(tkroot, basic):
    b, clock = make_buddy(tkroot, basic)
    seen = []
    for _ in range(80):
        tap(b)
        run(b, clock, 0.2, lambda: seen.append(b.motion if b.mode != "포기" else "포기"))
        if b.mode == "포기":
            break
    order = [m for i, m in enumerate(seen) if i == 0 or seen[i - 1] != m]
    assert order == ["놀람", "짜증", "화남", "포기"]   # 떼자마자 놀람, 단계가 오르면 번갈지 않는다
    assert b.mode == "포기" and b.motion == "포기"     # 그림이 없으면 빌린다 (서기)
    tap(b)                                            # 체념한 동안은 받기만 한다
    assert b.absorbed() and b.mode == "포기" and b.motion == "포기"
    b.hold(*spot(b))
    assert not b.held
    run(b, clock, GIVEUP_SEC + 0.3)
    assert b.mode == ""                               # 회복 (슬픔을 끼우지 않는다)
    tap(b)
    run(b, clock, 0.5)
    assert b.motion == "놀람"                          # 처음부터 다시


def test_mash_never_flips_back_to_surprise(tkroot, basic):
    """자꾸 누름(11-21 사용자: 놀람과 짜증이 번갈아 나온다): 짜증에 닿으면 놀람이 다시 안 나온다.
    누르는 빠르기가 짜증 문턱 언저리에서 오르내려도 그렇다."""
    b, clock = make_buddy(tkroot, basic)
    seen = []
    for i in range(40):
        tap(b)
        run(b, clock, 0.3 if i % 3 else 0.6, lambda: seen.append(b.motion))
    order = [m for i, m in enumerate(seen) if i == 0 or seen[i - 1] != m]
    assert "짜증" in order and order.index("짜증") == order.index("놀람") + 1
    assert "놀람" not in order[order.index("짜증"):] and "서기" not in order[order.index("놀람"):]


def test_buddy_click_stage_cools_down(tkroot, basic):
    b, clock = make_buddy(tkroot, basic)
    for _ in range(5):
        tap(b)
        run(b, clock, 0.15)
    assert b._annoy.level(clock.t) == 0               # 몇 번 누르는 것으로는 짜증 안 남
    for _ in range(7):
        tap(b)
        run(b, clock, 0.15)
    assert b._annoy.level(clock.t) >= 1
    run(b, clock, 20)
    tap(b)
    run(b, clock, 0.5)
    assert b.motion == "놀람"


def test_no_tap_faint_anymore(tkroot, basic):
    b, clock = make_buddy(tkroot, basic)
    for _ in range(30):
        tap(b)
        run(b, clock, 0.08)
        assert b.mode != "기절"


# ------------------------------------------------------------------ 흔들기 → 헤롱 기절
def shake(feed, cx, cy, now, n=24, amp=60, dt=0.03):
    for i in range(n):
        feed(cx + (amp if i % 2 else -amp), cy + (amp / 2 if i % 4 < 2 else -amp / 2), now + i * dt)
    return now + n * dt


def test_shake_detect():
    s = Shake()
    end = shake(s.feed, 0, 0, 10.0)
    assert s.dizzy(end)
    assert not s.dizzy(end + 5)                       # 흔든 뒤 한참 들고 있으면 정신 차린다
    s = Shake()
    for i in range(40):                               # 한 방향으로 길게 끌기
        s.feed(i * 30, 0, 10 + i * 0.03)
    assert not s.dizzy(12)
    s = Shake()
    for i in range(40):                               # 느리게 오가기
        s.feed(40 if i % 2 else -40, 0, 10 + i * 0.6)
    assert not s.dizzy(34)
    s = Shake()
    for i in range(40):                               # 손 떨림 정도로 작게
        s.feed(5 if i % 2 else -5, 3 if i % 2 else -3, 10 + i * 0.02)
    assert not s.dizzy(11)


def test_buddy_shaken_off_bar_faints_where_dropped(tkroot, basic, pressed):
    b, clock = make_buddy(tkroot, basic)
    home = b.home_x
    x, y = spot(b)
    assert b.catch(x, y)

    def feed(px, py, t):
        clock.t = t
        b.drag(px, py - 400)
    clock.t = shake(feed, x, y, clock.t, n=60)
    assert b._stage == 3 and b.motion == "기절"      # 잡힌 채로 셋째 단계
    at = b._carry.at
    b.put_down()
    assert b.mode == "기절" and b._carry is not None   # 바 밖 놓은 그 자리에서 뻗는다
    assert b.clip.effect == "헤롱"                     # 기절 그림이 없으면 헤롱 효과
    cyc = b._cycle()
    assert 2.5 <= cyc <= 3.6 and cyc - 0.6 <= b.until - clock.t <= cyc + 1e-6
    run(b, clock, 1.0)
    assert b.mode == "기절" and b._carry.at == pytest.approx(at)
    b.react(*spot(b))
    assert b.mode == "기절"
    run(b, clock, cyc - 0.9)
    assert b.mode == "날기" and b.motion == "뛰기"     # 깨어나 곧장 뛰어 돌아온다
    run(b, clock, carry.RUN_MAX + 0.2)
    assert b.mode == "" and b._carry is None and b.x == pytest.approx(home)


def test_shake_two_or_three_swings_is_enough():
    """좌우로 두세 번 세게 흔들면 걸린다 (11-20 넷째: 옛 기준은 안 걸렸다)."""
    s = Shake()
    t, x = 10.0, 0.0
    hit = []
    for target in (80, -80, 80, -80):                 # 0.12초에 160px 씩 오가기
        for k in range(6):
            x += (target - x) / (6 - k)
            t += 0.02
            hit.append(s.feed(x, 0, t))
    assert s.dizzy(t) and hit.count(True) == 1         # 새로 어지러워진 때만 참
    s = Shake()
    t, x = 10.0, 0.0
    for target in (80, -80):                           # 한 번 오간 것으로는 아니다
        for k in range(6):
            x += (target - x) / (6 - k)
            t += 0.02
            s.feed(x, 0, t)
    assert not s.dizzy(t)


def test_held_dizzy_wears_off_slowly(tkroot, basic, pressed):
    b, clock = make_buddy(tkroot, basic)
    x, y = spot(b)
    assert b.catch(x, y)

    def feed(px, py, t):
        clock.t = t
        b.drag(px, py - 400)
    clock.t = shake(feed, x, y, clock.t, n=60)
    assert b.motion == "기절"
    got = []
    run(b, clock, 25.0, lambda: got.append(b.motion) if not got or got[-1] != b.motion else None)
    assert got == ["기절", "헤롱", "어질", "끌림"]       # 들고 가만히 있으면 한 단계씩 천천히 내려온다
    assert b.mode == "끌림"


def shake_for(b, clock, seconds, x, y, amp=60, dt=0.03, hz=4.0):
    """사람이 마구 흔들듯: 초에 hz 번 좌우로 오간다 (끌기 신호는 dt 마다)."""
    stages = []
    t0 = clock.t
    while clock.t - t0 < seconds:
        clock.t += dt
        phase = ((clock.t - t0) * hz) % 1.0
        dx = amp * (4 * phase - 1 if phase < 0.5 else 3 - 4 * phase)
        b.drag(x + dx, y - 400)
        stages.append(b._stage)
    return stages


def test_shake_three_stages_need_real_shaking(tkroot, basic, pressed):
    """흔들기 세 단계(11-21 사용자: 기절 역치가 너무 낮다): 어질 → 헤롱 → 기절 순서로,
    어질도 1초 넘게 작정하고 세게 흔들어야 닿는다."""
    b, clock = make_buddy(tkroot, basic)
    x, y = spot(b)
    assert b.catch(x, y)
    stages = shake_for(b, clock, 1.0, x, y)
    assert max(stages) == 0                           # 1초 흔든 것으로는 아직 끌림
    stages += shake_for(b, clock, 6.0, x, y)
    firsts = [stages.index(k) for k in (1, 2, 3)]
    assert firsts == sorted(firsts)                   # 차례대로
    assert b._stage == 3 and b.motion == "기절"
    assert len([1 for i in range(1, len(stages)) if stages[i] != stages[i - 1]]) == 3   # 오르기만, 번갈지 않음


def test_shake_meter_rules():
    m = ShakeMeter()
    t = 10.0
    for i in range(80):                               # 한 방향으로 길게 빨리 끌기
        m.feed(i * 30, 0, t + i * 0.02)
    assert m.level(t + 2) == 0
    m = ShakeMeter()
    for i in range(60):                               # 느리게 오가기
        m.feed(80 if i % 2 else -80, 0, t + i * 0.5)
    assert m.level(t + 31) == 0
    m = ShakeMeter()
    for i in range(200):                              # 손 떨림 정도로 작게
        m.feed(10 if i % 2 else -10, 6 if i % 2 else -6, t + i * 0.02)
    assert m.level(t + 5) == 0


@pytest.mark.parametrize("stage,motion", [(1, "어질"), (2, "헤롱")])
def test_dizzy_release_wobbles_there_then_runs_home(tkroot, basic, pressed, stage, motion):
    b, clock = make_buddy(tkroot, basic)
    home = b.home_x
    x, y = spot(b)
    assert b.catch(x, y)
    b.drag(x - 100, y)
    b._shake.energy = (b._shake.stages[stage - 1] + b._shake.stages[stage]) / 2
    b._shake.t = clock.t
    b._shake.stage = stage
    b.drag(x - 100, y)
    assert b.motion == motion
    b.put_down()                                      # 바 위: 그 자리에서 잠깐 비틀댄다 (그림 그대로)
    assert b.mode == "기절" and b.motion == motion and abs(b.x - (home - 100)) < 1
    got = []
    run(b, clock, 3.5, lambda: got.append(b.motion) if not got or got[-1] != b.motion else None)
    assert got[0] == motion and "놀람" not in got and "뛰기" in got


def test_buddy_shaken_on_bar_faints_there_then_runs_home(tkroot, basic, pressed):
    b, clock = make_buddy(tkroot, basic)
    home = b.home_x
    x, y = spot(b)
    assert b.catch(x, y)

    def feed(px, py, t):
        clock.t = t
        b.drag(px - 100, py)
    clock.t = shake(feed, x, y, clock.t, n=48, amp=30)
    b.drag(x - 100, y)                                # 바 위 그 자리로
    b.put_down()
    assert b.mode == "기절" and abs(b.x - (home - 100)) < 1
    run(b, clock, b._cycle() + 0.1)
    assert b.mode == "복귀" and b.motion == "뛰기"     # 깨어나 뛰어 돌아간다 (뛰기 → 걷기 빌림)
    for _ in range(60):
        if b.mode != "복귀":
            break
        run(b, clock, TICK_MS / 1000)
    assert b.mode == "" and b.x == pytest.approx(home)


def test_buddy_gentle_drag_no_faint(tkroot, basic, pressed):
    b, clock = make_buddy(tkroot, basic)
    x, y = spot(b)
    assert b.catch(x, y)
    for i in range(30):
        clock.t += 0.03
        b.drag(x - i * 20, y - i * 10)
    b.put_down()
    run(b, clock, carry.RUN_MAX + 0.2)
    assert b.mode == "" and b.motion != "기절"


def test_claudi_shaken_faints(tkroot, pressed):
    c = tk.Canvas(tkroot, width=W, height=H)
    cl = Claudi(c, (10, 0, 450, H))
    cl.home(330)
    cl.start()
    clock = Clock()
    cl.now = clock
    assert cl.catch(cl.cx, cl.cy)

    def feed(px, py, t):
        clock.t = t
        cl.drag(px - 900, py - 500)
    clock.t = shake(feed, cl.cx, cl.cy, clock.t)
    cl.put_down()
    for _ in range(30):
        clock.t += 0.045
        cl._animate(cl.c, cl._anim_gen)
    assert not cl._grabbed and cl._faint > 0         # 날아와 내려앉자마자 헤롱헤롱
    for _ in range(FAINT_FRAMES + 5):
        cl._animate(cl.c, cl._anim_gen)
    assert cl._faint == 0


def test_claudi_gentle_drag_no_faint(tkroot, pressed):
    c = tk.Canvas(tkroot, width=W, height=H)
    cl = Claudi(c, (10, 0, 450, H))
    cl.home(330)
    cl.start()
    clock = Clock()
    cl.now = clock
    assert cl.catch(cl.cx, cl.cy)
    for i in range(20):
        clock.t += 0.03
        cl.drag(cl.cx - i * 30, cl.cy - i * 20)
    cl.put_down()
    for _ in range(30):
        clock.t += 0.045
        cl._animate(cl.c, cl._anim_gen)
    assert not cl._grabbed and cl._faint == 0


# ------------------------------------------------------------------ 곧은 줄 복귀
def test_flight_is_straight_and_smooth():
    f = carry.Flight((100.0, 900.0), (700.0, 300.0), 0.0)
    pts = [f.at(i * 0.02) for i in range(int(f.dur / 0.02) + 3)]
    assert pts[-1] == (700.0, 300.0, True)
    for x, y, _ in pts:                               # 모든 점이 두 끝을 잇는 줄 위
        assert abs((x - 100) * (300 - 900) - (y - 900) * (700 - 100)) < 1e-6 * 600 * 600
    xs = [x for x, _, _ in pts]
    assert xs == sorted(xs) and max(xs) <= 700        # 넘어갔다 돌아오지 않는다
    steps = [b - a for a, b in zip(xs, xs[1:])]
    assert steps[0] < max(steps) and steps[-3] < max(steps)   # 천천히 떠나 살며시 멎는다
    assert 0.5 <= f.dur <= 1.1


def test_buddy_lands_softly(tkroot, basic, pressed):
    b, clock = make_buddy(tkroot, basic)
    x, y = spot(b)
    assert b.catch(x, y)
    b.drag(x + 600, y - 600)
    b.put_down()
    run(b, clock, carry.RUN_MAX + 0.2)
    assert b.mode == "" and b.vy == 0 and b.y == 0     # 내려앉을 때 폴짝 튀지 않는다


def test_buddy_flight_plays_run_if_own(tkroot, basic, pressed):
    _png(os.path.join(basic, CHAR, "뛰기", "r.png"), (10, 200, 10, 255))
    b, clock = make_buddy(tkroot, basic)
    x, y = spot(b)
    assert b.catch(x, y)
    b.drag(x - 600, y - 600)
    b.put_down()
    assert b.mode == "날기" and b.motion == "뛰기"


# ------------------------------------------------------------------ 평소 동작: 천천히·쉼·다음
@pytest.fixture
def calm(tmp_path):
    """서기 셋(첫 장이 쉬는 그림)과 움직이는 딴짓 하나."""
    root = str(tmp_path)
    for i, n in enumerate(("0.png", "1.png", "2.png")):
        _png(os.path.join(root, CHAR, "서기", n), (40 + 60 * i, 90, 160, 255))
    _png(os.path.join(root, CHAR, "딴짓", "d.png"), (220, 60, 60, 255), frames=7)  # 1.4초 한 바퀴
    return root


def watch(b, clock, seconds):
    """[(동작, 후보 key, 시작 때, 끝 때)] 차례."""
    seq = []

    def each():
        k = (b.motion, b.clip.key if b.clip else None)
        if not seq or tuple(seq[-1][:2]) != k:
            if seq:
                seq[-1][3] = clock.t
            seq.append([k[0], k[1], clock.t, None])
    run(b, clock, seconds, each)
    seq[-1][3] = clock.t
    return seq


def test_everyday_rests_between_pictures(tkroot, calm):
    random.seed(3)
    b, clock = make_buddy(tkroot, calm)
    b._touched = clock.t
    b.target = None
    rest = pack.rest_clip(CHAR, calm).key
    seq = watch(b, clock, 240)[1:-1]
    shows = [s for s in seq if s[0] in ("서기", "딴짓", "인사") and s[1] != rest]
    assert shows
    for s in seq:                                     # 한 그림을 너무 짧게 두지 않는다
        if s[0] in ("서기", "딴짓") and s[1] != rest:
            assert s[3] - s[2] >= 2.9
        if s[1] == rest:
            assert 0.9 <= s[3] - s[2] <= REST_MAX + 0.2
    for a, nxt in zip(seq, seq[1:]):                   # 쉼 없이 다른 서기·딴짓으로 곧장 바뀌지 않는다
        if a[1] != rest and a[0] in ("서기", "딴짓") and nxt[0] in ("서기", "딴짓"):
            assert nxt[1] == rest
    for s in seq:                                     # 움직이는 그림은 바퀴가 끝나는 데까지
        if s[0] == "딴짓":
            laps = (s[3] - s[2] - len(FADE) * FADE_MS / 1000) / 1.4
            assert abs(laps - round(laps)) < 0.1 and round(laps) >= 1


def test_fade_frames_on_change(tkroot, calm):
    b, clock = make_buddy(tkroot, calm)
    b._show("딴짓", 3.0)
    assert b._fade_n == len(FADE) and len(b.frames) == len(FADE) + 7
    assert b.loop_from == len(FADE)
    run(b, clock, 0.4)
    b._face(-b.dir)                                    # 돌아서도 엉키지 않는다
    assert b._fade_n == 0 and len(b.frames) == 7


def test_next_is_followed(tkroot, calm):
    _meta(calm, "서기", {"다음": {"1.png": ["딴짓/d.png"], "2.png": ["서기/없는.png", "엉뚱/d.png"]}})
    got = [(m, c.key) for m, c in pack.next_clips(CHAR, pack.candidates(CHAR, "서기", calm)[1], calm)]
    assert got == [("딴짓", pack.candidates(CHAR, "딴짓", calm)[0].key)]
    assert pack.next_clips(CHAR, pack.candidates(CHAR, "서기", calm)[2], calm) == []  # 잘못된 값은 무시
    random.seed(5)
    b, clock = make_buddy(tkroot, calm)
    one = pack.candidates(CHAR, "서기", calm)[1]
    followed = rested = 0
    for _ in range(60):
        b._show("서기", 3.0, one)
        b.until = clock.t
        b.step(clock.t + 0.04)
        clock.t += 0.04
        if b.motion == "딴짓":
            followed += 1
        elif b.clip.key == pack.rest_clip(CHAR, calm).key:
            rested += 1
    assert followed + rested == 60
    assert 0.5 <= followed / 60 <= 0.9                # 대개(70%) 「다음」을 따른다


def test_next_to_walk_uses_that_clip(tkroot, calm):
    _png(os.path.join(calm, CHAR, "걷기", "w1.png"), (0, 0, 255, 255))
    _png(os.path.join(calm, CHAR, "걷기", "w2.png"), (0, 255, 0, 255))
    _meta(calm, "서기", {"다음": {"1.png": ["걷기/w2.png"]}})
    b, clock = make_buddy(tkroot, calm)
    one = pack.candidates(CHAR, "서기", calm)[1]
    random.seed(1)
    for _ in range(40):
        b._show("서기", 3.0, one)
        b.until = clock.t
        b.step(clock.t + 0.04)
        clock.t += 0.04
        if b.target is not None:
            break
    assert b.target is not None and b._walk_clip is not None
    run(b, clock, 0.1)
    assert b.motion == "걷기" and b.clip.files[0].endswith("w2.png")


# ------------------------------------------------------------------ 「다음」 정리
def test_next_meta_clean_and_cleanup(tmp_path):
    root = str(tmp_path)
    for n in ("a.png", "b.png"):
        _png(os.path.join(root, CHAR, "서기", n), (1, 2, 3, 255))
    _png(os.path.join(root, CHAR, "딴짓", "d.png"), (1, 2, 3, 255))
    raw = {"다음": {"a.png": ["딴짓/d.png", "딴짓/d.png", "놀람/x.png", "딴짓/../x.png", 3, "서기/b.png"],
                   "../x.png": ["서기/a.png"], "b.png": "딴짓/d.png"}}
    meta = pack.clean_meta(raw)
    assert meta["다음"] == {"a.png": ["딴짓/d.png", "서기/b.png"]}


def test_pack_roundtrip_keeps_next(tmp_path):
    root, other = str(tmp_path / "a"), str(tmp_path / "b")
    for n in ("a.png", "b.png"):
        _png(os.path.join(root, CHAR, "서기", n), (1, 2, 3, 255))
    _png(os.path.join(root, CHAR, "딴짓", "d.png"), (1, 2, 3, 255))
    _meta(root, "서기", {"다음": {"a.png": ["딴짓/d.png", "인사/없음.png"]}})
    dest = str(tmp_path / ("x" + pack.PACK_SUFFIX))
    pack.export_pack(CHAR, dest, root)
    name = pack.import_pack(dest, other)
    assert pack.motion_meta(name, "서기", other)["다음"] == {"a.png": ["딴짓/d.png"]}  # 팩에 없는 것은 걷는다
