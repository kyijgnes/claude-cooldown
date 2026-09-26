package com.kyijgnes.cooldown.dino

import android.content.Context
import android.graphics.Canvas
import android.view.MotionEvent
import android.view.View
import com.kyijgnes.cooldown.Palette
import com.kyijgnes.cooldown.dino.DinoSpec as S

/**
 * 앱 첫 화면의 공룡 점프 — `DinoBoard` 를 게이지 자리에 얹는 뷰. 판은 뷰 너비에 맞추고 세로는 가운데.
 * 높이를 안 정해 주면 판 비율(600:150)대로 잡는다. 판 밖(위아래 여백)은 바탕색.
 * 앱 안이라 **아래로 밀면 숙이기**도 된다(홈 화면 배경화면에서는 알림창과 겹쳐 뺐다).
 */
class DinoView(ctx: Context, best: Int, seed: Long? = null) : View(ctx) {

    val board = DinoBoard(ctx, best, seed)
    val game get() = board.game

    /** 알에서 깬 공룡이 선 자리 `[x, 발 y, 칸]`(화면 좌표) — 첫 장에서 이 뷰 좌표로 옮겨 들어오는 장면을 건다. */
    var introFromScreen: FloatArray? = null
    private val loc = IntArray(2)

    private val bg = Palette(ctx).bg
    private var downY = 0f
    private var ducked = false
    private val swipe = 24f * ctx.resources.displayMetrics.density

    init {
        keepScreenOn = true
        isClickable = true
    }

    fun resume() {
        board.resume()
        postInvalidateOnAnimation()
    }

    fun pause() {
        board.pause()
        invalidate()
    }

    override fun onMeasure(widthSpec: Int, heightSpec: Int) {
        val w = MeasureSpec.getSize(widthSpec)
        val h = if (MeasureSpec.getMode(heightSpec) == MeasureSpec.EXACTLY) MeasureSpec.getSize(heightSpec)
        else (w * S.H / S.W).toInt()
        setMeasuredDimension(w, h)
    }

    /** 판 위끝 — 뷰 세로 가운데. */
    fun top(): Float = (height - board.heightFor(width.toFloat())) / 2f

    override fun onDraw(c: Canvas) {
        introFromScreen?.let {
            getLocationOnScreen(loc)
            board.startIntro(it[0] - loc[0], it[1] - loc[1], it[2])
            introFromScreen = null
        }
        board.advance()
        paint(c)
        if (board.active) postInvalidateOnAnimation()
    }

    /** 그리기만 — 테스트가 폰 없이 그림을 뽑을 때도 이걸 부른다. */
    fun paint(c: Canvas) {
        c.drawColor(bg)
        board.paint(c, top(), width.toFloat())
    }

    override fun onTouchEvent(ev: MotionEvent): Boolean {
        when (ev.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                parent?.requestDisallowInterceptTouchEvent(true)   // 위아래로 밀어도 스크롤이 채 가지 않게
                downY = ev.y
                ducked = false
                board.down(ev.x, ev.y)
                postInvalidateOnAnimation()
            }
            MotionEvent.ACTION_MOVE -> {
                val dy = ev.y - downY
                if (!ducked && dy > swipe) { ducked = true; board.duck(true) }
                else if (ducked && dy < swipe / 2) { ducked = false; board.duck(false) }
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                board.up()
                ducked = false
                parent?.requestDisallowInterceptTouchEvent(false)
                performClick()
            }
        }
        return true
    }

    override fun performClick(): Boolean = super.performClick()
}
