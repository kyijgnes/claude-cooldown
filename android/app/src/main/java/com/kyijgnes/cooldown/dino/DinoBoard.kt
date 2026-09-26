package com.kyijgnes.cooldown.dino

import android.content.Context
import android.content.res.Configuration
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Typeface
import com.kyijgnes.cooldown.Palette
import com.kyijgnes.cooldown.R
import com.kyijgnes.cooldown.dino.DinoSpec as S

/**
 * 공룡 점프 판 한 장 — **뷰가 아니다.** 규칙(`DinoGame`)·시간·그리기·손가락을 한데 들고, 그릴 자리는
 * 부르는 쪽이 정한다. 그래서 **배경화면**(`CooldownWallpaperService`, 홈 화면에서 바로)과
 * **앱 첫 화면**(`DinoView`)이 같은 판을 쓴다. PC `cooldown_dino_view.py` 와 같은 그림이다.
 *
 * - 판(600×150)을 받은 너비에 맞춰 늘려 `paint(c, top, width)` 자리에 그린다. 판 밖은 안 칠한다.
 * - **어디를 눌러도 뛴다**(누르고 있으면 높이, 일찍 떼면 낮게). 왼쪽 위 ✕ 는 닫기.
 *   새가 두 높이뿐이라(`touch = true`) 숙이지 않아도 다 넘는다 — 크롬 휴대폰판과 같다.
 * - 닫는 길: ✕ · 기다림/부딪힘/멈춤으로 20초(`IDLE_EXIT`) · 부르는 쪽이 직접(뒤로 가기·화면 잠김).
 * - 한 걸음은 1/60초로 고정하고 흐른 시간만큼 밟는다(`advance`).
 * - **들어오는 장면**(`startIntro`): 알에서 깬 작은 공룡이 그 자리에서 **폴짝 판으로 뛰어들고**, 판은
 *   땅 줄에서 위아래로 벌어지며 공룡 자리에서 오른쪽으로 번진다(크롬 첫 장면처럼). 0.6초. 그동안은 누르기를 안 받는다.
 * - 색은 폰 테마(`Palette`), 밤(700점마다 12초)에는 판만 반대 테마로 뒤집는다.
 */
class DinoBoard(ctx: Context, best: Int, seed: Long? = null) {

    val game = DinoGame(seed = seed, best = best, touch = true)

    /** 최고 기록을 넘긴 판이 끝날 때 한 번 (부르는 쪽이 저장한다). */
    var onBest: ((Int) -> Unit)? = null

    /** 닫을 때 한 번 (✕ · 오래 그대로 둠). 판을 실제로 치우는 것은 부르는 쪽이 한다. */
    var onExit: (() -> Unit)? = null

    private val day = Palette(ctx)
    private val night = Palette(flipped(ctx))
    private val coral = ctx.getColor(R.color.coral)
    private val fill = Paint()            // 도트 칸 — 안티에일리어싱 없이 (칸 경계가 번지지 않게)
    private val text = Paint(Paint.ANTI_ALIAS_FLAG).apply { textAlign = Paint.Align.RIGHT }
    private val mid = Paint(Paint.ANTI_ALIAS_FLAG).apply { textAlign = Paint.Align.CENTER }
    private val numBold = Typeface.create(Typeface.MONOSPACE, Typeface.BOLD)
    private val num = Typeface.create(Typeface.MONOSPACE, Typeface.NORMAL)

    private var last = 0L
    private var acc = 0.0
    private var idle = 0.0                // 기다림·부딪힘·멈춤으로 흐른 초
    private var running = false
    var exited = false
        private set
    var paused = false
        private set
    private var savedOver = false

    // 마지막으로 그린 자리 — 손가락 좌표를 판 좌표로 옮길 때 쓴다
    private var drawnTop = 0f
    private var drawnScale = 1f

    // 들어오는 장면 — 알에서 깬 공룡이 서 있던 자리(그리는 좌표 px): 가운데 x, 발 y, 도트 한 칸
    private var intro = 0
    private val introFrom = FloatArray(3)

