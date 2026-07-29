package com.kyijgnes.cooldown.work

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.kyijgnes.cooldown.Refresher

/** 재부팅·앱 업데이트 뒤에도 알림과 주기 갱신을 되살린다. */
class BootReceiver : BroadcastReceiver() {

    override fun onReceive(ctx: Context, intent: Intent) {
        // 시스템만 보낼 수 있는 방송이지만, 남이 빈 인텐트를 찔러도 움직이지 않게 확인한다
        if (intent.action != Intent.ACTION_BOOT_COMPLETED &&
            intent.action != Intent.ACTION_MY_PACKAGE_REPLACED
        ) return

        RefreshWorker.schedule(ctx)
        ResetAlarm.schedule(ctx)
        Refresher.renderAll(ctx)  // 저장해 둔 값으로 알림·위젯을 곧바로 되살린다
        RefreshWorker.once(ctx)
    }
}
