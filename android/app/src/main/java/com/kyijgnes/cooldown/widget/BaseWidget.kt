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
        // RemoteViews 로 넘기는 비트맵은 크면 잘려 나간다 — 넉넉하되 상한을 둔다
        val wPx = (wDp * density).toInt().coerceIn(72, 1440)
        val hPx = (hDp * density).toInt().coerceIn(72, 720)

        val now = System.currentTimeMillis()
        val snap = Store.snapshot(ctx).settled(now)
        val views = RemoteViews(ctx.packageName, R.layout.widget)
        views.setImageViewBitmap(R.id.canvas, render(ctx, wPx, hPx, snap, now))
        views.setOnClickPendingIntent(R.id.canvas, openApp(ctx))
        try {
            mgr.updateAppWidget(id, views)
        } catch (e: Exception) {
            // 그림이 너무 커서 거부당한 경우 — 다음 갱신 때 더 작은 칸으로 다시 온다
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

    private fun openApp(ctx: Context): PendingIntent = PendingIntent.getActivity(
        ctx, 0,
        Intent(ctx, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP),
        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
    )
}
