package com.kyijgnes.cooldown.wallpaper

import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Path
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow
import kotlin.math.sin

/**
 * 배경화면에 사는 클로디 — 데스크탑 위젯(`pc/windows/skins/slim.py`)의 도트 친구를 폰으로 옮겼다.
 * 그림표는 생성기가 만든 `MascotSprite`(같은 원본)를 쓰고, **여기는 움직임만** 맡는다.
 *
 * 상태(튀는 속도·표정·콤보)를 들고 있으므로 **그리는 쪽마다 하나씩** 만든다
 * (배경화면 엔진 하나, 꾸미기 미리보기 하나). `WallpaperArt` 는 상태를 안 갖는다.
 *
 * 노는 법:
 *  - **콕 찌르기** — 펄쩍 뛰고 눈이 커진다. 뛰는 동안 몸이 늘었다 눌린다(스쿼시·스트레치).
 *  - **박자 맞히기(콤보)** — 통통 튀다 **바닥에 멎는 그 순간**에 다시 찌르면 콤보가 오른다.
 *    5단까지 있고 단마다 다른 재주가 나오며, 다 채우면 화면 전체에 축하 폭죽이 터진다.
 *  - **꾹 누르기** — 손가락에 눌려 납작해지고, 떼면 눌린 만큼 튕겨 오른다.
 *    ★ 홈 화면에서는 런처가 길게 누르기를 자기 메뉴로 채 가므로 꾸미기 미리보기에서 제대로 된다.
 *      홈에서 노는 길은 **콕 찌르기와 박자 콤보**다(둘 다 누르는 순간 반응하므로 채여도 된다).
 *  - **마구 두드리면 기절**한다(X_X + 별). 박자를 맞히면 덜 지친다.
 *  - **오래 안 건드리면 딴짓**을 한다 — 노트북 두드리기·낮잠·공 놀이·자리 비움.
 *
 * ★ **터치는 배경화면이 직접 받는다** — 런처가 흘려 준 좌표가 클로디 위면 반응.
 *   아이콘·위젯 위를 누르면 그쪽이 먹으므로 우리에게는 안 온다.
 *
 * ★★ **값은 전부 '칸' 단위다**(픽셀이 아니라). 폰은 도트도 화면도 커서 데스크탑과 같은
 *   픽셀 값을 쓰면 제자리 꿈틀거림밖에 안 된다 — 칸으로 세야 어느 화면에서나 **제 몸 높이의
 *   몇 배**로 똑같이 튄다. 데스크탑 값(px)을 옮길 때는 `MASCOT_U`(2px)로 나누고,
 *   프레임당 속도는 프레임 수 차이(22fps → 30fps)만큼 다시 잡았다.
 */
class Mascot {

    // ★ **프레임은 30fps 다**(`CooldownWallpaperService.FRAME_MS`). 16fps 로는 튀는 게
    //   느릿느릿 보였다 — 아래 '프레임 수'로 적은 값은 전부 30fps 기준이다.
    private var t = 0
    private var yoff = 0f      // 위아래 용수철 (칸). 양수가 아래.
    private var vy = 0f

    private var surprise = 0

    // 심심할 때 하는 잔동작 — 한 번에 하나씩, 사이사이 쉰다
    private var blink = 0
    private var look = 0
    private var tilt = 0
    private var stretch = 0
    private var wave = 0
    private var lookDir = 1
    private var tiltDir = 1
    private var waveDir = 1
    private var nextGesture = 50

    // 오래 심심할 때 하는 딴짓 — 제자리에서 하는 것(act)과 자리 비움(away)
    private var quiet = 0            // 마지막 반응 뒤 흐른 프레임 (딴짓 중에는 안 센다)
    private var act = ""             // "" / "type"(노트북) / "nap"(낮잠) / "ball"(공 놀이)
    private var actLeft = 0
    // ★★ **딴짓은 곧바로 지우지 않는다 — 접는 동안(`ACT_EXIT`)을 둔다.** 한 프레임에
    //   갈아 끼우면 몸이 옆으로 튀고 노트북·공이 허공에서 사라진다(데스크탑에서 겪은 것).
    private var exit = 0             // 접는 중인 남은 프레임
    private var exitAct = ""         // 접는 중인 것이 무엇이었나 (소품을 치워야 한다)
    private var ballAt = floatArrayOf(0f, 0f)   // 공이 마지막으로 있던 자리 (px)
    private var away = 0
    private var awayTotal = 0
    // 올라오는 데 걸리는 프레임. **실수다** — 부르면 '지금 내려가 있는 만큼'에서 잇느라
    // RUSH_BACK / 지금sink 로 잡힌다(정수로 자르면 그 자리에서 튄다).
    private var rise = SINK_FRAMES.toFloat()
    private var rushing = false      // 불려서 호다닥 올라오는 중인가
    private var runx = 0f            // 달려오는 중의 가로 어긋남 (칸, 0 이면 제자리)
    private var running = 0
    private val zzz = ArrayList<FloatArray>()   // 낮잠 z [x, y, 남은 수명] — 칸

    // 누르기 — **꾹 누르면 눌린다**
    private var touching = false     // 손가락이 얹혀 있는 중
    private var holdF = 0            // 얹힌 뒤 흐른 프레임 (HOLD_FRAMES 넘으면 눌리기 시작)
    private var pressed = false
    private var press = 0f           // 눌린 정도 0~1
    private var launch = 0           // 이 동안은 높이 가둠을 푼다 (꾹 누르기의 특전)

    private var clicks = 0f          // 콕 누적 — 식으면서 준다
    private var faint = 0

    // 박자 맞히기(콤보)
    private var combo = 0            // 지금 단 (0~COMBO_MAX)
    private var beats = 0            // 이 판에서 박자를 맞힌 횟수
    private var beatAt = -999        // 마지막으로 박자를 맞힌 프레임
    private var trick = 0            // 재주 남은 프레임
    private var trickLen = 1
    private var flipN = 0            // 세로 회전(앞구르기) 바퀴
    private var spinN = 0            // 가로 회전(팽이돌기) 바퀴
    // 완주 축하 — **폭죽을 쏘는 동안(`finale`)이 아니라 반짝이가 다 사그라들 때까지(`party`)**
    // 가 한 장면이다. `finale` 로만 재면 화면엔 폭죽이 한창인데 클로디만 먼저 평소로 돌아가
    // 누르는 것에 반응한다(데스크탑에서 실제로 그랬다).
    private var finale = 0           // 폭죽을 **쏘는** 남은 프레임
    private var party = false        // 축하가 흐르는 중 (폭죽 + 사그라드는 꼬리까지)
    private val shells = ArrayList<Shell>()   // 쏘아 올린 폭죽
    private var shot = 0             // 쏘고 나서 팔을 든 채 늘어나 있는 프레임
    private var hopIn = 0            // 다음 폴짝(=쏘는 박자)까지 남은 프레임
    private var popSide = -1         // 파티 폭죽을 든 손 (겨누는 쪽)
    private var popMouth = floatArrayOf(0f, 0f)   // 그 크래커 입 자리(칸) — 알은 여기서 나간다
    private var popDrop = 0          // 다 쏘고 크래커를 아래로 치우는 프레임

    /** 뿜은 반짝이. 자리는 **몸 한가운데 기준 칸**이다. */
    private val sparks = ArrayList<Spark>()
    private var sparkCool = 0

    // 화면 크기(몸 한가운데 기준 칸) — 자리 비움에서 얼마나 내려갈지, 폭죽을 어디까지
    // 뿌릴지가 여기서 나온다. `step` 이 그릴 자리를 받아 다시 잰다.
    private var edgeL = -20f
    private var edgeR = 20f
    private var edgeT = -20f
    private var edgeB = 20f

    // 마지막으로 그린 자리(px) — 크래커 입처럼 **px 로 셈한 것을 다시 칸으로** 옮길 때 쓴다
    private var lastCx = 0f
    private var lastCy = 0f

    /** 반짝이 한 알. 색은 **번호로만** 들고 있다 — 팔레트는 그리는 쪽에만 있다. */
    private class Spark(
        var x: Float, var y: Float, var vx: Float, var vy: Float,
        var life: Float, val born: Float, val ink: Int,
    )

    /** 쏘아 올린 폭죽 한 알 — 자리에 닿으면 거기서 터진다. 자리는 칸. */
    private class Shell(
        var x: Float, var y: Float, val vx: Float, val vy: Float,
        var left: Int, val ink: Int,
    )