    /** 들어오는 장면이 끝났을 때 한 번 (배경화면이 그때 미터기를 치운다). */
    var onIntroDone: (() -> Unit)? = null

    /** 알에서 깬 공룡이 `(x, feet)` 에 `cell` 크기로 서 있다 — 거기서 폴짝 판으로 뛰어들며 판이 열린다. */
    fun startIntro(x: Float, feet: Float, cell: Float) {
        introFrom[0] = x
        introFrom[1] = feet
        introFrom[2] = cell
        intro = INTRO_FRAMES
    }

    val inIntro: Boolean get() = intro > 0

    // -------------------------------------------------- 돌리기
    fun resume() {
        running = true
        last = System.nanoTime()
        acc = 0.0
    }

    fun pause() {
        running = false
        if (game.state == "run") {
            paused = true
            game.releaseJump()
            game.releaseDuck()
        }
    }

    val active: Boolean get() = running && !exited

    /** 흐른 시간만큼 걸음을 밟는다. 한 번에 `MAX_CATCH_UP` 넘게는 안 밟는다(순간이동 방지). */
    fun advance(nowNs: Long = System.nanoTime()) {
        if (!running || exited) { last = nowNs; acc = 0.0; return }
        val dt = (nowNs - last) / 1e9
        last = nowNs
        if (paused || game.state != "run") {  // 아무도 안 놀고 있다 — 오래 그대로면 접는다
            idle += dt
            if (idle * S.FPS >= S.IDLE_EXIT) { exit(); return }
        }
        if (paused) { acc = 0.0; return }
        acc += dt
        var n = 0
        while (acc >= STEP && n < MAX_CATCH_UP) {
            if (intro > 0) {                   // 들어오는 장면 — 판은 아직 안 돈다
                intro--
                idle = 0.0
                if (intro == 0) onIntroDone?.invoke()
            } else {
                game.step()
            }
            acc -= STEP
            n++
        }
        if (n == MAX_CATCH_UP) acc = 0.0
        if (game.state == "over" && !savedOver) {
            savedOver = true
            if (game.newBest) onBest?.invoke(game.best)
        }
    }

    fun exit() {
        if (exited) return
        exited = true
        running = false
        onExit?.invoke()
    }

    // -------------------------------------------------- 손가락 (그린 자리 기준 좌표)
    /** 누름. ✕ 를 짚었으면 닫고, 멈춘 판이면 이어 하고(뛰지는 않는다), 아니면 뛴다. */
    fun down(x: Float, y: Float) {
        idle = 0.0
        if (intro > 0) return                  // 뛰어드는 중 — 다 들어오면 누른다
        val bx = x / drawnScale
        val by = (y - drawnTop) / drawnScale
        if (bx in 0f..S.CLOSE_HIT.toFloat() && by in 0f..S.CLOSE_HIT.toFloat()) { exit(); return }
        if (paused) {
            paused = false
            last = System.nanoTime()
            return
        }
        if (game.state == "over" && game.overT >= S.OVER_WAIT) savedOver = false
        game.pressJump()
    }

    fun up() {
        game.releaseJump()
        game.releaseDuck()
    }

    /** 아래로 밀었을 때(앱 안에서만 — 홈 화면에서는 알림창 끌어내리기와 겹친다). */
    fun duck(on: Boolean) {
        if (on) { game.releaseJump(); game.pressDuck() } else game.releaseDuck()
    }

    // -------------------------------------------------- 그리기
    /** 판 높이 (그릴 너비 기준, px). */
    fun heightFor(width: Float) = S.H * width / game.w

    /** `top` 에서부터 `width` 폭으로 판을 그린다. 판 바탕만 칠하고 그 밖은 건드리지 않는다. */
    fun paint(c: Canvas, top: Float, width: Float) {
        if (intro > 0) {
            paintIntro(c, top, width)
            return
        }
        paintBoard(c, top, width, true)
    }

