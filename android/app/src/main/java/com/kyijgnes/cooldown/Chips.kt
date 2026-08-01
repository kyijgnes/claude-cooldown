package com.kyijgnes.cooldown

import android.content.Context
import android.graphics.drawable.GradientDrawable
import android.view.Gravity
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.TextView

/**
 * 고른 것 하나가 색으로 드러나는 한 줄. **항목 이름이 곧 그 모양의 이름**이라
 * 따로 설명할 게 없다 — 앱 화면과 꾸미기 화면이 같은 걸 쓴다.
 */
object Chips {

    fun fill(row: LinearLayout, items: List<Pair<String, String>>, chosen: String, onPick: (String) -> Unit) {
        val ctx = row.context
        row.removeAllViews()
        row.orientation = LinearLayout.HORIZONTAL
        items.forEachIndexed { i, (label, value) ->
            val on = value == chosen
            row.addView(TextView(ctx).apply {
                text = label
                gravity = Gravity.CENTER
                // 고른 것만 진하게 뒤집는다. 두 벌 다 배경 대비 10:1 이상 (밝게·어둡게)
                setTextColor(ctx.getColor(if (on) R.color.bg else R.color.title))
                textSize = 14f
                setPadding(0, dp(ctx, 12), 0, dp(ctx, 12))
                background = GradientDrawable().apply {
                    cornerRadius = dp(ctx, 12).toFloat()
                    setColor(ctx.getColor(if (on) R.color.sub else R.color.track))
                }
                setOnClickListener { onPick(value) }
                layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
                    .apply { if (i > 0) marginStart = dp(ctx, 8) }
            })
        }
    }

    fun dp(ctx: Context, v: Int) = Math.round(v * ctx.resources.displayMetrics.density)
}
