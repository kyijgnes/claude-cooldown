package com.kyijgnes.cooldown

import android.graphics.Bitmap
import android.graphics.Canvas
import android.view.View
import com.kyijgnes.cooldown.wallpaper.Mascot
import com.kyijgnes.cooldown.wallpaper.WallpaperArt
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File

/**
 * 폰 없이 화면 그림을 PNG 로 뽑는다 — `gradlew testDebugUnitTest` 후
 * `app/build/미리보기/` 를 열어 보면 된다. 값 규칙(초기화 보정)도 여기서 확인한다.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34])
class RenderPreviewTest {

    private val out = File("build/미리보기").apply { mkdirs() }
    private val now = 1_753_800_000_000L  // 고정 시각 — 그림이 매번 같게
    private val W = 1080f                 // FHD+ 세로 (배경화면 그림 기준)
    private val H = 2340f

    private fun snap(five: Float?, week: Float?, stale: Boolean = false) = Snapshot(
        five = Limit("5시간", five, now + 2 * 3600_000L + 7 * 60_000L),
        week = Limit("주간", week, now + 3 * 86_400_000L + 4 * 3600_000L),
        updatedAt = now - 60_000L,
        stale = stale,
    )

    private fun save(bmp: Bitmap, name: String) {
        File(out, name).outputStream().use { bmp.compress(Bitmap.CompressFormat.PNG, 100, it) }
    }

    /** 꾸미기 값 한 벌로 배경화면 한 장. 테스트엔 사진이 없어 바탕색 위에 미터기만 뜬다. */
    private fun wallpaper(
        ctx: android.content.Context, name: String,
        look: Look.Values = Look.DEFAULT, at: Long = now,
        mascot: Mascot = Mascot(),
    ) {
        val bmp = Bitmap.createBitmap(1080, 2340, Bitmap.Config.ARGB_8888)
        WallpaperArt.render(ctx, Canvas(bmp), snap(37f, 62f), at, look, mascot)
        save(bmp, "$name.png")
    }

    /**
     * 클로디가 **딴짓·기절처럼 어쩌다 나오는 장면**에 있을 때의 그림.
     * 그냥 렌더하면 늘 가만히 서 있는 한 장만 나와서, 장면을 세우고 몇 프레임 굴려 잡는다.
     */
    private fun claudi(ctx: android.content.Context, name: String, pose: String, frames: Int) {
        val m = Mascot()
        m.poseForPreview(pose)
        val u = WallpaperArt.mascotCell(W)
        repeat(frames) { m.step(Look.DEFAULT.mascotX * W, Look.DEFAULT.mascotY * H, u, W, H) }
        wallpaper(ctx, name, mascot = m)
    }

    @Test
    fun `위젯과 배경화면 그림을 남긴다`() {
        val ctx = RuntimeEnvironment.getApplication()

        // 넓은 위젯 — 보통 / 최악(100%·긴 글자) / 값 없음.
        // ★ 홈 위젯은 **판 없이(card=false)** 배경화면 위에 바로 얹힌다 — 실제와 같게 그린다.
        //   글자에 바탕색 후광이 둘러져 있는지 그림으로 확인할 것(어두운 배경화면 대비).
        save(GaugeRenderer.wide(ctx, 1080, 300, snap(37f, 62f), now, card = false), "넓은위젯_보통.png")
        save(GaugeRenderer.wide(ctx, 1080, 300, snap(100f, 100f), now, card = false), "넓은위젯_가득.png")
        save(GaugeRenderer.wide(ctx, 1080, 300, snap(null, null), now, card = false), "넓은위젯_값없음.png")
        save(
            GaugeRenderer.wide(ctx, 720, 260, snap(37f, 62f, stale = true), now, card = false),
            "넓은위젯_PC꺼짐.png",
        )
        // 앱 화면은 판을 깐 쪽을 쓴다
        save(GaugeRenderer.wide(ctx, 1080, 300, snap(37f, 62f), now), "앱화면_게이지.png")

        // 작은 위젯
        save(GaugeRenderer.small(ctx, 300, snap(37f, 62f), now, card = false), "작은위젯.png")
        save(GaugeRenderer.small(ctx, 300, snap(93f, 12f), now, card = false), "작은위젯_임박.png")

        // 상태바 아이콘 (실제로는 24dp 로 줄어든다)
        save(GaugeRenderer.statusIcon(7f), "상태바_7.png")
        save(GaugeRenderer.statusIcon(47f), "상태바_47.png")
        save(GaugeRenderer.statusIcon(100f), "상태바_100.png")
        save(GaugeRenderer.statusIcon(null), "상태바_값없음.png")

        // 라이브 배경화면 (FHD+ 세로) — 클로디가 있는 판과 없는 판 (클로디는 눌러서 논다)
        wallpaper(ctx, "배경화면")
        wallpaper(ctx, "배경화면_클로디없음", look = Look.DEFAULT.copy(mascot = false))

        // 클로디가 어쩌다 하는 것들 — 오래 안 건드리면 나오는 딴짓과 기절.
        // 데스크탑 위젯과 같은 장면이라, 여기 그림으로 **폰에서도 같은 친구인지** 본다.
        claudi(ctx, "클로디_노트북", "type", 8)      // 옆으로 돌아앉아 두드린다
        claudi(ctx, "클로디_낮잠", "nap", 45)         // 눈 감고 z 를 띄운다
        claudi(ctx, "클로디_공놀이", "ball", 9)       // 공이 손을 떠나 있는 순간
        claudi(ctx, "클로디_기절", "faint", 6)        // X_X + 별이 뱅뱅
        claudi(ctx, "클로디_자리비움", "away", 1)     // 화면 아래로 내려가는 중
        // 완주 축하 — 크래커를 들고 쏘는 중(날아가는 알 + 터진 것이 같이 보이는 즈음)
        claudi(ctx, "클로디_축하", "party", 26)
        claudi(ctx, "클로디_공룡", "dino", 3)          // 판 속에 들어가 있는 채 (앱 첫 화면에서는 숨는다)
        claudi(ctx, "클로디_공룡알", "egg", 3)        // 기절에서 깨어나 굴러 나온 알 — 금 하나
        claudi(ctx, "클로디_알깨짐", "hatch", 2)      // 뚜껑이 튀고 작은 공룡이 올라온다

        // 홈 화면에서 알을 깨면 — 미터기 자리가 판이 된다 (클로디는 판 속에, 미터기는 안 그린다)
        val home = Bitmap.createBitmap(1080, 2340, Bitmap.Config.ARGB_8888)
        WallpaperArt.render(ctx, Canvas(home), snap(37f, 62f), now, Look.DEFAULT, null, meter = false)
        val play = com.kyijgnes.cooldown.dino.DinoBoard(ctx, 312, seed = 3L)
        play.game.pressJump(); play.game.releaseJump()
        repeat(900) { if (play.game.state == "run") { dinoBot(play.game); play.game.step() } }
        play.paint(Canvas(home), WallpaperArt.boardTop(W, H, Look.DEFAULT, play.heightFor(W)), W)
        save(home, "배경화면_공룡점프.png")

        // 꾸미기 — 고를 수 있는 것들을 한 장씩 (CustomizeActivity 의 선택지와 같은 순서)
        wallpaper(ctx, "꾸미기_링", look = Look.DEFAULT.copy(meter = Look.RINGS))
        wallpaper(ctx, "꾸미기_숫자만", look = Look.DEFAULT.copy(meter = Look.NUMBERS))
        wallpaper(ctx, "꾸미기_미터기없음", look = Look.DEFAULT.copy(meter = Look.NONE))
        wallpaper(ctx, "꾸미기_글씨뒤판", look = Look.DEFAULT.withPlate(true))
        wallpaper(
            ctx, "꾸미기_크게_위로",
            look = Look.DEFAULT.copy(meterSize = Look.METER_MAX)
                .withMeterPos(0.5f, 0.28f).withBg(0.5f, 0.7f),
        )
        wallpaper(
            ctx, "꾸미기_작게_구석",
            // 화면 밖으로 못 나간다 — 모서리에 붙는다
            look = Look.DEFAULT.copy(meter = Look.NUMBERS, meterSize = Look.METER_MIN).withMeterPos(0f, 1f),
        )
        // 사진을 못 읽으면(안 골랐거나 지웠거나) 밋밋한 바탕색으로 내려간다
        wallpaper(ctx, "꾸미기_사진못읽음", look = Look.DEFAULT.copy(photo = "content://없는것/1"))

        // 앱 아이콘 — 런처가 달라는 크기가 제각각이라 두 크기로 뽑아 비율을 확인한다
        for (size in listOf(432, 144)) {
            ctx.getDrawable(R.mipmap.ic_launcher)?.let { icon ->
                val ic = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888)
                icon.setBounds(0, 0, size, size)
                icon.draw(Canvas(ic))
                save(ic, "앱아이콘_$size.png")
            }
        }

        // 어둡게
        RuntimeEnvironment.setQualifiers("+night")
        val dark = Bitmap.createBitmap(1080, 2340, Bitmap.Config.ARGB_8888)
        WallpaperArt.render(
            RuntimeEnvironment.getApplication(), Canvas(dark), snap(37f, 62f), now, Look.DEFAULT,
        )
        save(dark, "배경화면_어둡게.png")
        RuntimeEnvironment.setQualifiers("+notnight")
    }

    /**
     * **위젯 고르는 화면에 뜨는 그림**(`previewLayout`)을 폰 없이 본다.
     * 실제 위젯 레이아웃은 런타임에 채우는 빈 ImageView 라 그대로 걸면 빈 칸이 된다 —
     * 그래서 미리보기 전용 레이아웃을 따로 두고, 여기서 비어 보이지 않는지 확인한다.
     */
    @Test
    @Config(sdk = [34], qualifiers = "w360dp-h780dp-xxhdpi")
    fun `위젯 고르는 화면 그림을 남긴다`() {
        for ((layout, w, h, name) in listOf(
            Quad(R.layout.widget_preview_wide, 900, 240, "위젯미리보기_넓은"),
            Quad(R.layout.widget_preview_small, 240, 240, "위젯미리보기_작은"),
        )) {
            val ctx = RuntimeEnvironment.getApplication()
            val view = android.view.LayoutInflater.from(ctx).inflate(layout, null)
            view.measure(
                View.MeasureSpec.makeMeasureSpec(w, View.MeasureSpec.EXACTLY),
                View.MeasureSpec.makeMeasureSpec(h, View.MeasureSpec.EXACTLY),
            )
            view.layout(0, 0, w, h)
            val bmp = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888)
            view.draw(Canvas(bmp))
            save(bmp, "$name.png")
        }
    }

    private data class Quad(val layout: Int, val w: Int, val h: Int, val name: String)

    /**
     * 꾸미기 화면 자체도 폰 없이 본다 — 미리보기 판·선택지가 한 화면에 들어오는지.
     * 미리보기 크기가 화면 크기에서 나오므로 **진짜 폰 해상도(1080×2340)로 재야** 뜻이 있다.
     */
    @Test
    @Config(sdk = [34], qualifiers = "w360dp-h780dp-xxhdpi")
    fun `꾸미기 화면 그림을 남긴다`() {
        Look.write(RuntimeEnvironment.getApplication(), Look.DEFAULT)
        val controller = Robolectric.buildActivity(CustomizeActivity::class.java).setup()
        val root = controller.get().window.decorView
        val w = 1080
        val h = 2340
        root.measure(
            View.MeasureSpec.makeMeasureSpec(w, View.MeasureSpec.EXACTLY),
            View.MeasureSpec.makeMeasureSpec(h, View.MeasureSpec.EXACTLY),
        )
        root.layout(0, 0, w, h)
        val bmp = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888)
        root.draw(Canvas(bmp))
        save(bmp, "꾸미기화면.png")
        controller.pause().destroy()
    }

    /**
     * ★ **위젯 그림은 1MB 를 넘으면 안 된다** — RemoteViews 로 못 넘겨 위젯이 통째로
     * 빈 칸이 된다(4×1 을 4×2 로 늘렸을 때 실제로 미터기가 사라졌다).
     * 4×2·5×3 처럼 큰 칸에서도 총량이 줄어드는지 여기서 지킨다.
     */
    @Test
    fun `위젯 그림이 넘길 수 있는 크기를 안 넘는다`() {
        val ctx = RuntimeEnvironment.getApplication()
        val limit = 1_000_000  // RemoteViews 한 번에 넘길 수 있는 양 (바이트)
        for ((wDp, hDp) in listOf(320 to 70, 320 to 150, 320 to 300, 400 to 400)) {
            val w = (wDp * 3f).toInt()   // xxhdpi 기준
            val h = (hDp * 3f).toInt()
            val k = kotlin.math.sqrt(w.toLong() * h / 230_000.0).coerceAtLeast(1.0)
            val bmp = GaugeRenderer.wide(
                ctx, (w / k).toInt(),
                minOf((h / k).toInt(), ((w / k) * 0.30f).toInt()).coerceAtLeast(60),
                snap(37f, 62f), now, card = false,
            )
            assert(bmp.byteCount < limit) { "${wDp}x$hDp → ${bmp.byteCount} 바이트" }
        }
    }

    /**
     * 클로디와 노는 규칙(데스크탑과 같은 것) — **박자를 맞히면 단이 오르고 안 지치지만,
     * 마구 두드리면 콤보가 아니라 기절에 먼저 닿는다.** 둘 중 하나만 어긋나도 놀이가 무너진다.
     */
    @Test
    fun `박자를 맞히면 단이 오르고 마구 두드리면 뻗는다`() {
        val u = WallpaperArt.mascotCell(W)
        val cx = Look.DEFAULT.mascotX * W
        val cy = Look.DEFAULT.mascotY * H

        // 통통 튀다 바닥에 멎는 박자(약 14프레임 = 0.47초)에 맞춰 — 13번 맞히면 5단·폭죽.
        // 첫 한 방은 제자리에서 치는 것이라 박자로 안 쳐 주므로 몇 번 넉넉히 둔다.
        val onBeat = Mascot()
        var sawTier = 0
        var sawFinale = false
        repeat(16) {
            onBeat.press()
            onBeat.release()
            repeat(14) { onBeat.step(cx, cy, u, W, H) }
            sawTier = maxOf(sawTier, onBeat.debug().combo)
            sawFinale = sawFinale || onBeat.debug().finale
        }
        assertEquals(5, sawTier)
        assertTrue("완주하면 축하 폭죽이 터져야 한다", sawFinale)
        assertFalse("박자대로 놀면 안 지친다", onBeat.debug().fainted)

        // 마구 두드리기 — 2초 안에 뻗는다
        val mash = Mascot()
        var fainted = false
        repeat(30) {
            mash.press()
            mash.release()
            repeat(2) { mash.step(cx, cy, u, W, H) }
            fainted = fainted || mash.debug().fainted
        }
        assertTrue("마구 두드리면 기절한다", fainted)
    }

    /**
     * 공룡 점프 판 — 기다림 / 달리는 중 / 부딪힘, 밝게·어둡게. **앱 첫 화면의 게이지 자리 크기**
     * (FHD 너비 1080 − 좌우 여백, 높이 = 게이지)로 그린다. PC(`cooldown_dino_view.py shot`)와 눈으로 대조.
     */
    @Test
    fun `공룡 점프 판 그림을 남긴다`() {
        for (theme in listOf("밝게", "어둡게")) {
            RuntimeEnvironment.setQualifiers(if (theme == "어둡게") "+night" else "+notnight")
            val ctx = RuntimeEnvironment.getApplication()
            for (scene in listOf("기다림", "달리기", "부딪힘")) {
                val view = com.kyijgnes.cooldown.dino.DinoView(ctx, best = 312, seed = 3L)
                view.layout(0, 0, 960, 307)
                val g = view.game
                if (scene != "기다림") {
                    g.pressJump(); g.releaseJump()
                    repeat(if (scene == "달리기") 1500 else 700) { if (g.state == "run") { dinoBot(g); g.step() } }
                    if (scene == "부딪힘") g.crashForPreview()
                }
                val bmp = Bitmap.createBitmap(960, 307, Bitmap.Config.ARGB_8888)
                view.paint(Canvas(bmp))
                save(bmp, "공룡점프_${scene}_$theme.png")
            }
        }
        RuntimeEnvironment.setQualifiers("+notnight")
    }

    /**
     * 앱 첫 화면 — 제목 옆 클로디, 그리고 **공룡 점프 중**(게이지 자리가 판이 되고 클로디는 숨는다).
     * 화면(액티비티)은 작업 예약까지 돌리므로 레이아웃만 불러 그대로 그린다.
     */
    @Test
    @Config(sdk = [34], qualifiers = "w360dp-h780dp-xxhdpi")
    fun `앱 첫 화면 그림을 남긴다`() {
        val ctx = RuntimeEnvironment.getApplication()
        for (playing in listOf(false, true)) {
            val root = android.view.LayoutInflater.from(ctx).inflate(R.layout.activity_main, null)
            val gauge = root.findViewById<android.widget.ImageView>(R.id.gauge)
            gauge.setImageBitmap(GaugeRenderer.wide(ctx, 960, 307, snap(37f, 62f), now, card = false))
            root.findViewById<View>(R.id.connect).visibility = View.GONE
            val claudi = root.findViewById<ClaudiView>(R.id.claudi)
            if (playing) {
                gauge.visibility = View.INVISIBLE
                claudi.visibility = View.INVISIBLE
                val board = com.kyijgnes.cooldown.dino.DinoView(ctx, best = 312, seed = 3L)
                board.game.pressJump(); board.game.releaseJump()
                repeat(900) { if (board.game.state == "run") { dinoBot(board.game); board.game.step() } }
                root.findViewById<android.widget.FrameLayout>(R.id.stage).addView(board,
                    android.widget.FrameLayout.LayoutParams(-1, -1))
            }
            root.measure(
                View.MeasureSpec.makeMeasureSpec(1080, View.MeasureSpec.EXACTLY),
                View.MeasureSpec.makeMeasureSpec(2340, View.MeasureSpec.EXACTLY),
            )
            root.layout(0, 0, 1080, 2340)
            if (!playing) claudi.stepForPreview(3)
            val bmp = Bitmap.createBitmap(1080, 2340, Bitmap.Config.ARGB_8888)
            root.draw(Canvas(bmp))
            save(bmp, if (playing) "앱첫화면_공룡점프.png" else "앱첫화면.png")
        }
    }

    /** 알아서 뛰는 공룡 — 가까운 장애물을 보면 뛴다 (PC `_bot` 과 같은 결). */
    private fun dinoBot(g: com.kyijgnes.cooldown.dino.DinoGame) {
        val S = com.kyijgnes.cooldown.dino.DinoSpec
        val ob = g.obstacles.firstOrNull { it.x + it.w > S.DINO_X } ?: return
        if (ob.kind == "bird" && ob.lift >= 42) return
        val dist = ob.x - (S.DINO_X + 38f)
        if (dist > 0 && dist < g.speed * 9 && !g.jumping) g.pressJump()
        else if (g.jumping && g.h > S.MAX_JUMP - 8f) g.releaseJump()
    }

    /** 공룡 점프 규칙 — 가만히 있으면 첫 장애물에 부딪히고, 알아서 뛰면 한참 달린다. */
    @Test
    fun `공룡 점프는 안 뛰면 부딪히고 뛰면 넘는다`() {
        val idle = com.kyijgnes.cooldown.dino.DinoGame(seed = 1L)
        idle.pressJump(); idle.releaseJump()
        repeat(60 * 20) { if (idle.state == "run") idle.step() }
        assertEquals("가만히 있으면 부딪힌다", "over", idle.state)

        val bot = com.kyijgnes.cooldown.dino.DinoGame(seed = 1L)
        bot.pressJump(); bot.releaseJump()
        repeat(60 * 40) { if (bot.state == "run") { dinoBot(bot); bot.step() } }
        assertTrue("알아서 뛰면 40초는 달린다 (${bot.runT / 60}초에 멈춤)", bot.state == "run")
        assertTrue("점수가 오른다", bot.score > 300)

        // 부딪힌 뒤 곧바로 누르면 안 받고, 잠깐 뒤에 누르면 다시 시작한다
        idle.pressJump()
        assertEquals("over", idle.state)
        repeat(com.kyijgnes.cooldown.dino.DinoSpec.OVER_WAIT) { idle.step() }
        idle.pressJump()
        assertEquals("run", idle.state)
        assertEquals(0, idle.score)
    }

    /** 마구 두드려 기절시킨다 — 뻗었으면 참. */
    private fun mash(m: Mascot, cx: Float, cy: Float, u: Float): Boolean {
        repeat(40) {
            m.press()
            m.release()
            repeat(2) { m.step(cx, cy, u, W, H) }
            if (m.debug().fainted) return true
        }
        return false
    }

    /**
     * 폰에서 공룡 점프로 들어가는 길 — **기절시키면 깨어날 때 알이 나오고, 금 둘 + 한 번 더 두드리면
     * 깨져 판을 부른다.** 판을 열 곳(`onHatch`)이 없는 클로디(꾸미기 미리보기)는 알을 안 낳고,
     * 아무도 안 깨면 알은 사라진다.
     */
    @Test
    fun `기절시키면 알이 나오고 깨면 판을 부른다`() {
        val u = WallpaperArt.mascotCell(W)
        val cx = Look.DEFAULT.mascotX * W
        val cy = Look.DEFAULT.mascotY * H

        val m = Mascot()
        var opened = 0
        m.onHatch = { opened++ }
        assertTrue("마구 두드리면 기절한다", mash(m, cx, cy, u))
        assertFalse("기절한 동안엔 알이 없다", m.hasEgg)
        repeat(m.faintFrames() + 20) { m.step(cx, cy, u, W, H) }
        assertTrue("깨어나면 알이 굴러 나온다", m.hasEgg)
        // 알은 클로디 곁 땅 위 — 한가운데는 옆으로 11칸, 위아래로는 발끝에 밑동이 닿는다
        val restY = com.kyijgnes.cooldown.wallpaper.MascotSprite.ROWS / 2f -
            com.kyijgnes.cooldown.dino.DinoSpec.EGG.size / 2f
        val onEgg = m.hitsEgg(cx, cy, u, cx + 11f * u, cy + restY * u) ||
            m.hitsEgg(cx, cy, u, cx - 11f * u, cy + restY * u)
        assertTrue("알 위를 누르면 알이 맞는다", onEgg)
        repeat(3) { m.crackEgg(); repeat(4) { m.step(cx, cy, u, W, H) } }
        assertEquals("깨지는 장면이 끝나야 판을 연다", 0, opened)
        repeat(30) { m.step(cx, cy, u, W, H) }
        assertEquals("판은 한 번만 부른다", 1, opened)
        assertTrue("클로디는 판 속으로", m.dino)
        m.unmorph()
        assertFalse("판을 접으면 클로디로", m.dino)
        assertFalse(m.hasEgg)

        val wall = Mascot()                    // 판을 열 곳이 없다 (꾸미기 미리보기)
        assertTrue(mash(wall, cx, cy, u))
        repeat(wall.faintFrames() + 20) { wall.step(cx, cy, u, W, H) }
        assertFalse("판을 열 곳이 없으면 알도 안 나온다", wall.hasEgg)

        val lone = Mascot()                    // 알을 두고 간다
        lone.onHatch = { opened++ }
        assertTrue(mash(lone, cx, cy, u))
        repeat(lone.faintFrames() + 20) { lone.step(cx, cy, u, W, H) }
        assertTrue(lone.hasEgg)
        repeat(400) { lone.step(cx, cy, u, W, H) }
        assertFalse("아무도 안 깨면 알은 사라진다", lone.hasEgg)
        assertEquals(1, opened)
    }

    @Test
    fun `초기화 시각이 지나면 0퍼센트로 본다`() {
        val past = Limit("5시간", 47f, now - 1_000L)
        val settled = past.settled(now)
        assertEquals(0f, settled.pct)
        assertNull(settled.resetAt)  // 창이 없으니 '사용 전'
        assertEquals("사용 전", settled.whenText(now))

        // 아직 안 지났으면 그대로 둔다
        val live = Limit("5시간", 47f, now + 60_000L)
        assertEquals(47f, live.settled(now).pct)
    }

    @Test
    fun `서버 응답을 읽는다`() {
        val body = """
            {"five_hour_pct":7.0,"five_hour_reset":"2026-07-29T22:19:59+00:00",
             "seven_day_pct":55.0,"seven_day_reset":"2026-08-01T00:00:00+00:00",
             "updated_at":"2026-07-29T13:00:00.000Z","stale":false,"age_min":1}
        """.trimIndent()
        val s = Snapshot.parse(body)!!
        assertEquals(7f, s.five.pct)
        assertEquals(55f, s.week.pct)
        assertEquals(false, s.stale)
        assertEquals(1785363599000L, s.five.resetAt)  // 2026-07-29T22:19:59Z

        // 필드 이름이 바뀌면 '빈 값' 이 아니라 '고장' 이다
        assertNull(Snapshot.parse("""{"fiveHourPct":7.0}"""))
    }

    @Test
    fun `주소를 정돈한다`() {
        assertEquals("https://a.vercel.app", Store.normalizeUrl("a.vercel.app"))
        assertEquals("https://a.vercel.app", Store.normalizeUrl("https://a.vercel.app/"))
        assertEquals("https://a.vercel.app", Store.normalizeUrl("https://a.vercel.app/api/cooldown"))
        assertEquals("", Store.normalizeUrl("  "))
        assertEquals("", Store.normalizeUrl("ftp://a"))
    }
}