    /**
     * 한 프레임. 배경화면·미리보기가 그리기 직전에 부른다.
     * 그릴 자리를 같이 받는다 — 자리 비움·폭죽이 **화면 크기**를 알아야 하기 때문.
     */
    fun step(cx: Float, cy: Float, u: Float, w: Float, h: Float) {
        if (u > 0f) {
            edgeL = -cx / u
            edgeR = (w - cx) / u
            edgeT = -cy / u
            edgeB = (h - cy) / u
        }
        t++
        stepPhysics()
        if (faint == 0) idleStep()
    }

    /** 용수철 한 걸음. 눌림으로 생긴 속도를 제자리(0)로 부드럽게 당긴다. */
    private fun stepPhysics() {
        stepFloaters()
        if (exit > 0) exit--                   // 하던 딴짓을 접는 중 (기절해도 흘러야 끝난다)
        if (faint > 0) {                       // 기절 — 늘어졌다가 깨어난다
            faint--
            vy *= 0.8f; yoff *= 0.85f
            if (faint == 0) {                  // 깨어남 — 펑 하고 털어낸다
                yoff = 0f; vy = 0f
                burst(SPARK_WAKE, 1.2f)
            }
            return
        }

        // 얹은 채로 HOLD_FRAMES 를 넘기면 '꾹 누름' — 그전까지는 그냥 콕 찌른 것이다
        if (touching && !pressed) {
            holdF++
            if (holdF >= HOLD_FRAMES) pressed = true
        }
        if (pressed) {                         // 눌리는 중 — 제자리에서 점점 납작해진다
            press = min(1f, press + 1f / PRESS_FRAMES)
            vy *= 0.6f
            yoff *= 0.8f
        }

        vy += -SPRING_K * yoff
        vy *= 1f - SPRING_DAMP
        // 너무 높이 안 뜨게 — 단 크게 튕겨 오른 직후(`launch`)에는 일부러 풀어 준다.
        // ★ 끝에 닿으면 **속도까지 죽인다.** 위치만 가두면 연타할 때 속도가 계속 쌓여
        //   천장에 붙은 채 한참 못 내려온다 — 그게 '연타하면 마비된 것 같다' 의 정체였다.
        val lift = if (launch > 0) { launch--; LAUNCH_LIFT } else LIFT
        var next = yoff + vy
        if (next < -lift) { next = -lift; vy = 0f } else if (next > lift * 0.55f) {
            next = lift * 0.55f; vy = 0f
        }
        yoff = next

        if (surprise > 0) surprise--
        if (clicks > 0f) clicks = max(0f, clicks - CLICK_DECAY)
        if (combo > 0 && t - beatAt > BEAT_WINDOW) { combo = 0; beats = 0 }   // 박자가 끊겼다
        if (party) {                           // 완주 축하 — 크래커를 뻥, 다 사그라들 때까지
            if (finale > 0) finale--
            else if (sparks.isEmpty() && shells.isEmpty()) party = false   // 이제 축하 끝
            if (shot > 0) shot--
            if (hopIn <= 0) {                  // 한 박자 — 웅크렸다 폴짝 뛰며 뻥
                hopIn = FINALE_HOP
                boost(JUMP * FINALE_POP)
                if (finale > 0) {
                    shot = SHOT_FRAMES
                    repeat(rndInt(SHELL_SHOTS_MIN, SHELL_SHOTS_MAX + 1)) { shoot() }
                    aim()                      // 다음 박자에 겨눌 쪽 (미리 그쪽으로 들고 있게)
                }
            }
            hopIn--
            if (finale <= 0 && popDrop < POP_DROP) popDrop++   // 크래커를 아래로 치운다
            stepShells()
        }
        if (trick > 0) {                       // 재주 — 부리는 동안 반짝이 꼬리를 흘린다
            trick--
            if (trick % TRICK_TRAIL == 0) {
                sparks.add(spark(rnd(-2f, 2f), yoff + rnd(-2f, 2f),
                    rnd(-0.09f, 0.09f), rnd(-0.13f, 0.02f), SPARK_LIFE * 0.7f, INK_BODY))
            }
        }
    }

    /** 떠다니는 것들(반짝이·낮잠 z·달려오기) 한 걸음. **기절 중에도 흘러야 하므로** 여기서 돈다. */
    private fun stepFloaters() {
        if (sparkCool > 0) sparkCool--
        var i = 0
        while (i < sparks.size) {
            val s = sparks[i]
            s.x += s.vx; s.y += s.vy; s.vy += SPARK_GRAV; s.life -= 1f
            if (s.life <= 0f) sparks.removeAt(i) else i++
        }
        var k = 0
        while (k < zzz.size) {                 // z 는 비스듬히 떠오른다
            val z = zzz[k]
            z[0] += 0.048f; z[1] -= 0.104f; z[2] -= 1f
            if (z[2] <= 0f) zzz.removeAt(k) else k++
        }
        if (running > 0) {                     // 달려오는 중 — 왼쪽에서 제자리로
            running--
            runx = -RUN_DIST * (running.toFloat() / RUN_FRAMES).pow(1.6f)
        }
    }

    // -------------------------------------------------- 심심할 때 하는 잔동작
    /**
     * 쉬는 동안 이따금 잔동작을 시킨다 — 깜빡·손 흔들기·눈 굴리기·고개 갸웃·기지개·
     * 반짝이·폴짝. 한 번에 하나씩만, 반응(눌림)으로 출렁일 땐 쉰다.
     * 한참(`DEEP_IDLE`) 아무도 안 건드리면 **딴짓에 열중하거나 자리를 비운다.**
     */
    private fun idleStep() {
        if (away > 0) {                        // 자리 비움 — 인사만 하고 내려가 있는다
            away--
            if (wave > 0) wave--
            if (away == 0 && rushing) {        // 불려서 올라왔다 — 허둥지둥 달려온다
                rushing = false
                rise = SINK_FRAMES.toFloat()
                runx = -RUN_DIST
                running = RUN_FRAMES
                surprise = SURPRISE_FRAMES * 5
            }
            return
        }
        if (act.isNotEmpty()) {                // 뭔가에 열중하는 중 — 잔동작을 겹치지 않는다
            actLeft--
            if (act == "nap" && actLeft % NAP_EVERY == 0) {
                zzz.add(floatArrayOf(1.5f, -4.5f, NAP_LIFE))
            }
            if (actLeft <= 0) {
                endAct()    // 혼자 끝날 때도 접는 동안을 거친다 (누른 것과 같은 결)
                quiet = 0   // 하나가 끝나자마자 다음 것이 이어지지 않게 되감는다
            }
            return
        }
        quiet++
        if (blink > 0) blink--
        if (look > 0) look--
        if (tilt > 0) tilt--
        if (stretch > 0) stretch--
        if (wave > 0) wave--
        val busy = blink > 0 || look > 0 || tilt > 0 || stretch > 0 || wave > 0 ||
            exit > 0 || party
        val moving = abs(vy) + abs(yoff) > 0.5f
        if (quiet > DEEP_IDLE && !busy && !moving && !touching) {
            beginAbsorbed()
            return
        }
        nextGesture--
        if (nextGesture <= 0 && !busy && !moving) {
            beginGesture()
            nextGesture = rndInt(40, 135)      // 다음 잔동작까지 1.3~4.5초
        }
    }

    /** 잔동작 하나 고르기. 깜빡·손 흔들기는 자주. */
    private fun beginGesture() {
        when (rndInt(0, 9)) {
            0, 1 -> blink = 4
            2, 3 -> { wave = 32; waveDir = if (rnd() < 0.5f) -1 else 1 }
            4 -> { look = 35; lookDir = if (rnd() < 0.5f) -1 else 1 }
            5 -> { tilt = 46; tiltDir = if (rnd() < 0.5f) -1 else 1 }
            6 -> stretch = 30
            7 -> burst(4, 0.8f)                // 혼자 반짝반짝
            else -> { vy -= JUMP * 0.5f; burst(3, 0.6f) }   // 혼자 살짝 폴짝
        }
    }

