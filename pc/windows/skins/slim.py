"""
초슬림 바 — 작업표시줄에 얹거나 화면 가장자리에 붙여 두는 낮고 긴 띠.
**창 높이를 작업표시줄 높이에 맞춘다** (기본 48px, 설정·배율에 따라 달라지는 값을 실측).
두 칸(5시간·주간)에 숫자와 눈금 게이지를 넣고, 오른쪽 끝에 번갈아 칸과 상태 점을 둔다.
왼쪽 세로 띠는 두 한도 중 더 급한 쪽 색. 오류일 때는 띠와 바탕이 빨강으로 바뀌고
번갈아 칸에 상태 문구가 대신 들어간다 (자리를 새로 만들지 않으므로 높이는 그대로).

    ┃ 5시간 17%   4시간 12분 후 │ 주간 56%   2일 07시간 후 │  Fable 7% ●
    ┃ ▪▪▪▪▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫     │ ▪▪▪▪▪▪▪▪▪▪▪▫▫▫▫┃▫▫▫▫▫     │

주간 게이지의 ┃ 는 '지금쯤' 눈금 — 주간 창이 흐른 만큼의 자리다. 채운 색이 눈금을
앞질렀으면 그만큼 빨리 쓰는 중. 숫자·판정은 우클릭 > 이번 주 사용 속도 에서 본다.

오른쪽 끝 두 가지:
- **번갈아 칸** — 한 줄뿐인데 보여 줄 것이 여럿이라 하나씩 바꿔 띄운다(모델별 한도 ·
  알림 · 오류). 칸보다 긴 글자는 **좌우로 훑어(pan)** 끝까지 보여 준다. 그래서 칸 자체는
  좁아도 된다 — 창 폭을 460 까지 줄인 근거다. **글자는 게이지 아래끝에 맞춰 아래 정렬.**
  ★ 훑는 글자가 옆 칸을 침범하지 않게, 이 칸만 **따로 캔버스**(`self.slot`)로 만들어
    거기 담는다. tk 캔버스는 제 테두리에서 잘라 주므로 이게 유일하게 깔끔한 길이다
    (한 캔버스에 그리면 도형 단위 클리핑이 없어 마스코트·게이지 위로 글자가 흘러넘친다).
- **상태 점** — 오른쪽 위 구석. 마지막 조회가 됐으면 초록, 안 됐으면 빨강. 옛 '03:07 기준'
  자리를 대신한다(시각은 작업표시줄 시계에 있으니 지금 것인지만 알면 된다).
  ★ 점 자체는 **앱이 그린다**(`status_spot()` 으로 자리만 알려 준다) — 새로고침 스피너가
    같은 자리에서 그 둘레를 도는 링이라, 둘을 한 캔버스에 두어야 겹쳐도 조화롭다.

폭은 "100%" · "6일 23시간 후" 같은 최대 길이 문자열을 실제 글꼴로 재서 칸을 나눈다.
두 한도 칸이 제 몫을 먼저 가져가고, 번갈아 칸은 남는 만큼만 쓴다(모자라면 훑는다).
"""

from __future__ import annotations

import math
import random
import tkinter as tk
from tkinter import font as tkfont

from cooldown_core import Usage, five_due, pace

from .base import (
    KR,
    MARK_W,
    NUM,
    P,
    Skin,
    mark_x,
    taskbar_height,
    tone,
    worst,
)

# ---------------------------------------------------------------- 치수
# 세로 배치는 작업표시줄 높이에서 계산한다 (build 참고). 가로만 여기서 고정.
# 왼쪽 끝엔 상태 띠(accent, 한도 색). 마스코트는 **주간 칸과 오른쪽(모델/기준) 사이
# 빈 틈(MGAP)** 에 앉는다 — 그 자리를 미리 비워 두므로 긴 모델명이 와도 안 겹친다.
# 마스코트는 상태와 무관하게 클로드 코랄색으로 고정 — 상태는 띠가 맡는다.
ACC = 4  # 왼쪽 상태 띠 (한도 색)
PAD_L = ACC + 12  # 내용 시작 (띠 뒤)
PAD_R = 10
# 주간 칸 ↔ 번갈아 칸 사이의 틈 — 여기 가운데에 마스코트가 앉는다.
# ★ **42 보다 줄이지 말 것** — 마스코트는 팔까지 11칸(22px)인데 숨쉬기·기지개로
#   부풀고 계단식 기울임으로 윗줄이 옆으로 밀려, 실제로는 30px 남짓 쓴다.
MGAP = 42
# 상태 점(과 그 둘레를 도는 새로고침 링)이 앉는 오른쪽 위 구석. 앱이 그리므로 자리만 잡는다.
DOT_INSET = 12
MIN_SLOT = 52  # 번갈아 칸이 아무리 좁아도 이만큼은 준다 (그 아래는 훑어도 못 읽는다)
MASCOT_U = 2    # 도트 한 칸 (px). 팔까지 가로 11칸(22px) · 세로 8칸(16px)
MASCOT_COLOR = "#d97757"  # 클로드 코랄 — 밝게/어둡게 양쪽에서 그대로 쓴다
# **박자 맞히기** — 통통 튀다 **가장 아래로 내려앉는 순간** 콕 찌르면 박자가 맞은 것이다.
# 이어 갈수록 콤보가 쌓여 더 높이 뛰고 반짝이도 화려해진다. 박자를 놓치면 처음부터.
# ★ **깐깐하게 잡는다** — 튀는 한 주기(약 13프레임)에서 **바닥에 멎는 3프레임**(≈0.14초)
#   만 인정한다. 아래로 충분히 내려갔고(`BEAT_AT`) 그 자리에서 거의 멎어 있을 때
#   (`|vy| <= BEAT_V`). 아무 때나 쳐도 되면 도전하는 맛이 없다.
BEAT_AT = 4.5         # 제자리보다 이만큼 아래(px)까지 내려가야
BEAT_V = 1.7          # 그 자리에서 이만큼 느려야 (되돌아 오르는 꼭짓점)
BEAT_WINDOW = 20      # 이 프레임 안에 다시 맞혀야 이어진다 — 늦으면 끊긴다
COMBO_MAX = 5         # 5단
COMBO_JUMP = 0.45     # 콤보 한 번마다 조금 더 높이 (상한 MAX_VY 에 걸린다)
# ★ **한 단을 올리는 데 두세 번 맞혀야 한다.** 맞히는 동안은 **소박하게** 반짝이만 조금,
#   그 단의 마지막 한 방에서 재주가 나온다 — 그래야 올라가는 맛이 있다.
TIER_HITS = (2, 2, 3, 3, 3)   # 각 단에 필요한 성공 횟수 (다 모으면 13번)
TIER_UP = [sum(TIER_HITS[:i + 1]) for i in range(len(TIER_HITS))]  # 단이 오르는 누적 횟수
# **콤보 단마다 다른 재주.** (프레임 수, 세로 회전 바퀴, 가로 회전 바퀴)
#   1단 반짝이만 · 2단 앞구르기 · 3단 두 바퀴 · 4단 팽이돌기 · 5단 둘 다 + 폭죽
TRICKS = {
    1: (0, 0, 0),
    2: (13, 1, 0),
    3: (16, 2, 0),
    4: (14, 0, 2),
    5: (18, 2, 2),
}
TRICK_TRAIL = 2       # 재주 부리는 동안 이 프레임마다 반짝이 하나씩 흘린다
# 5단까지 다 채우면 **슬림 바 전체에 축하 폭죽**을 터뜨리고 콤보를 끝낸다.
# ★★ 그동안은 **누르는 걸 안 받는다**(`react`·`hold` 무시) — 완주는 짧은 장면이라
#   중간에 끼어들면 축하가 반응 놀이로 되돌아간다. 대신 **클로디도 가만있지 않고
#   폴짝폴짝 만세를 부르며 같이 축하한다**(`_finale` 가지).
FINALE_FRAMES = 68    # 폭죽·축하가 이어지는 프레임 (약 3초)
FINALE_EVERY = 4      # 이 프레임마다 한 발
FINALE_DOUBLE = 2     # 이 배수 발마다 **두 발이 겹쳐** 터진다
FINALE_PER = (9, 15)  # 한 발에 뿜는 반짝이 (발마다 다르게)
FINALE_SPREAD = (0.55, 1.35)  # 발마다 퍼지는 정도도 다르다 — 같으면 한 발을 복사한 듯하다
FINALE_BIG = (1.4, 2.4)  # 축하 반짝이는 수명을 길게 줘 더 크고 오래 남는다
FINALE_HOP = 11       # 축하하는 동안 이 프레임마다 폴짝 (통통 튀는 주기와 맞는 값)
FINALE_POP = 1.9      # 그 폴짝의 힘 (`JUMP_IMPULSE` 배수). 0.95 는 4px 라 뛰는 줄 몰랐다
# ★ **만세는 프레임 수로 세지 않고 '떠 있으면 든다'** — 뛰는 것과 팔이 따로 놀면
#   신난 게 아니라 헛도는 것으로 보인다. 뜬 김에 들고 내려앉으면 내린다.
FINALE_CHEER = 1.0    # 이만큼(px) 떠 있으면 두 팔 번쩍
FRAME_MS = 45  # 애니메이션 한 프레임 (약 22fps — 물리가 부드럽게 이어지게)
# 눌림 반응은 용수철처럼 — 누를 때마다 위로 튀는 '속도'를 더한다. 연타하면 힘이
# 쌓여 자연스럽게 출렁이고(뚝 끊기지 않고), 너무 많이 치면 기절한다.
JUMP_IMPULSE = 2.6    # 아무 데나 눌렀을 때 위로 튀는 속도
POKE_MULT = 2.6       # 마스코트를 직접 콕 찌르면 반응이 이만큼 커진다
# 뛸 때 몸이 늘었다 눌린다(스쿼시·스트레치) — 이게 없으면 그냥 위아래로 미끄러질 뿐이라
# 점프에 손맛이 없다. **세로로만** 늘리고 줄인다(좌우로 흔드는 건 안 쓴다).
SQUASH = 0.055        # 속도 1당 늘어나는 비율
SQUASH_MAX = 0.34     # 최대로 늘어나는 정도
SQUASH_MIN = -0.20    # 최대로 눌리는 정도
# **꾹 누르고 있으면 눌린다.** 손가락에 눌려 점점 납작해지고, 떼면 용수철처럼 튕겨 오른다.
# ★★ 여기에 '기 모아 뛰기' · '기 모아 쏘기' · '쓰다듬기(하트)' 를 차례로 붙여 봤다가 전부 뺐다.
#   소품이나 기호를 얹으면 게임 같거나 유치했다. **누르니까 눌린다** — 그 이상 필요 없다.
PRESS_FRAMES = 26     # 이만큼이면 최대로 눌린다
PRESS_FLAT = 0.46     # 최대로 납작해지는 정도
# ★ 꾹 눌렀다 떼면 **작업표시줄 위로 아예 사라졌다 돌아올 만큼** 튄다 — 그냥 한 번
#   클릭한 것과 다를 게 없으면 참았다 놓는 뜻이 없다.
PRESS_POP = 18.0      # 떼면 튕겨 오르는 힘 (눌린 만큼 곱해진다)
PRESS_BURST = 0.35    # 이만큼 넘게 눌렸다 떼면 **팡** 터진다
LAUNCH_LIFT = 70.0    # 날아오르는 동안엔 창 안으로 가두지 않는다 (칸이 아니라 px)
LAUNCH_FRAMES = 46    # 이 프레임 동안은 가둠을 푼다
# ★ **창 밖으로 나가는 건 꾹 누르기의 특전이다.** 콤보로는 안 나간다 — 연타로 자꾸 나가면
#   화면에 없는 시간이 길어져 굼떠 보인다. 콤보의 상은 높이가 아니라 **공중제비와 반짝이**다.
MAX_VY = 8.2          # 그냥 누르기·콤보로 낼 수 있는 최대 속도 (꾹 누르기는 예외)
# ★ **좌우로 흔드는 움직임은 뺐다** — 늘 살랑거리니 산만하고 안 예뻤다.
#   누를 때 도는 힘도 0 이다. 남은 좌우 움직임은 **가끔 하는 고개 갸웃**(_tilt) 과
#   노트북 볼 때 기울이는 것(TYPE_LEAN) 뿐이다. 되살리지 말 것.
SPIN_IMPULSE = 0.0
SPRING_K = 0.20       # 제자리로 당기는 용수철 세기
SPRING_DAMP = 0.14    # 감쇠 (0=계속 튐, 1=즉시 멈춤)
# 직접 콕 찌른 게 이만큼 쌓여야 기절 (딴 데 클릭은 안 쌓임). 한 번에 +2, 매 프레임
# CLICK_DECAY 만큼 식으므로 **초당 1.3번보다 빠르게** 계속 찔러야 는다.
# ★ 어쩌다 기절하면 놀라니까 높게 잡는다 — 작정하고 두드려야 뻗는다(약 12초 연타).
FAINT_AT = 46.0
CLICK_DECAY = 0.12    # 눌림 누적이 프레임마다 이만큼 식는다
FAINT_FRAMES = 60     # 기절 지속 (약 2.7초)
# 기절 땐 조금 부풀려 X_X 눈이 보이게 한다. ★ 1.35 는 딴 친구가 나타난 것처럼 커 보였다 —
# 눈이 보일 만큼만 키운다(도트 한 칸 2px → 2.3px).
FAINT_SCALE = 1.15
SURPRISE_FRAMES = 7   # 직접 찔렸을 때 눈이 동그래지는 프레임 수
HIT_R = 15            # 이 반경 안을 누르면 '직접 찌름'으로 본다 (px — 도트 그림 크기에 맞춤)
# 반짝이 — **크게 뛸 때만** 터진다 (폰 쪽과 같은 규칙).
# ★★ 누를 때마다 뿜었더니 연타에서 앞것과 겹쳐 지저분했다. 지금은 **박자를 맞혔을 때만**
#   나온다(`BEAT_AT` — 가장 아래로 내려앉는 순간에 콕). 이어 갈수록 콤보가 쌓여 화려해진다.
# ★ 모양은 폰(`Mascot.burst`)과 같은 결: 부채꼴로 가지런히 퍼뜨리면 도형을 그린 것처럼
#   보이므로, 머리 둘레에 **흩뿌려 놓고 위로 떠오르며 작아지게** 한다.
# 자리는 두 가지다 — **크게 뛰면 머리 위로, 그냥 콕 찌르면 발밑으로**(먼지처럼).
# 같은 자리에서 크기만 다르면 둘이 구별이 안 돼, 아예 나오는 곳을 갈랐다.
SPARK_LIFE = 22       # 반짝이 수명 (프레임)
SPARK_POKE = 6        # 박자를 맞췄을 때 뿜는 기본 개수 (콤보만큼 더 나온다)
SPARK_DUST = 3        # 그냥 콕 찔렀을 때 발밑에 이는 먼지
SPARK_WAKE = 7        # 기절에서 깨어날 때 (펑)
SPARK_COOL = 26       # 한 번 뿜으면 이만큼(프레임 ≈ 1.2초)은 다시 안 뿜는다
SPARK_SPREAD = 8.0    # 흩뿌리는 가로 폭 (px)
SPARK_SIZE = 0.55     # 반짝이 크기 (도트 칸 대비). 작을수록 가루 같다.
SPARK_GRAV = 0.035    # 떠오르던 것이 처지는 정도

