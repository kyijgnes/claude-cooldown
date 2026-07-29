package com.kyijgnes.cooldown.wallpaper

import android.content.Context
import android.graphics.Canvas
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.RectF
import android.graphics.Shader
import android.graphics.Typeface
import com.kyijgnes.cooldown.GaugeRenderer
import com.kyijgnes.cooldown.Limit
import com.kyijgnes.cooldown.Palette
import com.kyijgnes.cooldown.Snapshot
import kotlin.math.cos
import kotlin.math.sin

/**
 * 배경화면 **그리기만** 한다 — 화면·수명 관리는 CooldownWallpaperService 가 맡는다.
 * (데스크탑에서 앱과 스킨을 나눈 것과 같은 결. 폰 없이 테스트로 그림을 뽑아 볼 수 있다)
 *
 * 배치 규칙: 게이지는 **아래 1/3**에만 둔다 — 잠금화면의 시계·알림이 위쪽을 쓴다.
 */
object WallpaperArt {

    private val REGULAR: Typeface = Typeface.create("sans-serif", Typeface.NORMAL)
    private val MEDIUM: Typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)

    fun render(ctx: Context, c: Canvas, snap: Snapshot, now: Long, frame: Long) {
        val p = Palette(ctx)
        val w = c.width.toFloat()
        val h = c.height.toFloat()

        drawBackdrop(c, w, h, p)

        val pad = w * 0.09f
        val top = h * 0.63f
        val gap = h * 0.11f

        c.drawText("클로드 쿨다운", pad, top - h * 0.035f, paint(w * 0.033f, p.faint, REGULAR))

        listOf(snap.five, snap.week).forEachIndexed { i, limit ->
            drawRow(c, limit, now, pad, top + gap * i, w, p)
        }

        drawClaudi(c, w - pad - w * 0.045f, top - h * 0.062f, w * 0.045f, frame, p)
    }

    private fun drawBackdrop(c: Canvas, w: Float, h: Float, p: Palette) {
        val sky = Paint().apply {
            shader = LinearGradient(
                0f, 0f, 0f, h,
                intArrayOf(p.bg, blend(p.bg, p.coral, 0.10f), blend(p.bg, p.coral, 0.22f)),
                floatArrayOf(0f, 0.62f, 1f),
                Shader.TileMode.CLAMP,
            )
        }
        c.drawRect(0f, 0f, w, h, sky)
    }

    private fun drawRow(
        c: Canvas, limit: Limit, now: Long, pad: Float, top: Float, w: Float, p: Palette,
    ) {
        c.drawText(limit.label, pad, top, paint(w * 0.036f, p.label, REGULAR))

        val pctBase = top + w * 0.082f
        val pctPt = paint(w * 0.085f, if (limit.pct == null) p.faint else p.title, MEDIUM)
        c.drawText(limit.pctText(), pad, pctBase, pctPt)

        // 배경화면은 보이는 동안 매 프레임 다시 그리므로 남은 시간을 상대 시간으로 써도 안 틀린다
        val leftPt = paint(w * 0.036f, p.faint, REGULAR)
        val left = limit.leftText(now)
        c.drawText(left, w - pad - leftPt.measureText(left), pctBase, leftPt)

        val barTop = pctBase + w * 0.030f
        GaugeRenderer.drawBar(c, RectF(pad, barTop, w - pad, barTop + w * 0.018f), limit.pct, p)
    }

    /**
     * 마스코트 '클로디' — 데스크탑 슬림 바에 사는 코랄색 별빛을 옮겨 왔다.
     * 숨쉬기 + 통통 + 이따금 깜빡. **상태와 무관하게 늘 코랄색**이다(상태는 게이지가 맡는다).
     */
    private fun drawClaudi(c: Canvas, cx: Float, cy: Float, r: Float, frame: Long, p: Palette) {
        val t = frame * 0.06
        val breathe = 1f + 0.05f * sin(t).toFloat()
        val y = cy + r * 0.30f * sin(t * 0.7).toFloat()

        c.drawOval(
            RectF(cx - r * breathe, y - r / breathe, cx + r * breathe, y + r / breathe),
            paint(0f, p.coral, REGULAR),
        )

        val ex = r * 0.34f
        val ey = y - r * 0.10f
        if ((frame % 80L) < 4L) {  // 5초에 한 번쯤 눈이 감긴다
            val lid = Paint(Paint.ANTI_ALIAS_FLAG).apply {
                color = p.bg
                strokeWidth = r * 0.13f
                strokeCap = Paint.Cap.ROUND
            }
            c.drawLine(cx - ex - r * 0.13f, ey, cx - ex + r * 0.13f, ey, lid)
            c.drawLine(cx + ex - r * 0.13f, ey, cx + ex + r * 0.13f, ey, lid)
        } else {
            val eye = paint(0f, p.bg, REGULAR)
            c.drawCircle(cx - ex, ey, r * 0.13f, eye)
            c.drawCircle(cx + ex, ey, r * 0.13f, eye)
        }

        // 반짝이 — 머리 위를 천천히 돈다
        val spark = paint(0f, p.coral, REGULAR).apply {
            alpha = (110 + 90 * sin(t * 1.3)).toInt().coerceIn(0, 255)
        }
        c.drawCircle(
            cx + r * 1.5f * cos(t * 0.5).toFloat(),
            y - r * 1.5f - r * 0.2f * sin(t * 0.9).toFloat(),
            r * 0.11f, spark,
        )
    }

    private fun paint(size: Float, color: Int, face: Typeface) =
        Paint(Paint.ANTI_ALIAS_FLAG).apply {
            textSize = size
            this.color = color
            typeface = face
        }

    /** 두 색을 섞는다 (0 이면 a, 1 이면 b). */
    private fun blend(a: Int, b: Int, ratio: Float): Int {
        fun mix(shift: Int): Int {
            val x = (a shr shift) and 0xff
            val y = (b shr shift) and 0xff
            return (x + (y - x) * ratio).toInt().coerceIn(0, 255)
        }
        return (0xff shl 24) or (mix(16) shl 16) or (mix(8) shl 8) or mix(0)
    }
}
