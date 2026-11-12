"""공룡 점프의 날개 활공(`cooldown_dino.Game`) 규칙 테스트. 화면·tk 없이 돈다."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cooldown_dino as dino  # noqa: E402


def airborne(wing=True):
    """달리는 판에서 뛰기를 누른 채 꼭대기(내려오기 직전)까지 올린 판."""
    g = dino.Game(seed=1)
    g.press_jump()
    g.release_jump()
    while g.jumping:               # 출발 점프가 내려앉을 때까지
        g.step()
    if wing:
        g.wing, g.glide = True, dino.GLIDE_FRAMES
    g.press_jump()
    while g.vy > 0:
        g.step()
    return g


def frames_to_land(g):
    n = 0
    while g.jumping:
        g.step()
        n += 1
        assert n < 1000
    return n


def test_hold_glides_and_falls_slowly():
    g = airborne()
    for _ in range(30):
        g.step()
    assert g.gliding and g.wing_pose in ("glide1", "glide2")
    before = g.h
    g.step()
    assert abs((before - g.h) - dino.GLIDE_FALL) < 0.01      # 한 프레임에 GLIDE_FALL 만큼만 내려온다


def test_glide_stays_up_much_longer_than_plain_fall():
    plain = frames_to_land(airborne(wing=False))
    glide = frames_to_land(airborne())
    assert glide > plain + 60                                 # 1초 넘게 더 떠 있는다


def test_release_ends_glide_at_once():
    g = airborne()
    for _ in range(20):
        g.step()
    assert g.gliding
    left = g.glide
    g.release_jump()
    g.step()
    assert not g.gliding and g.glide == left                  # 뗀 뒤로는 활공을 안 쓴다
    assert g.wing and g.wing_pose == "up"
    for _ in range(5):
        g.step()
    assert g.vy < -dino.GLIDE_FALL * 3                        # 보통대로 떨어진다


def test_press_again_resumes_with_what_is_left():
    g = airborne()
    for _ in range(20):
        g.step()
    g.release_jump()
    for _ in range(4):
        g.step()
    left = g.glide
    g.press_jump()
    for _ in range(12):
        g.step()
    assert g.gliding and g.glide == left - 12
    assert -g.vy < dino.GLIDE_FALL + 0.2                      # 떨어지던 속도가 다시 잡힌다


def test_limit_uses_up_the_wing():
    g = airborne()
    g.h = 10_000.0                                            # 땅에 닿기 전에 한도가 먼저 끝나게
    n = 0
    while g.wing:
        g.step()
        n += 1
    assert n == dino.GLIDE_FRAMES
    assert not g.gliding and g.glide_left == 0 and g.wing_pose is None
    assert any(e[0] == "wing_out" for e in g.events)
    g.step()
    g.step()
    assert g.vy < -dino.GLIDE_FALL                            # 날개가 사라지면 그냥 떨어진다


def test_no_wing_no_glide():
    g = airborne(wing=False)
    for _ in range(8):
        g.step()
    assert not g.gliding and g.vy < -dino.GLIDE_FALL * 3


def test_duck_cancels_glide():
    g = airborne()
    for _ in range(10):
        g.step()
    g.press_duck()
    g.step()
    assert not g.gliding and g.fast_drop


def test_wing_pickup_fills_glide_and_landing_keeps_the_rest():
    g = airborne(wing=False)
    frames_to_land(g)
    g.release_jump()
    g.items.append([dino.DINO_X + 20, 0.0, "wing"])
    while not g.wing:
        g.step()
    assert g.glide == dino.GLIDE_FRAMES and g.wing_pose == "fold"
    g.press_jump()
    while not g.gliding:
        g.step()
    for _ in range(30):
        g.step()
    g.release_jump()
    frames_to_land(g)
    assert g.wing and 0 < g.glide < dino.GLIDE_FRAMES         # 남은 만큼은 다음 점프에 쓴다


def test_events_do_not_pile_up_unread():
    g = dino.Game(seed=2)
    g.press_jump()
    for _ in range(3000):
        if g.state != "run":
            g.over_t = dino.OVER_WAIT
            g.press_jump()
        if not g.jumping:
            g.press_jump()
        g.step()
    assert len(g.events) <= 16