    /**
     * 오래 심심해서 하는 일 하나를 고른다 — 노트북·낮잠·공 놀이, 또는 자리 비움.
     * 시작할 때 `quiet` 를 되감고, 딴짓 중에는 그 값을 안 세므로 다음 것까지 또 뜸을 들인다.
     */
    private fun beginAbsorbed() {
        quiet = 0
        val pick = rndInt(0, 13)               // 노트북 4 · 낮잠 3 · 공 3 · 자리 비움 3
        when {
            pick < 4 -> startAct("type")
            pick < 7 -> startAct("nap")
            pick < 10 -> startAct("ball")
            else -> {                          // 손 한 번 흔들고 아래로 쏙 내려갔다 돌아온다
                rise = SINK_FRAMES.toFloat()
                rushing = false
                awayTotal = AWAY_LEAD + rndInt(AWAY_MIN, AWAY_MAX)
                away = awayTotal
                wave = AWAY_LEAD
            }
        }
    }

    private fun startAct(name: String) {
        act = name
        actLeft = rndInt(ACT_MIN, ACT_MAX)
    }

    /**
     * 딴짓을 **접는 동안**을 둔다 — 곧바로 지우면 자세도 소품도 한 프레임에 갈려 튄다
     * (노트북 두드리다 누르면 몸이 옆으로 뛰고 노트북이 사라졌다).
     * `exit` 가 도는 동안 `draw` 가 몸을 제자리로 되돌리며 소품을 치운다.
     */
    private fun endAct() {
        if (act.isEmpty()) return
        exitAct = act
        exit = ACT_EXIT
        act = ""
    }

    /** 자리 비움에서 얼마나 내려가 있나 (0=제자리, 1=화면 아래로 완전히). */
    private fun sinkAmount(): Float {
        if (away <= 0) return 0f
        val gone = awayTotal - away - AWAY_LEAD    // 인사가 끝난 뒤 흐른 프레임
        if (gone < 0) return 0f                    // 아직 손 흔드는 중
        if (away < rise) return away.toFloat() / rise          // 올라오는 중
        if (gone < SINK_FRAMES) return gone.toFloat() / SINK_FRAMES   // 내려가는 중
        return 1f
    }

    // -------------------------------------------------- 손가락
    /**
     * 누르기 시작 — **누르는 순간 반응한다**(떼기를 기다리지 않는다).
     * 박자를 맞혔으면 콤보가 오르고, 아무 때나 친 것은 발밑에 먼지만 인다.
     * ★ 홈 화면에서는 런처가 떼기(UP)를 채 갈 수 있어, 반응을 여기서 내야 놀 수 있다.
     */
    fun press() {
        quiet = 0
        endAct()          // 하던 딴짓은 곧바로 지우지 않고 접는다 (한 프레임에 안 갈리게)
        touching = true
        holdF = 0
        if (away > 0) {
            // 자리를 비웠는데 불렀다 — **호다닥 올라와서 허둥지둥**한다.
            // ★★ **달려오는 연출은 완전히 숨었을 때만 시작한다.** 보이는 채로 왼쪽에 옮겨
            //   놓으면 그 순간 옆으로 순간이동한다 — '올라오다 갑자기 왼쪽에서 튀어나오는'
            //   것이 그것이었다. 안 보이는 동안 미리 옮겨 두면 한 동작으로 이어진다.
            val now = sinkAmount()
            if (!rushing) {
                rushing = now >= 1f
                if (rushing) runx = -RUN_DIST
            }
            // ★ 올라오기는 **지금 내려가 있는 만큼**에서 잇는다 — `away` 만 갈아 끼우면
            //   내려가는 도중에 부른 경우 아래로 뚝 떨어졌다가 올라온다.
            away = RUSH_BACK
            rise = RUSH_BACK / max(now, 0.001f)
            wave = 0
            if (rushing) surprise = SURPRISE_FRAMES * 5
            return
        }
        // 기절했거나 **완주 축하가 흐르는 동안은 안 받는다** — 끼어들면 축하가 도로
        // 반응 놀이가 된다. `finale`(쏘는 동안)이 아니라 `party`(폭죽이 다 질 때까지)다.
        if (faint > 0 || party) return

        // **박자 맞히기** — 통통 튀다 **바닥에 멎는 그 순간**에만 맞은 것으로 친다.
        // 한 주기(약 18프레임)에 4프레임(≈0.13초)뿐이다 — 아무 때나 쳐도 되면 맛이 없다.
        val onBeat = yoff >= BEAT_AT && abs(vy) <= BEAT_V
        beats = if (onBeat && t - beatAt <= BEAT_WINDOW) beats + 1 else if (onBeat) 1 else 0
        beatAt = t
        combo = tier(beats)
        boost(JUMP + combo * COMBO_JUMP)
        surprise = SURPRISE_FRAMES
        // ★ **박자를 맞히면 덜 지친다.** 그래야 '너무 빠르게 마구 누르면 콤보가 아니라
        //   기절에 먼저 닿는다' 가 된다 (박자대로면 식는 속도를 못 이겨 안 뻗는다).
        clicks += if (combo > 0) 1.0f else 2.4f
        if (combo > 0) {
            sparkCool = 0
            if (TIER_UP.contains(beats)) {     // 이 한 방으로 단이 올랐다 — 재주가 나온다
                burst(SPARK_POKE + combo * 3, 1f + combo * 0.25f)
                beginTrick(combo)
                if (combo >= COMBO_MAX) {      // 완주 — 크래커를 들고 축하 폭죽
                    finale = FINALE_FRAMES
                    party = true
                    popDrop = 0
                    aim()
                    // ★ 첫 발은 **한 프레임 뒤**다 — 크래커를 한 번 그려 봐야 입이
                    //   어디인지 알고(`popMouth`), 거기서 알이 나간다.
                    hopIn = 1
                    beats = 0
                    combo = 0
                }
            } else {                           // 아직 올라가는 중 — 소박하게
                burst(2 + combo, 0.6f + combo * 0.08f)
            }
        } else {                               // 아무 때나 친 것 — 발밑에 먼지만
            burst(SPARK_DUST, 1f, foot = true)
        }
        if (clicks >= FAINT_AT) {              // 과부하 — 뻗는다
            faint = FAINT_FRAMES
            clicks = 0f
            surprise = 0
            pressed = false
            press = 0f
        }
    }

    /**
     * 떼기 — **눌린 만큼 튕겨 오른다.** 꾹 눌렀던 거면 **팡** 터진다.
     *
     * ★★ 여기에 '기 모아 뛰기'·'기 모아 쏘기'·'쓰다듬기(하트)' 를 차례로 붙여 봤다가
     * 데스크탑에서 **전부 뺐다.** 소품이나 기호를 얹으면 게임 같거나 유치했다 —
     * **누르니까 눌린다**, 그 이상 필요 없다. 새 아이디어를 넣기 전에 이 셋을 기억할 것.
     */
    fun release() {
        touching = false
        holdF = 0
        if (!pressed) return
        pressed = false
        val amount = press
        press = 0f
        if (faint > 0) return
        boost(JUMP * 0.4f + PRESS_POP * amount, launch = true)
        if (amount >= PRESS_BURST) {
            surprise = SURPRISE_FRAMES * 3
            sparkCool = 0                      // 일부러 만든 순간이라 쿨다운과 무관하게
            burst(SPARK_POKE + (8 * amount).toInt(), 1.2f + amount * 0.8f)
        }
    }

    /** 끌기 등으로 반응을 물릴 때 — 눌린 것은 그냥 펴진다(튕기지 않는다). */
    fun cancel() {
        touching = false
        holdF = 0
        pressed = false
        press = 0f
    }

    /**
     * 한동안 안 보이다가 다시 보일 때 — **지친 것도 하던 딴짓도 잊는다.**
     * 그리는 동안에만 시간이 흐르므로, 안 그러면 어제 찌른 게 남아 오늘 한 번에 기절한다.
     */
    fun rest() {
        clicks = 0f
        combo = 0
        beats = 0
        cancel()
        quiet = 0
        act = ""
        exit = 0
        away = 0
        rushing = false
        running = 0
        runx = 0f
        party = false
        finale = 0
        shells.clear()
        shot = 0
        popDrop = 0
        zzz.clear()
    }

    /** 맞힌 횟수로 지금 몇 단인지. 한 단을 올리는 데 `TIER_HITS` 번씩 걸린다. */
    private fun tier(hits: Int): Int {
        if (hits <= 0) return 0
        return min(COMBO_MAX, TIER_UP.count { hits > it } + 1)
    }