    /**
     * 들어오는 장면 한 장. `k` 0→1 (빨리 시작해 천천히 멎는다).
     * 판: 땅 줄 높이를 한가운데로 위아래로 벌어지고, 왼쪽(공룡 자리)에서 오른쪽 끝까지 번진다.
     * 공룡: 알 자리 → 판의 공룡 자리로 포물선을 그리며 뛰고, 크기도 판 크기로 바뀐다. 착지하면 판이 다 열린다.
     */
    private fun paintIntro(c: Canvas, top: Float, width: Float) {
        val s = width / game.w
        val raw = 1f - intro / INTRO_FRAMES.toFloat()
        val k = 1f - (1f - raw) * (1f - raw)   // 점점 느리게
        val bh = S.H * s
        val ground = top + S.GROUND * s
        val openH = bh * k
        val openR = (S.DINO_X + 60f) * s + (width - (S.DINO_X + 60f) * s) * k
        c.save()
        c.clipRect(0f, ground - openH * S.GROUND / S.H, openR, ground + openH * (S.H - S.GROUND) / S.H)
        paintBoard(c, top, width, false)
        c.restore()
        // 폴짝 — 알 자리에서 판의 공룡 자리로
        val rows = S.POSES.getValue("stand")
        val cols = rows.maxOf { it.length }
        val cell = introFrom[2] + (S.U * s - introFrom[2]) * raw
        val fromLeft = introFrom[0] - cols * introFrom[2] / 2f
        val left = fromLeft + (S.DINO_X * s - fromLeft) * raw
        val hop = kotlin.math.max(90f * s, kotlin.math.abs(ground - introFrom[1]) * 0.35f)
        val feet = introFrom[1] + (ground - introFrom[1]) * raw - hop * kotlin.math.sin(Math.PI * raw).toFloat()
        val y0 = feet - rows.size * cell
        fill.color = coral
        for ((r, line) in rows.withIndex()) {
            var col = 0
            while (col < line.length) {
                if (line[col] != '#') { col++; continue }
                var n = 1
                while (col + n < line.length && line[col + n] == '#') n++
                c.drawRect(Math.round(left + col * cell).toFloat(), Math.round(y0 + r * cell).toFloat(),
                    Math.round(left + (col + n) * cell).toFloat(), Math.round(y0 + (r + 1) * cell).toFloat(), fill)
                col += n
            }
        }
        fill.color = (if (game.night > 0) night else day).bg
        val eyes = S.DINO_EYE.getValue("open")
        var i = 0
        while (i < eyes.size) {
            c.drawRect(Math.round(left + eyes[i] * cell).toFloat(), Math.round(y0 + eyes[i + 1] * cell).toFloat(),
                Math.round(left + (eyes[i] + 1) * cell).toFloat(), Math.round(y0 + (eyes[i + 1] + 1) * cell).toFloat(), fill)
            i += 2
        }
    }

