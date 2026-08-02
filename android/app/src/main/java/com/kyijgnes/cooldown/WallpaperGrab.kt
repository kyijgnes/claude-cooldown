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
 * 앱을 열 때마다 시도한다:
 *   · 우리 게 **안 걸려 있으면** 지금 배경화면을 그대로 뜬다(사용자가 바꾸면 따라간다).
 *   · 우리 게 **걸려 있으면** '지금 배경화면'은 우리라서, **잠금화면 쪽**을 본다 —
 *     홈에만 걸어 둔 사람은 거기 자기 그림이 남아 있다. 그것도 없으면 떠 둔 걸 그대로 쓴다.
 * ★ 실패해도 조용히 넘어간다. 기기·버전에 따라 권한 없이는 못 읽는 경우가 있고,
 *   그럴 땐 기본 바탕으로 내려가면 그만이다.
 */
object WallpaperGrab {

    private const val NAME = "phone_wallpaper.png"
    private const val TAG = "cooldown-wallpaper"

    /**
     * 잠금화면에 걸려 있는 그림. **우리 배경화면이 홈에 걸린 뒤에도** 사용자의 그림을
     * 볼 수 있는 유일한 창이다. 잠금화면까지 우리 것이거나 따로 안 걸어 뒀으면 null.
     */
    @android.annotation.SuppressLint("MissingPermission")
    private fun lockWallpaper(ctx: Context, wm: WallpaperManager): Bitmap? = try {
        wm.getWallpaperFile(WallpaperManager.FLAG_LOCK)?.use { pfd ->
            android.graphics.BitmapFactory.decodeFileDescriptor(pfd.fileDescriptor)
        }
    } catch (e: Exception) {
        android.util.Log.w(TAG, "잠금화면 배경도 못 읽었다: $e")
        null
    } catch (e: OutOfMemoryError) {
        null
    }

    /** 떠 놓은 그림. 되돌리기(해제)가 이걸 다시 배경화면으로 건다. 없으면 null. */
    fun bitmap(ctx: Context): android.graphics.Bitmap? {
        val f = File(ctx.filesDir, NAME)
        if (!f.exists() || f.length() == 0L) return null
        return try {
            android.graphics.BitmapFactory.decodeFile(f.absolutePath)
        } catch (e: Exception) {
            null
        } catch (e: OutOfMemoryError) {
            null
        }
    }

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
        // ★ 우리 라이브 배경화면이 이미 걸려 있으면 '지금 배경화면'은 우리다 — 대신
        //   **잠금화면 쪽**을 본다. 홈에만 걸어 둔 사람은 잠금화면에 자기 그림이 그대로
        //   남아 있어서, 그걸로 배경을 갱신할 수 있다(그러면 껐다 켜는 수고가 없다).
        if (wm.wallpaperInfo?.packageName == ctx.packageName) lockWallpaper(ctx, wm)
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
        // 권한 없음·기기 제약 — 기본 바탕으로 간다. 왜 못 떴는지는 로그에만 남긴다(화면엔 안 띄운다)
        android.util.Log.w(TAG, "배경화면을 못 떠 왔다: $e")
        null
    } catch (e: OutOfMemoryError) {
        android.util.Log.w(TAG, "배경화면이 너무 크다")
        null
    }
}
