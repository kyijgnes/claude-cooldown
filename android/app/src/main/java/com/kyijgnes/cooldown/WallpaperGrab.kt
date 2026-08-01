package com.kyijgnes.cooldown

import android.app.WallpaperManager
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.drawable.BitmapDrawable
import java.io.File

/**
 * **폰에 지금 걸려 있는 배경화면을 한 장 떠 온다.** 앱을 처음 켠 사람이 사진을 고르기도 전에
 * 쓰던 배경 그대로 + 미터기가 보이게 하려고 있다.
 *
 * ★ **우리 라이브 배경화면이 걸리기 전에 떠 놔야 한다** — 걸린 뒤엔 '지금 배경화면'이 우리다.
 *   그래서 앱을 열 때마다(아직 안 떠 왔으면) 시도한다.
 * ★ 실패해도 조용히 넘어간다. 기기·버전에 따라 권한 없이는 못 읽는 경우가 있고,
 *   그럴 땐 상어 바다로 내려가면 그만이다.
 */
object WallpaperGrab {

    private const val NAME = "phone_wallpaper.png"

    /** 떠 놓은 파일의 주소. 아직 없으면 빈 문자열. */
    fun saved(ctx: Context): String {
        val f = File(ctx.filesDir, NAME)
        return if (f.exists() && f.length() > 0) android.net.Uri.fromFile(f).toString() else ""
    }

    /**
     * 아직 안 떠 왔으면 지금 떠 온다. 떠 온(또는 이미 있던) 주소를 준다 — 못 하면 빈 문자열.
     * 이미 파일이 있으면 **다시 안 뜬다**(우리 배경화면이 걸린 뒤에 덮어쓰면 안 되기 때문).
     */
    fun ensure(ctx: Context): String {
        saved(ctx).takeIf { it.isNotEmpty() }?.let { return it }
        val bmp = current(ctx) ?: return ""
        return try {
            File(ctx.filesDir, NAME).outputStream().use {
                bmp.compress(Bitmap.CompressFormat.PNG, 100, it)
            }
            saved(ctx)
        } catch (e: Exception) {
            ""
        }
    }

    private fun current(ctx: Context): Bitmap? = try {
        val wm = WallpaperManager.getInstance(ctx)
        // 우리 라이브 배경화면이 이미 걸려 있으면 떠 봐야 우리 그림이다
        if (wm.wallpaperInfo?.packageName == ctx.packageName) null
        else when (val d = wm.drawable) {
            null -> null
            is BitmapDrawable -> d.bitmap
            else -> Bitmap.createBitmap(
                d.intrinsicWidth.coerceAtLeast(1), d.intrinsicHeight.coerceAtLeast(1),
                Bitmap.Config.ARGB_8888,
            ).also {
                d.setBounds(0, 0, it.width, it.height)
                d.draw(Canvas(it))
            }
        }
    } catch (e: Exception) {
        null   // 권한 없음·기기 제약 — 상어 바다로 간다
    } catch (e: OutOfMemoryError) {
        null
    }
}
