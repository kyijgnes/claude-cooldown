package com.kyijgnes.cooldown

import android.content.Context

/**
 * **배경화면 꾸미기 값은 여기 한 곳**이다 — 무엇을 그리고(모양) 어디에 얼마만큼(자리·크기).
 * 그리는 쪽은 `wallpaper/WallpaperArt`, 고르는 쪽은 `CustomizeActivity`.
 *
 * 기본값은 **꾸미기 기능을 넣기 전 화면 그대로**다(1080×2340 기준으로 맞췄다).
 * 처음 켠 사람은 달라진 걸 못 느끼고, 만지고 싶은 사람만 만진다.
 *
 * 자리는 화면 비율(0~1)로 담는다 — 폰이 달라도 같은 구도가 나온다.
 */
object Look {
    private const val FILE = "cooldown"

    // 배경 종류
    const val SEA = "sea"       // 상어 바다 (원본 테마)
    const val PLAIN = "plain"   // 바다색만
    const val PHOTO = "photo"   // 내 사진

    // 상어 얼굴
    const val CLOSED = "closed"
    const val OPEN = "open"

    // 미터기 모양
    const val BARS = "bars"       // 막대 두 줄
    const val RINGS = "rings"     // 링 둘
    const val NUMBERS = "numbers" // 숫자만
    const val NONE = "none"       // 안 보임

    private const val K_SCENE = "look_scene"
    private const val K_PHOTO = "look_photo"
    private const val K_MOUTH = "look_mouth"
    private const val K_METER = "look_meter"
    private const val K_METER_X = "look_meter_x"
    private const val K_METER_Y = "look_meter_y"
    private const val K_METER_SIZE = "look_meter_size"
    private const val K_PLATE = "look_plate"
    private const val K_ART_X = "look_art_x"
    private const val K_ART_Y = "look_art_y"
    private const val K_ART_SIZE = "look_art_size"
    private const val K_PHOTO_X = "look_photo_x"
    private const val K_PHOTO_Y = "look_photo_y"

    // 꾸미기 전 화면과 같은 자리 (1080×2340 에서 잰 값)
    const val METER_X = 0.5f
    const val METER_Y = 0.689f

    // ★ 배경 자리는 **상어 자신의 한가운데**다(물방울 판의 한가운데가 아니라).
    //   그래야 크게 키워도 상어가 제자리에서 커지고, 끌면 끈 만큼만 움직인다.
    const val ART_X = 0.5118f
    const val ART_Y = 0.4566f

    // 미터기는 화면 너비를 넘을 수 없다(넘으면 글자가 잘린다) — 기본 0.82 × 1.15 ≒ 화면의 94%
    const val METER_MIN = 0.5f
    const val METER_MAX = 1.15f

    // 상어는 잘릴 게 없으니 더 넉넉히
    const val ART_MIN = 0.5f
    const val ART_MAX = 1.7f

    private fun prefs(ctx: Context) =
        ctx.applicationContext.getSharedPreferences(FILE, Context.MODE_PRIVATE)

    // ---------------------------------------------------------------- 배경

    fun scene(ctx: Context): String = prefs(ctx).getString(K_SCENE, SEA) ?: SEA

    fun setScene(ctx: Context, v: String) {
        prefs(ctx).edit().putString(K_SCENE, v).apply()
    }

    /** 고른 사진의 content:// 주소. 비면 바다로 내려간다. */
    fun photo(ctx: Context): String = prefs(ctx).getString(K_PHOTO, "") ?: ""

    fun setPhoto(ctx: Context, uri: String) {
        prefs(ctx).edit().putString(K_PHOTO, uri).apply()
    }

    fun mouth(ctx: Context): String = prefs(ctx).getString(K_MOUTH, CLOSED) ?: CLOSED

    fun setMouth(ctx: Context, v: String) {
        prefs(ctx).edit().putString(K_MOUTH, v).apply()
    }

    // ---------------------------------------------------------------- 미터기

    fun meter(ctx: Context): String = prefs(ctx).getString(K_METER, BARS) ?: BARS

    fun setMeter(ctx: Context, v: String) {
        prefs(ctx).edit().putString(K_METER, v).apply()
    }

    fun meterX(ctx: Context): Float = prefs(ctx).getFloat(K_METER_X, METER_X)

    fun meterY(ctx: Context): Float = prefs(ctx).getFloat(K_METER_Y, METER_Y)

    fun setMeterPos(ctx: Context, x: Float, y: Float) {
        prefs(ctx).edit()
            .putFloat(K_METER_X, x.coerceIn(0f, 1f))
            .putFloat(K_METER_Y, y.coerceIn(0f, 1f))
            .apply()
    }

    fun meterSize(ctx: Context): Float = prefs(ctx).getFloat(K_METER_SIZE, 1f)

    fun setMeterSize(ctx: Context, v: Float) {
        prefs(ctx).edit().putFloat(K_METER_SIZE, v.coerceIn(METER_MIN, METER_MAX)).apply()
    }

    /**
     * 글씨 뒤 판. 안 정했으면 **사진 배경일 때만 켠 것으로 본다** —
     * 사진 위에서는 판 없이 글씨만 얹으면 읽을 수가 없다.
     */
    fun plate(ctx: Context): Boolean = when (prefs(ctx).getInt(K_PLATE, -1)) {
        1 -> true
        0 -> false
        else -> scene(ctx) == PHOTO
    }

    fun setPlate(ctx: Context, on: Boolean) {
        prefs(ctx).edit().putInt(K_PLATE, if (on) 1 else 0).apply()
    }

    // ---------------------------------------------------------------- 배경 그림 자리

    /**
     * 상어 자리와 사진 자리는 **따로 담는다** — 사진을 가운데로 끌어 놓고 상어 바다로
     * 돌아왔을 때 상어까지 가운데로 내려가 있으면 안 된다.
     */
    private fun xKey(ctx: Context) = if (scene(ctx) == PHOTO) K_PHOTO_X else K_ART_X

    private fun yKey(ctx: Context) = if (scene(ctx) == PHOTO) K_PHOTO_Y else K_ART_Y

    fun artX(ctx: Context): Float =
        prefs(ctx).getFloat(xKey(ctx), if (scene(ctx) == PHOTO) 0.5f else ART_X)

    fun artY(ctx: Context): Float =
        prefs(ctx).getFloat(yKey(ctx), if (scene(ctx) == PHOTO) 0.5f else ART_Y)

    fun setArtPos(ctx: Context, x: Float, y: Float) {
        prefs(ctx).edit()
            .putFloat(xKey(ctx), x.coerceIn(0f, 1f))
            .putFloat(yKey(ctx), y.coerceIn(0f, 1f))
            .apply()
    }

    fun artSize(ctx: Context): Float = prefs(ctx).getFloat(K_ART_SIZE, 1f)

    fun setArtSize(ctx: Context, v: Float) {
        prefs(ctx).edit().putFloat(K_ART_SIZE, v.coerceIn(ART_MIN, ART_MAX)).apply()
    }

    // ---------------------------------------------------------------- 되돌리기

    /** 처음 모양으로. 고른 사진은 지우지 않는다 — 다시 고르게 만들 일이 아니다. */
    fun reset(ctx: Context) {
        prefs(ctx).edit()
            .remove(K_SCENE).remove(K_MOUTH).remove(K_METER)
            .remove(K_METER_X).remove(K_METER_Y).remove(K_METER_SIZE)
            .remove(K_PLATE)
            .remove(K_ART_X).remove(K_ART_Y).remove(K_ART_SIZE)
            .remove(K_PHOTO_X).remove(K_PHOTO_Y)
            .apply()
    }
}
