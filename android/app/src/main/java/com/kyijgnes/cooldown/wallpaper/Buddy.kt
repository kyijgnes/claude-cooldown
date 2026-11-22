package com.kyijgnes.cooldown.wallpaper

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.BitmapRegionDecoder
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Rect
import android.graphics.RectF
import org.json.JSONObject
import java.io.File

/**
 * 클로디 자리에 서는 **캐릭터팩 캐릭터**를 틀고 그린다(2026-11-22). 가져오기·고르기는 `BuddyPack`.
 *
 * 노는 규칙은 클로디(`Mascot`) 것을 그대로 쓴다 — 누르기·박자·꾹·기절(→ 공룡알)·딴짓·자리 비움이 같은 때 일어나고,
 * `Mascot` 이 지금 무엇을 하는지(`Mascot.buddyMotion`)를 동작 이름으로 넘기면 여기서 그 동작 그림을 튼다.
 *
 * - ★ **1모션 원칙(PC 바 캐릭터와 같다):** 상호작용 하나 동안 그림 하나. 같은 동작이 이어지는 동안 그림을
 *   안 바꾸고, 자꾸 눌러 단계가 오를 때(놀람 → 짜증 → 화남 → 포기)만 바꾼다. 상호작용 그림은 끝까지
 *   한 번은 다 틀고(`HOLD_MAX_MS` 까지) 평소 동작으로 돌아간다. 같은 동작을 또 누르면 처음부터(`seq`).
 * - 그림은 PC 가 장면으로 구워 보낸다(효과·빌려 온 그림·장면 길이까지). 여기는 장면 길이(ms)대로 넘길 뿐이다.
 *   `되감기` 가 있으면 끝까지 튼 뒤 그 장면부터 되풀이한다. 한 번만 트는 동작(`ONCE`)은 끝 장면에 멈춘다.
 * - 시간은 `Mascot` 의 프레임(30fps)으로 센다 — 폰 없이 뽑는 미리보기가 돌릴 때마다 같다.
 */
class Buddy(val character: Character) {

    class Clip(val file: File, val w: Int, val h: Int, val cols: Int, val ms: IntArray, val loopFrom: Int) {
        val total = ms.sum()
        private val loopStart = ms.take(loopFrom).sum()

        /** `elapsed` ms 에 보일 장면 번호. `once` 면 끝 장면에 멈춘다. */
        fun frameAt(elapsed: Long, once: Boolean): Int {
            var t = elapsed
            if (t >= total) {
                if (once) return ms.size - 1
                val span = total - loopStart
                t = if (span <= 0) total - 1L else loopStart + (t - loopStart) % span
            }
            var acc = 0L
            for (i in ms.indices) {
                acc += ms[i]
                if (t < acc) return i
            }
            return ms.size - 1
        }

        fun cell(i: Int): Rect {
            val x = (i % cols) * w
            val y = (i / cols) * h
            return Rect(x, y, x + w, y + h)
        }
    }

    class Character(val name: String, val facesRight: Boolean, val motions: Map<String, List<Clip>>) {
        companion object {
            fun parse(o: JSONObject, dir: File): Character {
                val out = HashMap<String, List<Clip>>()
                val ms = o.getJSONObject("동작")
                for (m in ms.keys()) {
                    val arr = ms.getJSONArray(m)
                    out[m] = (0 until arr.length()).map { i ->
                        val e = arr.getJSONObject(i)
                        val list = e.getJSONArray("ms")
                        Clip(File(dir, e.getString("그림")), e.getInt("폭"), e.getInt("높이"), e.getInt("열"),
                            IntArray(list.length()) { list.getInt(it) }, e.optInt("되감기", 0))
                    }
                }
                return Character(o.getString("이름"), o.optString("보는 쪽") != "왼쪽", out)
            }
        }

        /** 그 동작의 후보들 — 없으면 빌린다(PC 가 이미 빌려 보내지만 옛 팩·빠진 칸에 대비). */
        fun clips(motion: String): List<Clip> {
            for (m in listOf(motion) + (FALLBACK[motion] ?: emptyList()) + listOf("서기")) {
                motions[m]?.takeIf { it.isNotEmpty() }?.let { return it }
            }
            return motions.values.firstOrNull { it.isNotEmpty() } ?: emptyList()
        }
    }

