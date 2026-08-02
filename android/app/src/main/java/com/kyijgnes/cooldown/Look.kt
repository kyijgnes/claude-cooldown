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
 * 기본은 **쓰던 배경화면 + 미터기**다 — 사람마다 배경이 다르니 그걸 그대로 두고
 * 미터기만 얹는다. 상어는 골라서 쓴다.
 */
object Look {
    private const val FILE = "cooldown"

    // 배경 종류
    const val PHOTO = "photo"   // 쓰던 배경화면, 또는 직접 고른 사진 (기본)
    const val SEA = "sea"       // 상어

    // 미터기 모양
    const val BARS = "bars"       // 막대 두 줄
    const val RINGS = "rings"     // 링 둘
    const val NUMBERS = "numbers" // 숫자만
    const val NONE = "none"       // 안 보임

    // 미터기는 화면 너비를 넘을 수 없다(넘으면 글자가 잘린다) — 기본 0.82 × 1.15 ≒ 화면의 94%
    const val METER_MIN = 0.5f
    const val METER_MAX = 1.15f

    // 상어는 잘릴 게 없으니 더 넉넉히
    const val ART_MIN = 0.5f
    const val ART_MAX = 1.7f

    /** '글씨 뒤 판'을 아직 안 정한 상태. */
    private const val UNSET = -1

    /**
     * @param plate  -1 안 정함 / 0 끔 / 1 켬
     * @param seaX   상어 자리는 **상어 자신의 한가운데**다(물방울 판의 한가운데가 아니라).
     *               판 기준으로 잡으면 크게 키웠을 때 상어만 화면 밖으로 밀려난다.
     * @param photoX 사진 자리는 **잘려 나간 쪽을 어디까지 보여 줄지**(0~1). 상어와 따로 담는다 —
     *               사진을 옮겨 놓고 상어로 돌아왔을 때 상어까지 따라 움직이면 안 된다.
     */
    data class Values(
        val scene: String = PHOTO,
        val photo: String = "",
        val meter: String = BARS,
        val meterX: Float = 0.5f,
        val meterY: Float = 0.689f,     // 꾸미기 전 화면과 같은 자리 (1080×2340 에서 잰 값)
        val meterSize: Float = 1f,
        val plate: Int = UNSET,
        val seaX: Float = 0.5118f,
        val seaY: Float = 0.4566f,
        val seaSize: Float = 1f,
        val photoX: Float = 0.5f,
        val photoY: Float = 0.5f,
    ) {
        /** 안 정했으면 **사진 배경일 때만 켠 것으로 본다** — 사진 위 글씨는 판 없이는 못 읽는다. */
        val plateOn: Boolean get() = if (plate == UNSET) scene == PHOTO else plate == 1

        val bgX: Float get() = if (scene == PHOTO) photoX else seaX
        val bgY: Float get() = if (scene == PHOTO) photoY else seaY

        fun withBg(x: Float, y: Float): Values {
            val cx = x.coerceIn(0f, 1f)
            val cy = y.coerceIn(0f, 1f)
            return if (scene == PHOTO) copy(photoX = cx, photoY = cy) else copy(seaX = cx, seaY = cy)
        }

        fun withMeterPos(x: Float, y: Float) =
            copy(meterX = x.coerceIn(0f, 1f), meterY = y.coerceIn(0f, 1f))

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
            meter = p.getString("look_meter", d.meter) ?: d.meter,
            meterX = p.getFloat("look_meter_x", d.meterX),
            meterY = p.getFloat("look_meter_y", d.meterY),
            meterSize = p.getFloat("look_meter_size", d.meterSize),
            plate = p.getInt("look_plate", d.plate),
            seaX = p.getFloat("look_art_x", d.seaX),
            seaY = p.getFloat("look_art_y", d.seaY),
            seaSize = p.getFloat("look_art_size", d.seaSize),
            photoX = p.getFloat("look_photo_x", d.photoX),
            photoY = p.getFloat("look_photo_y", d.photoY),
        )
    }

    fun write(ctx: Context, v: Values) {
        prefs(ctx).edit()
            .putString("look_scene", v.scene)
            .putString("look_photo", v.photo)
            .putString("look_meter", v.meter)
            .putFloat("look_meter_x", v.meterX)
            .putFloat("look_meter_y", v.meterY)
            .putFloat("look_meter_size", v.meterSize)
            .putInt("look_plate", v.plate)
            .putFloat("look_art_x", v.seaX)
            .putFloat("look_art_y", v.seaY)
            .putFloat("look_art_size", v.seaSize)
            .putFloat("look_photo_x", v.photoX)
            .putFloat("look_photo_y", v.photoY)
            .apply()
    }
}
