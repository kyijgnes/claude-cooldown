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

/**
 * 클로드 전용 라이브 배경화면 — 홈 화면과 잠금 화면에 그대로 걸린다.
 * 그림은 WallpaperArt 가 그린다. 여기는 **언제 그릴지**만 정한다.
 *
 * 배터리 규칙: **보일 때만 그린다.** 화면이 꺼지거나 다른 앱이 앞에 오면 시스템이
 * `onVisibilityChanged(false)` 를 주고, 그 순간 루프를 세운다.
 */
class CooldownWallpaperService : WallpaperService() {

    override fun onCreateEngine(): Engine = CooldownEngine()

    private inner class CooldownEngine : Engine() {
        private val handler = Handler(Looper.getMainLooper())
        private val runner = Runnable { drawFrame() }
        private var showing = false
        private var wasLocked: Boolean? = null

        override fun onVisibilityChanged(visible: Boolean) {
            showing = visible
            if (visible) drawFrame() else handler.removeCallbacks(runner)
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
                    ctx, Canvas(bmp), Store.snapshot(ctx).settled(now), now,
                    Look.read(ctx), locked(),
                )
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
            var canvas: Canvas? = null
            try {
                canvas = surfaceHolder.lockCanvas()
                if (canvas != null) {
                    val ctx = this@CooldownWallpaperService
                    // 박자는 시계로 몬다 — 프레임을 몇 장 흘려도 상어가 느려지지 않는다
                    val now = System.currentTimeMillis()
                    WallpaperArt.render(
                        ctx, canvas, Store.snapshot(ctx).settled(now), now,
                        Look.read(ctx), locked,
                    )
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
            // 잠금이 풀리면 그림이 통째로 바뀔 수 있다(상어 얼굴) — 색도 다시 재게 한다.
            // ★ notifyColorsChanged 는 API 27 부터다(minSdk 26). 안 막으면 26 에서 죽는다 —
            //   NoSuchMethodError 는 Error 라 아래 catch(Exception) 에 안 걸린다.
            if (wasLocked != locked && Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
                wasLocked = locked
                try {
                    notifyColorsChanged()
                } catch (e: Exception) {
                    // 아직 붙기 전 — 다음 기회에
                }
            }
            handler.removeCallbacks(runner)
            if (showing) handler.postDelayed(runner, FRAME_MS)
        }
    }

    private companion object {
        /** 한 프레임 (약 16fps). 마스코트가 부드러운 선에서 배터리를 가장 덜 쓰는 값. */
        const val FRAME_MS = 60L
    }
}
