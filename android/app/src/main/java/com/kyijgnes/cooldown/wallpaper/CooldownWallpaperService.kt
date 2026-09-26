package com.kyijgnes.cooldown.wallpaper

import android.app.KeyguardManager
import android.app.WallpaperColors
import android.graphics.Bitmap
import android.graphics.Canvas
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.service.wallpaper.WallpaperService
import android.view.SurfaceHolder
import com.kyijgnes.cooldown.Look
import com.kyijgnes.cooldown.Store
import com.kyijgnes.cooldown.dino.DinoBoard
import com.kyijgnes.cooldown.dino.DinoHost
import com.kyijgnes.cooldown.dino.DinoOverlayActivity
import com.kyijgnes.cooldown.dino.DinoSpec

/**
 * 클로드 전용 라이브 배경화면 — 홈 화면과 잠금 화면에 그대로 걸린다.
 * 그림은 WallpaperArt 가 그린다. 여기는 **언제 그릴지**만 정한다.
 *
 * 배터리 규칙: **보일 때만 그린다.** 화면이 꺼지거나 다른 앱이 앞에 오면 시스템이
 * `onVisibilityChanged(false)` 를 주고, 그 순간 루프를 세운다.
 *
 * **공룡 점프도 여기서 들어간다**(2026-09-26) — 앱을 안 열고 홈 화면에서 바로. 클로디를 기절시키면
 * 1초 뒤 알이 굴러 나오고, 톡톡 깨면 미터기 자리가 판이 된다(`WallpaperArt.boardTop`).
 * ★ **판은 배경화면이 아니라 투명한 화면(`DinoOverlayActivity`)이 그린다.** 배경화면은 런처가 길게 누르기를
 *   채 가서 점프를 조금만 길게 눌러도 홈 편집 메뉴가 떴다. 그동안 배경화면은 클로디를 숨기고, 판이 다
 *   열리면(`DinoHost.boardSettled`) 미터기도 숨긴다. 투명한 화면이 못 뜨면(폰이 막으면) `OVERLAY_WAIT_MS`
 *   뒤에 **배경화면이 직접 판을 그린다**(그때는 홈 화면 빈 곳을 눌러 뛴다, 60fps `GAME_FRAME_MS`).
 */
class CooldownWallpaperService : WallpaperService() {

    override fun onCreateEngine(): Engine = CooldownEngine()

    private inner class CooldownEngine : Engine() {
        private val handler = Handler(Looper.getMainLooper())
        private val runner = Runnable { drawFrame() }
        private var showing = false

        /** 클로디 — 이 엔진 하나가 상태를 들고 있다(튀는 속도·표정). */
        private val mascot = Mascot()
        private var lastW = 0f
        private var lastH = 0f

        /** 공룡 점프 판 — 알이 깨진 동안만 있다. 클로디는 그동안 판 속에 있다. */
        private var board: DinoBoard? = null
        private var hiddenAt = 0L

        override fun onCreate(holder: SurfaceHolder?) {
            super.onCreate(holder)
            // ★ 이걸 켜야 런처가 홈 화면 터치를 흘려 준다 — 클로디를 누를 수 있게 된다.
            //   아이콘·위젯 위를 누르면 그쪽이 먹으므로 우리에게는 안 온다.
            setTouchEventsEnabled(true)
            mascot.onHatch = { askOverlay() }  // 기절 → 알 → 깨면 여기
        }

        /** 투명 판을 부른 때 (0 이면 안 부름) · 그때 넘긴 알 자리 — 못 뜨면 이걸로 배경화면에서 논다. */
        private var overlayAsked = 0L
        private var hatchFrom: FloatArray? = null

        /** 알이 깨졌다 — 투명한 판을 부른다. 미터기 자리(판 위끝)와 공룡이 선 자리를 화면 좌표로 넘긴다. */
        private fun askOverlay() {
            val ctx = this@CooldownWallpaperService
            val from = mascot.hatchPoint()
            hatchFrom = from
            val top = WallpaperArt.boardTop(lastW, lastH, Look.read(ctx), DinoSpec.H * lastW / DinoSpec.W)
            DinoHost.onClosed = { handler.post { mascot.unmorph(); if (showing) drawFrame() } }
            overlayAsked = android.os.SystemClock.elapsedRealtime()
            try {
                startActivity(
                    android.content.Intent(ctx, DinoOverlayActivity::class.java)
                        .addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK or
                            android.content.Intent.FLAG_ACTIVITY_NO_ANIMATION)
                        .putExtra(DinoHost.EXTRA_SOURCE, "wallpaper")
                        .putExtra(DinoHost.EXTRA_FROM, from)
                        .putExtra(DinoHost.EXTRA_TOP, top),
                )
            } catch (e: Exception) {
                android.util.Log.w("cooldown-wallpaper", "투명 판을 못 띄웠다 — 배경화면에서 논다", e)
                overlayAsked = 0L
                startGame()
            }
        }

