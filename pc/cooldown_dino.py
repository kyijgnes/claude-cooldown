"""
공룡 점프 — 클로디가 공룡으로 변신해 달리는 미니게임의 **규칙** (Tk 없음)
======================================================================
크롬이 인터넷이 끊기면 띄우는 그 공룡 게임을 그대로 옮겼다. 위젯의 클로디를 **아주 오래
꾹 누르면**(끝까지 납작해진 뒤로도 더) 공룡으로 변신하고 이 판이 열린다.

- **그림표(도트)·수치·규칙이 전부 여기 한 곳이다.** 그리는 쪽(PC `windows/cooldown_dino_view.py`,
  폰 `dino/DinoView.kt`)은 여기서 정한 것을 옮겨 그리기만 한다.
  ★ 폰은 이 파일을 **생성기**(`android/art/make_claudi_icon.py`)로 읽어 그림표와 수치를
  `DinoSpec.kt` 로 뽑는다. 수치·그림을 고쳤으면 그 스크립트를 다시 돌린다.
  규칙(아래 `Game`)은 `DinoGame.kt` 가 손으로 옮긴 것이라 **고치면 거기도 같이 고친다.**
- 수치는 크롬 원본(Runner·Trex·Obstacle config)에서 왔다. 판이 600×150 이고 한 프레임이
  1/60초인 것도 같다. 달라진 것만 적는다:
  · 공룡이 조금 작다(38px, 크롬 47px). 머리가 **클로디 머리**(9칸, 모서리 깎음)라서.
  · 충돌은 상자가 아니라 **도트 칸끼리**(`hits`) 본다. 그림이 도트 표라 그대로 쓰면 된다.
  · 새는 높이가 셋(`BIRD_LIFTS`) — 낮은 것은 뛰어넘고, 가운데는 숙이거나 뛰고, 높은 것은 지나간다.
    폰은 가운데를 뺀 둘(`BIRD_LIFTS_TOUCH`, `touch=True`) — 크롬도 휴대폰에선 그렇다.
- 한 걸음(`step`)이 1/60초다. 그리는 쪽은 흐른 시간만큼 `step` 을 불러 맞춘다.
- 난수는 `random.Random(seed)` 하나만 쓴다. 같은 씨앗이면 같은 판이 나온다(확인용).

확인: `python pc/cooldown_dino.py` — 알아서 뛰는 공룡으로 판을 몇 번 돌려 점수를 본다.
"""

from __future__ import annotations

import random

# ---------------------------------------------------------------- 판
FPS = 60                # step 한 번 = 1/60초
W, H = 600, 150         # 판 크기 (px) — 크롬과 같다
GROUND = 138            # 발이 닿는 선 (y)
U = 2                   # 도트 한 칸 (px) — 위젯의 클로디와 같은 칸
DINO_X = 40             # 공룡 그림 왼쪽 끝 (꼬리 끝)

# ---------------------------------------------------------------- 달리기
SPEED0 = 6.0            # 처음 속도 (px/프레임)
SPEED_MAX = 13.0
ACCEL = 0.001           # 프레임마다 이만큼 빨라진다 (6 → 13 까지 약 2분)
CLEAR_FRAMES = 180      # 시작하고 이만큼(3초)은 장애물이 없다
SCORE_COEF = 0.025      # 달린 거리 × 이것 = 점수

# ---------------------------------------------------------------- 뛰기
# 누르고 있는 동안은 높이 오르고, 일찍 떼면 낮게 뛴다(크롬과 같다).
GRAVITY = 0.6
JUMP_V = 10.0           # 뛰어오르는 속도 (+ 지금 속도/10)
DROP_V = 5.0            # 떼면 오르는 속도를 여기까지 꺾는다
MIN_JUMP = 30           # 떼도 이만큼은 오른다 (px)
MAX_JUMP = 63           # 누르고 있어도 이 높이에서 오르기를 꺾는다
FAST_DROP = 3           # 뛰는 중에 ↓ 를 누르면 이 배로 빨리 떨어진다