    // ---------------------------------------------------------------- 지금 트는 것
    private var motion = ""
    private var clip: Clip? = null
    private var startF = 0
    private var seq = -1

    /** 지금 보이는 동작 (시험·미리보기용). */
    val showing: String get() = motion

    /**
     * 이 프레임에 보일 동작을 정한다. `want` 는 `Mascot` 이 지금 하는 것, `seq` 는 누를 때마다 오르는 번호,
     * `f` 는 프레임 번호.
     */
    fun update(want: String, seq: Int, f: Int) {
        val cur = clip
        val playing = cur != null && motion in INTERACT && (f - startF) * FRAME_MS < minOf(cur.total.toLong(), HOLD_MAX_MS)
        when {
            want == motion && want in INTERACT && seq != this.seq -> start(want, f, keep = true)  // 또 눌렀다: 처음부터
            want == motion -> {
                // 평소 동작은 한참 틀었으면 다른 후보로 갈아 끼운다 (늘 같은 그림만 안 보이게)
                if (want in EVERYDAY && cur != null && (f - startF) * FRAME_MS >= maxOf(cur.total.toLong(), SWAP_MS)) {
                    start(want, f, keep = false)
                }
            }
            // 상호작용 그림이 아직 안 끝났으면 평소 동작이 끼어들지 못한다 (1모션)
            playing && want !in INTERACT && want !in STATES_URGENT -> Unit
            else -> start(want, f, keep = false)
        }
        this.seq = seq
    }

    private fun start(want: String, f: Int, keep: Boolean) {
        val all = character.clips(want)
        val next = when {
            all.isEmpty() -> null
            keep && clip != null && clip in all -> clip
            want in INTERACT -> all[0]                       // 상호작용은 늘 같은 반응
            else -> {                                        // 평소 동작: 방금 것은 피해서 하나 (자리 난수)
                val pool = all.filter { it !== clip }.ifEmpty { all }
                pool[((f.toLong() * 2654435761L) ushr 7).mod(pool.size.toLong()).toInt()]
            }
        }
        motion = want
        clip = next
        startF = f
    }

    /**
     * 그린다. 발 가운데가 (`footX`,`footY`), 서 있는 키가 `height` px. `dir` 은 보는 쪽(-1 왼쪽 / 1 오른쪽).
     * 그림 칸의 바닥 가운데가 발 자리다(PC 가 바닥 가운데로 맞춰 굽는다).
     */
    fun draw(c: Canvas, footX: Float, footY: Float, height: Float, dir: Int, f: Int, alpha: Int = 255) {
        val cl = clip ?: return
        val bmp = Sheets.get(cl.file) ?: return
        val i = cl.frameAt((f - startF) * FRAME_MS, motion in ONCE)
        val k = height / cl.h
        val dw = cl.w * k
        val dst = RectF(footX - dw / 2f, footY - height, footX + dw / 2f, footY)
        val flip = (dir > 0) != character.facesRight
        paint.alpha = alpha
        if (flip) {
            c.save()
            c.scale(-1f, 1f, footX, footY)
        }
        c.drawBitmap(bmp, cl.cell(i), dst, paint)
        if (flip) c.restore()
    }

    /** 그려질 폭 (px) — 누름 판정에 쓴다. */
    fun widthAt(height: Float): Float {
        val cl = clip ?: character.clips("서기").firstOrNull() ?: return height
        return cl.w * height / cl.h
    }

    private val paint = Paint(Paint.FILTER_BITMAP_FLAG or Paint.ANTI_ALIAS_FLAG)