        /** 배경화면이 직접 판을 그린다 — 투명 판이 못 떴을 때만. */
        private fun startGame() {
            if (board != null) return
            val ctx = this@CooldownWallpaperService
            val prefs = ctx.getSharedPreferences(DINO_PREFS, MODE_PRIVATE)
            val b = DinoBoard(ctx, prefs.getInt(DINO_BEST, 0))
            b.onBest = { best -> prefs.edit().putInt(DINO_BEST, best).apply() }
            b.onExit = { handler.post { endGame() } }   // 그리는 중에 판을 치우지 않게 한 박자 뒤로
            hatchFrom?.let { b.startIntro(it[0], it[1], it[2]) }
            board = b
            b.resume()
        }

        /** 판을 접는다 — 클로디가 펑 하고 돌아온다. */
        private fun endGame() {
            val b = board ?: return
            board = null
            b.pause()
            mascot.unmorph()
        }

        /** 클로디를 짚고 있는 중인가 — 누른 채로 있으면 납작해지고 떼면 튕겨 오른다. */
        private var holding = false

        /**
         * 빈 곳을 눌렀을 때만 온다(아이콘·위젯 위는 그쪽이 먹는다).
         * ★ **반응은 누르는 순간 난다**(떼기를 기다리지 않는다) — 박자 콤보가 손끝과
         *   맞아야 하고, 런처가 길게 누르기를 자기 메뉴로 채 가면 UP 이 아예 안 오기 때문.
         *   그대로 누르고 있으면 눌려서 납작해지고, 떼면 눌린 만큼 튕겨 오른다.
         *   UP 이 안 오는 경우는 `onVisibilityChanged(false)` 에서 물린다(아래).
         */
        override fun onTouchEvent(event: android.view.MotionEvent) {
            if (lastW <= 0f) return
            val b = board
            if (b != null) {                   // 공룡 점프 중 — 빈 곳 어디를 눌러도 뛴다 (✕ 는 닫기)
                when (event.actionMasked) {
                    android.view.MotionEvent.ACTION_DOWN -> b.down(event.x, event.y)
                    android.view.MotionEvent.ACTION_UP, android.view.MotionEvent.ACTION_CANCEL -> b.up()
                }
                return
            }
            when (event.actionMasked) {
                android.view.MotionEvent.ACTION_DOWN -> {
                    val look = Look.read(this@CooldownWallpaperService)
                    // 알이 있으면 알부터 — 클로디 곁이라 누르는 자리가 겹칠 수 있다
                    if (WallpaperArt.hitsEgg(lastW, lastH, look, mascot, event.x, event.y)) {
                        mascot.crackEgg()
                        return
                    }
                    holding = WallpaperArt.hitsMascot(lastW, lastH, look, mascot, event.x, event.y)
                    if (holding) mascot.press()
                }

                android.view.MotionEvent.ACTION_UP -> if (holding) {
                    holding = false
                    mascot.release()
                    if (!showing) drawFrame()
                }

                android.view.MotionEvent.ACTION_CANCEL -> if (holding) {
                    holding = false
                    mascot.cancel()
                }
            }
        }

        override fun onVisibilityChanged(visible: Boolean) {
            showing = visible
            if (visible) {
                val b = board
                if (DinoHost.overlayUp) {
                    // 투명 판이 떠 있다 — 클로디는 판 속이니 그대로 둔다 (판을 닫을 때 돌아온다)
                } else if (b == null) {
                    mascot.rest()      // 오래 안 보다 왔다 — 지친 것도 하던 딴짓도 잊는다
                } else if (System.currentTimeMillis() - hiddenAt > GAME_AWAY_MS) {
                    endGame()          // 한참 딴 데 있다 왔다 — 판은 접는다
                    mascot.rest()
                } else {
                    b.resume()         // 잠깐 다녀왔다 — 멈춘 판 그대로 (눌러서 이어 하기)
                }
                drawFrame()
            } else {
                hiddenAt = System.currentTimeMillis()
                board?.pause()
                if (holding) { holding = false; mascot.cancel() }   // 런처 메뉴가 채 갔다
                handler.removeCallbacks(runner)
            }
        }

        override fun onSurfaceChanged(h: SurfaceHolder?, format: Int, w: Int, height: Int) {
            drawFrame()
        }

        override fun onSurfaceDestroyed(holder: SurfaceHolder?) {
            showing = false
            handler.removeCallbacks(runner)
        }

        override fun onDestroy() {
            handler.removeCallbacks(runner)
            super.onDestroy()
        }

