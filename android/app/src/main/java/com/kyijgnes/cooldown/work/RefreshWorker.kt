package com.kyijgnes.cooldown.work

import android.content.Context
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequest
import androidx.work.PeriodicWorkRequest
import androidx.work.WorkManager
import androidx.work.Worker
import androidx.work.WorkerParameters
import com.kyijgnes.cooldown.Refresher
import java.util.concurrent.TimeUnit

/**
 * 15분마다 서버에서 값을 읽는다 (WorkManager 의 최소 주기).
 *
 * 더 자주 물을 이유가 없다 — 퍼센트는 **클로드를 실제로 쓸 때만** 변하고,
 * 초기화는 폰이 스스로 계산한다(Limit.settled). 그래서 15분이어도 화면은 안 틀린다.
 */
class RefreshWorker(ctx: Context, params: WorkerParameters) : Worker(ctx, params) {

    override fun doWork(): Result {
        Refresher.refresh(applicationContext)
        return Result.success()  // 실패해도 다음 주기에 다시 온다 (재시도로 배터리를 쓰지 않는다)
    }

    companion object {
        private const val PERIODIC = "cooldown-refresh"
        private const val ONCE = "cooldown-refresh-once"

        private val NEEDS_NETWORK = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()

        fun schedule(ctx: Context) {
            val req = PeriodicWorkRequest.Builder(
                RefreshWorker::class.java, 15, TimeUnit.MINUTES
            ).setConstraints(NEEDS_NETWORK).build()

            WorkManager.getInstance(ctx)
                .enqueueUniquePeriodicWork(PERIODIC, ExistingPeriodicWorkPolicy.KEEP, req)
        }

        /** 지금 한 번 (앱을 열었을 때·초기화 시각이 됐을 때). */
        fun once(ctx: Context) {
            val req = OneTimeWorkRequest.Builder(RefreshWorker::class.java)
                .setConstraints(NEEDS_NETWORK).build()
            WorkManager.getInstance(ctx)
                .enqueueUniqueWork(ONCE, ExistingWorkPolicy.REPLACE, req)
        }
    }
}
