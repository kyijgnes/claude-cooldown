package com.kyijgnes.cooldown.widget

import android.content.Context
import android.graphics.Bitmap
import com.kyijgnes.cooldown.GaugeRenderer
import com.kyijgnes.cooldown.Snapshot

/** 링 하나 + 숫자. 더 급한 쪽(5시간·주간 중 큰 값)을 보여 준다. */
class SmallWidget : BaseWidget() {
    override val fallbackDp = Pair(70, 70)

    override fun render(ctx: Context, wPx: Int, hPx: Int, snap: Snapshot, now: Long): Bitmap =
        GaugeRenderer.small(ctx, minOf(wPx, hPx), snap, now, card = false)
}
