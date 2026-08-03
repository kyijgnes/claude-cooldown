package com.kyijgnes.cooldown.wallpaper

import android.graphics.Canvas
import android.graphics.Paint
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.max
import kotlin.math.sin

/**
 * 배경화면에 사는 클로디 — 데스크탑 위젯(`windows/skins/slim.py`)의 도트 친구를 폰으로 옮겼다.
 * 그림표는 생성기가 만든 `MascotSprite`(같은 원본)를 쓰고, **여기는 움직임만** 맡는다.
 *
 * 상태(튀는 속도·표정·기 모은 양)를 들고 있으므로 **그리는 쪽마다 하나씩** 만든다
 * (배경화면 엔진 하나, 꾸미기 미리보기 하나). `WallpaperArt` 는 상태를 안 갖는다.
 *
 * 노는 법 세 가지:
 *  - **콕 찌르기** — 펄쩍 뛰고 눈이 커진다. 뛰는 동안 몸이 늘었다 눌린다(스쿼시·스트레치).
 *  - **길게 누르기** — 쭈그려 앉아 부르르 떨며 **기를 모은다.** 떼면 모은 만큼 높이 뛴다
 *    (꽉 채우면 반짝이를 흩뿌리며 붕 뜬다).
 *    ★ **홈 화면에서는 런처가 길게 누르기를 자기 메뉴로 채 간다** — 그래서 이건 꾸미기
 *      화면(미리보기)에서만 제대로 된다. 홈에서는 아래 '연타 콤보'가 그 자리를 맡는다.
 *  - **연타** — 빠르게 이어 찌르면 **콤보**가 쌓여 점점 높이 뛰고(반짝이도 터진다),
 *    그러다 지치면 **기절**한다(X_X + 별이 뱅뱅). 잠깐 못 논다.
 *
 * ★ **터치는 배경화면이 직접 받는다** — 런처가 흘려 준 좌표가 클로디 위면 반응.
 *   아이콘·위젯 위를 누르면 그쪽이 먹으므로 우리에게는 안 온다.
 */
class Mascot {

    // ★ **프레임은 30fps 다**(`CooldownWallpaperService.FRAME_MS`). 16fps 로는 튀는 게
    //   느릿느릿 보였다 — 아래 '프레임 수'로 적은 값은 전부 30fps 기준이다.
    private var t = 0
    // ★ **용수철은 픽셀이 아니라 '칸' 단위로 센다.** 폰은 도트가 크고 화면도 커서
    //   픽셀로 잡으면 데스크탑과 같은 값이 제자리 꿈틀거림밖에 안 된다.
    //   칸으로 세면 어느 화면에서나 **몸 높이의 몇 배**로 똑같이 튄다.
    private var yoff = 0f      // 위아래 용수철 (칸)
    private var vy = 0f
    private var lean = 0f      // 좌우 기울임(계단식 밀기)
    private var vLean = 0f
    private var spinDir = 1

    private var surprise = 0
    private var blink = 0
    private var nextBlink = 120

    private var charging = false
    private var charge = 0f    // 0~1
    private var heldFrames = 0

    private var clicks = 0f    // 콕 누적 — 식으면서 준다
    private var faint = 0
    private var lastPoke = -999
    private var combo = 0      // 빠르게 이어 찌른 횟수 — 뛰는 힘이 커진다

    /**
     * 반짝이 [x, y, vx, vy, 남은 수명] — **누를 때마다** 머리 위로 부채꼴로 흩뿌린다.
     * 세게 눌렀거나 콤보가 붙으면 한 움큼 더, 기 모으는 동안엔 한 알씩 새어 나온다.
     */
    private val sparks = ArrayList<FloatArray>()