# ---------------------------------------------------------------- 장애물
GAP_COEF = 0.6
GAP_MAX = 1.5           # 틈은 최소 틈의 1~1.5배 사이
MAX_GROUP = 3           # 선인장은 셋까지 붙어 나온다
MAX_DUP = 2             # 같은 종류는 셋 연달아 안 나온다
BIRD_LIFTS = (0, 22, 42)  # 새 그림 아래끝의 높이 — 뛰어넘기 · 숙이거나 뛰기 · 그냥 지나감
# 폰(손가락)에서는 가운데 높이를 뺀다 — 크롬도 휴대폰에선 새가 두 높이뿐이다(숙일 단추가 없어서).
BIRD_LIFTS_TOUCH = (0, 42)
BIRD_WOBBLE = 0.8       # 새는 제 속도가 조금씩 다르다 (±)

# ---------------------------------------------------------------- 그 밖
OVER_WAIT = 45          # 부딪힌 뒤 이만큼(0.75초)은 누르기를 안 받는다 (눌러 대다 바로 다시 시작되지 않게)
RUN_BEAT = 5            # 이 프레임마다 발을 바꾼다 (12fps)
FLAP_BEAT = 10          # 새가 날갯짓을 바꾸는 프레임
BLINK_EVERY = (120, 300)  # 기다리는 동안 눈 깜빡이는 사이 (프레임)
FLASH_EVERY = 100       # 이 점수마다 점수가 반짝인다
FLASH_FRAMES = 60
NIGHT_EVERY = 700       # 이 점수마다 밤이 온다
NIGHT_FRAMES = 720      # 밤은 12초
CLOUD_MAX = 6
CLOUD_GAP = (100, 400)
CLOUD_SKY = (32, 72)    # 구름이 뜨는 높이 (y) — 점수 글자(위 30px)와 안 겹치게
CLOUD_SPEED = 0.2       # 달리는 속도의 이만큼으로 흐른다

# ---------------------------------------------------------------- 그림 (도트 표)
# `#` 한 칸이 U px. 방향은 전부 **오른쪽을 본다**(달리는 쪽).
#
# 공룡 — **머리가 클로디 머리다**(9칸, 위 모서리 깎음). 크롬 공룡의 몸·꼬리·팔에 클로디
# 머리를 얹었다. 눈은 표에 없고 `DINO_EYE` 칸을 바탕색으로 파낸다(클로디 `EYES` 와 같은 결).
DINO_BODY = (
    "............#####..",
    "...........#######.",
    "..........#########",
    "..........#########",
    "..........#########",
    "..........#########",
    "..........######...",
    "#........#######...",
    "#.......#########..",
    "##.....#########.#.",
    "###...##########...",
    "###############....",
    ".#############.....",
    "..###########......",
    "...#########.......",
    "....#######........",
)
DINO_LEGS = {
    "stand": ("....###..###.......", "....##....##.......", "....##....##......."),
    "run1": ("....###..###.......", "....##.....##......", "...........##......"),
    "run2": ("....###..###.......", "....##....##.......", "....##............."),
}
# 숙이기 — 납작하게 엎드려 머리를 앞으로 내민다
DINO_DUCK = (
    "........................#####..",
    "#......................#######.",
    "##.......############.#########",
    ".###..#########################",
    "..#############################",
    "...##########################..",
    "....#######################....",
)
DINO_DUCK_LEGS = {
    "duck1": ("......###.....###..............", "......##......##..............."),
    "duck2": ("......###.....###..............", ".......##.....##..............."),
}
# 눈 — (칸, 줄). 서 있을 때와 숙였을 때 자리가 다르다.
DINO_EYE = {
    "open": ((12, 2), (13, 2), (12, 3), (13, 3)),
    "blink": ((12, 3), (13, 3)),
    "dead": ((11, 2), (13, 2), (12, 3), (11, 4), (13, 4)),   # X
}
DUCK_EYE = {
    "open": ((25, 2), (26, 2), (25, 3), (26, 3)),
    "blink": ((25, 3), (26, 3)),
    "dead": ((24, 1), (26, 1), (25, 2), (24, 3), (26, 3)),
}

