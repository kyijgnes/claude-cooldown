package com.kyijgnes.cooldown

import android.content.Context

/**
 * **배경화면 꾸미기 값 한 벌**. 그리는 쪽은 `wallpaper/WallpaperArt`,
 * 고르는 쪽은 `CustomizeActivity`.
 *
 * ★ 값은 **`Values` 한 덩어리로 읽고 쓴다.** 꾸미기 화면은 저장을 누르기 전까지
 *   자기 손 안의 `Values` 만 고치고(미리보기도 그걸로 그린다), `저장` 에서 한 번에 쓴다.
 *   낱개 setter 를 되살리지 말 것 — 그 순간 '저장 전'이 없어진다.
 *
 * 배경은 **쓰던 배경화면(떠 온 것)·고른 사진**이 기본이고, **상어 앱이 깔려 있으면 상어**도
 * 고를 수 있다(그림은 그 앱에서 읽어 온다 — `SharkPack`). 보여 줄 게 없으면 밋밋한 바탕색.
 */
object Look {
    private const val FILE = "cooldown"

    // 배경 종류 — 상어는 **상어 앱이 깔려 있을 때만** 고를 수 있다(그림을 거기서 읽어 온다)
    const val PHOTO = "photo"   // 쓰던 배경화면, 또는 직접 고른 사진 (기본)
    const val SHARK = "shark"   // 상어 바다 (com.kyijgnes.sharkwallpaper 필요)

    // 상어는 잘릴 게 없으니 크기를 넉넉히
    const val ART_MIN = 0.5f
    const val ART_MAX = 1.7f

    // 미터기 모양
    const val BARS = "bars"       // 막대 두 줄
    const val RINGS = "rings"     // 링 둘
    const val NUMBERS = "numbers" // 숫자만
    const val NONE = "none"       // 안 보임 — 고르는 칸에서는 뺐다(배경화면에 미터기가 없을 이유가 없다)

    // 미터기는 화면 너비를 넘을 수 없다(넘으면 글자가 잘린다) — 기본 0.82 × 1.15 ≒ 화면의 94%
    const val METER_MIN = 0.5f
    const val METER_MAX = 1.15f

    /** '글씨 뒤 판'을 아직 안 정한 상태. */
    private const val UNSET = -1

    /**
     * @param plate  -1 안 정함 / 0 끔 / 1 켬
     * @param photoX 사진 자리는 **잘려 나간 쪽을 어디까지 보여 줄지**(0~1).
     */
    data class Values(
        val scene: String = PHOTO,
        val photo: String = "",
        val seaX: Float = 0.5118f,      // 상어 자리는 **상어 자신의 한가운데**다
        val seaY: Float = 0.4566f,
        val seaSize: Float = 1f,
        val mascot: Boolean = true,     // 배경화면에 사는 클로디 (눌러서 놀 수 있다)
        // 기본 자리는 **미터기 판 안쪽 오른쪽 위** — 제목 줄 옆이 비어 있다
        val mascotX: Float = 0.80f,
        val mascotY: Float = 0.612f,
        val meter: String = BARS,
        val meterX: Float = 0.5f,
        val meterY: Float = 0.689f,     // 꾸미기 전 화면과 같은 자리 (1080×2340 에서 잰 값)
        val meterSize: Float = 1f,
        val plate: Int = UNSET,
        val photoX: Float = 0.5f,
        val photoY: Float = 0.5f,
    ) {
        /** 안 정했으면 **켠 것으로 본다** — 사진 위 글씨는 판 없이는 못 읽는다. */
        val plateOn: Boolean get() = if (plate == UNSET) scene != SHARK else plate == 1

        val bgX: Float get() = if (scene == SHARK) seaX else photoX
        val bgY: Float get() = if (scene == SHARK) seaY else photoY

        /** ★ 사진 자리와 상어 자리는 **따로 담는다** — 사진을 옮겨 놓고 상어로 돌아왔을 때
         *  상어까지 따라 움직이면 안 된다. */
        fun withBg(x: Float, y: Float): Values {
            val cx = x.coerceIn(0f, 1f)
            val cy = y.coerceIn(0f, 1f)
            return if (scene == SHARK) copy(seaX = cx, seaY = cy) else copy(photoX = cx, photoY = cy)
        }

        fun withMeterPos(x: Float, y: Float) =
            copy(meterX = x.coerceIn(0f, 1f), meterY = y.coerceIn(0f, 1f))

        fun withMascotPos(x: Float, y: Float) =
            copy(mascotX = x.coerceIn(0f, 1f), mascotY = y.coerceIn(0f, 1f))

        fun withPlate(on: Boolean) = copy(plate = if (on) 1 else 0)
    }

