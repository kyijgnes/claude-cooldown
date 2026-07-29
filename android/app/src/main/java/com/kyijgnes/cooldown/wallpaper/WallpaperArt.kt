package com.kyijgnes.cooldown.wallpaper

import android.content.Context
import android.graphics.Canvas
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.graphics.Shader
import android.graphics.Typeface
import com.kyijgnes.cooldown.GaugeRenderer
import com.kyijgnes.cooldown.Limit
import com.kyijgnes.cooldown.Palette
import com.kyijgnes.cooldown.Snapshot
import kotlin.math.sin

/**
 * 배경화면 **그리기만** 한다 — 화면·수명 관리는 CooldownWallpaperService 가 맡는다.
 * (데스크탑에서 앱과 스킨을 나눈 것과 같은 결. 폰 없이 테스트로 그림을 뽑아 볼 수 있다)
 *
 * 결: 사용자가 쓰던 **파란 상어 바다**. 위쪽은 상어가 헤엄치는 바다(잠금화면 시계·알림 자리),
 * 아래 1/3 에만 게이지를 둔다.
 */
object WallpaperArt {

    private val REGULAR: Typeface = Typeface.create("sans-serif", Typeface.NORMAL)
    private val MEDIUM: Typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)

    fun render(ctx: Context, c: Canvas, snap: Snapshot, now: Long, frame: Long) {
        val p = Palette(ctx)
        val w = c.width.toFloat()
        val h = c.height.toFloat()

        drawBackdrop(c, w, h, p)
        drawBubbles(c, w, h, frame, p)

        // 상어는 위쪽 바다에서 둥실 떠 있다 (게이지 위, 잠금화면 시계 아래쯤)
        val swim = sin(frame * 0.02).toFloat()
        drawShark(c, w * 0.50f, h * 0.37f + h * 0.012f * swim, w * 0.36f, frame, p)

        val pad = w * 0.09f
        val top = h * 0.63f
        val gap = h * 0.11f

        c.drawText("클로드 쿨다운", pad, top - h * 0.035f, paint(w * 0.033f, p.faint, REGULAR))

        listOf(snap.five, snap.week).forEachIndexed { i, limit ->
            drawRow(c, limit, now, pad, top + gap * i, w, p)
        }
    }

    private fun drawBackdrop(c: Canvas, w: Float, h: Float, p: Palette) {
        // 원본 배경화면처럼 거의 평평한 파스텔 바다 — 위가 아주 살짝 밝다
        val sea = Paint().apply {
            shader = LinearGradient(
                0f, 0f, 0f, h,
                intArrayOf(p.seaTop, p.seaBottom),
                floatArrayOf(0f, 0.7f),
                Shader.TileMode.CLAMP,
            )
        }
        c.drawRect(0f, 0f, w, h, sea)
    }

    /** 위로 올라가는 물방울 몇 개. 프레임에 따라 천천히 떠오른다. */
    private fun drawBubbles(c: Canvas, w: Float, h: Float, frame: Long, p: Palette) {
        val fill = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = p.bubble }
        val ring = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            style = Paint.Style.STROKE
            strokeWidth = w * 0.004f
            color = p.sharkShadow
            alpha = 120
        }
        // (x비율, 반지름비율, 속도, 시작높이비율)
        val bubbles = listOf(
            floatArrayOf(0.14f, 0.016f, 0.9f, 0.20f),
            floatArrayOf(0.28f, 0.010f, 1.4f, 0.52f),
            floatArrayOf(0.72f, 0.020f, 0.7f, 0.34f),
            floatArrayOf(0.84f, 0.012f, 1.1f, 0.60f),
            floatArrayOf(0.62f, 0.008f, 1.7f, 0.14f),
            floatArrayOf(0.40f, 0.014f, 1.0f, 0.44f),
        )
        for (b in bubbles) {
            val cycle = h * 0.5f
            val rise = (frame * b[2] * (h * 0.0016f)) % cycle
            val cy = h * (0.10f + b[3] * 0.9f) - rise
            if (cy < -h * 0.05f) continue
            val cx = w * b[0] + w * 0.01f * sin((frame * 0.03 + b[0] * 10).toDouble()).toFloat()
            val r = w * b[1]
            c.drawCircle(cx, cy, r, fill)
            c.drawCircle(cx, cy, r, ring)
        }
    }

    /**
     * 옆에서 본 상어. 오른쪽을 보고, 숨쉬듯 위아래로 흔들리며 꼬리를 젓는다.
     * **몸통은 늘 파란색** — 사용량 상태는 아래 게이지가 맡는다.
     */
    private fun drawShark(c: Canvas, cx: Float, cy: Float, len: Float, frame: Long, p: Palette) {
        val t = frame * 0.05
        val l = len

        val body = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = p.sharkBody }
        val belly = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = p.sharkBelly }
        val dark = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = p.sharkOutline }
        val outline = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            style = Paint.Style.STROKE
            strokeWidth = l * 0.014f
            strokeJoin = Paint.Join.ROUND
            color = p.sharkOutline
        }

        // 바닥 그림자 (바로 아래, 납작하게)
        val shadow = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = p.sharkShadow; alpha = 90 }
        c.drawOval(RectF(cx - 0.42f * l, cy + 0.30f * l, cx + 0.40f * l, cy + 0.40f * l), shadow)

        // 꼬리지느러미 — 위아래 끝이 같이 흔들려 젓는 느낌
        val wag = sin(t * 1.8).toFloat() * 0.05f * l
        val tj = cx - 0.50f * l
        val tail = Path().apply {
            moveTo(tj + 0.04f * l, cy)
            lineTo(tj - 0.16f * l, cy - 0.24f * l + wag)
            lineTo(tj - 0.05f * l, cy)
            lineTo(tj - 0.14f * l, cy + 0.20f * l + wag)
            close()
        }
        c.drawPath(tail, body)
        c.drawPath(tail, outline)

        // 등지느러미
        val dorsal = Path().apply {
            moveTo(cx - 0.06f * l, cy - 0.17f * l)
            lineTo(cx + 0.05f * l, cy - 0.42f * l)
            lineTo(cx + 0.15f * l, cy - 0.16f * l)
            close()
        }
        c.drawPath(dorsal, body)
        c.drawPath(dorsal, outline)

        // 가슴지느러미
        val pec = Path().apply {
            moveTo(cx + 0.04f * l, cy + 0.13f * l)
            lineTo(cx + 0.18f * l, cy + 0.34f * l)
            lineTo(cx + 0.22f * l, cy + 0.11f * l)
            close()
        }
        c.drawPath(pec, body)
        c.drawPath(pec, outline)

        // 몸통 (어뢰꼴, 코가 오른쪽)
        val bodyPath = Path().apply {
            moveTo(cx + 0.50f * l, cy)
            cubicTo(cx + 0.42f * l, cy - 0.17f * l, cx + 0.10f * l, cy - 0.21f * l, cx - 0.20f * l, cy - 0.15f * l)
            cubicTo(cx - 0.36f * l, cy - 0.11f * l, cx - 0.46f * l, cy - 0.06f * l, cx - 0.52f * l, cy)
            cubicTo(cx - 0.46f * l, cy + 0.06f * l, cx - 0.36f * l, cy + 0.11f * l, cx - 0.20f * l, cy + 0.16f * l)
            cubicTo(cx + 0.10f * l, cy + 0.22f * l, cx + 0.42f * l, cy + 0.17f * l, cx + 0.50f * l, cy)
            close()
        }
        c.drawPath(bodyPath, body)

        // 흰 배 — 몸통 안쪽 아래 절반에만
        c.save()
        c.clipPath(bodyPath)
        val bellyPath = Path().apply {
            moveTo(cx + 0.46f * l, cy + 0.02f * l)
            cubicTo(cx + 0.20f * l, cy + 0.14f * l, cx - 0.12f * l, cy + 0.15f * l, cx - 0.34f * l, cy + 0.07f * l)
            lineTo(cx - 0.34f * l, cy + 0.30f * l)
            lineTo(cx + 0.46f * l, cy + 0.30f * l)
            close()
        }
        c.drawPath(bellyPath, belly)
        c.restore()

        c.drawPath(bodyPath, outline)

        // 아가미 세 줄
        val gill = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            style = Paint.Style.STROKE
            strokeWidth = l * 0.012f
            strokeCap = Paint.Cap.ROUND
            color = p.sharkOutline
            alpha = 150
        }
        for (i in 0..2) {
            val gx = cx + 0.24f * l - i * 0.05f * l
            c.drawLine(gx, cy - 0.09f * l, gx - 0.02f * l, cy + 0.08f * l, gill)
        }

        // 입 — 코 아래 짧은 선
        c.drawLine(cx + 0.48f * l, cy + 0.05f * l, cx + 0.34f * l, cy + 0.075f * l, gill)

        // 눈
        c.drawCircle(cx + 0.36f * l, cy - 0.04f * l, l * 0.035f, dark)
        val glint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = p.sharkBelly }
        c.drawCircle(cx + 0.372f * l, cy - 0.052f * l, l * 0.012f, glint)
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