# 선인장 — 작은 것(8×17)과 큰 것(12×25). 여럿이 붙어 나올 땐 하나 걸러 좌우를 뒤집는다.
CACTUS_S = (
    "...##...",
    "..####..",
    "..####..",
    "..####.#",
    "#.####.#",
    "#.####.#",
    "#.######",
    "#.#####.",
    "######..",
    ".#####..",
    "..####..",
    "..####..",
    "..####..",
    "..####..",
    "..####..",
    "..####..",
    "..####..",
)
CACTUS_L = (
    ".....##.....",
    "....####....",
    "....####....",
    "....####....",
    "....####..#.",
    "....####.###",
    "##..####.###",
    "##..####.###",
    "##..####.###",
    "##..####.###",
    "##..####.###",
    "##..#######.",
    "##..######..",
    "##..####....",
    "########....",
    ".#######....",
    "....####....",
    "....####....",
    "....####....",
    "....####....",
    "....####....",
    "....####....",
    "....####....",
    "....####....",
    "....####....",
)
# 새 — 날개를 올렸다 내렸다. 두 장의 높이를 같게(10줄) 잡아 `BIRD_LIFTS` 가 그림 아래끝을 가리킨다.
# 눈은 `BIRD_EYE` 칸을 바탕색으로 파낸다.
BIRD = (
    (
        "......#...............",
        "......##..............",
        "......###.............",
        "......####............",
        "....#######...........",
        "..###########.........",
        "##############........",
        "..#################...",
        ".......#############..",
        "........#########.....",
    ),
    (
        "......................",
        "......................",
        "......................",
        "....#######...........",
        "..###########.........",
        "##############........",
        "..#################...",
        ".......#############..",
        "......#####...........",
        "......###.............",
    ),
)
BIRD_EYE = ((4, 6), (4, 5))   # 장마다 눈 자리 (날개를 내린 장은 몸이 한 줄 위다)

CLOUD = (
    "......####......",
    "....########....",
    "..############..",
    "################",
)

# 다시 하기 — 둥근 화살표
RESTART = (
    "...#####...",
    "..#.....#..",
    ".#.......#.",
    "#.........#",
    "#..........",
    "#.......###",
    "#........##",
    ".#......#.#",
    "..#.....#..",
    "...#####...",
)


def runs(rows: tuple[str, ...], flip: bool = False) -> list[tuple[int, int, int, int]]:
    """도트 표를 **줄마다 이어진 칸 덩이**로 — `(x, y, w, h)` px. 그리기와 충돌이 같이 쓴다.

    한 칸씩 그리면 도형이 세 배다. 경계 식이 같으므로 그림은 한 픽셀도 안 달라진다."""
    out = []
    width = max(len(r) for r in rows)
    for r, line in enumerate(rows):
        line = line.ljust(width, ".")
        if flip:
            line = line[::-1]
        c = 0
        while c < width:
            if line[c] != "#":
                c += 1
                continue
            n = 1
            while c + n < width and line[c + n] == "#":
                n += 1
            out.append((c * U, r * U, n * U, U))
            c += n
    return out


def size(rows: tuple[str, ...]) -> tuple[int, int]:
    """그림 크기 (px)."""
    return max(len(r) for r in rows) * U, len(rows) * U


# 공룡 자세마다의 그림 — 충돌도 이걸로 본다
POSES = {
    "stand": DINO_BODY + DINO_LEGS["stand"],
    "run1": DINO_BODY + DINO_LEGS["run1"],
    "run2": DINO_BODY + DINO_LEGS["run2"],
    "duck1": DINO_DUCK + DINO_DUCK_LEGS["duck1"],
    "duck2": DINO_DUCK + DINO_DUCK_LEGS["duck2"],
}
_POSE_RUNS = {k: runs(v) for k, v in POSES.items()}

# 장애물 종류 — 크롬 Obstacle.types 를 옮긴 것
#   min_gap: 틈 계산의 바탕 · multi: 이 속도를 넘어야 여럿 붙어 나온다 · min_speed: 이 속도부터 나온다
KINDS = {
    "cactus": {"art": (CACTUS_S,), "min_gap": 120, "multi": 4.0, "min_speed": 0.0},
    "cactus_big": {"art": (CACTUS_L,), "min_gap": 120, "multi": 7.0, "min_speed": 0.0},
    "bird": {"art": BIRD, "min_gap": 150, "multi": 999.0, "min_speed": 8.5},
}