    /** 한 프레임. 배경화면·미리보기가 그리기 직전에 부른다. */
    fun step() {
        t++
        if (faint > 0) {                       // 기절 — 늘어졌다가 깨어난다
            faint--
            vy *= 0.8f; yoff *= 0.85f
            vLean *= 0.9f; lean *= 0.9f
            if (faint == 0) {                  // 깨어남 — 펑 하고 털어낸다
                yoff = 0f; vy = 0f; lean = 0f; vLean = 0f
                burst(SPARK_WAKE, 1.4f)
            }
            stepSparks()
            return
        }

        if (charging) {
            heldFrames++
            charge = (charge + 1f / CHARGE_FRAMES).coerceAtMost(1f)
            // 기 모으는 동안 한 알씩 새어 나온다 (모을수록 자주)
            if (heldFrames % max(3, 9 - (charge * 6f).toInt()) == 0) burst(1, 0.55f)
        }

        vy += -SPRING_K * yoff
        vy *= 1f - SPRING_DAMP
        yoff = (yoff + vy).coerceIn(-LIFT, LIFT * 0.55f)

        vLean += -SPRING_K * lean
        vLean *= 1f - SPRING_DAMP
        lean += vLean

        if (surprise > 0) surprise--
        if (clicks > 0f) clicks = max(0f, clicks - CLICK_DECAY)
        if (blink > 0) {
            blink--
        } else if (--nextBlink <= 0) {
            blink = 5
            nextBlink = 120 + (t % 180)   // 규칙적이지 않게 (난수 없이도 흩어진다)
        }
        stepSparks()
    }

    private fun stepSparks() {
        var i = 0
        while (i < sparks.size) {
            val s = sparks[i]
            s[0] += s[2] * 0.5f; s[1] += s[3] * 0.5f; s[3] += 0.06f; s[4] -= 1f
            if (s[4] <= 0f) sparks.removeAt(i) else i++
        }
    }

    /** 누르기 시작 — 기를 모은다. */
    fun press() {
        if (faint > 0) return
        charging = true
        charge = 0f
        heldFrames = 0
    }

    /**
     * 떼기 — 모은 만큼 뛴다. 짧게 눌렀다 떼면 그냥 콕 찌른 것이다.
     * 연타로 지치면(`FAINT_AT`) 기절한다.
     */
    fun release() {
        if (faint > 0) { charging = false; charge = 0f; return }
        val held = charging && heldFrames >= CHARGE_MIN
        // 빠르게 이어 찌르면 콤보 — 홈 화면에서는 길게 누르기를 런처가 채 가므로 이쪽으로 논다
        combo = if (!held && t - lastPoke <= COMBO_FRAMES) (combo + 1).coerceAtMost(COMBO_MAX) else 0
        lastPoke = t
        val power = when {
            held -> JUMP + charge * CHARGE_JUMP
            else -> JUMP + combo * COMBO_JUMP
        }
        charging = false

        vy -= power
        vLean += SPIN * spinDir * (1f + charge)
        spinDir = -spinDir
        surprise = SURPRISE_FRAMES

        // **누를 때마다** 반짝인다. 꽉 채웠거나 콤보가 붙었으면 한 움큼 더.
        val big = (held && charge > 0.6f) || combo >= 3
        burst(if (big) SPARK_BIG + combo else SPARK_TAP + combo, if (big) 1.35f else 1f)
        clicks += if (held) 1f else 2f              // 콕콕 찌르는 쪽이 더 지친다
        if (clicks >= FAINT_AT) {
            faint = FAINT_FRAMES
            clicks = 0f
            surprise = 0
            charge = 0f
        }
        if (!held) charge = 0f
    }

    /** 끌기 등으로 반응을 물릴 때. */
    fun cancel() {
        charging = false
        charge = 0f
    }

    /**
     * 한동안 안 보이다가 다시 보일 때 — **지친 걸 잊는다.**
     * 그리는 동안에만 시간이 흐르므로, 안 그러면 어제 찌른 게 남아 오늘 한 번에 기절한다.
     */
    fun rest() {
        clicks = 0f
        combo = 0
        charging = false
        charge = 0f
    }

