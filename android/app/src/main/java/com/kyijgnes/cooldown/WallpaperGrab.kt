package com.kyijgnes.cooldown

import android.app.WallpaperManager
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.drawable.BitmapDrawable
import java.io.File

/**
 * **폰에 지금 걸려 있는 배경화면을 한 장 떠 온다.** 사람마다 배경화면이 다르니, 아무것도
 * 안 고른 사람에게는 **쓰던 배경 그대로 + 미터기**가 보여야 한다.
 *
 * ★ **우리 라이브 배경화면이 걸리기 전에 떠 놔야 한다** — 걸린 뒤엔 '지금 배경화면'이 우리다.
 *   그래서 앱을 열 때마다 시도하고, **우리 게 안 걸려 있으면 그때마다 새로 뜬다**
 *   (사용자가 배경을 바꾸면 그걸 따라가야 한다). 우리 게 걸려 있으면 떠 온 걸 그대로 쓴다.
 * ★ 실패해도 조용히 넘어간다. 기기·버전에 따라 권한 없이는 못 읽는 경우가 있고,
 *   그럴 땐 상어로 내려가면 그만이다.
 */
object WallpaperGrab {

    private const val NAME = "phone_wallpaper.png"
    private const val TAG = "cooldown-wallpaper"

    /** 떠 놓은 파일의 주소. 아직 없으면 빈 문자열. */
    fun saved(ctx: Context): String {
        val f = File(ctx.filesDir, NAME)
        return if (f.exists() && f.length() > 0) android.net.Uri.fromFile(f).toString() else ""
    }

    /**
     * 지금 배경화면을 떠 둔다. 떠 온(또는 이미 있던) 주소를 준다 — 아무것도 없으면 빈 문자열.
     *
     * **우리 배경화면이 안 걸려 있으면 그때마다 새로 뜬다** — 사용자가 배경을 바꾸면
     * 그 배경을 따라가야 하기 때문. 우리 게 걸려 있으면 `current` 가 null 이라 덮어쓸 일이 없다.
     * 주소(파일 이름)는 늘 같으므로, 새로 떴을 때는 부르는 쪽이 그림 캐시를 비워야 한다.
     */
    fun ensure(ctx: Context): String {
        val bmp = current(ctx) ?: return saved(ctx)
        return try {
            File(ctx.filesDir, NAME).outputStream().use {
                bmp.compress(Bitmap.CompressFormat.PNG, 100, it)
            }
            android.util.Log.i(TAG, "배경화면을 떠 왔다 ${bmp.width}x${bmp.height}")
            saved(ctx)
        } catch (e: Exception) {
            android.util.Log.w(TAG, "떠 온 배경화면을 저장 못 했다: $e")
            saved(ctx)
        }
    }

    /**
     * `getDrawable()` 은 문서상 `MANAGE_EXTERNAL_STORAGE`/`READ_WALLPAPER_INTERNAL` 을 요구한다고
     * 표시돼 있지만 **보통 앱도 홈 배경화면은 읽힌다**(S20 Ultra / Android 13 실측 — 실제로
     * 폰에 걸려 있던 사진을 그대로 떠 왔다). 못 읽는 기기에서는 SecurityException 이 날 뿐이고
     * 아래에서 잡아 null 로 내려가므로, 권한을 새로 달라고 하지 않는다.
     */
    @android.annotation.SuppressLint("MissingPermission")
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
        // 권한 없음·기기 제약 — 상어로 간다. 왜 못 떴는지는 로그에만 남긴다(화면엔 안 띄운다)
        android.util.Log.w(TAG, "배경화면을 못 떠 왔다: $e")
        null
    } catch (e: OutOfMemoryError) {
        android.util.Log.w(TAG, "배경화면이 너무 크다")
        null
    }
}