class Obstacle:
    """판 위의 장애물 하나(선인장 여럿이 붙은 무리도 하나다)."""

    def __init__(self, kind: str, x: float, count: int, lift: int, wobble: float, gap: int):
        self.kind = kind
        self.x = x
        self.count = count       # 붙어 나온 개수 (새는 늘 1)
        self.lift = lift         # 그림 아래끝이 땅에서 뜬 높이 (새만)
        self.wobble = wobble     # 제 속도 보탬 (새만)
        self.gap = gap           # 다음 장애물까지 띄울 틈
        self.frame = 0           # 새 날갯짓 (0/1)
        self.follow = False      # 다음 장애물을 이미 불렀나
        art = KINDS[kind]["art"][0]
        self.one_w, self.h = size(art)
        self.w = self.one_w * count

    @property
    def y(self) -> float:
        """그림 위끝."""
        return GROUND - self.lift - self.h

    def parts(self):
        """그릴 조각들 — `(그림 표, x, y, 뒤집기)`. 선인장 무리는 하나 걸러 뒤집는다."""
        arts = KINDS[self.kind]["art"]
        art = arts[self.frame % len(arts)]
        for i in range(self.count):
            yield art, self.x + i * self.one_w, self.y, i % 2 == 1

    def hit_runs(self):
        for art, x, y, flip in self.parts():
            for rx, ry, rw, rh in _art_runs(art, flip):
                yield x + rx, y + ry, rw, rh


_RUN_CACHE: dict = {}


def _art_runs(art, flip):
    key = (id(art), flip)
    if key not in _RUN_CACHE:
        _RUN_CACHE[key] = runs(art, flip)
    return _RUN_CACHE[key]