# ---------------------------------------------------------------- 딴짓(오래 심심할 때)
# 한참 아무도 안 건드리면 **혼자 뭔가에 열중한다** — 노트북 두드리기 · 낮잠 · 공 놀이,
# 아니면 아예 자리를 비운다. 위젯을 누르면 곧바로 하던 걸 접고 돌아온다.
# ★ 자주 하면 산만하다 — `DEEP_IDLE` 은 넉넉히 잡고, **딴짓 중에는 `_quiet` 를 안 센다**
#   (안 그러면 하나가 끝나자마자 다음 것이 곧바로 이어진다).
DEEP_IDLE = 1500      # 이만큼(프레임 ≈ 68초) 아무 반응이 없으면 딴짓을 시작한다
ACT_MIN, ACT_MAX = 200, 400      # 한 가지 딴짓 지속 (9~18초)
# ★★ **딴짓은 곧바로 지우지 않는다 — 접는 동안(`ACT_EXIT`)을 둔다.** 한 프레임에 갈아
#   끼우면 몸이 `TYPE_SHIFT`(8px) 옆으로 튀고 노트북·공이 허공에서 사라진다(실제로 그랬다).
#   이 동안 소품을 치우고 몸을 제자리로 미끄러뜨리며 **가로로 납작해졌다 펴져** 돌아앉는다.
ACT_EXIT = 8          # 하던 걸 접고 돌아앉는 데 걸리는 프레임 (약 0.36초)
AWAY_MIN, AWAY_MAX = 170, 340    # 자리 비움 지속 (8~15초)
AWAY_LEAD = 20        # 내려가기 전에 손 흔드는 프레임 (인사하고 간다)
SINK_FRAMES = 10      # 아래로 내려가는 데 걸리는 프레임
RUSH_BACK = 6         # 자리 비운 사이 부르면 이만큼 만에 호다닥 올라온다
RUN_DIST = 15.0       # 부르면 이만큼 왼쪽에서 **달려서** 제자리로 온다 (px)
RUN_FRAMES = 16       # 달려오는 데 걸리는 프레임
RUN_BEAT = 2          # 이 프레임마다 발을 바꾼다
TYPE_BEAT = 3         # 이 프레임마다 손을 바꿔 두드린다
NAP_EVERY = 30        # 낮잠 중 이 프레임마다 z 하나
NAP_LIFE = 36         # z 가 떠 있는 프레임
BALL_PERIOD = 26      # 공을 던졌다 받는 주기 (프레임)
BALL_H = 13.0         # 공이 오르는 높이 (px)
BALL_R = 1.6          # 공 반지름 (도트 칸)
GAP = 16  # 칸 사이
SEG_GAP = 2  # 눈금 사이
MARK_OUT = 2  # '지금쯤' 눈금이 게이지 위아래로 삐져나오는 길이
LV_GAP = 6  # 항목 이름 ↔ 숫자
VR_GAP = 10  # 숫자 ↔ 남은시간 최소 간격
LBL_BASE = 2  # 9pt 글자를 큰 숫자의 기준선에 맞추는 보정
SM_BASE = 3  # 8pt 글자 보정
ROW_GAP = 6  # 윗줄 ↔ 게이지

# ---------------------------------------------------------------- 번갈아 뜨는 칸
# 오른쪽 자리는 한 줄인데 보여 줄 것은 여럿이다(모델별 한도 · 주간 적정선 · 알림 · 오류).
# 그래서 하나씩 번갈아 띄운다 — 보여 주던 것이 위로 밀리며 바탕색에 스며들고,
# 다음 것이 아래에서 떠오른다. **칸보다 긴 글자는 좌우로 훑어** 끝까지 보여 준다.
SLOT_HOLD = 4200  # 한 가지를 보여 주는 시간 (ms). 훑는 것은 훑는 시간이 더해진다.
SLOT_STEP = 35  # 애니메이션 한 프레임 (ms)
SLOT_FRAMES = 6  # 나가기·들어오기 각각의 프레임 수
SLOT_RISE = 4  # 밀려 나가는 거리 (px)
PAN_WAIT = 950  # 훑기 전·후로 멈춰 서 있는 시간 (ms) — 머리와 꼬리를 읽을 틈
PAN_SPEED = 44  # 훑는 속도 (px/초). 눈으로 따라갈 만큼 느리게.
PAN_MAX = 2.8  # 칸 폭의 이 배까지만 훑는다 — 더 길면 … 로 줄인다 (하염없이 안 흐르게)
# ★ 몇 px 만 넘칠 때도 **그 시간을 다 써서 천천히** 민다. 속도대로 하면 4px 를
#   0.1초에 밀어 버려 글자가 흠칫 떠는 것처럼 보인다 (실제로 그랬다).
PAN_MIN_FRAMES = 14  # 약 0.5초
MAX_SLOTS = 4  # 한 바퀴에 넣는 최대 가짓수 (더 있으면 뒤를 자른다)

# 폭을 정할 때 쓰는 최대 길이 표본
MAX_VALUE = "100%"
# 주간은 '6일 23시간 후'보다 하루 안쪽으로 들어온 '23시간 59분 후'가 더 넓다.
MAX_LEFT = ("4시간 59분 후", "23시간 59분 후")
# 번갈아 칸이 '자르지 않고' 담아 주면 좋은 것들. 못 담아도 훑어서 보여 주므로
# 이건 최소 요구가 아니라 **바라는 폭**이다 (두 한도 칸이 먼저 제 몫을 가져간다).
MAX_SCOPED = "Claude Opus 99%"
MAX_ERROR = "재로그인 필요"
MAX_NOTICE = "23:59 핑 실패"


# ---------------------------------------------------------------- 마스코트 도트 그림
# 클로디는 **도트(픽셀) 그림**이다. 한 칸이 MASCOT_U px 인 격자에 네모만 찍어 그리므로
# 20~30px 에서도 획이 뭉개지지 않는다. 좌표는 전부 '몇 번째 칸'(col, row)이고,
# 실제 픽셀 변환은 `_sprite` 한 곳에서만 한다.
#
#   col: 0..8 이 머리(가로 9칸), 그 밖 -1 / 9 가 팔이 뻗는 자리
#   row: 0..5 가 머리, 6·7 이 다리와 발
#
# **몸통도 입도 없다** — 큰 머리에 짧은 팔 둘·다리 둘만 붙은 친구.
# 표정은 **눈으로만** 낸다(옛 클로디도 눈이 얼굴의 거의 전부였다).
#
# ★ 머리는 **9칸**이라야 한다. 7칸으로 줄이면 눈 구멍 둘이 살을 다 먹어 머리가
#   가로로 갈라져 보인다(게 집게처럼). 눈 옆·사이에 살이 남아야 얼굴로 읽힌다.
# ★ 팔은 **눈 아래**에서 나간다. 눈 높이에 걸치면 수염처럼 보인다.
HEAD = (
    "..#####..",   # 0 머리 위 (모서리 깎음)
    ".#######.",   # 1
    "#########",   # 2 눈
    "#########",   # 3 눈
    "#########",   # 4 팔이 여기서 옆으로
    ".#######.",   # 5 턱
)
LEGS = ("..#...#..", ".##...##.")       # 평소 — 다리 둘에 발
LEGS_WIDE = (".#.....#.", "##.....##")  # 기절 — 다리가 벌어져 주저앉는다
LEGS_RUN = ("...#.#...", "..##.##..")   # 달릴 때 — 다리가 모였다 (LEGS 와 번갈아 쓴다)

