package com.kyijgnes.cooldown.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Canvas
import com.kyijgnes.cooldown.Palette
import com.kyijgnes.cooldown.dino.DinoOverlayActivity
import com.kyijgnes.cooldown.dino.DinoSpec
import com.kyijgnes.cooldown.wallpaper.Mascot
import com.kyijgnes.cooldown.wallpaper.MascotSprite

/**
 * 넓은 홈 위젯 오른쪽 끝에 사는 클로디 — **배경화면 대신 위젯을 두는 사람도 공룡 점프를 하게**(2026-09-26).
 *
 * 위젯은 그림 한 장이라 움직이지도, 손가락을 따라가지도 못한다. 누를 때마다 한 장씩 다시 그려
 * 배경화면과 **같은 길**을 흉내 낸다:
 *  1. 클로디를 톡톡 — `FAINT_TAPS`(5)번을 `FAINT_WINDOW_MS`(3초) 안에 누르면 뻗고 곁에 알이 나온다.
 *  2. 알을 톡톡 — 금이 번지고(`DinoSpec.EGG_CRACKS` 두 단계) 한 번 더 누르면 깨진다.
 *  3. 깨지는 그 누르기는 방송이 아니라 **바로 화면을 여는 PendingIntent**다(`tapIntent`). 방송을 받고
 *     나서 화면을 열면 안드로이드 10+ 의 백그라운드 실행 제한에 걸릴 수 있어서. 열리는 것은 홈 화면
 *     위에 투명하게 뜨는 `DinoOverlayActivity` — 판이 **위젯이 있던 줄**에 깔려 위젯이 판이 된 것처럼 보인다.
 * 상태는 위젯마다(`id`) 따로 저장한다. 알은 한참(`EGG_LIFE_MS`) 안 깨면 다음 갱신 때 사라진다.
 * 작은(1×1) 위젯은 링이 칸을 다 써서 클로디를 안 둔다.
 */
object WidgetClaudi {
    const val ACTION_TAP = "com.kyijgnes.cooldown.CLAUDI_TAP"
    const val FAINT_TAPS = 5
    const val FAINT_WINDOW_MS = 3_000L
    const val EGG_LIFE_MS = 10 * 60_000L
    const val POKE_MS = 4_000L
    private const val PREFS = "widget_claudi"

    /** `idle` 평소 · `poke` 막 찔림 · `egg` 뻗은 채 곁에 알(금 `cracks`) · `away` 판 속에 들어가 있음. */
    data class State(val stage: String, val cracks: Int)

    private fun prefs(ctx: Context) = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun read(ctx: Context, id: Int, now: Long = System.currentTimeMillis()): State {
        val p = prefs(ctx)
        val stage = p.getString("stage_$id", "idle") ?: "idle"
        val at = p.getLong("at_$id", 0L)
        return when {
            stage == "egg" && now - at > EGG_LIFE_MS -> State("idle", 0)   // 아무도 안 깼다
            stage == "poke" && now - at > POKE_MS -> State("idle", 0)
            else -> State(stage, p.getInt("cracks_$id", 0))
        }
    }

    private fun write(ctx: Context, id: Int, stage: String, cracks: Int, now: Long) {
        prefs(ctx).edit().putString("stage_$id", stage).putInt("cracks_$id", cracks)
            .putLong("at_$id", now).apply()
    }

    /** 클로디 칸을 눌렀다 (깨지는 마지막 누르기는 여기로 안 온다 — 바로 판이 열린다). */
    fun tap(ctx: Context, id: Int, now: Long = System.currentTimeMillis()) {
        val s = read(ctx, id, now)
        if (s.stage == "egg") {
            write(ctx, id, "egg", minOf(s.cracks + 1, DinoSpec.EGG_CRACKS.size), now)
            return
        }
        val p = prefs(ctx)
        val taps = (p.getString("taps_$id", "") ?: "").split(',').mapNotNull { it.toLongOrNull() }
            .filter { now - it <= FAINT_WINDOW_MS } + now
        if (taps.size >= FAINT_TAPS) {       // 뻗었다 — 곁에 알
            p.edit().remove("taps_$id").apply()
            write(ctx, id, "egg", 0, now)
        } else {
            p.edit().putString("taps_$id", taps.joinToString(",")).apply()
            write(ctx, id, "poke", 0, now)
        }
    }

    /** 판이 열리고 닫힐 때 — 모든 넓은 위젯의 클로디를 한꺼번에 (판 속으로 / 평소로). */
    fun setAll(ctx: Context, stage: String) {
        val mgr = AppWidgetManager.getInstance(ctx)
        val ids = try {
            mgr.getAppWidgetIds(ComponentName(ctx, WideWidget::class.java))
        } catch (e: Exception) {
            IntArray(0)
        }
        val now = System.currentTimeMillis()
        for (id in ids) write(ctx, id, stage, 0, now)
        val w = WideWidget()
        for (id in ids) w.draw(ctx, mgr, id)
    }

    /** 이 칸을 누르면 무엇이 일어나나 — 마지막 금까지 갔으면 **판을 바로 연다**, 아니면 방송. */
    fun tapIntent(ctx: Context, id: Int, s: State): PendingIntent =
        if (s.stage == "egg" && s.cracks >= DinoSpec.EGG_CRACKS.size) {
            PendingIntent.getActivity(
                ctx, 1000 + id,
                Intent(ctx, DinoOverlayActivity::class.java)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_NO_ANIMATION),
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
            )
        } else {
            PendingIntent.getBroadcast(
                ctx, id,
                Intent(ctx, WideWidget::class.java).setAction(ACTION_TAP)
                    .putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, id),
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
            )
        }

    /**
     * 클로디 칸 그림. 칸 크기는 **알까지 들어가는 크기**(가로 23칸 · 세로 14칸)로 잡아 어느 장면에서나
     * 클로디 덩치가 같다. 평소엔 가운데, 알이 있으면 클로디는 왼쪽·알은 오른쪽. 바탕은 투명이다.
     */
    fun bitmap(ctx: Context, wPx: Int, hPx: Int, s: State): Bitmap {
        val bmp = Bitmap.createBitmap(wPx.coerceAtLeast(8), hPx.coerceAtLeast(8), Bitmap.Config.ARGB_8888)
        if (s.stage == "away") return bmp     // 판 속에 들어가 있다
        val p = Palette(ctx)
        val u = minOf(wPx / 23f, hPx / 14f)
        val egg = s.stage == "egg"
        val cx = if (egg) 6.5f * u else wPx / 2f
        val cy = hPx - MascotSprite.ROWS / 2f * u - 1.5f * u
        val m = Mascot()
        m.poseForWidget(s.stage, s.cracks)
        m.draw(Canvas(bmp), cx, cy, u, p.coral, p.bg, p.amber, p.label, p.green, p.red, p.title)
        return bmp
    }
}