class Game:
    """한 판. 상태는 셋 — `ready`(기다림) · `run`(달리는 중) · `over`(부딪힘).

    누르기: `press_jump`/`release_jump`(스페이스·↑·클릭·탭), `press_duck`/`release_duck`(↓).
    `step()` 한 번이 1/60초. 그리는 쪽은 `pose`·`dino_y`·`obstacles`·`clouds`·`score`… 를 읽는다.
    """

    def __init__(self, seed: int | None = None, best: int = 0, touch: bool = False):
        self.rng = random.Random(seed)
        self.best = int(best)
        self.lifts = BIRD_LIFTS_TOUCH if touch else BIRD_LIFTS
        self.t = 0
        self._reset()
        self.state = "ready"

    # -------------------------------------------------- 판 새로
    def _reset(self) -> None:
        self.state = "run"
        self.speed = SPEED0
        self.distance = 0.0
        self.run_t = 0             # 이 판에서 달린 프레임
        self.h = 0.0               # 공룡이 땅에서 뜬 높이 (px, 위가 +)
        self.vy = 0.0              # 오르는 속도 (위가 +)
        self.jumping = False
        self.reached_min = False
        self.fast_drop = False
        self.holding = False       # 뛰기를 누르고 있다
        self.down = False          # ↓ 를 누르고 있다
        self.ducking = False       # 숙이고 있다 (땅에서 ↓)
        self.obstacles: list[Obstacle] = []
        self.history: list[str] = []   # 최근에 나온 종류 (같은 것 셋 연달아 금지)
        self.over_t = 0
        self.flash = 0             # 점수 반짝임 남은 프레임
        self.flash_score = 0
        self.night = 0             # 밤 남은 프레임
        self.blink = 0
        self.next_blink = self.rng.randint(*BLINK_EVERY)
        self.new_best = False
        self.clouds: list[list[float]] = [[self.rng.uniform(W * 0.3, W), self.rng.uniform(*CLOUD_SKY)]]
        self.cloud_gap = self.rng.uniform(*CLOUD_GAP)
        # 땅의 자갈 — (x, 땅 아래 깊이, 폭). 흘러가다 왼쪽으로 빠지면 오른쪽에서 다시 나온다.
        self.pebbles = [[self.rng.uniform(0, W), self.rng.choice((2, 4, 6)), self.rng.choice((2, 2, 4))]
                        for _ in range(18)]

    # -------------------------------------------------- 누르기
    def press_jump(self) -> None:
        if self.state == "ready":        # 첫 누르기 — 뛰어오르며 출발
            self._reset()
            self._jump()
        elif self.state == "run":
            if not self.jumping and not self.ducking:
                self._jump()
        elif self.state == "over" and self.over_t >= OVER_WAIT:
            self._reset()                # 다시 하기 — 뛰지 않고 그냥 달린다(크롬과 같다)
        self.holding = True

    def release_jump(self) -> None:
        self.holding = False
        if self.jumping:
            self._end_jump()

    def press_duck(self) -> None:
        self.down = True
        if self.state != "run":
            return
        if self.jumping:              # 공중이면 빨리 떨어진다 (내려앉으면 그대로 숙인다)
            if not self.fast_drop:
                self.fast_drop = True
                self.vy = -1.0
        else:
            self.ducking = True

    def release_duck(self) -> None:
        self.down = False
        self.ducking = False
        self.fast_drop = False

    def _jump(self) -> None:
        self.jumping = True
        self.reached_min = False
        self.fast_drop = False
        self.vy = JUMP_V + self.speed / 10

    def _end_jump(self) -> None:
        if self.reached_min and self.vy > DROP_V:
            self.vy = DROP_V

    # -------------------------------------------------- 한 걸음
    def step(self) -> None:
        self.t += 1
        if self.state == "ready":
            self._step_blink()
            return
        if self.state == "over":
            self.over_t += 1
            return
        self.run_t += 1
        if self.jumping:
            self._step_jump()
        if self.speed < SPEED_MAX:
            self.speed = min(SPEED_MAX, self.speed + ACCEL)
        self.distance += self.speed
        self._step_obstacles()
        self._step_scenery()
        before = self.flash_score
        self.flash_score = self.score // FLASH_EVERY * FLASH_EVERY
        if self.flash_score > before and self.flash_score > 0:
            self.flash = FLASH_FRAMES
            if self.flash_score % NIGHT_EVERY == 0:
                self.night = NIGHT_FRAMES
        elif self.flash > 0:
            self.flash -= 1
        if self.night > 0:
            self.night -= 1
        if self._collides():
            self._crash()

    def _step_jump(self) -> None:
        self.h += self.vy * (FAST_DROP if self.fast_drop else 1)
        self.vy -= GRAVITY
        if self.h > MIN_JUMP or self.fast_drop:
            self.reached_min = True
        if self.h > MAX_JUMP or self.fast_drop:
            self._end_jump()
        elif not self.holding:
            self._end_jump()
        if self.h <= 0:           # 내려앉았다 — ↓ 를 누른 채면 그대로 숙인다
            self.h = 0.0
            self.vy = 0.0
            self.jumping = False
            self.fast_drop = False
            self.ducking = self.down

    def _step_blink(self) -> None:
        if self.blink > 0:
            self.blink -= 1
            return
        self.next_blink -= 1
        if self.next_blink <= 0:
            self.blink = 8
            self.next_blink = self.rng.randint(*BLINK_EVERY)

    def _step_obstacles(self) -> None:
        for ob in self.obstacles:
            ob.x -= self.speed + ob.wobble
            if ob.kind == "bird" and self.t % FLAP_BEAT == 0:
                ob.frame ^= 1
        self.obstacles = [ob for ob in self.obstacles if ob.x + ob.w > 0]
        if self.run_t < CLEAR_FRAMES:
            return
        last = self.obstacles[-1] if self.obstacles else None
        if last is None:
            self._add_obstacle()
        elif not last.follow and last.x + last.w + last.gap < W:
            last.follow = True
            self._add_obstacle()

    def _add_obstacle(self) -> None:
        kinds = [k for k, v in KINDS.items() if self.speed >= v["min_speed"]]
        for _ in range(10):
            kind = self.rng.choice(kinds)
            recent = self.history[-MAX_DUP:]
            if len(recent) == MAX_DUP and all(k == kind for k in recent):
                continue
            break
        spec = KINDS[kind]
        count = self.rng.randint(1, MAX_GROUP) if self.speed > spec["multi"] else 1
        lift, wobble = 0, 0.0
        if kind == "bird":
            lift = self.rng.choice(self.lifts)
            wobble = self.rng.choice((-BIRD_WOBBLE, BIRD_WOBBLE))
        one_w, _ = size(spec["art"][0])
        min_gap = round(one_w * count * self.speed + spec["min_gap"] * GAP_COEF)
        gap = self.rng.randint(min_gap, round(min_gap * GAP_MAX))
        self.obstacles.append(Obstacle(kind, float(W), count, lift, wobble, gap))
        self.history = (self.history + [kind])[-MAX_DUP:]

    def _step_scenery(self) -> None:
        drift = self.speed * CLOUD_SPEED
        for c in self.clouds:
            c[0] -= drift
        cw, _ = size(CLOUD)
        self.clouds = [c for c in self.clouds if c[0] + cw > 0]
        last = self.clouds[-1] if self.clouds else None
        if len(self.clouds) < CLOUD_MAX and (last is None or last[0] < W - self.cloud_gap):
            self.clouds.append([float(W), self.rng.uniform(*CLOUD_SKY)])
            self.cloud_gap = self.rng.uniform(*CLOUD_GAP)
        for p in self.pebbles:
            p[0] -= self.speed
            if p[0] + p[2] < 0:
                p[0] += W + self.rng.uniform(0, 40)
                p[1] = self.rng.choice((2, 4, 6))
                p[2] = self.rng.choice((2, 2, 4))

    # -------------------------------------------------- 부딪힘
    def dino_runs(self):
        """지금 자세의 도트 덩이 — 판 좌표."""
        top = self.dino_y
        for rx, ry, rw, rh in _POSE_RUNS[self.pose]:
            yield DINO_X + rx, top + ry, rw, rh

    def _collides(self) -> bool:
        dx0, dy0 = DINO_X, self.dino_y
        dw, dh = size(POSES[self.pose])
        mine = None
        for ob in self.obstacles:
            # 먼저 그림 테두리끼리 — 안 겹치면 칸을 볼 것도 없다
            if ob.x >= dx0 + dw or ob.x + ob.w <= dx0 or ob.y >= dy0 + dh or ob.y + ob.h <= dy0:
                continue
            if mine is None:
                mine = list(self.dino_runs())
            for ox, oy, ow, oh in ob.hit_runs():
                for mx, my, mw, mh in mine:
                    if ox < mx + mw and mx < ox + ow and oy < my + mh and my < oy + oh:
                        return True
        return False

    def _crash(self) -> None:
        self.state = "over"
        self.over_t = 0
        self.jumping = False
        self.holding = False
        self.ducking = False
        self.fast_drop = False
        if self.score > self.best:
            self.best = self.score
            self.new_best = True

    # -------------------------------------------------- 그리는 쪽이 읽는 것
    @property
    def score(self) -> int:
        return int(self.distance * SCORE_COEF)

    @property
    def pose(self) -> str:
        """지금 자세 — POSES 의 열쇠."""
        if self.state != "run" or self.jumping:
            return "stand"
        beat = (self.run_t // RUN_BEAT) % 2
        if self.ducking:
            return "duck2" if beat else "duck1"
        return "run2" if beat else "run1"

    @property
    def eye(self) -> str:
        if self.state == "over":
            return "dead"
        if self.state == "ready" and self.blink > 0:
            return "blink"
        return "open"

    @property
    def dino_y(self) -> float:
        """공룡 그림 위끝."""
        return GROUND - self.h - size(POSES[self.pose])[1]

    @property
    def shown_score(self) -> int:
        """화면에 적을 점수 — 100점을 넘길 때마다 그 숫자에서 반짝인다(크롬과 같다)."""
        return self.flash_score if self.flash > 0 else self.score

    @property
    def score_visible(self) -> bool:
        """반짝이는 동안 켜졌다 꺼졌다 한다 (1/4초마다)."""
        return self.flash <= 0 or (self.flash // 15) % 2 == 0


# ---------------------------------------------------------------- 확인
def _bot(g: Game) -> None:
    """알아서 뛰는 공룡 — 가까운 장애물을 보고 뛰거나 숙인다(규칙이 이길 만한지 보는 용도)."""
    ahead = [ob for ob in g.obstacles if ob.x + ob.w > DINO_X]
    if not ahead:
        g.release_duck()
        return
    ob = ahead[0]
    dist = ob.x - (DINO_X + size(POSES["stand"])[0])
    if ob.kind == "bird" and ob.lift >= BIRD_LIFTS[2]:
        g.release_duck()
        return
    if ob.kind == "bird" and ob.lift == BIRD_LIFTS[1]:
        if dist < g.speed * 6:
            g.press_duck()
        return
    g.release_duck()
    if 0 < dist < g.speed * 9 and not g.jumping:
        g.press_jump()
    elif g.jumping and g.h > MAX_JUMP - 8:
        g.release_jump()


def _selftest(rounds: int = 8) -> None:
    import statistics

    scores = []
    for seed in range(rounds):
        g = Game(seed=seed)
        g.press_jump()
        g.release_jump()
        while g.state == "run" and g.run_t < FPS * 60 * 4:
            _bot(g)
            g.step()
        scores.append(g.score)
        print(f"씨앗 {seed}: {g.score}점 · 속도 {g.speed:.1f} · {g.run_t / FPS:.0f}초"
              + (" · 끝까지 달림" if g.state == "run" else ""))
    print(f"평균 {statistics.mean(scores):.0f}점")


if __name__ == "__main__":
    _selftest()