    companion object {
        const val FRAME_MS = 33L
        const val HOLD_MAX_MS = 3_500L   // 상호작용 그림을 끝까지 틀어 주는 한도 (긴 움짤은 여기서 끊는다)
        const val SWAP_MS = 6_000L       // 평소 그림을 이만큼 틀면 다른 후보로

        /** 폰이 쓰는 동작 — PC `cooldown_pack_export.PHONE_MOTIONS` 와 같게 둔다. 모르는 이름은 안 읽는다. */
        val MOTIONS = setOf(
            "서기", "딴짓", "걷기", "인사", "뛰기", "점프",
            "놀람", "눌림", "짜증", "화남", "포기", "기절", "깡충", "깸",
            "허둥", "잠", "축하", "자리비움",
        )
        val EVERYDAY = setOf("서기", "딴짓", "걷기", "잠", "허둥", "자리비움")
        val INTERACT = setOf("놀람", "눌림", "짜증", "화남", "포기", "기절", "깡충", "깸", "인사", "점프", "뛰기")
        /** 상호작용 그림이 덜 끝났어도 끼어드는 것. */
        private val STATES_URGENT = setOf("축하")
        private val ONCE = setOf("기절", "깸")
        private val FALLBACK = mapOf(
            "딴짓" to listOf("서기"), "걷기" to listOf("서기"), "인사" to listOf("놀람"),
            "뛰기" to listOf("걷기"), "점프" to listOf("축하", "놀람"), "놀람" to listOf("서기"),
            "눌림" to listOf("놀람"), "짜증" to listOf("놀람"), "화남" to listOf("짜증", "놀람"),
            "포기" to listOf("잠", "눌림"), "기절" to listOf("잠", "눌림"), "깡충" to listOf("점프", "놀람"),
            "깸" to listOf("놀람"), "허둥" to listOf("뛰기", "걷기"), "잠" to listOf("서기"),
            "축하" to listOf("점프", "인사"), "자리비움" to listOf("잠", "딴짓"),
        )

        /** 홈 위젯 한 장 — 그 동작의 첫 후보에서 장면 하나만 떠서 그린다(전체 그림을 안 펼친다). */
        fun still(ch: Character, motion: String, c: Canvas, footX: Float, footY: Float, height: Float, at: Float = 0f) {
            val cl = ch.clips(motion).firstOrNull() ?: return
            val i = (cl.ms.size * at).toInt().coerceIn(0, cl.ms.size - 1)
            val part = try {
                @Suppress("DEPRECATION")
                BitmapRegionDecoder.newInstance(cl.file.path, false)?.let { d ->
                    try { d.decodeRegion(cl.cell(i), null) } finally { d.recycle() }
                }
            } catch (e: Exception) {
                null
            }
            val k = height / cl.h
            val dw = cl.w * k
            val dst = RectF(footX - dw / 2f, footY - height, footX + dw / 2f, footY)
            val p = Paint(Paint.FILTER_BITMAP_FLAG or Paint.ANTI_ALIAS_FLAG)
            if (part != null) {
                c.drawBitmap(part, null, dst, p)
                part.recycle()
            } else {   // 한 칸만 못 뜨면 통째로 펼쳐서 그 칸을 그린다
                val all = Sheets.get(cl.file) ?: return
                c.drawBitmap(all, cl.cell(i), dst, p)
            }
        }
    }

    /** 펼친 장면 묶음 그림 — 한 벌이 수 MB 라 최근 것만 들고 있는다(`MAX_BYTES`). */
    object Sheets {
        private const val MAX_BYTES = 48L * 1024 * 1024
        private val map = LinkedHashMap<String, Bitmap>(16, 0.75f, true)
        private var bytes = 0L

        @Synchronized
        fun get(f: File): Bitmap? {
            map[f.path]?.let { return it }
            val bmp = try {
                BitmapFactory.decodeFile(f.path, BitmapFactory.Options().apply {
                    inPreferredConfig = Bitmap.Config.ARGB_8888
                })
            } catch (e: Throwable) {   // 메모리가 모자라면 이번엔 건너뛴다
                null
            } ?: return null
            map[f.path] = bmp
            bytes += bmp.byteCount
            val it = map.entries.iterator()
            while (bytes > MAX_BYTES && map.size > 1 && it.hasNext()) {
                val e = it.next()
                if (e.value === bmp) continue
                bytes -= e.value.byteCount
                it.remove()   // recycle 은 안 한다 — 다른 쪽이 이 프레임에 그리고 있을 수 있다
            }
            return bmp
        }
    }
}