    /** 콤보 단에 맞는 재주를 시작한다. 1단은 반짝이뿐, 5단은 앞구르기+팽이돌기+폭죽. */
    private fun beginTrick(combo: Int) {
        val spec = TRICKS[combo - 1]
        trick = spec[0]
        trickLen = max(1, spec[0])
        flipN = spec[1]
        spinN = spec[2]
        if (combo >= COMBO_MAX) {              // 마지막 단 — 사방으로 크게 한 번 더
            for (k in 0 until 10) {
                val a = rnd(0f, TAU)
                sparks.add(spark(cos(a) * 2f, yoff + sin(a) * 2f,
                    cos(a) * 0.3f, sin(a) * 0.24f - 0.07f,
                    SPARK_LIFE * rnd(0.7f, 1f), INK_BODY))
            }
        }
    }

    /**
     * 이번 박자에 크래커를 겨누는 쪽을 고른다 — **넓은 쪽이 자주 걸리게.**
     * (클로디가 화면 어디에 앉아 있느냐에 따라 한쪽이 좁다)
     */
    private fun aim() {
        val left = max(1f, -edgeL)
        val right = max(1f, edgeR)
        popSide = if (rnd() < left / (left + right)) -1 else 1
    }

    /**
     * **크래커 입에서 폭죽 한 알이 나간다.** 겨눈 쪽으로 쏘고, 날아간 알은
     * `stepShells` 가 자리에 닿는 순간 터뜨린다.
     *
     * ★★ **'몇 프레임에 도착'으로 잡지 말 것** — 화면 끝까지가 수십 칸이라 몇 프레임이면
     * 한 프레임에 제 몸을 몇 개씩 건너뛴다. 그걸 점 하나로 그리면 **아예 안 보인다**
     * (데스크탑에서 '이펙트만 뜨고 물체가 안 나온다' 였다). **속도**로 잡고 그리는 것도
     * 점이 아니라 **지나온 자리를 잇는 줄기**다(`drawShells`).
     */
    private fun shoot() {
        val sx = popMouth[0]
        val sy = popMouth[1]
        val fx = if (popSide < 0) rnd(edgeL + 1f, min(-2f, edgeL + 2f))
        else rnd(max(2f, edgeR - 2f), edgeR - 1f)
        val fy = rnd(edgeT + 2f, -3f)          // 위쪽에서 터진다
        val ink = FIREWORK_INKS[rndInt(0, FIREWORK_INKS.size)]
        val dist = kotlin.math.hypot(fx - sx, fy - sy)
        val fly = (dist / SHELL_SPEED).toInt().coerceIn(SHELL_MIN, SHELL_MAX)
        shells.add(Shell(sx, sy, (fx - sx) / fly, (fy - sy) / fly, fly, ink))
        // 뻥 — 입에서 색종이가 흩어진다 (터지는 건 저 위지만 쏜 자리도 티가 나야 한다)
        for (k in 0 until POP_CONFETTI) {
            val a = MascotSprite.POP_TILT + rnd(-0.55f, 0.55f)
            val sp = rnd(0.18f, 0.42f)
            sparks.add(spark(sx, sy, cos(a) * sp * popSide, sin(a) * sp,
                SPARK_LIFE * rnd(0.4f, 0.7f), FIREWORK_INKS[rndInt(0, FIREWORK_INKS.size)]))
        }
    }

    /** 쏘아 올린 알 한 걸음 — 꼬리를 흘리며 날아가다 자리에 닿으면 거기서 터진다. */
    private fun stepShells() {
        var i = 0
        while (i < shells.size) {
            val s = shells[i]
            s.x += s.vx; s.y += s.vy; s.left--
            sparks.add(spark(s.x, s.y, s.vx * 0.12f, s.vy * 0.12f + 0.02f,
                SPARK_LIFE * SHELL_TRAIL, s.ink))
            if (s.left <= 0) { pop(s.x, s.y, s.ink); shells.removeAt(i) } else i++
        }
    }

    /**
     * 쏘아 올린 알이 터진다 — 그 자리에서 사방으로 흩뿌린다.
     * ★ **발마다 퍼지는 정도가 다르다** — 다 같으면 한 발을 복사해 놓은 것처럼 보인다.
     */
    private fun pop(fx: Float, fy: Float, ink: Int) {
        val spread = rnd(FINALE_SPREAD_MIN, FINALE_SPREAD_MAX)
        val core = if (rnd() < 0.5f) INK_STAR else ink
        val n = rndInt(FINALE_PER_MIN, FINALE_PER_MAX + 1)
        for (k in 0 until n) {
            val a = rnd(0f, TAU)
            val r = rnd(0.12f, 0.34f) * spread
            sparks.add(spark(fx, fy, cos(a) * r, sin(a) * r - 0.05f,
                SPARK_LIFE * rnd(1.3f, 2.0f), if (k % 4 == 0) core else ink))
        }
    }

    /**
     * 위로 튀어오르게 한다. `launch` 면 잠시 **훨씬 높이** 나가도록 가둠을 푼다 —
     * 그건 꾹 누르기의 특전이고, 그냥 누르기·콤보는 `MAX_VY` 를 넘지 않는다.
     * ★ 상한이 없으면 연타할 때 속도가 쌓여 천장에 붙은 채 굼떠 보인다.
     * ★ **콤보의 상은 높이가 아니다** — 높이는 꾹 누르기 몫이고, 콤보는 재주·반짝이로 갚는다.
     */
    private fun boost(power: Float, launch: Boolean = false) {
        vy -= power
        if (launch) this.launch = LAUNCH_FRAMES else vy = max(vy, -MAX_VY)
    }

    /**
     * 반짝이를 한 움큼 뿜는다 — **흩뿌려** 놓고 사그라든다.
     * ★★ **부채꼴로 가지런히 퍼뜨리지 말 것** — 도형을 그린 것처럼 보인다(실제로 그랬다).
     * `foot` 이면 **발밑에서 옆으로 낮게** 인다(그냥 콕 찔렀을 때의 먼지),
     * 아니면 **머리 위로** 떠오른다(박자를 맞혀 크게 뛰었을 때).
     * ★★ **누를 때마다 뿜지 말 것** — 연타에서 앞것과 겹쳐 지저분하다(`SPARK_COOL`).
     */
    private fun burst(count: Int, power: Float, foot: Boolean = false) {
        if (sparkCool > 0) return
        sparkCool = SPARK_COOL
        for (k in 0 until count.coerceIn(0, 16)) {
            if (foot) {                        // 발밑 먼지 — 낮게 깔려 옆으로 퍼진다
                val side = if (rnd() < 0.5f) -1f else 1f
                sparks.add(spark(
                    side * rnd(1f, 3f), yoff + rnd(3f, 4.2f),
                    side * rnd(0.10f, 0.23f) * power, rnd(-0.11f, -0.03f) * power,
                    SPARK_LIFE * rnd(0.45f, 0.75f), INK_BODY,
                ))
            } else {                           // 머리 위 — 떠오른다
                sparks.add(spark(
                    rnd(-1f, 1f) * SPARK_SPREAD * power, yoff - rnd(2.5f, 7f),
                    rnd(-0.08f, 0.08f) * power, rnd(-0.31f, -0.13f) * power,
                    SPARK_LIFE * rnd(0.62f, 1f), INK_BODY,
                ))
            }
        }
    }

    private fun spark(x: Float, y: Float, vx: Float, vy: Float, life: Float, ink: Int) =
        Spark(x, y, vx, vy, life, life, ink)

    /**
     * 누른 자리가 클로디 위인가. `u` 는 칸 크기(px).
     * ★ 자리를 비운 동안에도 참이다 — **없는 자리를 누르면 불러낸 것**이라 호다닥 돌아온다.
     */
    fun hits(cx: Float, cy: Float, u: Float, x: Float, y: Float): Boolean {
        val halfW = (MascotSprite.COLS / 2f + 2f) * u
        val halfH = MascotSprite.ROWS / 2f * u
        return abs(x - cx) <= halfW + u && abs(y - (cy + yoff * u)) <= halfH + u
    }

