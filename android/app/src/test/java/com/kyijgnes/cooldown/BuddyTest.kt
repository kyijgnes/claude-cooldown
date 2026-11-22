package com.kyijgnes.cooldown

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import com.kyijgnes.cooldown.wallpaper.Mascot
import com.kyijgnes.cooldown.wallpaper.WallpaperArt
import com.kyijgnes.cooldown.widget.WidgetClaudi
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/**
 * 캐릭터팩(`BuddyPack`·`Buddy`) — 가져오기 검사 · 누르기 단계 · 1모션 · 미리보기 그림(`build/미리보기/캐릭터_*.png`).
 * 그림은 여기서 색 네모로 그려 만든다(저장소에 남의 그림을 안 둔다).
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34])
class BuddyTest {

    private val ctx get() = RuntimeEnvironment.getApplication()
    private val out = File("build/미리보기").apply { mkdirs() }

    @Before
    fun clean() {
        BuddyPack.root(ctx).deleteRecursively()
        BuddyPack.setActive(ctx, null)
    }

    /** 색 네모 장면 n 개를 늘어놓은 묶음 그림 (PNG 바이트. 폰은 내용으로 형식을 알아본다). */
    private fun sheet(n: Int, color: Int, w: Int = 40, h: Int = 60, cols: Int = 4): ByteArray {
        val rows = (n + cols - 1) / cols
        val bmp = Bitmap.createBitmap(w * minOf(cols, n), h * rows, Bitmap.Config.ARGB_8888)
        val c = Canvas(bmp)
        val p = Paint()
        for (i in 0 until n) {
            p.color = color
            p.alpha = 255 - i * 20
            val x = (i % cols) * w
            val y = (i / cols) * h
            c.drawRect((x + 4).toFloat(), (y + 6 + i % 3).toFloat(), (x + w - 4).toFloat(), (y + h).toFloat(), p)
        }
        return ByteArrayOutputStream().also { bmp.compress(Bitmap.CompressFormat.PNG, 100, it) }.toByteArray()
    }

    private val motions = linkedMapOf(
        "서기" to (4 to Color.rgb(90, 160, 220)), "걷기" to (4 to Color.rgb(90, 200, 120)),
        "놀람" to (3 to Color.rgb(250, 200, 40)), "짜증" to (3 to Color.rgb(240, 140, 40)),
        "화남" to (3 to Color.rgb(230, 60, 40)), "포기" to (3 to Color.rgb(120, 120, 120)),
        "기절" to (8 to Color.rgb(160, 80, 200)), "모르는동작" to (2 to Color.BLACK),
    )

    private fun pack(name: String = "시험떡", extra: List<Pair<String, ByteArray>> = emptyList(),
                     manifestName: String = "폰팩.json"): ByteArray {
        val files = ArrayList<Pair<String, ByteArray>>()
        val table = JSONObject()
        var k = 0
        for ((m, spec) in motions) {
            val (n, color) = spec
            val pic = "c0/%016x.webp".format(++k)
            files.add(pic to sheet(n, color))
            table.put(m, JSONArray().put(JSONObject().put("그림", pic).put("폭", 40).put("높이", 60).put("열", 4)
                .put("ms", JSONArray(List(n) { 200 })).put("되감기", 0)))
        }
        val manifest = JSONObject().put("형식", 1).put("바 캐릭터", name).put("캐릭터", JSONArray().put(
            JSONObject().put("이름", name).put("폴더", "c0").put("보는 쪽", "오른쪽").put("동작", table)))
        val bytes = ByteArrayOutputStream()
        ZipOutputStream(bytes).use { z ->
            z.putNextEntry(ZipEntry(manifestName)); z.write(manifest.toString().toByteArray()); z.closeEntry()
            for ((n, b) in files + extra) { z.putNextEntry(ZipEntry(n)); z.write(b); z.closeEntry() }
        }
        return bytes.toByteArray()
    }

    private fun import(b: ByteArray) = BuddyPack.importStream(ctx, ByteArrayInputStream(b))

    @Test
    fun `가져오면 고를 수 있고 고르기 전에는 클로디`() {
        assertEquals(listOf("시험떡"), import(pack()))
        assertEquals(listOf("시험떡"), BuddyPack.names(ctx))
        assertNull(BuddyPack.current(ctx))           // 가져와도 저절로 안 바뀐다 (PC 와 같다)
        BuddyPack.setActive(ctx, "시험떡")
        val ch = BuddyPack.current(ctx)
        assertNotNull(ch)
        assertTrue("모르는 동작은 버린다", "모르는동작" !in ch!!.motions)
        assertEquals(setOf("서기", "걷기", "놀람", "짜증", "화남", "포기", "기절"), ch.motions.keys)
        // 같은 이름을 또 가져오면 바꿔 넣는다 (둘이 되지 않는다)
        import(pack())
        assertEquals(listOf("시험떡"), BuddyPack.names(ctx))
        BuddyPack.remove(ctx, "시험떡")
        assertNull(BuddyPack.current(ctx))
        assertTrue(BuddyPack.names(ctx).isEmpty())
    }

    @Test
    fun `이상한 파일은 통째로 거절하고 아무것도 안 남긴다`() {
        fun bad(b: ByteArray, why: String) {
            try {
                import(b)
                fail("들어가면 안 된다: $why")
            } catch (e: BuddyPack.PackError) {
                // 바라던 것
            }
            assertTrue(why, BuddyPack.names(ctx).isEmpty())
            assertTrue(why, (BuddyPack.root(ctx).listFiles() ?: emptyArray()).none { it.name.startsWith("_") })
        }
        bad(pack(extra = listOf("../밖.webp" to ByteArray(4))), "경로 탈출")
        bad(pack(extra = listOf("c0/a.exe" to ByteArray(4))), "그림 아닌 파일")
        bad(pack(manifestName = "팩.json"), "PC 끼리 쓰는 캐릭터팩")
        bad("zip 아님".toByteArray(), "zip 아님")
    }

    private fun buddyMascot(): Mascot {
        import(pack())
        BuddyPack.setActive(ctx, "시험떡")
        val m = Mascot()
        BuddyPack.sync(ctx, m, Snapshot.EMPTY)
        assertNotNull(m.buddy)
        return m
    }

    private fun frame(m: Mascot, c: Canvas) {
        m.step(540f, 1500f, 12f, 1080f, 2340f)
        m.draw(c, 540f, 1500f, 12f, Color.RED, Color.WHITE)
    }

    @Test
    fun `자꾸 누르면 놀람 짜증 화남 포기 기절 차례로 오르고 내려가지 않는다`() {
        val m = buddyMascot()
        val c = Canvas(Bitmap.createBitmap(1080, 2340, Bitmap.Config.ARGB_8888))
        val seen = ArrayList<String>()
        for (i in 0 until 400) {
            if (i % 3 == 0 && "기절" !in seen) m.press()
            if (i % 3 == 1) m.release()
            frame(m, c)
            val now = m.buddy!!.showing
            if (seen.lastOrNull() != now) seen.add(now)
        }
        val order = listOf("놀람", "짜증", "화남", "포기", "기절")
        assertEquals("단계가 이 차례로만 바뀐다: $seen", order, seen.filter { it in order }.take(5))
    }

    @Test
    fun `한 번 누르면 놀람 그림 하나를 끝까지 틀고 평소로 돌아온다`() {
        val m = buddyMascot()
        val c = Canvas(Bitmap.createBitmap(1080, 2340, Bitmap.Config.ARGB_8888))
        frame(m, c)
        m.press(); m.release()
        val shown = ArrayList<String>()
        repeat(150) { frame(m, c); shown.add(m.buddy!!.showing) }
        // 놀람 그림(3장 × 200ms = 18프레임) 동안은 다른 그림으로 안 바뀐다
        assertTrue(shown.take(18).all { it == "놀람" })
        assertTrue("평소로 돌아온다: ${shown.last()}", shown.last() !in listOf("놀람", "짜증", "화남", "포기"))
    }

    @Test
    fun `사용량으로 기분을 정한다`() {
        val now = 1_753_800_000_000L
        fun s(five: Float, reset: Long) = Snapshot(Limit("5시간", five, reset), Limit("주간", 10f, now + 9e8.toLong()), now, false)
        assertEquals("", BuddyPack.moodOf(s(30f, now + 3_600_000L), now))
        assertEquals("허둥", BuddyPack.moodOf(s(85f, now + 3_600_000L), now))
        assertEquals("잠", BuddyPack.moodOf(s(100f, now + 3_600_000L), now))
        assertTrue(BuddyPack.moodOf(s(100f, now - 60_000L), now).startsWith("풀림"))
        assertEquals("", BuddyPack.moodOf(s(100f, now - 3_600_000L), now))   // 오래전에 풀린 것
    }

    @Test
    fun `캐릭터 미리보기 그림을 남긴다`() {
        val m = buddyMascot()
        m.onHatch = {}
        val bmp = Bitmap.createBitmap(1080, 2340, Bitmap.Config.ARGB_8888)
        val snap = Snapshot(Limit("5시간", 37f, null), Limit("주간", 62f, null), 0L, false)
        WallpaperArt.render(ctx, Canvas(bmp), snap, 1_753_800_000_000L, Look.DEFAULT, m)
        save(bmp, "캐릭터_서기.png")
        repeat(60) { if (it % 2 == 0) m.press() else m.release(); WallpaperArt.render(ctx, Canvas(bmp), snap, 0L, Look.DEFAULT, m) }
        repeat(40) { WallpaperArt.render(ctx, Canvas(bmp), snap, 0L, Look.DEFAULT, m) }
        save(bmp, "캐릭터_기절_알.png")
        assertTrue("기절시키면 캐릭터일 때도 알이 나온다", m.hasEgg)
        save(WidgetClaudi.bitmap(ctx, 230, 140, WidgetClaudi.State("egg", 1)), "캐릭터_위젯_알.png")
        save(WidgetClaudi.bitmap(ctx, 230, 140, WidgetClaudi.State("idle", 0)), "캐릭터_위젯_평소.png")
    }

    /**
     * PC 에서 만든 진짜 폰용 팩으로 미리보기 (`COOLDOWN_PHONE_PACK=<zip 경로>` 일 때만, 그림은 build 에만 남는다).
     * 캐릭터마다 동작 줄을 한 장에 늘어놓는다: 동작마다 첫·가운데 장면.
     */
    @Test
    fun `진짜 팩 미리보기`() {
        val path = System.getenv("COOLDOWN_PHONE_PACK") ?: return
        val names = BuddyPack.importStream(ctx, File(path).inputStream())
        for ((ci, name) in names.withIndex()) {
            BuddyPack.setActive(ctx, name)
            val ch = BuddyPack.current(ctx)!!
            val list = com.kyijgnes.cooldown.wallpaper.Buddy.MOTIONS.filter { it in ch.motions }
            val cell = 150
            val bmp = Bitmap.createBitmap(cell * 2 * 6, cell * ((list.size + 5) / 6), Bitmap.Config.ARGB_8888)
            val c = Canvas(bmp)
            c.drawColor(Color.rgb(222, 236, 250))
            list.forEachIndexed { i, m ->
                for (k in 0..1) {
                    val x = ((i % 6) * 2 + k) * cell + cell / 2f
                    val y = (i / 6 + 1) * cell - 6f
                    com.kyijgnes.cooldown.wallpaper.Buddy.still(ch, m, c, x, y, cell - 20f, if (k == 0) 0f else 0.5f)
                }
            }
            save(bmp, "실제팩_$ci.png")
        }
    }

    private fun save(bmp: Bitmap, name: String) {
        File(out, name).outputStream().use { bmp.compress(Bitmap.CompressFormat.PNG, 100, it) }
    }
}