    /** 머리 위쪽 반원으로 고르게 흩뿌린다. `power` 는 퍼지는 힘. */
    private fun burst(count: Int, power: Float) {
        val n = count.coerceIn(1, 20)
        for (k in 0 until n) {
            val a = (PI * (k + 0.5f) / n).toFloat()
            sparks.add(floatArrayOf(
                cos(a) * 4f, -6f,
                -cos(a) * 1.6f * power,
                (-1.5f - sin(a) * 1.3f) * power,
                (SPARK_LIFE - (k % 4) * 4).toFloat(),
            ))
        }
    }

    /** 누른 자리가 클로디 위인가. `u` 는 칸 크기(px). */
    fun hits(cx: Float, cy: Float, u: Float, x: Float, y: Float): Boolean {
        val halfW = (MascotSprite.COLS / 2f + 2f) * u
        val halfH = MascotSprite.ROWS / 2f * u
        return abs(x - cx) <= halfW + u && abs(y - (cy + yoff * u)) <= halfH + u
    }

    /**
     * 그린다. `cx`,`cy` 는 한가운데, `u` 는 칸 크기(px), `color` 는 몸 색,
     * `bg` 는 눈을 파낼 색, `star` 는 기절했을 때 머리 위를 도는 별 색.
     */
    fun draw(c: Canvas, cx: Float, cy: Float, u: Float, color: Int, bg: Int, star: Int = color) {
        val body = Paint().apply { this.color = color }
        val hole = Paint().apply { this.color = bg }

        if (faint > 0) {
            drawSprite(c, cx, cy + 2f, u * FAINT_SCALE, u * FAINT_SCALE,
                sin(t * 0.1f) * 0.20f, "faint", 1, MascotSprite.LEGS_WIDE, body, hole)
            drawDizzy(c, cx, cy - MascotSprite.ROWS / 2f * u * FAINT_SCALE - u, u, star)
            drawSparks(c, cx, cy, u, body)
            return
        }

        // 기 모으는 중에는 쭈그리고 부르르 떤다 — 모을수록 더 눌리고 더 떤다
        val squat = if (charging) charge else 0f
        val shake = if (charging) sin(t * 0.8f) * 0.10f * charge else 0f

        val breathe = 1f + 0.045f * sin(t * 0.045f)
        val stretch = (-yoff * 0.055f).coerceIn(-0.20f, 0.34f)   // 뜰수록 늘고 눌릴수록 납작
        val sx = breathe * (1f - stretch * 0.6f + squat * 0.22f)
        val sy = breathe * (1f + stretch - squat * 0.30f)

        val y = cy + (yoff + sin(t * 0.06f) * 0.10f + squat * 0.9f) * u
        val speed = abs(vy) + abs(yoff)
        val expr = when {
            charging -> "grin"
            surprise > 0 -> "surprise"
            speed > 1.2f -> "grin"
            blink > 0 -> "blink"
            else -> "idle"
        }
        val arm = when {
            charging -> 1                 // 기 모을 땐 팔을 내린다
            surprise > 0 || speed > 1.2f -> -1
            else -> 0
        }

        drawSprite(c, cx, y, u * sx, u * sy, lean + shake, expr, arm, MascotSprite.LEGS, body, hole)
        drawSparks(c, cx, cy, u, body)
    }

