package com.kyijgnes.cooldown.wallpaper

import android.graphics.Canvas
import android.os.Handler
import android.os.Looper
import android.service.wallpaper.WallpaperService
import android.view.SurfaceHolder
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

        private fun drawFrame() {
            var canvas: Canvas? = null
            try {
                canvas = surfaceHolder.lockCanvas()
                if (canvas != null) {
                    val ctx = this@CooldownWallpaperService
                    // 박자는 시계로 몬다 — 프레임을 몇 장 흘려도 상어가 느려지지 않는다
                    val now = System.currentTimeMillis()
                    WallpaperArt.render(ctx, canvas, Store.snapshot(ctx).settled(now), now)
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
            if (showing) handler.postDelayed(runner, FRAME_MS)
        }
    }

    private companion object {
        /** 한 프레임 (약 16fps). 마스코트가 부드러운 선에서 배터리를 가장 덜 쓰는 값. */
        const val FRAME_MS = 60L
    }
}