    /**
     * 그린다. `cx`,`cy` 는 한가운데, `u` 는 칸 크기(px), `color` 는 몸 색,
     * `bg` 는 눈을 파낼 색, `star` 는 별·공 색, `prop` 은 노트북·z 같은 소품 색.
     */
    fun draw(
        c: Canvas, cx: Float, cy: Float, u: Float,
        color: Int, bg: Int, star: Int = color, prop: Int = star,
        green: Int = star, red: Int = color, glow: Int = star,
    ) {
        lastCx = cx
        lastCy = cy
        val body = Paint().apply { this.color = color }
        val hole = Paint().apply { this.color = bg }
        // 붓은 색 수만큼만 만든다 — 알마다 만들면 30fps 에서 GC 가 쉴 틈이 없다.
        // 뒤 셋(초록·빨강·흰빛)은 **축하 폭죽 전용**이다(평소 반짝이는 몸 색뿐).
        val inks = arrayOf(body, Paint().apply { this.color = star },
            Paint().apply { this.color = prop }, Paint().apply { this.color = green },
            Paint().apply { this.color = red }, Paint().apply { this.color = glow })

        if (faint > 0) {
            drawSprite(c, cx, cy + u, u * FAINT_SCALE, u * FAINT_SCALE,
                sin(t * 0.15f) * 0.20f, "faint", 1, 1, MascotSprite.LEGS_WIDE, body, hole)
            drawDizzy(c, cx, cy - MascotSprite.ROWS / 2f * u * FAINT_SCALE - u, u, inks[INK_STAR])
            drawSparks(c, cx, cy, u, inks)
            return
        }

        // 자리 비움 — 화면 아래로 쏙 내려가 있다 (화면 밖이라 저절로 잘린다)
        val sink = sinkAmount()
        if (sink >= 1f) {
            drawSparks(c, cx, cy, u, inks)
            return
        }

        // --- 잔동작에서 오는 보정값들 ---
        var eyeDx = 0                          // 눈 굴리기는 **칸 단위**로 옮긴다
        if (look > 0) {
            val pr = 1f - look / 35f
            if (sin(pr * PI) > 0.5f) eyeDx = lookDir
        }
        var lean = 0f                          // 좌우 기울임은 **고개 갸웃할 때만**
        if (tilt > 0) {
            val pr = 1f - tilt / 46f
            lean = tiltDir * 0.42f * sin(pr * PI)
        }
        var sxk = 1f
        var syk = 1f
        var reach = 0f
        if (stretch > 0) {                     // 기지개 — 위로 쭉 늘었다 준다 (팔도 번쩍)
            reach = sin((1f - stretch / 30f) * PI)
            syk = 1f + 0.24f * reach
            sxk = 1f - 0.10f * reach
        }
        // 뛸 때 몸이 늘었다 눌린다 — 이게 점프의 손맛이다(**세로로만**)
        val squash = (-vy * SQUASH).coerceIn(SQUASH_MIN, SQUASH_MAX)
        sxk *= 1f - squash * 0.55f
        syk *= 1f + squash
        // 재주 — 앞구르기(세로 회전)와 팽이돌기(가로 회전). 배율을 음수까지 돌리면
        // 도트를 그대로 뒤집어 그리므로 획이 안 뭉개진다.
        if (trick > 0) {
            val pr = (1f - trick.toFloat() / trickLen) * TAU
            if (flipN > 0) syk *= cos(pr * flipN)
            if (spinN > 0) sxk *= cos(pr * spinN)
        }
        val springScale = 1f + max(0f, -yoff) * 0.02f      // 위로 뜰수록 살짝 커짐
        // 낮잠 중엔 더 크고 느리게 숨쉰다
        val breathe = if (act == "nap") 1f + 0.10f * sin(t * 0.037f)
        else 1f + 0.045f * sin(t * 0.067f)
        sxk *= springScale * breathe
        syk *= springScale * breathe

        var px = cx + runx * u                             // 달려오는 중이면 왼쪽에서
        var py = cy + (sin(t * 0.089f) * 0.55f + yoff) * u  // 잔잔한 통통 + 용수철
        py += sink * (edgeB + MascotSprite.ROWS) * u        // 자리 비우러 내려가는 중
        val speed = abs(vy) + abs(yoff)                    // 출렁이는 중이면 신났다

        // 표정과 팔 — 콕 찔리면 놀라 만세, 출렁이면 눈웃음, 기지개도 만세
        var expr: String
        var armL: Int?
        var armR: Int?
        var legs = MascotSprite.LEGS
        var lap: FloatArray? = null            // 노트북 자리 (몸과 따로 움직인다)
        var ball: FloatArray? = null
        var extra: IntArray? = null
        var popper: FloatArray? = null         // 파티 폭죽 자리 [x, y]
        if (pressed) {                         // 눌리는 중 — 눈을 질끈 감고 납작해진다
            expr = "blink"; armL = 0; armR = 0
            sxk *= 1f + PRESS_FLAT * 0.75f * press
            syk *= 1f - PRESS_FLAT * press
            py += 1.6f * press * u
        } else if (running > 0 || rushing) {   // 달려오는 중 (불려서 올라오는 동안부터)
            // ★ 발 박자는 `t` 로 센다 — **올라오는 중과 달리는 중이 같은 걸음으로 이어진다**
            //   (`running` 으로 세면 땅에 닿는 순간 걸음이 처음으로 되감긴다).
            expr = if (surprise > 0) "surprise" else "grin"
            val step = (t / RUN_BEAT) % 2 == 0
            armL = if (step) -1 else 0
            armR = if (step) 0 else -1
            legs = if (step) MascotSprite.LEGS else MascotSprite.LEGS_RUN
        } else if (exit > 0) {                 // 하던 걸 접고 돌아앉는 중 — 소품을 치운다
            val k = exit / ACT_EXIT.toFloat()  // 1 → 0
            sxk *= 1f - 0.5f * sin((1f - k) * PI)   // 가운데서 납작 = 돌아앉는 결
            val done = if (surprise > 0) "surprise" else "idle"
            when (exitAct) {
                "type" -> {
                    px += MascotSprite.TYPE_SHIFT * u * k   // 물렸던 몸이 제자리로
                    expr = if (k > 0.5f) "side" else done
                    armL = if (k > 0.5f) null else 0
                    armR = armL
                    extra = if (k > 0.5f) MascotSprite.TYPE_ARM[1] else null
                    // 노트북은 몸을 안 따라간다 — 제자리에서 화면 밖으로 떨어진다
                    lap = floatArrayOf(cx + MascotSprite.TYPE_SHIFT * u,
                        py + (1f - k) * (1f - k) * (edgeB + MascotSprite.ROWS) * u)
                }
                "nap" -> {                     // 자다 깼다 — 눈을 뜨며 일어난다
                    py += 0.75f * u * k
                    expr = if (k > 0.5f) "blink" else done
                    armL = if (k > 0.5f) 1 else 0
                    armR = armL
                }
                else -> {                      // 공 놀이 — 던져 둔 공은 아래로 떨어져 나간다
                    expr = done; armL = 0; armR = 0
                    ball = floatArrayOf(ballAt[0],
                        ballAt[1] + (1f - k) * (1f - k) * (edgeB + MascotSprite.ROWS) * u)
                }
            }
        } else if (party) {                    // 완주 축하 — 크래커를 겨눴다 뻥, 폴짝, 만세
            expr = "grin"
            if (shot > 0) {                    // 막 터뜨렸다 — 팔을 든 채 몸이 늘고 밀린다
                armL = -1; armR = -1
                val s = shot / SHOT_FRAMES.toFloat()
                syk *= 1f + SHOT_STRETCH * s
                sxk *= 1f - SHOT_STRETCH * 0.4f * s
                px -= popSide * POP_KICK * s * u
            } else if (finale > 0 && hopIn <= SHOT_WIND) {   // 쏘기 직전 — 웅크린다
                armL = 0; armR = 0
                syk *= 1f - SHOT_CROUCH
                sxk *= 1f + SHOT_CROUCH * 0.6f
                py += 0.8f * u
            } else {                           // 그 사이엔 뜬 동안만 만세
                armL = if (yoff < -FINALE_CHEER) -1 else 0
                armR = armL
            }
            // 크래커는 **겨눈 쪽 손**에 들려 있다. 팔이 오르내리면 같이 따라간다.
            if (popDrop < POP_DROP) {
                val row = if (armL == -1) 3 else 4
                var hy = py + (row + 0.5f - 4f) * u * syk
                if (popDrop > 0) {             // 다 쏘면 손에서 놓아 아래로 치운다
                    val k = popDrop / POP_DROP.toFloat()
                    hy += k * k * (edgeB + MascotSprite.ROWS) * u
                }
                popper = floatArrayOf(px + popSide * MascotSprite.POP_HAND * u * sxk, hy)
            }
        } else if (surprise > 0) {
            expr = "surprise"; armL = -1; armR = -1
        } else if (speed > 0.6f) {
            expr = "grin"; armL = -1; armR = -1
        } else if (wave > 0) {                 // 손 흔들기 — 한 팔만 번쩍, 그 팔이 오르내린다
            val up = (wave / 5) % 2 == 0
            expr = "grin"
            armL = if (waveDir < 0) (if (up) -1 else 0) else 0
            armR = if (waveDir < 0) 0 else (if (up) -1 else 0)
        } else if (act == "type") {            // 노트북에 열중 — **옆으로 돌아앉아** 본다
            expr = "side"
            // 옆모습이라 기본 팔은 안 그리고(null), **노트북까지 뻗은 긴 팔**을 대신 그린다
            armL = null; armR = null
            extra = MascotSprite.TYPE_ARM[(actLeft / TYPE_BEAT) % 2]
            px += MascotSprite.TYPE_SHIFT * u  // 노트북까지 한 그림이 되게 몸을 오른쪽으로
            lap = floatArrayOf(px, py)         // 접을 땐 몸만 돌아가고 이건 제자리에 남는다
        } else if (act == "nap") {             // 낮잠 — 눈 감고 팔을 늘어뜨린 채 크게 숨쉰다
            expr = "blink"; armL = 1; armR = 1
            py += 0.75f * u
        } else if (act == "ball") {            // 공 놀이 — 던져 올렸다 받는다
            val frac = (t % BALL_PERIOD) / BALL_PERIOD.toFloat()
            ball = floatArrayOf(
                cx + sin(frac * TAU) * 2f * u,
                py - 4.4f * u - sin(frac * PI) * BALL_H * u,
            )
            ballAt = ball                      // 접을 때 공이 여기서부터 떨어진다
            val flying = frac > 0.12f && frac < 0.88f
            expr = if (flying) "grin" else "surprise"
            armL = if (flying) -1 else 0
            armR = armL
            eyeDx = if (frac < 0.5f) 1 else 0  // 공을 눈으로 좇는다
        } else if (blink > 0) {
            expr = "blink"; armL = 0; armR = 0
        } else if (reach > 0.5f) {
            expr = "idle"; armL = -1; armR = -1
        } else {
            expr = "idle"; armL = 0; armR = 0
        }

        drawSprite(c, px, py, u * sxk, u * syk, lean, expr, armL, armR, legs, body, hole, extra, eyeDx)
        if (lap != null) drawLaptop(c, lap[0], lap[1], u, inks[INK_PROP])
        if (popper != null) drawPopper(c, popper[0], popper[1], u, inks)
        if (ball != null) {
            // ★ 공을 몸 색으로 그리면 **몸에 붙은 혹**처럼 보인다 — 호박색 장난감으로 둔다
            val r = BALL_R * u
            c.drawRect(ball[0] - r, ball[1] - r, ball[0] + r, ball[1] + r, inks[INK_STAR])
        }
        drawSparks(c, cx, cy, u, inks)
        drawShells(c, cx, cy, u, inks)   // 날아가는 폭죽은 반짝이보다 앞에
        drawZzz(c, cx, cy, u, inks[INK_PROP])
    }

