package com.kyijgnes.cooldown.dino

import android.content.Context
import android.content.res.Configuration
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Typeface
import android.view.MotionEvent
import android.view.View
import com.kyijgnes.cooldown.Palette
import com.kyijgnes.cooldown.R
import com.kyijgnes.cooldown.dino.DinoSpec as S

/**
 * 공룡 점프 판 — `DinoGame` 을 그리고 손가락을 받는다. PC `cooldown_dino_view.py` 와 같은 그림이다.
 *
 * - **새 화면을 띄우지 않는다.** 앱 첫 화면(`MainActivity`)이 게이지 자리에 이 판을 끼운다.
 *   판(600×150)을 **뷰 너비에 맞춰** 늘리고 세로는 가운데. 높이를 안 정해 주면 판 비율대로 잡는다.
 * - **판 어디를 눌러도 뛴다**(누르고 있으면 높이, 일찍 떼면 낮게). 아래로 밀면 숙인다(덤).
 *   새가 두 높이뿐이라(`touch = true`) 숙이지 않아도 다 넘을 수 있다 — 크롬 휴대폰판과 같다.
 * - 닫는 길: 왼쪽 위 ✕ · 뒤로 가기(화면이 받는다) · 기다림/부딪힘/멈춤으로 20초(`IDLE_EXIT`).
 * - 한 걸음은 1/60초로 고정하고 흐른 시간만큼 밟은 뒤 한 번 그린다(`postInvalidateOnAnimation`).
 * - 색은 폰 테마(`Palette`), 밤(700점마다 12초)에는 판만 반대 테마로 뒤집는다.
 * - 화면을 떠나면(`pause`) 멈추고, 돌아와 누르면 이어 한다(그 누르기로 뛰지는 않는다).
 */
class DinoView(ctx: Context, best: Int, seed: Long? = null) : View(ctx) {

    val game = DinoGame(seed = seed, best = best, touch = true)

    /** 최고 기록을 넘긴 판이 끝날 때 한 번 (화면이 저장한다). */
    var onBest: ((Int) -> Unit)? = null

    /** 닫을 때 한 번 (✕ · 오래 그대로 둠). 판을 실제로 치우는 것은 화면이 한다. */
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
    private var exited = false
    var paused = false
        private set
    private var savedOver = false
    private var downY = 0f
    private var ducked = false
    private val swipe = 24f * ctx.resources.displayMetrics.density

    init {
        keepScreenOn = true
        isClickable = true
    }

    // -------------------------------------------------- 돌리기
    fun resume() {
        running = true
        last = System.nanoTime()
        acc = 0.0
        postInvalidateOnAnimation()
    }

    fun pause() {
        running = false
        if (game.state == "run") {
            paused = true
            game.releaseJump()
            game.releaseDuck()
        }
        invalidate()
    }

    /** 흐른 시간만큼 걸음을 밟는다. 한 번에 `MAX_CATCH_UP` 넘게는 안 밟는다(순간이동 방지). */
    fun advance(nowNs: Long = System.nanoTime()) {
        if (!running) { last = nowNs; acc = 0.0; return }
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
            game.step()
            acc -= STEP
            n++
        }
        if (n == MAX_CATCH_UP) acc = 0.0
        if (game.state == "over" && !savedOver) {
            savedOver = true
            if (game.newBest) onBest?.invoke(game.best)
        }
    }

    private fun exit() {
        if (exited) return
        exited = true
        running = false
        post { onExit?.invoke() }       // 그리는 중에 판을 치우지 않게 한 박자 뒤로
    }

    // -------------------------------------------------- 손가락
    override fun onTouchEvent(ev: MotionEvent): Boolean {
        when (ev.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                parent?.requestDisallowInterceptTouchEvent(true)   // 위아래로 밀어도 스크롤이 채 가지 않게
                downY = ev.y
                ducked = false
                idle = 0.0
                val s = scale()
                if (ev.x / s < S.CLOSE_HIT && (ev.y - top()) / s < S.CLOSE_HIT) {   // 왼쪽 위 ✕
                    exit()
                    return true
                }
                if (paused) {                 // 멈춘 판을 누르면 이어서 — 그 누르기로 뛰지는 않는다
                    paused = false
                    last = System.nanoTime()
                    postInvalidateOnAnimation()
                    return true
                }
                if (game.state == "over" && game.overT >= S.OVER_WAIT) savedOver = false
                game.pressJump()
            }
            MotionEvent.ACTION_MOVE -> {
                val dy = ev.y - downY
                if (!ducked && dy > swipe) {      // 아래로 밀었다 — 숙이기(공중이면 빨리 떨어진다)
                    ducked = true
                    game.releaseJump()
                    game.pressDuck()
                } else if (ducked && dy < swipe / 2) {
                    ducked = false
                    game.releaseDuck()
                }
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                game.releaseJump()
                game.releaseDuck()
                ducked = false
                parent?.requestDisallowInterceptTouchEvent(false)
                performClick()
            }
        }
        return true
    }

    override fun performClick(): Boolean = super.performClick()

    // -------------------------------------------------- 크기·그리기
    /** 높이를 정해 주지 않으면 판 비율(600:150)대로. */
    override fun onMeasure(widthSpec: Int, heightSpec: Int) {
        val w = MeasureSpec.getSize(widthSpec)
        val h = if (MeasureSpec.getMode(heightSpec) == MeasureSpec.EXACTLY) MeasureSpec.getSize(heightSpec)
        else (w * S.H / S.W).toInt()
        setMeasuredDimension(w, h)
    }

    /** 판이 놓이는 자리 — 배율과 위끝(세로 가운데). */
    fun scale(): Float = width / game.w
    fun top(): Float = (height - S.H * scale()) / 2f

    override fun onDraw(c: Canvas) {
        advance()
        paint(c)
        if (running && !exited) postInvalidateOnAnimation()
    }

    /** 그리기만 — 테스트가 폰 없이 그림을 뽑을 때도 이걸 부른다. */
    fun paint(c: Canvas) {
        val g = game
        val p = if (g.night > 0) night else day
        c.drawColor(p.bg)
        val s = scale()
        c.save()
        c.translate(0f, top())
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
        art(c, S.POSES.getValue(pose), S.DINO_X, g.dinoY, coral)
        val eyes = (if (pose.startsWith("duck")) S.DUCK_EYE else S.DINO_EYE).getValue(g.eye)
        cells(c, eyes, S.DINO_X, g.dinoY, p.bg)
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
