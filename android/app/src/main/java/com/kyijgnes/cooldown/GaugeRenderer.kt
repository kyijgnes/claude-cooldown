package com.kyijgnes.cooldown

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Rect
import android.graphics.RectF
import android.graphics.Typeface
import kotlin.math.min

/**
 * **화면 넷이 함께 쓰는 단 하나의 그리기 코드** — 홈 위젯, 앱 화면, 라이브 배경화면,
 * 상태바 아이콘. 모양을 바꾸려면 여기만 고친다.
 *
 * 데스크탑 스킨과 같은 규칙:
 *   · 흐린 글자도 배경 대비 4.5:1 이상 — 위계는 밝기가 아니라 글자 크기로 준다
 *   · 100% 가 아니면 게이지를 끝까지 채우지 않는다 (99% 와 구별돼야 한다)
 */
object GaugeRenderer {

    private val REGULAR = Typeface.create("sans-serif", Typeface.NORMAL)
    private val MEDIUM = Typeface.create("sans-serif-medium", Typeface.NORMAL)

    private fun paint(size: Float, color: Int, face: Typeface) = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        textSize = size
        this.color = color
        typeface = face
    }

    /**
     * **판(카드) 없이 배경화면 위에 바로 얹을 때** 글자에 바탕색 후광을 두른다.
     * 획 둘레가 글자와 반대 색으로 감싸여 어떤 배경화면 위에서도 읽힌다
     * (배경이 무슨 그림인지 우리는 알 수 없으므로 색을 고를 수가 없다).
     */
    private fun Paint.halo(on: Boolean, p: Palette, radius: Float): Paint {
        if (on) setShadowLayer(radius, 0f, 0f, (p.bg and 0xFFFFFF) or 0xE6000000.toInt())
        return this
    }

    /**
     * 뒷판. **홈 위젯은 반투명(`card=false`)** 이라 배경화면이 그대로 비쳐 보이고,
     * 앱 화면은 꽉 찬 판을 쓴다.
     *
     * ★ 홈 위젯을 아예 투명하게 두지 않는 이유: 위젯 글자색은 폰 테마(밝게/어둡게)를
     *   따르는데 **배경화면이 밝은지 어두운지는 알 길이 없다.** 밝은 테마 + 어두운
     *   배경화면이면 글자가 통째로 안 보인다. 반투명 판이 그 경우를 막아 준다.
     */
    private fun plate(c: Canvas, r: RectF, radius: Float, p: Palette, card: Boolean) {
        val color = if (card) p.bg else (p.bg and 0xFFFFFF) or 0xA6000000.toInt()
        c.drawRoundRect(r, radius, radius, paint(0f, color, REGULAR))
    }

    // ---------------------------------------------------------------- 조각

    /** 둥근 막대 게이지. 100% 가 아니면 끝을 살짝 남긴다. */
    fun drawBar(c: Canvas, r: RectF, pct: Float?, p: Palette) {
        val radius = r.height() / 2f
        c.drawRoundRect(r, radius, radius, paint(0f, p.track, REGULAR))
        if (pct == null || pct <= 0f) return
        val full = r.width()
        var w = full * (pct / 100f)
        if (pct < 100f) w = w.coerceAtMost(full - r.height() * 0.35f)
        w = w.coerceAtLeast(r.height())  // 1% 도 보이게 최소한 동그라미 하나
        val fill = RectF(r.left, r.top, r.left + w, r.bottom)
        c.drawRoundRect(fill, radius, radius, paint(0f, p.tone(pct), REGULAR))
    }

    /** 270도 열린 링 게이지 (작은 위젯·배경화면용). */
    fun drawArc(c: Canvas, box: RectF, pct: Float?, p: Palette, thickness: Float) {
        val ring = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            style = Paint.Style.STROKE
            strokeWidth = thickness
            strokeCap = Paint.Cap.ROUND
        }
        val inset = thickness / 2f
        val r = RectF(box.left + inset, box.top + inset, box.right - inset, box.bottom - inset)
        ring.color = p.track
        c.drawArc(r, 135f, 270f, false, ring)
        if (pct == null || pct <= 0f) return
        ring.color = p.tone(pct)
        val sweep = (270f * (pct / 100f)).coerceAtMost(if (pct < 100f) 266f else 270f)
        c.drawArc(r, 135f, sweep.coerceAtLeast(4f), false, ring)
    }

    /** 가운데 정렬 글자. y 는 글자 상자의 세로 중심. */
    private fun centerText(c: Canvas, text: String, cx: Float, cy: Float, pt: Paint) {
        val fm = pt.fontMetrics
        c.drawText(text, cx - pt.measureText(text) / 2f, cy - (fm.ascent + fm.descent) / 2f, pt)
    }

    private fun baseline(cy: Float, pt: Paint): Float {
        val fm = pt.fontMetrics
        return cy - (fm.ascent + fm.descent) / 2f
    }

    // ---------------------------------------------------------------- 넓은 판

    /**
     * 5시간·주간 두 줄. 4×1 홈 위젯과 앱 화면이 쓴다.
     *
     * `[5시간] [47%] [━━━━게이지━━━━] [17:32 초기화]`
     */
    fun wide(ctx: Context, wPx: Int, hPx: Int, snap: Snapshot, now: Long, card: Boolean = true): Bitmap {
        val p = Palette(ctx)
        val w = wPx.coerceAtLeast(120)
        val h = hPx.coerceAtLeast(60)
        val bmp = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888)
        val c = Canvas(bmp)

        val pad = h * 0.10f
        plate(c, RectF(0f, 0f, w.toFloat(), h.toFloat()), (h * 0.20f).coerceAtMost(48f), p, card)

        val rows = listOf(snap.five, snap.week)
        val rh = (h - pad * 2) / rows.size
        val glow = rh * 0.13f
        val labelPt = paint(rh * 0.30f, p.label, REGULAR).halo(!card, p, glow)
        val pctPt = paint(rh * 0.42f, p.title, MEDIUM).halo(!card, p, glow)
        val rightPt = paint(rh * 0.26f, p.faint, REGULAR).halo(!card, p, glow)

        // 칸 폭은 가장 긴 글자를 미리 재서 잡는다 — 값이 바뀌어도 게이지가 안 흔들린다
        val labelW = rows.maxOf { labelPt.measureText(it.label) } + rh * 0.30f
        val pctW = pctPt.measureText("100%") + rh * 0.30f
        val rightW = rightPt.measureText("7/31 09:00 초기화") + rh * 0.20f

        rows.forEachIndexed { i, limit ->
            val top = pad + rh * i
            val cy = top + rh / 2f
            var x = pad

            c.drawText(limit.label, x, baseline(cy, labelPt), labelPt)
            x += labelW

            pctPt.color = if (limit.pct == null) p.faint else p.title
            c.drawText(limit.pctText(), x, baseline(cy, pctPt), pctPt)
            x += pctW

            val barW = w - pad - rightW - x
            if (barW > rh * 0.8f) {
                val barH = rh * 0.22f
                drawBar(c, RectF(x, cy - barH / 2f, x + barW - rh * 0.30f, cy + barH / 2f),
                    limit.pct, p)
            }

            val text = limit.whenText(now)
            c.drawText(text, w - pad - rightPt.measureText(text), baseline(cy, rightPt), rightPt)
        }

        drawStaleMark(c, w.toFloat(), pad, snap, p)
        return bmp
    }

    /**
     * PC 가 꺼져 값이 오래됐다는 표시. 글로 설명하지 않고 **모서리 점 하나**로 —
     * 숫자 자체는(초기화 보정 덕분에) 맞으므로 크게 말할 일이 아니다.
     */
    private fun drawStaleMark(c: Canvas, w: Float, pad: Float, snap: Snapshot, p: Palette) {
        if (!snap.stale || snap.updatedAt == 0L) return
        c.drawCircle(w - pad * 0.6f, pad * 0.6f, pad * 0.22f, paint(0f, p.faint, REGULAR))
    }

    // ---------------------------------------------------------------- 작은 판

    /** 링 하나 + 큰 숫자. 1×1 홈 위젯(잠금화면 위젯이 열리면 거기도) 용. */
    fun small(ctx: Context, sizePx: Int, snap: Snapshot, now: Long, card: Boolean = true): Bitmap {
        val p = Palette(ctx)
        val s = sizePx.coerceAtLeast(72)
        val bmp = Bitmap.createBitmap(s, s, Bitmap.Config.ARGB_8888)
        val c = Canvas(bmp)
        val limit = snap.worst()

        plate(c, RectF(0f, 0f, s.toFloat(), s.toFloat()), s * 0.24f, p, card)

        val pad = s * 0.13f
        drawArc(c, RectF(pad, pad, s - pad, s - pad), limit.pct, p, s * 0.075f)

        val glow = s * 0.055f
        val numPt = paint(s * 0.30f, if (limit.pct == null) p.faint else p.title, MEDIUM)
            .halo(!card, p, glow)
        centerText(c, limit.pctText(), s / 2f, s * 0.46f, numPt)

        val labelPt = paint(s * 0.14f, p.label, REGULAR).halo(!card, p, glow)
        centerText(c, limit.label, s / 2f, s * 0.70f, labelPt)

        drawStaleMark(c, s.toFloat(), pad, snap, p)
        return bmp
    }

    // ---------------------------------------------------------------- 상태바 아이콘

    private val BOLD = Typeface.create("sans-serif-condensed", Typeface.BOLD)

    /**
     * 상태바·잠금화면·**AOD** 에 뜨는 작은 아이콘 — **네모 점 넷에 감싸인 숫자.**
     * 앱 아이콘(도트 마스코트 클로디)과 같은 결이라 상태바에서도 우리 것인 줄 바로 안다.
     *
     * 시스템이 **알파를 마스크로 써서 한 가지 색으로 물들이므로** 흰색 + 투명 배경으로
     * 그린다. 색을 넣어도 무시된다.
     *
     * ★ **글자 상자가 아니라 잉크(실제 획)를 재서 칸에 채운다.** 폰트 여백까지 칸으로
     * 치면 24dp 로 줄었을 때 숫자가 다른 아이콘들보다 눈에 띄게 작아진다 — 상태바에서
     * 안 보이던 주된 이유다. 좁은 볼드체를 쓰는 것도 같은 이유(세 자리도 안 가늘어진다).
     */
    fun statusIcon(pct: Float?): Bitmap {
        val s = 96
        val bmp = Bitmap.createBitmap(s, s, Bitmap.Config.ARGB_8888)
        val c = Canvas(bmp)
        val text = pct?.let { Math.round(it).toString() } ?: "–"
        val mid = s / 2f

        // 클로디의 도트 결 — **네 모서리에 네모 점**으로만 놓는다(마스코트가 도트 그림이라
        // 동그라미가 아니라 네모다).
        // ★ 살(대각선 짧은 선)로 그리면 24dp 에서 숫자 획과 섞여 `)17(` 처럼 읽힌다.
        //   점은 획으로 안 보여서 숫자를 안 건드린다. 가로·세로 살은 애초에 못 넣는다 —
        //   그 자리를 숫자가 다 쓰고, 숫자를 줄이면 그게 더 안 보인다.
        val spark = paint(0f, Color.WHITE, BOLD)
        val half = s * 0.068f
        for (k in 0..3) {
            val a = Math.PI / 4 + k * Math.PI / 2
            val dx = mid + Math.cos(a).toFloat() * s * 0.60f
            val dy = mid + Math.sin(a).toFloat() * s * 0.60f
            c.drawRect(dx - half, dy - half, dx + half, dy + half, spark)
        }

        val pt = paint(s.toFloat(), Color.WHITE, BOLD)
        // ★ 크기는 **두 자리('00')를 기준**으로 한 번만 정한다. 그리는 글자로 재면
        //   7% 일 때만 숫자가 칸을 꽉 채워 커졌다가 10% 가 되면 확 작아진다 — 그게 더 눈에 띈다.
        //   '–'(값 없음)도 잉크가 납작해서 기준으로 삼으면 화면 폭짜리 막대가 된다.
        val ref = Rect()
        pt.getTextBounds("00", 0, 2, ref)
        if (ref.width() > 0 && ref.height() > 0) {
            pt.textSize = s * min(s * 0.80f / ref.height(), s * 0.80f / ref.width())
        }
        // 세 자리('100')만 폭이 넘친다 — 그때만 들어갈 만큼 줄인다
        val wide = pt.measureText(text)
        if (wide > s * 0.80f) pt.textSize *= s * 0.80f / wide

        val box = Rect()
        pt.getTextBounds(text, 0, text.length, box)
        c.drawText(text, (s - box.width()) / 2f - box.left, (s + box.height()) / 2f - box.bottom, pt)
        return bmp
    }
}
