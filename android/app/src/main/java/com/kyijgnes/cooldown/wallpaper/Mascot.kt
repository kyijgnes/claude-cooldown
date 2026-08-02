package com.kyijgnes.cooldown.wallpaper

import android.graphics.Canvas
import android.graphics.Paint
import kotlin.math.abs
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
 *  - **연타** — 지치다가 **기절**한다(X_X + 별이 뱅뱅). 잠깐 못 논다.
 *
 * ★ **터치는 배경화면이 직접 받는다** — 런처가 흘려 준 좌표가 클로디 위면 반응.
 *   아이콘·위젯 위를 누르면 그쪽이 먹으므로 우리에게는 안 온다.
 */
class Mascot {

    private var t = 0
    private var yoff = 0f      // 위아래 용수철
    private var vy = 0f
    private var lean = 0f      // 좌우 기울임(계단식 밀기)
    private var vLean = 0f
    private var spinDir = 1

    private var surprise = 0
    private var blink = 0
    private var nextBlink = 60

    private var charging = false
    private var charge = 0f    // 0~1
    private var heldFrames = 0

    private var clicks = 0f    // 콕 누적 — 식으면서 준다
    private var faint = 0

    /** 반짝이 [x, y, vy, 남은 수명] — 기를 다 모아 뛸 때 흩뿌린다. */
    private val sparks = ArrayList<FloatArray>()

    /** 한 프레임. 배경화면·미리보기가 그리기 직전에 부른다. */
    fun step() {
        t++
        if (faint > 0) {                       // 기절 — 늘어졌다가 깨어난다
            faint--
            vy *= 0.8f; yoff *= 0.85f
            vLean *= 0.9f; lean *= 0.9f
            if (faint == 0) { yoff = 0f; vy = 0f; lean = 0f; vLean = 0f }
            stepSparks()
            return
        }

        if (charging) {
            heldFrames++
            charge = (charge + 1f / CHARGE_FRAMES).coerceAtMost(1f)
        }

        vy += -SPRING_K * yoff
        vy *= 1f - SPRING_DAMP
        yoff = (yoff + vy).coerceIn(-26f, 9f)

        vLean += -SPRING_K * lean
        vLean *= 1f - SPRING_DAMP
        lean += vLean

        if (surprise > 0) surprise--
        if (clicks > 0f) clicks = max(0f, clicks - CLICK_DECAY)
        if (blink > 0) {
            blink--
        } else if (--nextBlink <= 0) {
            blink = 3
            nextBlink = 60 + (t % 90)   // 규칙적이지 않게 (난수 없이도 흩어진다)
        }
        stepSparks()
    }

    private fun stepSparks() {
        var i = 0
        while (i < sparks.size) {
            val s = sparks[i]
            s[1] += s[2]; s[2] += 0.06f; s[3] -= 1f
            if (s[3] <= 0f) sparks.removeAt(i) else i++
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
        val power = if (held) JUMP + charge * CHARGE_JUMP else JUMP
        charging = false

        vy -= power
        vLean += SPIN * spinDir * (1f + charge)
        spinDir = -spinDir
        surprise = SURPRISE_FRAMES

        if (held && charge > 0.6f) burst()          // 꽉 채웠다 — 반짝이를 흩뿌린다
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

    private fun burst() {
        for (k in 0 until 7) {
            val a = k * 0.9f
            sparks.add(floatArrayOf(sin(a) * 14f, -abs(sin(a * 1.7f)) * 10f, -1.4f - k * 0.1f, 22f))
        }
    }

    /** 누른 자리가 클로디 위인가. `u` 는 칸 크기(px). */
    fun hits(cx: Float, cy: Float, u: Float, x: Float, y: Float): Boolean {
        val halfW = (MascotSprite.COLS / 2f + 2f) * u
        val halfH = MascotSprite.ROWS / 2f * u
        return abs(x - cx) <= halfW + u && abs(y - (cy + yoff)) <= halfH + u
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
                sin(t * 0.2f) * 0.20f, "faint", 1, MascotSprite.LEGS_WIDE, body, hole)
            drawDizzy(c, cx, cy - MascotSprite.ROWS / 2f * u * FAINT_SCALE - u, u, star)
            drawSparks(c, cx, cy, u, body)
            return
        }

        // 기 모으는 중에는 쭈그리고 부르르 떤다 — 모을수록 더 눌리고 더 떤다
        val squat = if (charging) charge else 0f
        val shake = if (charging) sin(t * 1.6f) * 0.10f * charge else 0f

        val breathe = 1f + 0.045f * sin(t * 0.09f)
        val stretch = (-yoff * 0.012f).coerceIn(-0.18f, 0.30f)   // 뜰수록 늘고 눌릴수록 납작
        val sx = breathe * (1f - stretch * 0.6f + squat * 0.22f)
        val sy = breathe * (1f + stretch - squat * 0.30f)

        val y = cy + yoff + sin(t * 0.12f) * u * 0.35f + squat * u * 1.2f
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

        fun cell(col: Int, row: Int, span: Int, p: Paint) {
            val left = x0 + col * ux + lean * (mid - row) * uy
            val top = y0 + row * uy
            c.drawRect(left, top, left + span * ux, top + uy, p)
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
            val a = t * 0.35f + k * 2.09f
            val x = cx + sin(a) * u * 3.4f
            val y = top + sin(a + 1.57f) * u * 1.1f
            plus(c, x, y, u * 0.5f, p)
        }
    }

    /** 뿜은 반짝이 — 도트 십자가 떠오르며 사그라든다. */
    private fun drawSparks(c: Canvas, cx: Float, cy: Float, u: Float, p: Paint) {
        for (s in sparks) {
            val k = u * 0.45f * (s[3] / 22f)
            if (k < 0.6f) continue
            plus(c, cx + s[0] * u * 0.25f, cy + s[1] * u * 0.25f, k, p)
        }
    }

    private fun plus(c: Canvas, x: Float, y: Float, r: Float, p: Paint) {
        c.drawRect(x - r, y - r / 3f, x + r, y + r / 3f, p)
        c.drawRect(x - r / 3f, y - r, x + r / 3f, y + r, p)
    }

    private companion object {
        const val SPRING_K = 0.20f
        const val SPRING_DAMP = 0.14f
        const val SPIN = 0.14f

        const val JUMP = 5.0f            // 콕 찔렀을 때
        const val CHARGE_JUMP = 11.0f    // 기를 꽉 모았을 때 더해지는 힘
        const val CHARGE_FRAMES = 45f    // 약 2.8초면 가득 (16fps)
        const val CHARGE_MIN = 6         // 이보다 짧게 누르면 그냥 콕

        const val SURPRISE_FRAMES = 12
        const val CLICK_DECAY = 0.035f
        const val FAINT_AT = 12f         // 콕 여섯 번쯤
        const val FAINT_FRAMES = 44      // 약 2.7초
        const val FAINT_SCALE = 1.3f
    }
}