    /** 도트 한 장. `lean` 은 **계단식 기울임** — 윗줄일수록 옆으로 더 민다(도트 결 유지). */
    private fun drawSprite(
        c: Canvas, cx: Float, cy: Float, ux: Float, uy: Float, lean: Float,
        expr: String, armL: Int?, armR: Int?, legs: Array<String>,
        body: Paint, hole: Paint, extra: IntArray? = null, eyeDx: Int = 0,
    ) {
        val mid = (MascotSprite.HEAD.size + legs.size) / 2f
        val x0 = cx - MascotSprite.COLS / 2f * ux
        val y0 = cy - mid * uy

        // ★ **칸 경계를 정수 픽셀로 맞춘다.** 실수 좌표로 그리면 이웃한 칸이 서로 다르게
        //   반올림돼 **머리카락 같은 틈**이 줄줄이 생긴다(폰에서 실제로 그랬다).
        //   좌우·상하 모두 '같은 식'을 반올림하므로 이웃 칸이 정확히 같은 선을 쓴다.
        // ★ 재주(회전)를 부리면 `ux`/`uy` 가 음수가 되므로 **두 점을 정렬해서** 그린다.
        fun cell(col: Int, row: Int, span: Int, p: Paint) {
            val slide = lean * (mid - row) * uy
            val ax = Math.round(x0 + col * ux + slide).toFloat()
            val bx = Math.round(x0 + (col + span) * ux + slide).toFloat()
            val ay = Math.round(y0 + row * uy).toFloat()
            val by = Math.round(y0 + (row + 1) * uy).toFloat()
            c.drawRect(min(ax, bx), min(ay, by), max(ax, bx), max(ay, by), p)
        }

        if (extra != null) {                   // 길게 뻗은 팔(타이핑) 같은 덧그림
            var i = 0
            while (i < extra.size) { cell(extra[i], extra[i + 1], 1, body); i += 2 }
        }
        if (armL != null) {
            val a = MascotSprite.ARM[armL] ?: MascotSprite.ARM[0]!!
            cell(a[0], a[1], 1, body)
        }
        if (armR != null) {                    // 오른팔은 좌우 뒤집기 (옆모습이면 안 그림)
            val a = MascotSprite.ARM[armR] ?: MascotSprite.ARM[0]!!
            cell(MascotSprite.COLS - 1 - a[0], a[1], 1, body)
        }

        for (rows in arrayOf(MascotSprite.HEAD, legs)) {
            val top = if (rows === legs) MascotSprite.HEAD.size else 0
            for ((r, line) in rows.withIndex()) {
                var col = 0
                while (col < line.length) {
                    if (line[col] != '#') { col++; continue }
                    var run = 1
                    while (col + run < line.length && line[col + run] == '#') run++
                    cell(col, top + r, run, body)
                    col += run
                }
            }
        }

        val eyes = MascotSprite.EYES[expr] ?: MascotSprite.EYES["idle"]!!
        var i = 0
        while (i < eyes.size) {
            cell(eyes[i] + eyeDx, eyes[i + 1], 1, hole)
            i += 2
        }
    }

    /**
     * 노트북 — ★★ **도트가 아니라 다각형 둘**로 그린다. 도트 격자로는 이 크기에서
     * 무슨 모양을 해도 판때기나 쐐기였다(데스크탑에서 다 해 보고 내린 결론).
     * ★ 고개를 따라 **기울이지 않는다** — 바닥에 놓인 물건이라 기울면 미끄러진 것처럼 보인다.
     */
    private fun drawLaptop(c: Canvas, cx: Float, cy: Float, u: Float, p: Paint) {
        val b = MascotSprite.LAP_BASE
        c.drawRect(cx + b[0] * u, cy + b[1] * u, cx + b[2] * u, cy + b[3] * u, p)
        val lid = MascotSprite.LAP_LID
        val path = Path()
        path.moveTo(cx + lid[0] * u, cy + lid[1] * u)
        var i = 2
        while (i < lid.size) { path.lineTo(cx + lid[i] * u, cy + lid[i + 1] * u); i += 2 }
        path.close()
        c.drawPath(path, p)
    }

    /**
     * 파티 폭죽(크래커) — 쥔 쪽은 좁고 입은 넓은 원뿔을 겨눈 쪽으로 기울여 든다.
     * 입 자리를 `popMouth` 에 남겨 뒀다가 **다음 발이 거기서 나가게** 한다.
     *
     * ★ 노트북과 같이 **다각형**이다(도트 격자로는 이 크기에 원뿔이 안 나온다).
     * ★ 몸과 같은 색으로 그리면 **몸에 붙은 혹**처럼 보인다 — 밝은 색 물건으로 둔다.
     */
    private fun drawPopper(c: Canvas, hx: Float, hy: Float, u: Float, inks: Array<Paint>) {
        val dx = cos(MascotSprite.POP_TILT) * popSide
        val dy = sin(MascotSprite.POP_TILT)
        val px = -dy * popSide                 // 축에 수직인 방향
        val py = dx * popSide
        val mx = hx + dx * MascotSprite.POP_LEN * u
        val my = hy + dy * MascotSprite.POP_LEN * u
        popMouth = floatArrayOf((mx - lastCx) / u, (my - lastCy) / u)
        val b = MascotSprite.POP_BASE * u
        val m = MascotSprite.POP_MOUTH * u
        val path = Path()
        path.moveTo(hx + px * b, hy + py * b)
        path.lineTo(mx + px * m, my + py * m)
        path.lineTo(mx - px * m, my - py * m)
        path.lineTo(hx - px * b, hy - py * b)
        path.close()
        c.drawPath(path, inks[INK_GLOW])
        // 입에 두른 띠 한 줄 — 원뿔이 통짜 세모로 안 보이게 (호박색 = 잔치 물건)
        val band = Paint().apply {
            color = inks[INK_STAR].color
            strokeWidth = u * 0.5f
        }
        c.drawLine(mx + px * m, my + py * m, mx - px * m, my - py * m, band)
    }