    /** 도트 한 장. `lean` 은 **계단식 기울임** — 윗줄일수록 옆으로 더 민다(도트 결 유지). */
    private fun drawSprite(
        c: Canvas, cx: Float, cy: Float, ux: Float, uy: Float, lean: Float,
        expr: String, arm: Int, legs: Array<String>, body: Paint, hole: Paint,
    ) {
        val mid = MascotSprite.ROWS / 2f
        val x0 = cx - MascotSprite.COLS / 2f * ux
        val y0 = cy - mid * uy

        // ★ **칸 경계를 정수 픽셀로 맞춘다.** 실수 좌표로 그리면 이웃한 칸이 서로 다르게
        //   반올림돼 **머리카락 같은 틈**이 줄줄이 생긴다(폰에서 실제로 그랬다).
        //   좌우·상하 모두 '같은 식'을 반올림하므로 이웃 칸이 정확히 같은 선을 쓴다.
        fun cell(col: Int, row: Int, span: Int, p: Paint) {
            val slide = lean * (mid - row) * uy
            val left = Math.round(x0 + col * ux + slide).toFloat()
            val right = Math.round(x0 + (col + span) * ux + slide).toFloat()
            val top = Math.round(y0 + row * uy).toFloat()
            val bottom = Math.round(y0 + (row + 1) * uy).toFloat()
            c.drawRect(left, top, right, bottom, p)
        }

        val a = MascotSprite.ARM[arm] ?: MascotSprite.ARM[0]!!
        cell(a[0], a[1], 1, body)
        cell(MascotSprite.COLS - 1 - a[0], a[1], 1, body)

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
            cell(eyes[i], eyes[i + 1], 1, hole)
            i += 2
        }
    }

    /** 기절 — 별 셋이 머리 위를 돈다 (도트답게 십자). */
    private fun drawDizzy(c: Canvas, cx: Float, top: Float, u: Float, color: Int) {
        val p = Paint().apply { this.color = color }
        for (k in 0 until 3) {
            val a = t * 0.18f + k * 2.09f
            val x = cx + sin(a) * u * 3.4f
            val y = top + sin(a + 1.57f) * u * 1.1f
            plus(c, x, y, u * 0.5f, p)
        }
    }

    /**
     * 뿜은 반짝이 — 도트 십자가 떠오르며 사그라든다.
     * ★ 크기를 수명에 **그대로** 비례시키면 뿜자마자 안 보인다 — 끝까지 또렷하게 남긴다.
     */
    private fun drawSparks(c: Canvas, cx: Float, cy: Float, u: Float, p: Paint) {
        for (s in sparks) {
            val k = u * 0.5f * (0.45f + 0.55f * s[4] / SPARK_LIFE)
            if (k < 0.6f) continue
            plus(c, cx + s[0] * u * 0.25f, cy + s[1] * u * 0.25f, k, p)
        }
    }

    private fun plus(c: Canvas, x: Float, y: Float, r: Float, p: Paint) {
        c.drawRect(x - r, y - r / 3f, x + r, y + r / 3f, p)
        c.drawRect(x - r / 3f, y - r, x + r / 3f, y + r, p)
    }

    private companion object {
        const val SPRING_K = 0.13f
        const val SPRING_DAMP = 0.10f
        const val SPIN = 0.10f

        const val LIFT = 7.0f            // 최대한 뜨는 높이 (칸) — 몸이 10칸이니 거의 한 몸 반
        const val JUMP = 2.7f            // 콕 찔렀을 때 (칸/프레임)
        const val CHARGE_JUMP = 3.6f     // 기를 꽉 모았을 때 더해지는 힘
        const val CHARGE_FRAMES = 80f    // 약 2.7초면 가득 (30fps)
        const val CHARGE_MIN = 10        // 이보다 짧게 누르면 그냥 콕

        const val SURPRISE_FRAMES = 20
        const val CLICK_DECAY = 0.018f
        const val COMBO_FRAMES = 22      // 약 0.75초 안에 다시 찌르면 이어진다 (30fps)
        const val COMBO_MAX = 5
        const val COMBO_JUMP = 0.8f      // 콤보 한 번마다 더 높이
        const val FAINT_AT = 12f         // 콕 여섯 번쯤
        const val FAINT_FRAMES = 80      // 약 2.7초
        // 기절 땐 X_X 눈이 보일 만큼만 키운다. ★ 1.3 은 딴 친구가 나타난 것처럼 커 보였다.
        const val FAINT_SCALE = 1.15f

        const val SPARK_LIFE = 44f       // 반짝이 수명 (프레임)
        const val SPARK_TAP = 4          // 그냥 콕 눌렀을 때 (+콤보)
        const val SPARK_BIG = 9          // 기를 채웠거나 콤보가 붙었을 때 (+콤보)
        const val SPARK_WAKE = 12        // 기절에서 깨어날 때
    }
}
