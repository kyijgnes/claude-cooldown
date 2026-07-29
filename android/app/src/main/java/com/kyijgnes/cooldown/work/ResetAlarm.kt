package com.kyijgnes.cooldown.work

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.kyijgnes.cooldown.Refresher
import com.kyijgnes.cooldown.Store

/**
 * 한도가 풀리는 순간 한 번 깨어나 화면을 0% 로 바꾼다.
 *
 * 이게 없으면 초기화된 지 15분이 지나도록 위젯이 옛 퍼센트를 붙들고 있다.
 * 정확한 알람 권한(SCHEDULE_EXACT_ALARM)은 쓰지 않는다 — 몇 분 늦어도 되는 일이라
 * 권한을 물어 사용자를 귀찮게 할 값어치가 없다.
 */
object ResetAlarm {
    private const val REQUEST = 100

    class Receiver : BroadcastReceiver() {
        override fun onReceive(ctx: Context, intent: Intent) {
            Refresher.renderAll(ctx)   // 지난 창을 0% 로 (네트워크 없이 바로)
            RefreshWorker.once(ctx)    // 겸사겸사 최신값도 받아 둔다
            schedule(ctx)              // 다음 초기화 예약
        }
    }

    fun schedule(ctx: Context) {
        val am = ctx.getSystemService(AlarmManager::class.java) ?: return
        val now = System.currentTimeMillis()
        val snap = Store.snapshot(ctx)
        val next = listOfNotNull(snap.five.resetAt, snap.week.resetAt)
            .filter { it > now }
            .minOrNull() ?: return

        val pi = PendingIntent.getBroadcast(
            ctx, REQUEST,
            Intent(ctx, Receiver::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        try {
            // 서버 시계와 몇 초 어긋나도 이미 지난 뒤가 되게 조금 늦춰 깨운다
            am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, next + 10_000, pi)
        } catch (e: SecurityException) {
            // 알람을 못 걸어도 15분 주기 갱신이 결국 따라잡는다
        }
    }
}