    /**
     * 쏘아 올려 날아가는 중인 폭죽.
     * ★★ **점 하나로 그리지 말 것** — 한 프레임에 제 몸을 몇 개씩 지나므로 눈에 안 걸린다
     * (데스크탑에서 '이펙트만 뜨고 물체가 안 나온다' 였다). **지나온 자리를 잇는 줄기**로
     * 그린다 — 머리가 제일 크고 꼬리로 갈수록 작아져 솟아오르는 결이 남는다.
     */
    private fun drawShells(c: Canvas, cx: Float, cy: Float, u: Float, inks: Array<Paint>) {
        for (s in shells) {
            val n = max(2, (kotlin.math.hypot(s.vx, s.vy) / SHELL_STEP).toInt())
            for (i in 0 until n) {
                val k = i / n.toFloat()        // 0 = 머리(지금 자리), 1 = 꼬리 끝
                plus(c, cx + (s.x - s.vx * k) * u, cy + (s.y - s.vy * k) * u,
                    u * (0.5f - 0.28f * k), inks[s.ink])
            }
        }
    }

    /** 낮잠 z — 머리 위로 비스듬히 떠오른다(멀어질수록 커진다). */
    private fun drawZzz(c: Canvas, cx: Float, cy: Float, u: Float, p: Paint) {
        for (z in zzz) {
            val k = u * (0.7f + 0.5f * (1f - z[2] / NAP_LIFE))
            for ((r, line) in MascotSprite.NAP_Z.withIndex()) {
                for (col in line.indices) {
                    if (line[col] != '#') continue
                    val x = cx + z[0] * u + col * k
                    val y = cy + z[1] * u + r * k
                    c.drawRect(x, y, x + k, y + k, p)
                }
            }
        }
    }

    /** 기절 — 별 셋이 머리 위를 돈다 (도트답게 십자). */
    private fun drawDizzy(c: Canvas, cx: Float, top: Float, u: Float, p: Paint) {
        for (k in 0 until 3) {
            val a = t * 0.26f + k * 2.09f
            val x = cx + sin(a) * u * 3.4f
            val y = top + sin(a + 1.57f) * u * 1.1f
            plus(c, x, y, u * 0.5f, p)
        }
    }

    /** 뿜은 반짝이 — 도트 십자가 떠오르며 **수명대로 작아진다**(가루가 흩어지는 결). */
    private fun drawSparks(c: Canvas, cx: Float, cy: Float, u: Float, inks: Array<Paint>) {
        for (s in sparks) {
            val k = u * SPARK_SIZE * (s.life / s.born)
            if (k < 0.6f) continue
            plus(c, cx + s.x * u, cy + s.y * u, k, inks[s.ink])
        }
    }

    private fun plus(c: Canvas, x: Float, y: Float, r: Float, p: Paint) {
        c.drawRect(x - r, y - r / 3f, x + r, y + r / 3f, p)
        c.drawRect(x - r / 3f, y - r, x + r / 3f, y + r, p)
    }

    // -------------------------------------------------- 난수
    // ★ **`Math.random()` 을 쓰지 않는다** — 폰 없이 뽑는 미리보기 PNG 가 돌릴 때마다
    //   달라지면 '바뀐 것'과 '흔들린 것'을 못 가린다. 씨앗이 고정된 자리 난수를 쓴다.
    private var seed = 0x2545F491

    private fun rnd(): Float {
        seed = seed * 1103515245 + 12345
        return ((seed ushr 9) and 0xFFFF) / 65536f
    }

    private fun rnd(a: Float, b: Float) = a + (b - a) * rnd()

    private fun rndInt(a: Int, b: Int) = a + (rnd() * (b - a)).toInt().coerceAtMost(b - a - 1)

    /**
     * 테스트가 노는 규칙을 확인할 때 들여다보는 창구 — **화면에는 안 쓴다.**
     * (박자를 맞히면 단이 오르고 안 지치는가 / 마구 두드리면 뻗는가)
     */
    fun debug() = Debug(combo, faint > 0, party, clicks)

    data class Debug(val combo: Int, val fainted: Boolean, val finale: Boolean, val tired: Float)

    /** 미리보기·테스트에서 특정 장면을 세워 보기 위한 손잡이 (실제 동작은 스스로 고른다). */
    fun poseForPreview(what: String) {
        rest()
        when (what) {
            "type", "nap", "ball" -> { startAct(what); actLeft = ACT_MAX }
            "faint" -> faint = FAINT_FRAMES / 2
            // 반쯤 내려간 순간 — 다 내려가면 화면 밖이라 그림에 아무것도 안 남는다
            "away" -> { awayTotal = AWAY_MIN; away = AWAY_MIN - AWAY_LEAD - SINK_FRAMES / 2 }
            // 완주 축하 — 크래커를 들고 쏘는 장면 (몇 프레임 굴려야 폭죽이 뜬다)
            "party" -> { finale = FINALE_FRAMES; party = true; popDrop = 0; aim(); hopIn = 1 }
        }
    }