    /** 처음 모양. `CustomizeActivity` 의 `처음 모양으로` 가 이걸로 되돌린다(고른 사진은 남긴다). */
    val DEFAULT = Values()

    private fun prefs(ctx: Context) =
        ctx.applicationContext.getSharedPreferences(FILE, Context.MODE_PRIVATE)

    fun read(ctx: Context): Values {
        val p = prefs(ctx)
        val d = DEFAULT
        return Values(
            scene = p.getString("look_scene", d.scene) ?: d.scene,
            photo = p.getString("look_photo", d.photo) ?: d.photo,
            seaX = p.getFloat("look_art_x", d.seaX),
            seaY = p.getFloat("look_art_y", d.seaY),
            seaSize = p.getFloat("look_art_size", d.seaSize),
            mascot = p.getBoolean("look_mascot", d.mascot),
            // 클로디 첫 자리가 화면 한가운데였는데 **미터기 판 안쪽**으로 옮겼다 —
            // 옛 자리 그대로인 사람은 새 자리로 올린다(직접 옮긴 사람 것은 안 건드린다).
            mascotX = p.getFloat("look_mascot_x", d.mascotX).let { if (isOldSpot(p)) d.mascotX else it },
            mascotY = p.getFloat("look_mascot_y", d.mascotY).let { if (isOldSpot(p)) d.mascotY else it },
            // '없음' 은 고르는 칸에서 뺐다 — 예전에 그걸로 저장해 둔 사람은 막대로 올린다
            meter = (p.getString("look_meter", d.meter) ?: d.meter).let {
                if (it == NONE) BARS else it
            },
            meterX = p.getFloat("look_meter_x", d.meterX),
            meterY = p.getFloat("look_meter_y", d.meterY),
            meterSize = p.getFloat("look_meter_size", d.meterSize),
            plate = p.getInt("look_plate", d.plate),
            photoX = p.getFloat("look_photo_x", d.photoX),
            photoY = p.getFloat("look_photo_y", d.photoY),
        )
    }

    /** 클로디를 처음 넣었을 때의 자리(화면 한가운데) 그대로인가. */
    private fun isOldSpot(p: android.content.SharedPreferences): Boolean =
        p.getFloat("look_mascot_x", 0.5f) == 0.5f && p.getFloat("look_mascot_y", 0.42f) == 0.42f

    fun write(ctx: Context, v: Values) {
        prefs(ctx).edit()
            .putString("look_scene", v.scene)
            .putString("look_photo", v.photo)
            .putFloat("look_art_x", v.seaX)
            .putFloat("look_art_y", v.seaY)
            .putFloat("look_art_size", v.seaSize)
            .putBoolean("look_mascot", v.mascot)
            .putFloat("look_mascot_x", v.mascotX)
            .putFloat("look_mascot_y", v.mascotY)
            .putString("look_meter", v.meter)
            .putFloat("look_meter_x", v.meterX)
            .putFloat("look_meter_y", v.meterY)
            .putFloat("look_meter_size", v.meterSize)
            .putInt("look_plate", v.plate)
            .putFloat("look_photo_x", v.photoX)
            .putFloat("look_photo_y", v.photoY)
            .apply()
    }
}