    private fun paintBoard(c: Canvas, top: Float, width: Float, withDino: Boolean) {
        val g = game
        val p = if (g.night > 0) night else day
        val s = width / g.w
        drawnTop = top
        drawnScale = s
        fill.color = p.bg
        c.drawRect(0f, top, width, top + S.H * s, fill)
        c.save()
        c.translate(0f, top)
        c.scale(s, s)

        for (cl in g.clouds) art(c, S.CLOUD, cl[0], cl[1], p.track)
        fill.color = p.label
        c.drawRect(0f, S.GROUND - 1f, g.w, S.GROUND, fill)
        fill.color = p.faint
        for (pb in g.pebbles) {
            val x = Math.round(pb[0]).toFloat()
            c.drawRect(x, S.GROUND + pb[1], x + pb[2], S.GROUND + pb[1] + 1f, fill)
        }
        for (ob in g.obstacles) {
            val bird = ob.kind == "bird"
            val color = if (bird) p.label else p.green
            for (i in 0 until ob.count) {
                val x = ob.x + i * ob.oneW
                art(c, ob.art(), x, ob.y, color, i % 2 == 1)
                if (bird) {
                    val e = ob.frame % 2 * 2
                    cells(c, intArrayOf(S.BIRD_EYE[e], S.BIRD_EYE[e + 1]), x, ob.y, p.bg)
                }
            }
        }
        val pose = g.pose
        if (withDino) art(c, S.POSES.getValue(pose), S.DINO_X, g.dinoY, coral)
        val eyes = (if (pose.startsWith("duck")) S.DUCK_EYE else S.DINO_EYE).getValue(g.eye)
        if (withDino) cells(c, eyes, S.DINO_X, g.dinoY, p.bg)
        art(c, S.CLOSE, S.CLOSE_AT[0].toFloat(), S.CLOSE_AT[1].toFloat(), p.faint)   // 닫기 ✕

        // 점수 — 오른쪽 위 (HI 최고 · 지금)
        text.textSize = 13f
        if (g.scoreVisible) {
            text.color = p.sub
            text.typeface = numBold
            c.drawText("%05d".format(g.shownScore), g.w - 12f, 26f, text)
        }
        if (g.best > 0 || g.state == "over") {
            text.color = p.label
            text.typeface = num
            c.drawText("HI %05d".format(g.best), g.w - 72f, 26f, text)
        }
        mid.textSize = 12f
        when {
            paused -> {
                mid.color = p.title
                mid.typeface = Typeface.DEFAULT_BOLD
                c.drawText(PAUSED, g.w / 2f, 60f, mid)
            }
            g.state == "ready" -> {
                mid.color = p.label
                mid.typeface = Typeface.DEFAULT
                c.drawText(HINT, g.w / 2f, 60f, mid)
            }
            g.state == "over" -> {
                mid.color = p.title
                mid.typeface = numBold
                mid.textSize = 14f
                c.drawText("G A M E   O V E R", g.w / 2f, 56f, mid)
                val rw = Art.width(S.RESTART)
                art(c, S.RESTART, g.w / 2f - rw / 2f, 68f, p.title)
            }
        }
        c.restore()
    }

    private fun art(c: Canvas, rows: Array<String>, x: Float, y: Float, color: Int, flip: Boolean = false) {
        fill.color = color
        val bx = Math.round(x).toFloat()
        val by = Math.round(y).toFloat()
        val r = Art.runs(rows, flip)
        var i = 0
        while (i < r.size) {
            c.drawRect(bx + r[i], by + r[i + 1], bx + r[i] + r[i + 2], by + r[i + 1] + r[i + 3], fill)
            i += 4
        }
    }

    /** 낱칸 몇 개 (눈 파내기). `cells` 는 (col, row) 가 번갈아. */
    private fun cells(c: Canvas, cells: IntArray, x: Float, y: Float, color: Int) {
        fill.color = color
        val bx = Math.round(x).toFloat()
        val by = Math.round(y).toFloat()
        var i = 0
        while (i < cells.size) {
            val cx = bx + cells[i] * S.U
            val cy = by + cells[i + 1] * S.U
            c.drawRect(cx, cy, cx + S.U, cy + S.U, fill)
            i += 2
        }
    }

    private companion object {
        const val STEP = 1.0 / S.FPS
        const val MAX_CATCH_UP = 5
        const val INTRO_FRAMES = 36     // 들어오는 장면 (60fps 로 0.6초)
        const val HINT = "눌러서 점프"
        const val PAUSED = "일시 정지 · 눌러서 이어 하기"

        /** 밤에 쓸 반대 테마 — 지금이 어둡게면 밝게, 밝게면 어둡게. */
        fun flipped(ctx: Context): Context {
            val cfg = Configuration(ctx.resources.configuration)
            val nightNow = (cfg.uiMode and Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES
            cfg.uiMode = (cfg.uiMode and Configuration.UI_MODE_NIGHT_MASK.inv()) or
                if (nightNow) Configuration.UI_MODE_NIGHT_NO else Configuration.UI_MODE_NIGHT_YES
            return ctx.createConfigurationContext(cfg)
        }
    }
}