    private companion object {
        const val PI = Math.PI.toFloat()
        const val TAU = (Math.PI * 2).toFloat()

        const val SPRING_K = 0.13f
        const val SPRING_DAMP = 0.10f

        const val LIFT = 7.0f            // 최대한 뜨는 높이 (칸) — 몸이 8칸이니 거의 한 몸
        const val JUMP = 2.7f            // 콕 찔렀을 때 (칸/프레임)
        const val MAX_VY = 3.3f          // 콕·콤보로 낼 수 있는 최대 속도 (꾹 누르기는 예외)

        // **꾹 누르고 있으면 눌린다.** 떼면 용수철처럼 튕겨 오른다.
        const val HOLD_FRAMES = 10       // 이만큼 얹혀 있어야 '꾹 누름' (0.33초)
        const val PRESS_FRAMES = 35f     // 이만큼이면 최대로 눌린다
        const val PRESS_FLAT = 0.46f     // 최대로 납작해지는 정도
        const val PRESS_POP = 14.0f      // 떼면 튕겨 오르는 힘 (눌린 만큼 곱해진다)
        const val PRESS_BURST = 0.35f    // 이만큼 넘게 눌렸다 떼면 **팡** 터진다
        const val LAUNCH_LIFT = 55f      // 날아오르는 동안엔 이 높이까지 (칸)
        const val LAUNCH_FRAMES = 62

        // 뛸 때 몸이 늘었다 눌린다(스쿼시·스트레치) — 없으면 그냥 미끄러질 뿐이라 손맛이 없다
        const val SQUASH = 0.12f
        const val SQUASH_MAX = 0.34f
        const val SQUASH_MIN = -0.20f

        // **박자 맞히기** — 바닥에 멎는 순간에만 맞은 것으로 친다(한 주기 18프레임 중 4프레임).
        const val BEAT_AT = 1.6f         // 제자리보다 이만큼 아래(칸)까지 내려가야
        const val BEAT_V = 0.8f          // 그 자리에서 이만큼 느려야 (되돌아 오르는 꼭짓점)
        const val BEAT_WINDOW = 27       // 이 프레임 안에 다시 맞혀야 이어진다 (0.9초)
        const val COMBO_MAX = 5
        const val COMBO_JUMP = 0.17f     // 콤보 한 번마다 조금 더 높이 (상한 MAX_VY 에 걸린다)

        // ★ **한 단을 올리는 데 두세 번 맞혀야 한다.** 올라가는 중엔 소박하게 반짝이만,
        //   그 단의 마지막 한 방에서 재주가 터진다 — 그래야 올라가는 맛이 있다.
        val TIER_HITS = intArrayOf(2, 2, 3, 3, 3)
        val TIER_UP = IntArray(TIER_HITS.size) { i -> TIER_HITS.take(i + 1).sum() }

        /** 단마다 다른 재주 — (프레임 수, 세로 회전 바퀴, 가로 회전 바퀴) */
        val TRICKS = arrayOf(
            intArrayOf(0, 0, 0),         // 1단 반짝이만
            intArrayOf(18, 1, 0),        // 2단 앞구르기
            intArrayOf(22, 2, 0),        // 3단 두 바퀴
            intArrayOf(19, 0, 2),        // 4단 팽이돌기
            intArrayOf(24, 2, 2),        // 5단 둘 다 + 폭죽
        )
        const val TRICK_TRAIL = 3        // 재주 부리는 동안 이 프레임마다 반짝이 하나

        // ── 완주 축하 (데스크탑 `slim.py` 의 `FINALE_*`·`SHELL_*`·`SHOT_*` 를 옮긴 것) ──
        // ★★ 축하하는 동안은 **누르는 걸 안 받는다**(`party`). 그 '동안' 은 쏘는 프레임이
        //   아니라 **반짝이가 다 사그라들 때까지**다 — 안 그러면 화면엔 폭죽이 한창인데
        //   클로디만 먼저 평소로 돌아가 클릭에 반응한다.
        const val FINALE_FRAMES = 49     // 폭죽을 쏘아 올리는 프레임 (약 1.6초)
        const val FINALE_PER_MIN = 9     // 한 발에 뿜는 반짝이 (발마다 다르게)
        const val FINALE_PER_MAX = 14
        const val FINALE_SPREAD_MIN = 0.55f   // 발마다 퍼지는 정도도 다르다
        const val FINALE_SPREAD_MAX = 1.35f
        // ★ 폴짝은 **누를 때보다 작고 잦게**(춤추듯). 크게 한 번씩 뛰면 눌러서 튄 것과
        //   똑같아 보인다 — '축하 중에 누르면 계속 점프한다' 로 읽힌다(데스크탑에서 겪음).
        const val FINALE_HOP = 12        // 이 프레임마다 한 박자 (웅크렸다 쏘며 폴짝)
        const val FINALE_POP = 1.25f     // 그 폴짝의 힘 (`JUMP` 배수) — 콕 찌른 것보다 작게
        const val FINALE_CHEER = 0.5f    // 이만큼(칸) 떠 있으면 두 팔 번쩍

        // 파티 폭죽(크래커)으로 쏘아 올리는 알 — 모양은 `MascotSprite.POP_*`
        const val SHELL_SPEED = 3.0f     // 날아가는 속도 (칸/프레임)
        const val SHELL_MIN = 6          // 아무리 가까워도 이만큼은 날아간다 (프레임)
        const val SHELL_MAX = 19         // 아무리 멀어도 이만큼 안에 닿는다 (안 늘어지게)
        const val SHELL_SHOTS_MIN = 2    // 한 박자에 이만큼 쏜다
        const val SHELL_SHOTS_MAX = 3
        const val SHELL_STEP = 0.8f      // 줄기를 이만큼(칸)마다 한 알씩 찍어 잇는다
        const val SHELL_TRAIL = 0.8f     // 지나온 자리에 남기는 연기 (반짝이 수명 배수)
        const val POP_CONFETTI = 6       // 쏠 때 입에서 흩어지는 색종이
        const val POP_KICK = 1.1f        // 쏜 반동으로 몸이 뒤로 밀리는 정도 (칸)
        const val POP_DROP = 12          // 다 쏘고 나면 이만큼에 걸쳐 아래로 치운다
        // 던지는 몸짓 — **웅크렸다가 쭉 펴며 쏜다.** 그냥 통통 튀면 누른 것에 반응하는
        // 것과 구별이 안 된다.
        const val SHOT_WIND = 4          // 쏘기 전에 이만큼 웅크린다
        const val SHOT_CROUCH = 0.18f
        const val SHOT_FRAMES = 8        // 쏘고 나서 이만큼은 팔을 든 채 몸이 늘어난다
        const val SHOT_STRETCH = 0.20f

        const val SURPRISE_FRAMES = 10
        // ★ 어쩌다 기절하면 놀라니까 높게 잡는다 — 작정하고 두드려야 뻗는다.
        //   한 번에 +2.4(박자를 맞히면 +1.0), 매 프레임 CLICK_DECAY 만큼 식는다.
        const val FAINT_AT = 46f
        const val CLICK_DECAY = 0.104f
        const val FAINT_FRAMES = 80      // 약 2.7초
        // 기절 땐 X_X 눈이 보일 만큼만 키운다. ★ 1.3 은 딴 친구가 나타난 것처럼 커 보였다.
        const val FAINT_SCALE = 1.15f

        const val SPARK_LIFE = 30f       // 반짝이 수명 (프레임)
        const val SPARK_POKE = 6         // 박자를 맞혔을 때 (콤보만큼 더 나온다)
        const val SPARK_DUST = 3         // 그냥 콕 찔렀을 때 발밑에 이는 먼지
        const val SPARK_WAKE = 7         // 기절에서 깨어날 때
        const val SPARK_COOL = 35        // 한 번 뿜으면 이만큼은 다시 안 뿜는다 (연타에 안 겹치게)
        const val SPARK_SPREAD = 4f      // 흩뿌리는 가로 폭 (칸)
        const val SPARK_SIZE = 0.55f     // 반짝이 크기 (칸 대비). 작을수록 가루 같다.
        const val SPARK_GRAV = 0.0096f   // 떠오르던 것이 처지는 정도
        const val INK_BODY = 0
        const val INK_STAR = 1
        const val INK_PROP = 2
        // 아래 셋은 **축하 폭죽·크래커 전용** — 평소 반짝이는 몸 색뿐이다
        const val INK_GREEN = 3
        const val INK_RED = 4
        const val INK_GLOW = 5           // 크래커 몸통 (바탕과 최대 대비)
        // ★ **폭죽 색에 `INK_GLOW`(제목색)를 넣지 말 것** — 밝은 테마에서 거의 검정이라
        //   **까만 폭죽**이 날아간다(미리보기에서 확인). 그건 물건 색이지 불꽃 색이 아니다.
        val FIREWORK_INKS = intArrayOf(INK_BODY, INK_STAR, INK_GREEN, INK_RED)

        /** 딴짓을 접는 데 걸리는 프레임 — 곧바로 지우면 한 프레임에 딴 그림으로 갈린다. */
        const val ACT_EXIT = 11

        // ── 딴짓 (오래 심심할 때) ──
        // ★ 자주 하면 산만하다 — `DEEP_IDLE` 은 넉넉히 잡고, **딴짓 중에는 `quiet` 를 안 센다.**
        const val DEEP_IDLE = 2000       // 이만큼(≈68초) 아무 반응이 없으면 딴짓을 시작한다
        const val ACT_MIN = 270          // 한 가지 딴짓 지속 (9~18초)
        const val ACT_MAX = 540
        const val AWAY_MIN = 230         // 자리 비움 지속 (8~15초)
        const val AWAY_MAX = 460
        const val AWAY_LEAD = 27         // 내려가기 전에 손 흔드는 프레임 (인사하고 간다)
        // ★ **내려가는 시간은 데스크탑보다 길게 잡는다.** 데스크탑은 작업표시줄 바로 아래로
        //   숨으면 끝이지만(제 몸 두 배), 폰은 **화면 아래 끝까지** 가야 해서 열 배가 넘는다 —
        //   같은 프레임 수로 하면 한 프레임에 제 몸을 지나쳐 사라진 것처럼 보인다.
        const val SINK_FRAMES = 34       // 아래로 내려가는 데 걸리는 프레임 (약 1.1초)
        const val RUSH_BACK = 20         // 자리 비운 사이 부르면 이만큼 만에 호다닥 올라온다
        const val RUN_DIST = 7.5f        // 부르면 이만큼 왼쪽에서 **달려서** 온다 (칸)
        const val RUN_FRAMES = 22
        const val RUN_BEAT = 3           // 이 프레임마다 발을 바꾼다
        const val TYPE_BEAT = 4          // 이 프레임마다 손을 바꿔 두드린다
        const val NAP_EVERY = 40         // 낮잠 중 이 프레임마다 z 하나
        const val NAP_LIFE = 48f
        const val BALL_PERIOD = 35       // 공을 던졌다 받는 주기 (프레임)
        const val BALL_H = 6.5f          // 공이 오르는 높이 (칸)
        const val BALL_R = 1.6f          // 공 반지름 (칸)
    }
}