        /**
         * ★ **시스템에게 "나 밝은 배경이다" 를 알려 주는 자리.** 이걸 안 주면 상태바 시계·
         * 아이콘이 흰 글씨로 남아 밝은 바다 위에서 통째로 안 보인다(우리 숫자 아이콘도 같이).
         * 실제 화면을 작게 그려 `fromBitmap` 에 넘기면 밝기 판단은 시스템이 알아서 한다 —
         * 사진 배경까지 저절로 맞는다.
         */
        override fun onComputeColors(): WallpaperColors? {
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O_MR1) return null
            return try {
                val ctx = this@CooldownWallpaperService
                val w = 96
                val h = (w * 2.2f).toInt()
                val bmp = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888)
                val now = System.currentTimeMillis()
                WallpaperArt.render(
                    ctx, Canvas(bmp), Store.snapshot(ctx).settled(now), now, Look.read(ctx),
                    null, locked(),
                )   // 색만 재는 자리라 클로디는 안 그린다(상태가 두 배로 흐른다)
                WallpaperColors.fromBitmap(bmp)
            } catch (e: Exception) {
                null
            }
        }

        /** 잠금화면인가 — 상어가 입을 다물지 벌릴지가 여기서 갈린다. */
        private fun locked(): Boolean =
            getSystemService(KeyguardManager::class.java)?.isKeyguardLocked ?: true

        private fun drawFrame() {
            val locked = locked()
            if (locked) endGame()              // 잠금화면에서는 못 논다 (누르는 것이 잠금화면으로 간다)
            // 투명 판을 불렀는데 안 떴다(폰이 막았다) — 배경화면이 직접 판을 그린다
            if (overlayAsked > 0L) {
                if (DinoHost.overlayUp) {
                    overlayAsked = 0L
                } else if (android.os.SystemClock.elapsedRealtime() - overlayAsked > OVERLAY_WAIT_MS) {
                    overlayAsked = 0L
                    DinoHost.onClosed = null
                    startGame()
                }
            }
            var canvas: Canvas? = null
            try {
                canvas = surfaceHolder.lockCanvas()
                if (canvas != null) {
                    val ctx = this@CooldownWallpaperService
                    val now = System.currentTimeMillis()
                    lastW = canvas.width.toFloat()
                    lastH = canvas.height.toFloat()
                    val look = Look.read(ctx)
                    val b = board
                    val overlay = DinoHost.overlayUp
                    // 판이 떠 있으면 클로디는 판 속에 있다 — 안 그리고 안 굴린다. 미터기는 판이 다 열리면
                    // (들어오는 장면이 끝나면) 숨긴다 — 그 자리가 판이다
                    val settled = if (b != null) !b.inIntro else overlay && DinoHost.boardSettled
                    WallpaperArt.render(
                        ctx, canvas, Store.snapshot(ctx).settled(now), now, look,
                        if (b == null && !overlay) mascot else null, locked, meter = !settled,
                    )
                    if (b != null) {
                        b.advance()
                        b.paint(canvas, WallpaperArt.boardTop(lastW, lastH, look, b.heightFor(lastW)), lastW)
                    }
                }
            } catch (e: Exception) {
                // 표면이 사라지는 중 — 다음 프레임에 다시 온다
            } finally {
                if (canvas != null) {
                    try {
                        surfaceHolder.unlockCanvasAndPost(canvas)
                    } catch (e: Exception) {
                        // 이미 놓인 표면
                    }
                }
            }
            handler.removeCallbacks(runner)
            if (showing) handler.postDelayed(runner, if (board != null) GAME_FRAME_MS else FRAME_MS)
        }
    }

    private companion object {
        /**
         * 한 프레임 (약 30fps). 16fps 로는 **클로디가 튀는 게 느릿느릿 보였다** —
         * 물리는 프레임마다 도므로 프레임이 빠를수록 같은 높이를 더 빨리 오간다.
         * **보일 때만 돈다**(`onVisibilityChanged`)라 홈 화면을 보고 있을 때만 쓴다.
         */
        const val FRAME_MS = 33L

        /** 공룡 점프 중에만 60fps — 판은 1/60초 걸음이라 30fps 로 그리면 두 걸음씩 뛰어 끊겨 보인다. */
        const val GAME_FRAME_MS = 16L

        /** 투명 판을 부르고 이만큼 안에 안 뜨면 배경화면이 직접 판을 그린다. */
        const val OVERLAY_WAIT_MS = 1_500L

        /** 이보다 오래 딴 데 있다 오면(앱을 열었다 오는 등) 멈춘 판을 접고 클로디로 돌아온다. */
        const val GAME_AWAY_MS = 30_000L

        const val DINO_PREFS = "dino"   // 앱 첫 화면과 같은 최고 기록
        const val DINO_BEST = "best"
    }
}