# 옆으로 돌아앉아 두드리는 **노트북**.
# ★★ **이것만은 도트 격자를 쓰지 않는다.** 한 칸이 2px 이라 노트북이 들어갈 자리(16×15px)에
#   칸이 8×7 밖에 안 나온다 — 그 해상도로는 무슨 모양·색을 해도 판때기나 쐐기였다
#   (작게·크게·정면·3/4·옆모습·회색·코랄·호박색 화면까지 다 해 보고 내린 결론).
#   **1px 단위 다각형 둘(기운 덮개 + 얇은 받침)** 이면 그 자리에서 바로 노트북이 된다.
#   마스코트 본체는 도트 그대로다 — 폰 앱과 표를 공유하므로 격자를 지킨다.
# ★ 좌표는 몸 한가운데(cx, cy) 기준 px. 노트북+몸을 합친 그림이 **마스코트 자리
#   (구분선~번갈아 칸, 35px) 안에** 들어가야 하므로 몸을 `TYPE_SHIFT` 만큼 오른쪽으로 물린다.
TYPE_SHIFT = 8        # 노트북까지 한 그림이 되도록 몸을 오른쪽으로 (px)
LAP_BASE = (-24, 6, -8, 9)          # 받침(키보드) — 왼쪽 x, 윗 y, 오른쪽 x, 아랫 y
LAP_LID = ((-22, 6), (-12, 6), (-15, -5), (-25, -5))  # 덮개 — 위가 왼쪽으로 기운 평행사변형
# 타이핑하는 팔 — 몸에서 왼쪽 아래로 뻗어 받침에 닿는다. 두 자세를 번갈아 두드린다.
# ★ 기본 팔(ARM)은 한 칸뿐이라 노트북까지 안 닿는다 — 이때만 길게 뻗은 팔을 따로 쓴다.
TYPE_ARM = (
    ((-1, 4), (-2, 5), (-3, 6)),   # 손을 내려 두드린다
    ((-1, 4), (-2, 4), (-3, 5)),   # 손을 들었다
)

# 낮잠 — 머리 위로 떠오르는 z.
# ★ **3×3 으로 그리지 말 것** — `###/.#./###` 는 z 가 아니라 I(공업 '工')로 읽힌다.
#   가운데 칸이 정확히 한가운데라 기울기가 안 보이기 때문. **4×4 라야 대각선이 산다.**
NAP_Z = (
    "####",
    "..#.",
    ".#..",
    "####",
)

# 팔은 **한 칸**이다(짧게). **왼팔 기준**이고 오른팔은 좌우로 뒤집어 쓴다(`8 - col`).
# -1 번쩍 / 0 옆으로 / 1 축 늘어뜨림
# ★ 팔 칸은 **그 줄의 머리 끝에 닿아야** 한다. 안 그러면 한 칸 떨어져 떠 보인다
#   (줄마다 머리 폭이 달라서 팔이 내려갈수록 안쪽 칸으로 붙는다).
ARM = {
    -1: ((-1, 3),),
    0: ((-1, 4),),
    1: ((0, 5),),
}

# 눈은 바탕색으로 파낸 칸이다 (오류 시 붉은 바탕에서도 얼굴이 남는다).
EYES = {
    "idle": ((2, 2), (3, 2), (2, 3), (3, 3), (5, 2), (6, 2), (5, 3), (6, 3)),
    "blink": ((2, 3), (3, 3), (5, 3), (6, 3)),                     # — —
    # 눈웃음은 **넓고 낮은 띠**(가늘게 뜬 눈)다. ∧ 모양을 칸으로 찍으면 이 크기에선
    # 떨어진 점 셋으로 보여 얼굴이 아니라 얼룩이 된다.
    "grin": ((1, 3), (2, 3), (3, 3), (5, 3), (6, 3), (7, 3)),
    "surprise": ((1, 2), (2, 2), (3, 2), (1, 3), (2, 3), (3, 3),   # 크게 뜬 눈
                 (5, 2), (6, 2), (7, 2), (5, 3), (6, 3), (7, 3)),
    # 열중 — 아랫줄만 남겨 화면을 내려다보는 눈. 깜빡임과 달리 안쪽 한 칸이 위로 붙어
    # '감은 것'이 아니라 '내려다보는 것'으로 읽힌다.
    "focus": ((2, 3), (3, 3), (3, 2), (5, 3), (6, 3), (5, 2)),
    # 옆모습 — **눈 하나만** 왼쪽에 (노트북 쪽으로 돌아앉았을 때).
    # 두 눈을 그대로 두면 정면인데 물건만 옆에 놓인 꼴이 된다.
    "side": ((1, 2), (2, 2), (1, 3), (2, 3)),
    "faint": ((1, 2), (3, 2), (2, 3), (1, 4), (3, 4),              # X_X
              (5, 2), (7, 2), (6, 3), (5, 4), (7, 4)),
}

SPRITE_H = (len(HEAD) + len(LEGS)) * MASCOT_U   # 도트 그림 전체 높이 (px)


def _clip(text: str, font: tkfont.Font, maxw: int) -> str:
    """maxw 를 넘으면 뒤를 잘라 … 를 붙인다. 자리가 없으면 아예 비운다(겹침 방지)."""
    if maxw <= 0:
        return ""
    if font.measure(text) <= maxw:
        return text
    while text and font.measure(text + "…") > maxw:
        text = text[:-1]
    return text + "…"


def _fit(text: str, font: tkfont.Font, maxw: int) -> str:
    """'Claude Sonnet 4.5 12%' 처럼 길면 뒤 퍼센트는 남기고 이름만 줄인다."""
    if font.measure(text) <= maxw:
        return text
    head, _, tail = text.rpartition(" ")
    while head and font.measure(f"{head}… {tail}") > maxw:
        head = head[:-1]
    return f"{head}… {tail}" if head else _clip(text, font, maxw)


def _mix(a: str, b: str, t: float) -> str:
    """두 색 사이 (t=0 이면 a, 1 이면 b). 글자를 바탕색으로 스미게 할 때 쓴다 —
    tk 캔버스 글자에는 투명도가 없어서, 색을 바탕 쪽으로 당겨 페이드를 흉내 낸다."""
    t = max(0.0, min(1.0, t))
    try:
        x = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
        y = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    except (ValueError, IndexError):  # 이름 있는 색(#rrggbb 가 아님) — 섞지 않는다
        return b if t > 0.5 else a
    return "#%02x%02x%02x" % tuple(int(p + (q - p) * t) for p, q in zip(x, y))


