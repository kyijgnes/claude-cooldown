package com.kyijgnes.cooldown.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.os.Bundle
import android.widget.RemoteViews
import com.kyijgnes.cooldown.MainActivity
import com.kyijgnes.cooldown.R
import com.kyijgnes.cooldown.Snapshot
import com.kyijgnes.cooldown.Store

/**
 * 홈 위젯 공통. 내용은 그림 한 장이라 위젯마다 `render` 만 다르다.
 *
 * 남은 시간을 '2시간 07분 후' 로 적지 않고 **초기화 시각**으로 적는 이유:
 * 위젯은 길면 30분에 한 번 갱신되므로 상대 시간은 금방 틀린 값이 된다.
 */
abstract class BaseWidget : AppWidgetProvider() {

    /** 이 위젯이 그리는 그림. */
    abstract fun render(ctx: Context, wPx: Int, hPx: Int, snap: Snapshot, now: Long): Bitmap

    /** 위젯 칸이 이 dp 보다 작다고 나오면 이 값을 쓴다 (처음 놓았을 때 0 이 온다). */
    protected abstract val fallbackDp: Pair<Int, Int>

    override fun onUpdate(ctx: Context, mgr: AppWidgetManager, ids: IntArray) {
        ids.forEach { draw(ctx, mgr, it) }
    }

    override fun onAppWidgetOptionsChanged(
        ctx: Context,
        mgr: AppWidgetManager,
        id: Int,
        newOptions: Bundle?,
    ) {
        draw(ctx, mgr, id)
    }

    fun draw(ctx: Context, mgr: AppWidgetManager, id: Int) {
        val (wDp, hDp) = sizeDp(mgr, id)
        val density = ctx.resources.displayMetrics.density
        var wPx = (wDp * density).toInt().coerceIn(72, 1440)
        var hPx = (hDp * density).toInt().coerceIn(72, 720)

        // ★★ **그림이 크면 위젯이 통째로 빈 칸이 된다.** RemoteViews 로 넘길 수 있는 양이
        //   1MB 남짓이라, 4×1 을 4×2 로 늘리면(가로 960 × 세로 450 = 1.7MB) `updateAppWidget`
        //   이 거부당한다 — 예전엔 그 예외를 조용히 삼켜서 **미터기가 사라진 것처럼** 보였다.
        //   그래서 넓이×높이 총량을 먼저 줄인다. 비율은 그대로라 `fitCenter` 로 다시 커진다.
        val over = wPx.toLong() * hPx / MAX_PIXELS.toDouble()
        if (over > 1.0) {
            val k = kotlin.math.sqrt(over)
            wPx = (wPx / k).toInt().coerceAtLeast(72)
            hPx = (hPx / k).toInt().coerceAtLeast(72)
        }

        val now = System.currentTimeMillis()
        val snap = Store.snapshot(ctx).settled(now)
        val views = RemoteViews(ctx.packageName, R.layout.widget)
        views.setImageViewBitmap(R.id.canvas, render(ctx, wPx, hPx, snap, now))
        views.setOnClickPendingIntent(R.id.canvas, openApp(ctx))
        try {
            mgr.updateAppWidget(id, views)
        } catch (e: Exception) {
            // 그래도 거부당하면 까닭을 남긴다 — 조용히 삼키면 '미터기가 없어졌다'로만 보인다
            android.util.Log.w(TAG, "위젯 그림을 못 넘겼다 (${wPx}x$hPx): $e")
        }
    }

    private fun sizeDp(mgr: AppWidgetManager, id: Int): Pair<Int, Int> {
        val o = try {
            mgr.getAppWidgetOptions(id)
        } catch (e: Exception) {
            null
        }
        val w = o?.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH, 0) ?: 0
        val h = o?.getInt(AppWidgetManager.OPTION_APPWIDGET_MAX_HEIGHT, 0) ?: 0
        return Pair(
            if (w > 0) w else fallbackDp.first,
            if (h > 0) h else fallbackDp.second,
        )
    }

    private companion object {
        const val TAG = "cooldown-widget"

        /** 한 장에 담을 수 있는 점 수. ARGB 4바이트라 230,000 점 ≒ 900KB (한계는 1MB 남짓). */
        const val MAX_PIXELS = 230_000
    }

    private fun openApp(ctx: Context): PendingIntent = PendingIntent.getActivity(
        ctx, 0,
        Intent(ctx, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP),
        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
    )
}