# ---------------------------------------------------------------- 한 칸
class Cell:
    """한 한도 — 이름 / 숫자 / 남은시간 한 줄 + 그 아래 눈금 게이지.

    자리는 만들 때 한 번 잡고, 이후에는 글자와 색만 바꿔 끼운다.
    """

    def __init__(self, skin: SlimSkin, x: int, w: int, label: str):
        self.c = skin.c
        self.f_value = skin.f_value
        self.f_small = skin.f_small
        self.x, self.w = x, w

        self.c.create_text(
            x, skin.top_y + LBL_BASE, text=label, anchor="w",
            font=skin.f_label, fill=P.label,
        )
        self.vx = x + skin.f_label.measure(label) + LV_GAP
        self.value = self.c.create_text(
            self.vx, skin.top_y, text="--", anchor="w", font=self.f_value, fill=P.faint
        )
        self.left = self.c.create_text(
            x + w, skin.top_y + SM_BASE, text="", anchor="e",
            font=self.f_small, fill=P.sub,
        )

        count = max(8, w // 8)
        pitch = w / count
        seg_w = max(3.0, pitch - SEG_GAP)
        self.segs = [
            self.c.create_rectangle(
                x + i * pitch, skin.bar_y,
                x + i * pitch + seg_w, skin.bar_y + skin.bar_h,
                fill=P.track, width=0,
            )
            for i in range(count)
        ]

        # '지금쯤' 눈금 — 칸 사이 틈에 떨어져도 보이게 눈금들 **뒤에** 만들어(맨 위)
        # 위아래로 MARK_OUT 만큼 삐져나오게 긋는다. 안 쓸 땐 숨긴다.
        self.mark_y0 = skin.bar_y - MARK_OUT
        self.mark_y1 = skin.bar_y + skin.bar_h + MARK_OUT
        self.mark = self.c.create_rectangle(
            0, 0, 0, 0, fill=P.title, width=0, state="hidden"
        )

    def set(self, pct: float | None, left: str, due: float | None = None) -> None:
        color = tone(pct)
        value = "--" if pct is None else f"{pct:.0f}%"
        self.c.itemconfigure(self.value, text=value, fill=color)

        room = int(self.x + self.w - (self.vx + self.f_value.measure(value) + VR_GAP))
        self.c.itemconfigure(
            self.left,
            text=_clip(left, self.f_small, room),
            fill=P.sub if pct is not None else P.faint,
        )

        # 내림이라 꽉 찬 게이지는 100% 뿐이다. 값이 있으면 아무리 작아도 한 칸은 켠다.
        # (반올림이면 98~100%가 모두 꽉 참으로 보여 한도 소진 여부를 구분 못 한다.)
        n = len(self.segs)
        filled = 0 if not pct else max(1, min(n, int(pct * n / 100)))
        for i, seg in enumerate(self.segs):
            self.c.itemconfigure(seg, fill=color if i < filled else P.track)

        if due is None:
            self.c.itemconfigure(self.mark, state="hidden")
        else:
            x = self.x + mark_x(due, self.w)
            self.c.coords(self.mark, x, self.mark_y0, x + MARK_W, self.mark_y1)
            self.c.itemconfigure(self.mark, state="normal", fill=P.title)


# ---------------------------------------------------------------- 스킨
class SlimSkin(Skin):
    key = "slim"
    name = "슬림 바 (작업표시줄용)"
    # 두 한도 칸이 제 몫(need_cell×2 ≈ 324px)을 가져가고 남는 만큼이 번갈아 칸이다.
    # ★ **긴 글자는 잘리지 않고 훑어서** 보여 주므로 이 폭을 늘릴 까닭이 없다 —
    #   작업표시줄에서 자리를 덜 먹는 쪽이 낫다. (520 까지 넓혔다가 되돌린 값)
    #   더 줄이면 두 한도 칸의 '23시간 59분 후' 부터 잘린다.
    width = 460
    dockable = True

    def build(self, parent: tk.Misc) -> None:
        self.f_label = tkfont.Font(parent, family=KR, size=9)
        self.f_value = tkfont.Font(parent, family=NUM, size=13, weight="bold")
        self.f_small = tkfont.Font(parent, family=KR, size=8)
        self.f_msg = tkfont.Font(parent, family=KR, size=9, weight="bold")

        # 창 높이를 작업표시줄에 맞추고, 그 안에서 세로 배치를 나눈다.
        # 작은 작업표시줄(40px)이든 고배율(60px 이상)이든 같은 비율로 앉는다.
        self.h = taskbar_height()
        row_h = self.f_value.metrics("linespace")
        self.bar_h = 6 if self.h >= 44 else 5
        slack = max(0, self.h - row_h - ROW_GAP - self.bar_h)
        top = slack * 45 // 100  # 위가 조금 좁아야 안정돼 보인다
        self.top_y = top + row_h // 2
        self.bar_y = top + row_h + ROW_GAP
        self.div_top = top
        self.div_bot = self.bar_y + self.bar_h

        self.c = tk.Canvas(
            parent, width=self.width, height=self.h, bg=P.bg,
            highlightthickness=0, bd=0,
        )
        self.c.pack(fill="both", expand=True)

        # 최대 길이 문자열을 실제 글꼴로 재서 폭을 나눈다.
        # 두 칸이 필요한 만큼 먼저 가져가고, 오른쪽 칸은 남은 폭을 제 몫만큼만 쓴다.
        need_cell = max(
            self.f_label.measure(label)
            + LV_GAP
            + self.f_value.measure(MAX_VALUE)
            + VR_GAP
            + self.f_small.measure(left)
            for label, left in zip(("5시간", "주간"), MAX_LEFT)
        )
        want_right = max(
            self.f_small.measure(MAX_SCOPED),
            self.f_small.measure(MAX_NOTICE),
            self.f_msg.measure(MAX_ERROR),
        )
        # 가로: [띠] 5시간칸 |GAP| 주간칸 |MGAP(마스코트)| 번갈아칸.
        # 두 한도 칸이 먼저 제 몫을 가져가고, 남는 만큼이 번갈아 칸이다.
        # (상태 점은 오른쪽 위 구석이라 이 줄의 가로를 먹지 않는다)
        avail = self.width - PAD_L - PAD_R - GAP - MGAP
        self.right_w = min(want_right, max(MIN_SLOT, avail - need_cell * 2))
        cell_w = (avail - self.right_w) // 2

        self.accent = self.c.create_rectangle(0, 0, ACC, self.h, fill=P.track, width=0)

        x1 = PAD_L
        x2 = PAD_L + cell_w + GAP
        rx = self.width - PAD_R
        self.five = Cell(self, x1, cell_w, "5시간")
        self.week = Cell(self, x2, cell_w, "주간")
        week_end = x2 + cell_w
        right_x0 = week_end + MGAP  # 번갈아 칸 왼쪽 경계
        # 구분선: 5시간|주간, 그리고 주간|마스코트틈 (오른쪽은 마스코트가 가른다)
        for dx in (x1 + cell_w + GAP // 2, week_end + 7):
            self.c.create_line(dx, self.div_top, dx, self.div_bot, fill=P.line, width=1)

        # 번갈아 칸은 **아래 정렬** — 글자 밑선을 게이지 아래끝(div_bot)에 맞춘다.
        # 가운데에 띄우면 두 한도 칸의 두 줄 사이에 붕 떠 보인다.
        line = self.f_small.metrics("linespace")
        slot_h = line + SLOT_RISE * 2
        self.slot_h = slot_h
        # ★ 훑는 글자가 옆으로 흘러넘치지 않게 이 칸만 따로 캔버스로 둔다 (테두리에서 잘림)
        self.slot = tk.Canvas(
            self.c, width=self.right_w, height=slot_h, bg=P.bg,
            highlightthickness=0, bd=0,
        )
        self.c.create_window(rx, self.div_bot + SLOT_RISE, window=self.slot, anchor="se")
        self.model = self.slot.create_text(
            self.right_w, slot_h / 2, text="불러오는 중", anchor="e",
            font=self.f_small, fill=P.faint,
        )

        # 상태 점 자리 — 오른쪽 위 구석. 그리는 건 앱이 한다(새로고침 링과 한 캔버스).
        self.dot_spot = (self.width - DOT_INSET, DOT_INSET)

        # 마스코트는 구분선과 번갈아 칸 사이 빈 틈 가운데에 앉는다.
        # **맨 마지막에 켠다** — 매 프레임 다시 그리므로 늘 맨 위에 온다.
        self.mascot_cx = (week_end + 7 + right_x0) // 2
        self._slot_init()
        self._start_mascot()  # 코랄 도트 마스코트 — 통통 튀고 눌리면 폴짝

        self.five.set(None, "")
        self.week.set(None, "")

    # -------------------------------------------------- 번갈아 뜨는 오른쪽 칸
    # 한 자리를 여럿이 나눠 쓴다. `show()` 가 늘 있는 것들(모델별·적정선)을 세우고,
    # `notice()` 가 있을 때만 알림을 얹는다. 둘은 잇달아 불리므로 **바로 반영하지 않고**
    # 한 박자 뒤(after_idle)에 한 번만 반영한다 — 안 그러면 갱신마다 알림이 사라졌다
    # 다시 붙어 순서가 처음으로 되감긴다.
    # 한 가지가 뜨는 흐름:  들어오기 → 멈춤 → (길면 훑기 → 멈춤) → 나가기 → 다음
    def _slot_init(self) -> None:
        self._slot: list[tuple[str, str, bool]] = []  # (글자, 색, 굵게?)
        self._slot_base: list[tuple[str, str, bool]] = []
        self._slot_notice: tuple[str, str, bool] | None = None
        self._slot_i = 0
        self._slot_on = True
        self._slot_pan = 0.0  # 지금 것이 칸보다 넘치는 폭 (0 이면 훑지 않는다)
        self._slot_pending = None
        # build 가 다시 불려도(테마 전환) 세대는 **올리기만** 한다 — 0 으로 되돌리면
        # 옛 캔버스에 걸려 있던 콜백이 새 세대와 번호가 겹쳐 두 루프가 같이 돈다.
        self._slot_gen = getattr(self, "_slot_gen", 0) + 1

    def _slot_queue(self) -> None:
        if self._slot_pending is None:
            try:
                self._slot_pending = self.slot.after_idle(self._slot_commit)
            except tk.TclError:
                pass

    def _slot_cancel(self) -> None:
        """예약해 둔 반영을 물린다. **`None` 으로 두기만 하면 안 된다** — 그러면
        예약은 그대로 살아 있다가 나중에 옛 목록으로 자리를 덮어쓴다."""
        if self._slot_pending is not None:
            try:
                self.slot.after_cancel(self._slot_pending)
            except (tk.TclError, ValueError):
                pass
            self._slot_pending = None

    def _slot_commit(self) -> None:
        self._slot_pending = None
        items = list(self._slot_base)[:MAX_SLOTS]
        if self._slot_notice is not None:
            items.append(self._slot_notice)
        if items == self._slot:
            return  # 내용이 그대로면 돌던 자리를 지킨다
        # 알림이 새로 떴으면 순서를 기다리지 않고 그것부터 보여 준다
        fresh = self._slot_notice is not None and self._slot_notice not in self._slot
        self._slot = items
        if not items:
            try:
                self.slot.itemconfigure(self.model, text="")
            except tk.TclError:
                pass
            return
        self._slot_i = len(items) - 1 if fresh else min(self._slot_i, len(items) - 1)
        self._slot_gen += 1  # 돌던 흐름을 은퇴시키고
        self._slot_enter(self._slot_gen, SLOT_FRAMES)  # 지금 것을 곧바로 앉힌다

    def _slot_seat(self) -> tuple[str, str, bool]:
        """지금 차례인 것을 글꼴·자리와 함께 앉히고, 넘치는 폭(`_slot_pan`)을 잰다."""
        text, color, bold = self._slot[min(self._slot_i, len(self._slot) - 1)]
        font = self.f_msg if bold else self.f_small
        # 하염없이 흐르지 않게, 칸의 PAN_MAX 배를 넘는 글자는 … 로 줄여서 들인다
        text = _fit(text, font, int(self.right_w * PAN_MAX))
        self._slot_pan = max(0.0, font.measure(text) - self.right_w)
        self.slot.itemconfigure(
            self.model, text=text, font=font,
            anchor="w" if self._slot_pan else "e",
        )
        return text, color, bold

    def _slot_paint(self, dx: float = 0.0, dy: float = 0.0, fade: float = 0.0) -> None:
        """`dx` 는 훑은 만큼, `dy` 는 위아래 밀림, `fade` 는 바탕에 스민 정도."""
        if not self._slot:
            return
        color = self._slot[min(self._slot_i, len(self._slot) - 1)][1]
        x = dx if self._slot_pan else self.right_w  # 훑을 땐 왼쪽 끝에서 시작한다
        try:
            self.slot.coords(self.model, x, self.slot_h / 2 + dy)
            self.slot.itemconfigure(
                self.model, fill=_mix(color, self.slot.cget("bg"), fade)
            )
        except tk.TclError:  # 캔버스가 사라졌다 (스킨·테마 전환)
            pass

    def _slot_after(self, gen: int, ms: int, fn) -> None:
        try:
            self.slot.after(ms, lambda: fn(gen))
        except tk.TclError:
            pass

    def _slot_moves(self) -> bool:
        """흐름을 돌릴 까닭이 있나 — 가짓수가 둘 이상이거나, 하나라도 넘쳐서 훑어야 하거나."""
        return self._slot_on and (len(self._slot) > 1 or self._slot_pan > 0)

    def _slot_enter(self, gen: int, n: int) -> None:
        """아래에서 떠오른다. n=SLOT_FRAMES 면 애니메이션 없이 바로 앉힌다."""
        if gen != self._slot_gen or not self._slot:
            return
        if n <= 0 or n >= SLOT_FRAMES:
            self._slot_seat()
        t = min(1.0, n / SLOT_FRAMES)
        self._slot_paint(dy=SLOT_RISE * (1 - t), fade=1 - t)
        if n < SLOT_FRAMES:
            self._slot_after(gen, SLOT_STEP, lambda g: self._slot_enter(g, n + 1))
        elif self._slot_moves():
            self._slot_after(gen, PAN_WAIT if self._slot_pan else SLOT_HOLD,
                             lambda g: self._slot_pan_step(g, 0))

    def _slot_pan_step(self, gen: int, n: int) -> None:
        """칸보다 긴 글자를 왼쪽으로 훑는다. 넘치는 게 없으면 곧바로 나간다."""
        if gen != self._slot_gen or not self._slot_moves():
            return
        if self._slot_pan <= 0:
            self._slot_out(gen, 1)
            return
        frames = max(PAN_MIN_FRAMES, int(self._slot_pan / PAN_SPEED * 1000 / SLOT_STEP))
        self._slot_paint(dx=-self._slot_pan * min(1.0, n / frames))
        if n < frames:
            self._slot_after(gen, SLOT_STEP, lambda g: self._slot_pan_step(g, n + 1))
        else:  # 꼬리까지 다 보여 준 채로 잠깐 멈췄다 나간다
            self._slot_after(gen, PAN_WAIT, lambda g: self._slot_out(g, 1))

    def _slot_out(self, gen: int, n: int) -> None:
        """보여 주던 것이 위로 밀리며 바탕에 스민다."""
        if gen != self._slot_gen or not self._slot_moves():
            return
        t = n / SLOT_FRAMES
        self._slot_paint(dx=-self._slot_pan, dy=-SLOT_RISE * t, fade=t)
        if n < SLOT_FRAMES:
            self._slot_after(gen, SLOT_STEP, lambda g: self._slot_out(g, n + 1))
        else:
            self._slot_i = (self._slot_i + 1) % len(self._slot)
            self._slot_enter(gen, 0)

    # -------------------------------------------------- 마스코트 '클로디' (도트 캐릭터)
    # 슬림 바에 사는 코랄색 도트 친구 — 몸통 없이 큰 머리에 팔 둘·다리 둘.
    # 통통 튀고, 이따금 손을 흔들고, 누르면 팔을 번쩍 들고 놀라고, 많이 누르면 기절한다.
    def _start_mascot(self) -> None:
        """마스코트 애니메이션을 켠다. build 가 다시 불려도(테마 전환 등) 세대(gen)
        토큰으로 옛 루프를 은퇴시켜 두 루프가 겹치지 않게 한다."""
        self._t = 0
        self._yoff = self._vy = 0.0   # 상하 용수철(위치·속도)
        self._roff = self._vr = 0.0   # 좌우 흔들 용수철
        self._clicks = 0.0            # 직접 콕 누적 (식으면서 준다)
        self._faint = 0               # 기절 남은 프레임
        self._surprise = 0            # 직접 찔려 눈이 동그래진 프레임
        self._spin_dir = 1            # 누를 때 도는 방향 (번갈아)
        # 심심할 때 하는 잔동작들 — 한 번에 하나씩, 사이사이 쉰다
        self._blink = self._look = self._tilt = self._stretch = 0
        self._wiggle = 0              # 안 쓴다 (좌우로 떠는 움직임은 뺐다). 자리만 남긴다
        self._wave = 0                # 손 흔들기 남은 프레임
        self._look_dir = self._tilt_dir = self._wave_dir = 1
        self._sparks: list[list[float]] = []   # 뿜은 반짝이 [x, y, vx, vy, life]
        self._spark_cool = 0          # 이만큼 지나야 다시 반짝인다 (연타에 겹치지 않게)
        # 오래 심심할 때 하는 딴짓 — 제자리에서 하는 것(_act)과 자리 비움(_away)
        self._quiet = 0               # 마지막 반응 뒤 흐른 프레임 (딴짓 중에는 안 센다)
        self._act = ""                # "" / "type"(노트북) / "nap"(낮잠) / "ball"(공 놀이)
        self._act_left = 0
        self._exit = 0                # 하던 딴짓을 접는 중인 남은 프레임
        self._exit_act = ""           # 접는 중인 것이 무엇이었나 (소품을 치워야 한다)
        self._ball_at = (0.0, 0.0)    # 공이 마지막으로 있던 자리 (접을 때 여기서 떨어진다)
        self._zzz: list[list[float]] = []   # 낮잠 z [x, y, life]
        self._away = 0                # 자리 비움 남은 프레임
        self._away_total = 0
        self._rise = SINK_FRAMES      # 올라오는 데 걸리는 프레임 (부르면 RUSH_BACK 로 줄인다)
        self._rushing = False         # 불려서 호다닥 올라오는 중인가
        self._pressed = False         # 꾹 누르고 있는 중 (손가락에 눌린다)
        self._press = 0.0             # 눌린 정도 0~1
        self._runx = 0.0              # 달려오는 중의 가로 어긋남 (px, 0 이면 제자리)
        self._running = 0             # 달려오는 남은 프레임
        self._played = False          # 마지막 누르기를 마스코트가 가져갔나
        self._combo = 0               # 지금 단 (0~COMBO_MAX)
        self._hits = 0                # 이 판에서 박자를 맞힌 횟수
        self._finale = 0              # 완주 축하 폭죽 남은 프레임
        self._beat_at = -999          # 마지막으로 박자를 맞힌 프레임
        self._trick = 0               # 재주 남은 프레임
        self._trick_len = 1            # 재주 전체 프레임
        self._flip_n = self._spin_n = 0  # 세로·가로 회전 바퀴 수
        self._launch = 0              # 이 동안은 창 밖까지 날아가도 안 가둔다
        self._next_gesture = random.randint(20, 60)
        self._anim_gen = getattr(self, "_anim_gen", 0) + 1
        self._draw_mascot()  # 첫 프레임은 바로 그린다
        self.c.after(FRAME_MS, lambda c=self.c, g=self._anim_gen: self._animate(c, g))

    def _near(self, x: float, y: float) -> bool:
        """누른 자리가 마스코트 자리인가 (자리를 비웠는지는 안 본다)."""
        dx = x - self.mascot_cx
        dy = y - self.h / 2
        return dx * dx + dy * dy <= HIT_R * HIT_R

    def _hit(self, x: float, y: float) -> bool:
        """누른 자리가 마스코트 위인가 (직접 콕 찌름). 자리를 비웠으면 없는 셈."""
        return self._away <= 0 and self._near(x, y)

    def absorbed(self) -> bool:
        """마지막 누르기를 마스코트가 가져갔나 — 그러면 앱이 새로고침을 안 한다."""
        return self._played

    def react(self, x: float | None = None, y: float | None = None) -> None:
        """눌렀을 때 반응. 좌표로 **마스코트를 직접 찔렀는지** 보고 다르게 논다:
        직접 찌르면 크게 놀라 펄쩍(눈 동그래짐)·많이 찌르면 기절.
        **딴 데 클릭은 잔잔히 통통만 하고 기절엔 안 쌓인다.**
        딴짓 중이었으면 그만두고 돌아온다."""
        self._quiet = 0
        self._end_act()  # 하던 딴짓은 곧바로 지우지 않고 접는다 (한 프레임에 안 갈리게)
        # 마스코트를 누른 것이면 '논 것' 이지 새로고침 요청이 아니다 (absorbed 참고)
        self._played = x is not None and self._near(x, y)
        if self._away > 0:
            # 자리를 비웠는데 불렀다 — **호다닥 올라와서 허둥지둥**한다.
            # ★ **달려오는 연출은 완전히 숨었을 때만 시작한다.** 보이는 채로 왼쪽에 옮겨
            #   놓으면 그 순간 옆으로 순간이동한다 — '아래에서 올라오다 갑자기 왼쪽에서
            #   튀어나오던' 것이 그것이었다. 안 보이는 동안 미리 옮겨 두면 **왼쪽에서
            #   올라와 그대로 달려오는** 한 동작이 된다.
            now = self._sink_amount()
            if not self._rushing:
                self._rushing = now >= 1.0
                if self._rushing:
                    self._runx = -RUN_DIST
            # ★ 올라오기는 **지금 내려가 있는 만큼**에서 잇는다 — `_away` 만 RUSH_BACK 로
            #   갈아 끼우면 내려가는 도중에 부른 경우 **아래로 뚝 떨어졌다가** 올라온다.
            self._away = RUSH_BACK
            self._rise = RUSH_BACK / max(now, 1e-3)  # RUSH_BACK 프레임 만에 now → 0
            self._wave = 0
            if self._rushing:
                self._surprise = SURPRISE_FRAMES * 5
            return
        # 기절했거나 **완주 축하가 흐르는 동안은 안 받는다** — 그 사이 누른 것은
        # 마스코트가 가져가되(위 `_played`) 아무 일도 일으키지 않는다.
        if self._faint > 0 or self._finale > 0:
            return
        if x is not None and self._hit(x, y):  # 콕! — 크게 놀란다
            # **박자 맞히기** — 가장 아래로 내려앉은 순간에 치면 콤보가 쌓인다.
            # 놓치면 처음부터. 이어 갈수록 더 높이 뛰고 반짝이도 화려해진다.
            # 바닥에 멎은 그 짧은 순간에만 박자가 맞은 것으로 친다
            on_beat = self._yoff >= BEAT_AT and abs(self._vy) <= BEAT_V
            if on_beat and self._t - self._beat_at <= BEAT_WINDOW:
                self._hits += 1
            else:
                self._hits = 1 if on_beat else 0
            self._beat_at = self._t
            self._combo = self._tier(self._hits)
            self._boost(JUMP_IMPULSE * POKE_MULT + self._combo * COMBO_JUMP)
            self._surprise = SURPRISE_FRAMES
            # ★ **박자를 맞히면 덜 지친다.** 그래야 '너무 빠르게 마구 누르면 콤보가 아니라
            #   기절에 먼저 닿는다' 가 된다 (박자대로면 식는 속도를 못 이겨 안 뻗는다).
            self._clicks += 1.0 if self._combo else 2.4
            if self._combo:
                self._spark_cool = 0
                if self._hits in TIER_UP:  # 이 한 방으로 단이 올랐다 — 재주가 나온다
                    self._burst(SPARK_POKE + self._combo * 3, 1.0 + self._combo * 0.25)
                    self._begin_trick(self._combo)
                    if self._combo >= COMBO_MAX:  # 완주 — 바 전체에 축하 폭죽
                        self._finale = FINALE_FRAMES
                        self._hits = self._combo = 0
                else:  # 아직 올라가는 중 — 소박하게
                    self._burst(2 + self._combo, 0.6 + self._combo * 0.08)
            else:  # 아무 때나 친 것 — 발밑에 먼지만
                self._burst(SPARK_DUST, 1.0, foot=True)
            if self._clicks >= FAINT_AT:  # 과부하 — 뻗는다
                self._faint = FAINT_FRAMES
                self._clicks = 0.0
                self._surprise = 0
        else:  # 딴 데 — 잔잔히 통통 (기절·반짝이와 무관)
            self._vy -= JUMP_IMPULSE
            self._combo = 0

    def hold(self, x: float, y: float) -> None:
        """꾹 누르고 있다 — **손가락에 눌려 납작해진다.** 딴 데를 누른 거면 아무 일도 없다.

        ★ 여기에 '기 모아 뛰기'·'기 모아 쏘기'·'쓰다듬기(하트)' 를 차례로 붙여 봤다가
        전부 뺐다. 소품이나 기호를 얹으면 게임 같거나 유치했다 — **누르니까 눌린다.**
        """
        if (self._faint > 0 or self._finale > 0 or self._away > 0
                or not self._hit(x, y)):
            return
        self._pressed = True

    def let_go(self) -> None:
        """손을 뗐다 — 눌린 만큼 튕겨 오르고, 꾹 눌렀던 거면 **팡** 터진다.
        (그냥 튕기기만 하면 참았다 놓는 맛이 없다)"""
        if not self._pressed:
            return
        self._pressed = False
        press, self._press = self._press, 0.0
        self._boost(JUMP_IMPULSE + PRESS_POP * press, launch=True)
        if press >= PRESS_BURST:
            self._surprise = SURPRISE_FRAMES * 3
            # 일부러 만든 순간이라 쿨다운과 무관하게 터뜨린다
            self._spark_cool = 0
            self._burst(SPARK_POKE + int(8 * press), 1.2 + press * 0.8)

    @staticmethod
    def _tier(hits: int) -> int:
        """맞힌 횟수로 지금 몇 단인지. 한 단에 `TIER_HITS` 번씩 걸린다."""
        if hits <= 0:
            return 0
        return min(COMBO_MAX, sum(1 for up in TIER_UP if hits > up) + 1)

    def _begin_trick(self, combo: int) -> None:
        """콤보 단에 맞는 재주를 시작한다. 1단은 반짝이뿐, 5단은 앞구르기+팽이돌기+폭죽."""
        spec = TRICKS.get(combo)
        if spec is None:
            return
        self._trick = self._trick_len = spec[0]
        self._flip_n, self._spin_n = spec[1], spec[2]
        if combo >= COMBO_MAX:  # 마지막 단 — 사방으로 크게 한 번 더
            for _ in range(10):
                a = random.uniform(0, math.tau)
                self._sparks.append([
                    self.mascot_cx + math.cos(a) * 4,
                    self.h / 2 + self._yoff + math.sin(a) * 4,
                    math.cos(a) * 0.9, math.sin(a) * 0.7 - 0.2,
                    SPARK_LIFE * random.uniform(0.7, 1.0), MASCOT_COLOR,
                ])

    def _firework(self) -> None:
        """축하 폭죽 한 발 — **마스코트 자리가 아니라 슬림 바 아무 데나** 터진다.
        (완주는 판 전체가 축하할 일이다. 반짝이는 캔버스 좌표라 바를 가로질러 뿌려진다)

        ★ **발마다 색·개수·퍼지는 정도가 다르다** — 다 같으면 한 발을 복사해 놓은 것처럼
        보인다. 몇 알은 흰빛(`P.title`)으로 섞어 심지가 남은 결을 낸다.
        """
        color = random.choice((P.green, P.amber, P.red, MASCOT_COLOR, P.title))
        core = P.title if random.random() < 0.5 else color
        fx = random.uniform(PAD_L, self.width - PAD_R)
        fy = random.uniform(6, self.h - 8)
        spread = random.uniform(*FINALE_SPREAD)
        for i in range(random.randint(*FINALE_PER)):
            a = random.uniform(0, math.tau)
            r = random.uniform(0.35, 1.0) * spread
            self._sparks.append([
                fx, fy, math.cos(a) * r, math.sin(a) * r - 0.15,
                SPARK_LIFE * random.uniform(*FINALE_BIG),
                core if i % 4 == 0 else color,
            ])

    def _boost(self, power: float, launch: bool = False) -> None:
        """위로 튀어오르게 한다. `launch` 면 잠시 **창 밖으로** 나가도록 가둠을 푼다 —
        그건 꾹 누르기의 특전이고, 그냥 누르기·콤보는 `MAX_VY` 를 넘지 않는다.
        (상한이 없으면 연타할 때 속도가 쌓여 천장에 붙어 굼떠 보인다)"""
        self._vy -= power
        if launch:
            self._launch = LAUNCH_FRAMES
        else:
            self._vy = max(self._vy, -MAX_VY)

    def _burst(self, count: int, power: float = 1.0, foot: bool = False) -> None:
        """반짝이를 한 움큼 뿜는다 — **흩뿌려** 놓고 사그라든다. 가지런히 퍼뜨리면
        (부채꼴) 도형을 그린 것처럼 보여, 자리를 일부러 흩는다.

        `foot` 이면 **발밑에서 옆으로 낮게** 인다(그냥 콕 찔렀을 때의 먼지),
        아니면 **머리 위로** 떠오른다(타이밍 맞춰 크게 뛰었을 때).

        ★ **`SPARK_COOL` 만큼 쉬었을 때만 나온다** — 연타할 때마다 뿜으면 앞것과 겹쳐
        지저분하다(실제로 그랬다). 아껴 써야 반짝일 때 반갑다.
        """
        if self._spark_cool > 0:
            return
        self._spark_cool = SPARK_COOL
        cx, cy = self.mascot_cx, self.h / 2 + self._yoff
        for _ in range(max(0, min(16, count))):
            if foot:  # 발밑 먼지 — 낮게 깔려 옆으로 퍼진다
                side = random.choice((-1, 1))
                self._sparks.append([
                    cx + side * random.uniform(2.0, 6.0),
                    cy + random.uniform(3.0, 4.2) * MASCOT_U,
                    side * random.uniform(0.28, 0.62) * power,
                    random.uniform(-0.30, -0.08) * power,
                    SPARK_LIFE * random.uniform(0.45, 0.75), MASCOT_COLOR,
                ])
            else:  # 머리 위 — 떠오른다
                self._sparks.append([
                    cx + random.uniform(-1, 1) * SPARK_SPREAD * power,
                    cy - random.uniform(2.5, 7.0) * MASCOT_U,
                    random.uniform(-0.22, 0.22) * power,
                    random.uniform(-0.85, -0.35) * power,
                    SPARK_LIFE * random.uniform(0.62, 1.0), MASCOT_COLOR,
                ])

    def _animate(self, canvas: tk.Canvas, gen: int) -> None:
        if gen != self._anim_gen:  # 새 build 가 시작됐다 — 이 루프는 은퇴
            return
        self._t += 1
        self._step_physics()
        if self._faint == 0:
            self._idle_step()
        try:
            self._draw_mascot()
        except tk.TclError:  # 캔버스가 사라졌다 (스킨/테마 전환)
            return
        canvas.after(FRAME_MS, lambda: self._animate(canvas, gen))

    def _step_sparks(self) -> None:
        """떠다니는 것들(반짝이·낮잠 z) 한 걸음. 기절 중에도 흘러야 하므로
        잔동작(_idle_step)이 아니라 여기서 돌린다."""
        if self._spark_cool > 0:
            self._spark_cool -= 1
        for s in self._sparks:
            s[0] += s[2]; s[1] += s[3]; s[3] += SPARK_GRAV; s[4] -= 1
        self._sparks = [s for s in self._sparks if s[4] > 0]
        for z in self._zzz:  # z 는 비스듬히 떠오른다 (옆 칸을 침범하지 않게 조금만)
            z[0] += 0.13; z[1] -= 0.28; z[2] -= 1
        self._zzz = [z for z in self._zzz if z[2] > 0]
        if self._running > 0:  # 달려오는 중 — 왼쪽에서 제자리로
            self._running -= 1
            self._runx = -RUN_DIST * (self._running / RUN_FRAMES) ** 1.6

    def _step_physics(self) -> None:
        """용수철 한 걸음. 눌림으로 생긴 속도를 제자리(0)로 부드럽게 당긴다."""
        self._step_sparks()
        if self._exit > 0:  # 하던 딴짓을 접는 중 (기절해도 흘러야 접히다 만 채로 안 멈춘다)
            self._exit -= 1
        if self._faint > 0:  # 기절 중 — 서서히 늘어졌다가 깨어난다
            self._faint -= 1
            self._vy *= 0.8; self._yoff *= 0.85
            self._vr *= 0.9; self._roff *= 0.9
            if self._faint == 0:  # 깨어남 — 말끔히 리셋하고 펑 하고 털어낸다
                self._yoff = self._vy = self._roff = self._vr = 0.0
                self._burst(SPARK_WAKE, 1.2)
            return
        if self._pressed:  # 눌리는 중 — 제자리에서 점점 납작해진다
            self._press = min(1.0, self._press + 1.0 / PRESS_FRAMES)
            self._vy *= 0.6
            self._yoff *= 0.8
        self._vy += -SPRING_K * self._yoff
        self._vy *= 1 - SPRING_DAMP
        # 창 밖으로 안 튀게 — 도트 그림 높이를 빼고 남는 만큼만 올라간다.
        # 단 크게 튀어오른 직후(`_launch`)에는 일부러 풀어 **창 밖까지** 날려 보낸다.
        if self._launch > 0:
            self._launch -= 1
            lift = LAUNCH_LIFT
        else:
            lift = max(4.0, (self.h - SPRITE_H) / 2 - 1)
        # ★ 끝에 닿으면 **속도까지 죽인다.** 위치만 가두면 연타할 때 속도가 계속 쌓여
        #   천장에 붙은 채 한참 못 내려온다 — 그게 '마비된 것 같다' 의 정체였다.
        nxt = self._yoff + self._vy
        if nxt < -lift:
            nxt, self._vy = -lift, 0.0
        elif nxt > lift * 0.65:
            nxt, self._vy = lift * 0.65, 0.0
        self._yoff = nxt
        self._vr += -SPRING_K * self._roff
        self._vr *= 1 - SPRING_DAMP
        self._roff += self._vr
        if self._surprise > 0:
            self._surprise -= 1
        if self._clicks > 0:  # 눌림 누적은 서서히 식는다
            self._clicks = max(0.0, self._clicks - CLICK_DECAY)
        if self._combo and self._t - self._beat_at > BEAT_WINDOW:
            self._combo = self._hits = 0   # 박자가 끊겼다
        if self._finale > 0:  # 완주 축하 — 바 전체에 폭죽이 이어지고 같이 폴짝거린다
            self._finale -= 1
            if self._finale % FINALE_EVERY == 0:
                self._firework()
                if (self._finale // FINALE_EVERY) % FINALE_DOUBLE == 0:
                    self._firework()  # 두 발이 겹쳐 터진다
            if self._finale % FINALE_HOP == 0:  # 클로디도 신나서 폴짝
                self._boost(JUMP_IMPULSE * FINALE_POP)
        if self._trick > 0:  # 재주 — 부리는 동안 반짝이 꼬리를 흘린다
            self._trick -= 1
            if self._trick % TRICK_TRAIL == 0:
                self._sparks.append([
                    self.mascot_cx + random.uniform(-4, 4),
                    self.h / 2 + self._yoff + random.uniform(-4, 4),
                    random.uniform(-0.25, 0.25), random.uniform(-0.35, 0.05),
                    SPARK_LIFE * 0.7, MASCOT_COLOR,
                ])

    # -------------------------------------------------- 심심할 때 하는 잔동작
    def _idle_step(self) -> None:
        """쉬는 동안 이따금 딴짓을 시킨다 — 손 흔들기·눈 굴리기·고개 갸웃·기지개·
        부르르·반짝이 뿜기·가끔 폴짝. 한 번에 하나씩만, 반응(눌림)으로 출렁일 땐 쉰다.
        한참(`DEEP_IDLE`) 아무도 안 건드리면 **노트북을 두드리거나 자리를 비운다.**
        (반짝이 자체를 굴리는 건 _step_sparks — 기절 중에도 흘러야 한다)"""
        if self._away > 0:  # 자리 비움 — 인사(손 흔들기)만 하고 내려가 있는다
            self._away -= 1
            if self._wave > 0:
                self._wave -= 1
            if self._away == 0 and self._rushing:  # 다 올라왔다 — 이제 제자리로 달린다
                self._rushing = False
                self._rise = SINK_FRAMES
                # **허겁지겁 달려온다** — 왼쪽에서 발을 바꿔 가며 제자리로, 눈은 동그래진 채.
                # ★ `_runx` 는 부를 때(`react`) 이미 여기로 옮겨 뒀다 — **올라온 그 자리에서
                #   그대로 이어 달린다**(여기서 옮기면 다 올라온 순간 옆으로 튄다).
                self._running = RUN_FRAMES
                self._surprise = SURPRISE_FRAMES * 5
            return
        if self._act:  # 뭔가에 열중하는 중 — 잔동작을 겹치지 않는다
            self._act_left -= 1
            if self._act == "nap" and self._act_left % NAP_EVERY == 0:
                self._zzz.append([self.mascot_cx + 3.0, self.h / 2 - 9.0, NAP_LIFE])
            if self._act_left <= 0:
                self._end_act()  # 혼자 끝날 때도 접는 동안을 거친다 (누른 것과 같은 결)
                self._quiet = 0  # 하나가 끝나자마자 다음 것이 이어지지 않게 되감는다
            return
        self._quiet += 1
        for key in ("_blink", "_look", "_tilt", "_stretch", "_wiggle", "_wave"):
            v = getattr(self, key)
            if v > 0:
                setattr(self, key, v - 1)
        busy = (self._blink or self._look or self._tilt or self._stretch
                or self._wiggle or self._wave or self._exit or self._finale)
        moving = abs(self._vy) + abs(self._yoff) > 0.8
        if self._quiet > DEEP_IDLE and not busy and not moving:
            self._begin_absorbed()
            return
        self._next_gesture -= 1
        if self._next_gesture <= 0 and not busy and not moving:
            self._begin_gesture()
            self._next_gesture = random.randint(30, 100)  # 다음 딴짓까지 1.4~4.5초

    def _begin_absorbed(self) -> None:
        """오래 심심해서 하는 일 하나를 고른다 — 노트북·낮잠·공 놀이, 또는 자리 비움.
        시작할 때 `_quiet` 를 되감고, 딴짓 중에는 그 값을 안 세므로 다음 것까지 또 뜸을 들인다."""
        self._quiet = 0
        pick = random.choices(("type", "nap", "ball", "away"), weights=(4, 3, 3, 3))[0]
        if pick == "away":  # 손 한 번 흔들고 아래로 쏙 내려갔다 돌아온다
            self._rise = SINK_FRAMES
            self._rushing = False
            self._away_total = AWAY_LEAD + random.randint(AWAY_MIN, AWAY_MAX)
            self._away = self._away_total
            self._wave = AWAY_LEAD
        else:
            self._act = pick
            self._act_left = random.randint(ACT_MIN, ACT_MAX)

    def _end_act(self) -> None:
        """딴짓을 **접는 동안**을 둔다 — 곧바로 지우면 자세도 소품도 한 프레임에 갈려
        튄다(노트북 두드리다 누르면 몸이 옆으로 뛰고 노트북이 사라졌다).
        `_exit` 가 도는 동안 `_draw_mascot` 이 몸을 제자리로 되돌리며 소품을 치운다."""
        if not self._act:
            return
        self._exit_act, self._exit = self._act, ACT_EXIT
        self._act = ""

    def _sink_amount(self) -> float:
        """자리 비움에서 얼마나 내려가 있나 (0=제자리, 1=작업표시줄 아래로 완전히)."""
        if self._away <= 0:
            return 0.0
        gone = self._away_total - self._away - AWAY_LEAD  # 인사가 끝난 뒤 흐른 프레임
        if gone < 0:  # 아직 손 흔드는 중
            return 0.0
        if self._away < self._rise:  # 올라오는 중 (부르면 _rise 가 짧아져 호다닥)
            return self._away / self._rise
        if gone < SINK_FRAMES:  # 내려가는 중
            return gone / SINK_FRAMES
        return 1.0

    def _begin_gesture(self) -> None:
        # '부르르(wiggle)' 는 뺐다 — 좌우로 떠는 움직임은 안 예뻤다
        g = random.choice(
            ("blink", "blink", "wave", "wave", "look", "tilt",
             "stretch", "sparkle", "hop")
        )
        if g == "blink":
            self._blink = 3
        elif g == "wave":  # 손 흔들기 — 한 팔을 네 프레임마다 올렸다 내린다
            self._wave = 24; self._wave_dir = random.choice((-1, 1))
        elif g == "look":
            self._look = 26; self._look_dir = random.choice((-1, 1))
        elif g == "tilt":
            self._tilt = 34; self._tilt_dir = random.choice((-1, 1))
        elif g == "stretch":
            self._stretch = 22
        elif g == "sparkle":
            self._burst(4, 0.8)  # 혼자 반짝반짝
        elif g == "hop":
            self._vy -= JUMP_IMPULSE * 0.7  # 혼자 살짝 폴짝
            self._burst(3, 0.6)

    def _draw_mascot(self) -> None:
        """매 프레임 지우고 다시 그린다. 평소엔 숨쉬듯 잔잔히 + 이따금 잔동작,
        누르면 팔을 번쩍 들고 출렁이며 눈웃음/놀람, 기절하면 X_X + 별이 뱅뱅."""
        c = self.c
        c.delete("mascot")
        if self._faint > 0:
            self._draw_faint(c, self.mascot_cx, c.cget("bg"))
            self._draw_sparks(c)  # 기절해서도 아까 뿜은 것은 마저 흐른다
            return
        # 자리 비움 — 작업표시줄 아래로 쏙 내려가 있다 (캔버스 밖이라 저절로 잘린다)
        sink = self._sink_amount()
        if sink >= 1.0:
            self._draw_sparks(c)
            return
        t = self._t

        # --- 잔동작에서 오는 보정값들 ---
        eye_dx = 0  # 눈 굴리기는 **칸 단위**로 옮긴다 (도트가 흐려지지 않게)
        if self._look:
            pr = 1 - self._look / 26
            eye_dx = self._look_dir if math.sin(pr * math.pi) > 0.5 else 0
        tilt = 0.0
        if self._tilt:  # 고개 갸웃 — 기울였다 돌아온다
            pr = 1 - self._tilt / 34
            tilt = self._tilt_dir * 0.42 * math.sin(pr * math.pi)
        sxk = syk = 1.0
        stretch = 0.0
        if self._stretch:  # 기지개 — 위로 쭉 늘었다 준다 (팔도 번쩍)
            stretch = math.sin((1 - self._stretch / 22) * math.pi)
            syk = 1 + 0.24 * stretch; sxk = 1 - 0.10 * stretch
        # 뛸 때 몸이 늘었다 눌린다 — 이게 점프의 손맛이다(세로로만)
        squash = max(SQUASH_MIN, min(SQUASH_MAX, -self._vy * SQUASH))
        sxk *= 1 - squash * 0.55
        syk *= 1 + squash
        # 재주 — 앞구르기(세로 회전)와 팽이돌기(가로 회전). `syk`/`sxk` 를 음수까지 돌리면
        # 도트를 그대로 뒤집어 그리므로(=`uy`/`ux` 가 음수) 획이 안 뭉개진다.
        if self._trick > 0:
            pr = (1 - self._trick / self._trick_len) * math.tau
            if self._flip_n:
                syk *= math.cos(pr * self._flip_n)
            if self._spin_n:
                sxk *= math.cos(pr * self._spin_n)
        spring_scale = 1.0 + max(0.0, -self._yoff) * 0.02  # 위로 뜰수록 살짝 커짐
        # 낮잠 중엔 더 크고 느리게 숨쉰다
        breathe = (1 + 0.10 * math.sin(t * 0.05)) if self._act == "nap" else (
            1 + 0.045 * math.sin(t * 0.09)
        )
        sxk *= spring_scale * breathe
        syk *= spring_scale * breathe
        cy = self.h / 2 + math.sin(t * 0.12) * 1.1 + self._yoff   # 잔잔한 통통 + 용수철
        cy += sink * (self.h / 2 + SPRITE_H)                      # 자리 비우러 내려가는 중
        cx = self.mascot_cx + self._runx                          # 달려오는 중이면 왼쪽에서
        # 좌우 기울임은 **고개 갸웃할 때만.** 늘 살랑거리게 두지 말 것(산만하다).
        lean = tilt
        speed = abs(self._vy) + abs(self._yoff)                   # 출렁이는 중이면 신났다

        # 표정과 팔 — 콕 찔리면 놀라 만세, 출렁이면 눈웃음, 기지개도 만세
        lap = ball = extra = None
        legs = LEGS
        if self._pressed:  # 눌리는 중 — 눈을 질끈 감고 납작해진다
            expr, arms = "blink", (0, 0)
            sxk *= 1 + PRESS_FLAT * 0.75 * self._press
            syk *= 1 - PRESS_FLAT * self._press
            cy += 3.2 * self._press
        elif self._running > 0 or self._rushing:  # 달려오는 중 (불려서 올라오는 동안부터)
            # ★ 발 박자는 `_t` 로 센다 — **올라오는 중과 달리는 중이 같은 걸음으로 이어진다**
            #   (`_running` 으로 세면 땅에 닿는 순간 걸음이 처음으로 되감긴다).
            expr = "surprise" if self._surprise > 0 else "grin"
            step = (self._t // RUN_BEAT) % 2 == 0
            arms = (-1, 0) if step else (0, -1)
            legs = LEGS if step else LEGS_RUN
        elif self._exit > 0:  # 하던 걸 접고 돌아앉는 중 — 소품을 치우고 몸을 제자리로
            k = self._exit / ACT_EXIT                     # 1 → 0
            sxk *= 1 - 0.5 * math.sin((1 - k) * math.pi)  # 가운데서 납작 = 돌아앉는 결
            done = "surprise" if self._surprise > 0 else "idle"
            if self._exit_act == "type":
                cx += TYPE_SHIFT * k       # 노트북 쪽으로 물렸던 몸이 제자리로 미끄러진다
                expr = "side" if k > 0.5 else done
                arms = (None, None) if k > 0.5 else (0, 0)
                extra = TYPE_ARM[1] if k > 0.5 else None   # 손은 이미 자판에서 뗐다
                # 노트북은 몸을 따라가지 않는다 — 제자리에서 아래로 치워진다.
                # ★ 내려가는 거리는 창 높이만큼 — **마지막 프레임에 창 밖으로 다 나가야**
                #   한다(모자라면 조각이 남은 채로 사라진다).
                lap = (self.mascot_cx + TYPE_SHIFT, cy + (1 - k) ** 2 * self.h)
            elif self._exit_act == "nap":  # 자다 깼다 — 눈을 뜨며 일어난다
                cy += 1.5 * k
                expr = "blink" if k > 0.5 else done
                arms = (1, 1) if k > 0.5 else (0, 0)
            else:  # 공 놀이 — 던져 둔 공은 아래로 떨어져 나간다
                expr, arms = done, (0, 0)
                ball = (self._ball_at[0], self._ball_at[1] + (1 - k) ** 2 * self.h)
        elif self._finale > 0:  # 완주 축하 — 폭죽이 터지는 동안 같이 폴짝폴짝 만세
            expr = "grin"
            arms = (-1, -1) if self._yoff < -FINALE_CHEER else (0, 0)
        elif self._surprise > 0:
            expr, arms = "surprise", (-1, -1)
        elif speed > 1.2:
            expr, arms = "grin", (-1, -1)
        elif self._wave:  # 손 흔들기 — 한 팔만 번쩍, 그 팔이 오르내린다
            up = (self._wave // 4) % 2 == 0
            expr = "grin"
            arms = (-1 if up else 0, 0) if self._wave_dir < 0 else (0, -1 if up else 0)
        elif self._act == "type":  # 노트북에 열중 — **옆으로 돌아앉아** 왼쪽 화면을 본다
            expr = "side"
            # 옆모습이라 기본 팔은 안 그리고(None), **노트북까지 뻗은 긴 팔**을 대신 그린다
            arms = (None, None)
            extra = TYPE_ARM[(self._act_left // TYPE_BEAT) % 2]
            cx += TYPE_SHIFT  # 노트북까지 한 그림이 되게 몸을 오른쪽으로
            lap = (cx, cy)    # 노트북 자리 — 접을 땐 몸만 돌아가고 이건 제자리에 남는다
        elif self._act == "nap":  # 낮잠 — 눈 감고 팔을 늘어뜨린 채 크게 숨쉰다
            expr, arms = "blink", (1, 1)
            cy += 1.5
        elif self._act == "ball":  # 공 놀이 — 던져 올렸다 받는다
            frac = (self._t % BALL_PERIOD) / BALL_PERIOD
            ball = (
                self.mascot_cx + math.sin(frac * math.tau) * 4.0,
                cy - 4.4 * MASCOT_U - math.sin(frac * math.pi) * BALL_H,
            )
            self._ball_at = ball  # 접을 때 공이 여기서부터 떨어진다
            # 손을 떠나 있는 동안만 팔을 번쩍 (받는 순간엔 내린다)
            flying = 0.12 < frac < 0.88
            expr = "grin" if flying else "surprise"
            arms = (-1, -1) if flying else (0, 0)
            eye_dx = 1 if frac < 0.5 else 0  # 공을 눈으로 좇는다
        elif self._blink > 0:
            expr, arms = "blink", (0, 0)
        elif stretch > 0.5:
            expr, arms = "idle", (-1, -1)
        else:
            expr, arms = "idle", (0, 0)

        self._sprite(expr, arms, legs, cx, cy,
                     MASCOT_U * sxk, MASCOT_U * syk, lean, eye_dx, None, extra)
        if lap is not None:  # 노트북은 도트가 아니라 다각형이라 스프라이트 뒤에 따로 그린다
            self._draw_laptop(c, *lap)
        if ball is not None:
            # 공은 몸 위에 그린다(손보다 앞). **몸 색으로 그리면 몸에 붙은 혹처럼 보인다** —
            # 호박색 장난감으로 둔다(알림 색과 자리가 겹치지 않아 헷갈릴 일이 없다).
            u = MASCOT_U * BALL_R
            c.create_rectangle(ball[0] - u, ball[1] - u, ball[0] + u, ball[1] + u,
                               fill=P.amber, width=0, tags="mascot")
        self._draw_sparks(c)
        self._draw_zzz(c)

    def _sprite(self, expr: str, arms: tuple[int | None, int | None],
                legs: tuple[str, ...],
                cx: float, cy: float, ux: float, uy: float,
                lean: float = 0.0, eye_dx: int = 0,
                front: tuple[str, ...] | None = None,
                extra: tuple | None = None) -> None:
        """도트 그림 한 장. 칸 경계를 같은 식으로 계산하므로 확대·기울임에도 틈이 안 생긴다.

        `lean` 은 기울임 — 위쪽 줄일수록 옆으로 더 미는 **계단식**이라 도트 결이 유지된다
        (도형을 돌리면 이 크기에서 획이 뭉개진다).
        """
        c = self.c
        bg = c.cget("bg")
        mid = (len(HEAD) + len(legs)) / 2
        x0 = cx - 4.5 * ux   # 머리 9칸의 왼쪽
        y0 = cy - mid * uy   # 머리 7줄 + 다리 2줄의 맨 위

        def cell(col: float, row: float, color: str, span: int = 1,
                 tilt: float | None = None, dx: int = 0) -> None:
            t = lean if tilt is None else tilt
            x = x0 + (col + dx) * ux + t * (mid - row) * uy
            y = y0 + row * uy
            c.create_rectangle(x, y, x + span * ux, y + uy,
                               fill=color, width=0, tags="mascot")

        def paint(lines: tuple[str, ...], top: int, color: str = MASCOT_COLOR,
                  tilt: float | None = None, dx: int = 0) -> None:
            """줄마다 이어진 칸을 **한 덩이로** 그린다 — 매 프레임 도형 수를 3분의 1로.
            경계 식이 낱칸과 같으므로 그림은 한 픽셀도 안 달라진다."""
            for r, line in enumerate(lines):
                col = 0
                while col < len(line):
                    if line[col] != "#":
                        col += 1
                        continue
                    run = 1
                    while col + run < len(line) and line[col + run] == "#":
                        run += 1
                    cell(col, top + r, color, run, tilt, dx)
                    col += run

        if extra is not None:                    # 길게 뻗은 팔(타이핑) 같은 덧그림
            for col, row in extra:
                cell(col, row, MASCOT_COLOR)
        if arms[0] is not None:                  # 왼팔
            for col, row in ARM[arms[0]]:
                cell(col, row, MASCOT_COLOR)
        if arms[1] is not None:                  # 오른팔 — 좌우 뒤집기 (옆모습이면 안 그림)
            for col, row in ARM[arms[1]]:
                cell(8 - col, row, MASCOT_COLOR)
        paint(HEAD, 0)
        paint(legs, len(HEAD))
        for col, row in EYES[expr]:
            cell(col + eye_dx, row, bg)

    def _draw_sparks(self, c: tk.Canvas) -> None:
        """뿜은 반짝이 — 도트답게 작은 십자(칸 다섯)로 떠오르며 사그라든다."""
        for sx, sy, _vx, _vy, life, color in self._sparks:
            # 수명대로 작아진다 — 가루가 흩어져 사그라드는 결(폰 쪽과 같은 식)
            u = MASCOT_U * SPARK_SIZE * (life / SPARK_LIFE)
            if u < 0.45:
                continue
            for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
                x, y = sx + dx * u, sy + dy * u
                c.create_rectangle(x - u / 2, y - u / 2, x + u / 2, y + u / 2,
                                   fill=color, width=0, tags="mascot")

    def _draw_laptop(self, c: tk.Canvas, cx: float, cy: float) -> None:
        """노트북 — **도트가 아니라 1px 다각형**으로 그린다(위 `LAP_*` 주석 참고).
        고개를 따라 기울이지 않는다 — 바닥에 놓인 물건이다."""
        x0, y0, x1, y1 = LAP_BASE
        c.create_rectangle(cx + x0, cy + y0, cx + x1, cy + y1,
                           fill=P.label, width=0, tags="mascot")
        pts = []
        for dx, dy in LAP_LID:
            pts += [cx + dx, cy + dy]
        c.create_polygon(pts, fill=P.label, width=0, tags="mascot")

    def _draw_zzz(self, c: tk.Canvas) -> None:
        """낮잠 z — 머리 위로 비스듬히 떠오른다. 도트 3×3 이라 이 크기에서도 z 로 읽힌다."""
        for zx, zy, life in self._zzz:
            u = MASCOT_U * (0.7 + 0.5 * (1 - life / NAP_LIFE))  # 멀어질수록 커진다
            for r, line in enumerate(NAP_Z):
                for col, ch in enumerate(line):
                    if ch != "#":
                        continue
                    x, y = zx + col * u, zy + r * u
                    c.create_rectangle(x, y, x + u, y + u,
                                       fill=P.label, width=0, tags="mascot")

    def _draw_faint(self, c: tk.Canvas, cx: int, bg: str) -> None:
        """기절 — 크게 부풀려 주저앉고(다리가 벌어진다), X_X 눈에 팔은 축 늘어진다.
        작아서 눈이 안 보이던 걸 FAINT_SCALE 로 키워 X 를 확실히 보이게 한다."""
        t = self._t
        u = MASCOT_U * FAINT_SCALE
        cy = self.h / 2 + 2.0 + math.sin(t * 0.25) * 0.6  # 살짝 처져 흐느적
        lean = math.sin(t * 0.2) * 0.20                   # 어질어질 크게 흔들
        self._sprite("faint", (1, 1), LEGS_WIDE, cx, cy, u, u, lean)
        # 어질어질 별 세 개가 머리 위를 돈다 (역시 도트 십자)
        oy = cy - 4.6 * u
        for i in range(3):
            a = t * 0.35 + i * (math.pi * 2 / 3)
            sx = cx + math.cos(a) * 8.0
            sy = oy + math.sin(a) * 2.4
            for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
                x, y = sx + dx * 2.0, sy + dy * 2.0
                c.create_rectangle(x - 1, y - 1, x + 1, y + 1,
                                   fill=P.amber, width=0, tags="mascot")

    # -------------------------------------------------- 바탕 두 얼굴
    def _paint(self, bg: str, accent: str) -> None:
        self.c.configure(bg=bg)
        self.slot.configure(bg=bg)  # 번갈아 칸도 같은 바탕이라야 이어져 보인다
        self.c.itemconfigure(self.accent, fill=accent)

    def status_spot(self) -> tuple[int, int, str]:
        """상태 점·새로고침 링을 놓을 자리(창 기준 한가운데)와 그 자리의 바탕색."""
        return self.dot_spot[0], self.dot_spot[1], self.c.cget("bg")

    # -------------------------------------------------- 값
    def show(self, usage: Usage, stamp: str) -> None:
        self._paint(P.bg, tone(worst(usage)))
        p = pace(usage)
        self.five.set(usage.five.pct, usage.five.left, five_due(usage))
        self.week.set(usage.week.pct, usage.week.left, p.due if p else None)

        # 번갈아 칸에 띄울 것들 — 모델별 한도(Fable 7%)와 알림. **적정선은 넣지 않는다**:
        # 게이지에 눈금(┃)으로 이미 서 있어서 숫자를 또 적을 까닭이 없다.
        self._slot_base = [
            (f"{s.label} {s.pct:.0f}%", P.label, False)
            for s in usage.scoped
            if s.pct is not None
        ]
        self._slot_notice = None  # 알림은 곧바로 이어 불리는 notice() 가 다시 얹는다
        self._slot_on = True
        self._slot_queue()
        # 상태 점은 앱이 그린다 (stamp 는 안 쓴다: 시각은 작업표시줄 시계에 있다)

    def show_error(self, text: str, keep_values: bool, stamp: str) -> None:
        self._paint(P.red_bg, P.red)
        # 오류가 번갈아 칸을 통째로 쓴다 (굵게·빨강 한 가지만). 길면 훑어서 다 보여 준다.
        self._slot_cancel()  # 조회 성공으로 예약해 뒀던 반영이 오류를 덮지 않게
        self._slot_base = []
        self._slot_notice = None
        self._slot_on = True
        self._slot_i = 0
        self._slot = [(text, P.red, True)]
        self._slot_gen += 1
        self._slot_enter(self._slot_gen, SLOT_FRAMES)
        if not keep_values:
            self.five.set(None, "")
            self.week.set(None, "")

    def notice(self, text: str) -> None:
        # 값은 멀쩡한데 알릴 것(핑 실패·놓침)을 번갈아 칸에 호박색으로 끼운다.
        # show() 직후 앱이 부른다 — 빈 문자열이면 그대로 둔다(show() 가 이미 비웠다).
        # 뜨는 순간 순서를 기다리지 않고 먼저 보여 준다(_slot_commit 의 fresh).
        if not text:
            return
        self._slot_notice = (text, P.amber, False)
        self._slot_queue()
