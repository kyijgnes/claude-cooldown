package com.kyijgnes.cooldown

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.text.format.DateFormat
import android.view.View
import android.widget.Button
import android.widget.ImageView
import android.widget.TextView
import android.widget.Toast
import com.kyijgnes.cooldown.work.RefreshWorker
import com.kyijgnes.cooldown.work.ResetAlarm

/**
 * 홈 — **지금 값만** 본다. 손댈 것(PC 연결·알림·배경화면)은 전부 `SettingsActivity` 로 갔다.
 *
 * ★ **PC 가 연결 안 돼 있으면 그것부터 하게 만든다** — 숫자가 있을 자리에
 *   [PC 연결하기] 가 대신 서고, 앱을 켤 때 한 번은 옵션 화면으로 곧장 보낸다.
 *   연결 전에는 새로고침할 것도 없다.
 */
class MainActivity : Activity() {

    private lateinit var gauge: ImageView
    private lateinit var status: TextView
    private lateinit var connect: Button
    private lateinit var refresh: Button

    /** 이번에 앱을 켠 뒤 연결 화면으로 한 번 보냈나 (계속 튕겨 나가지 않게). */
    private var sentToPair = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        gauge = findViewById(R.id.gauge)
        status = findViewById(R.id.status)
        connect = findViewById(R.id.connect)
        refresh = findViewById(R.id.refresh)

        connect.setOnClickListener { openOptions() }
        refresh.setOnClickListener { reload() }
        findViewById<Button>(R.id.options).setOnClickListener { openOptions() }

        takePairFrom(intent)
        seedWallpaper()
        RefreshWorker.schedule(this)
        ResetAlarm.schedule(this)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        takePairFrom(intent)
        showValues()
    }

    override fun onResume() {
        super.onResume()
        showValues()
        if (!Store.paired(this)) {
            if (!sentToPair) {
                sentToPair = true
                openOptions()
            }
            return
        }
        reload()
    }

    private fun openOptions() {
        startActivity(Intent(this, SettingsActivity::class.java))
    }

    // ---------------------------------------------------------------- 화면

    private fun showValues() {
        val paired = Store.paired(this)
        connect.visibility = if (paired) View.GONE else View.VISIBLE
        refresh.visibility = if (paired) View.VISIBLE else View.GONE
        gauge.visibility = if (paired) View.VISIBLE else View.GONE

        if (paired) drawGauge()
        status.text = statusLine()
    }

    private fun drawGauge() {
        val w = gauge.width
        if (w == 0) {
            gauge.post { drawGauge() }
            return
        }
        val now = System.currentTimeMillis()
        val snap = Store.snapshot(this).settled(now)
        gauge.setImageBitmap(GaugeRenderer.wide(this, w, (w * 0.32f).toInt(), snap, now, card = false))
    }

    private fun statusLine(): String {
        if (!Store.paired(this)) return "PC 와 연결하면 사용량이 보입니다"
        val err = Store.error(this)
        val fetched = Store.fetchedAt(this)
        val clock = if (fetched > 0) DateFormat.getTimeFormat(this).format(fetched) else "--:--"
        if (err.isNotEmpty()) return "$err · $clock 시도"
        val snap = Store.snapshot(this)
        val head = "$clock 갱신"
        val age = snap.ageText(System.currentTimeMillis())
        return if (age.isEmpty()) head else "$head · $age"
    }

    // ---------------------------------------------------------------- 동작

    private fun reload() {
        Thread {
            Refresher.refresh(this)
            runOnUiThread { if (!isFinishing) showValues() }
        }.start()
    }

    /**
     * 기본 배경은 **쓰던 배경화면 + 미터기**다. 그러려면 우리 라이브 배경화면이 걸리기 전에
     * 지금 배경화면을 한 장 떠 놔야 한다 — 걸린 뒤엔 '지금 배경화면'이 우리다.
     * 못 떠 와도 그만이다(상어 바다로 내려간다).
     */
    private fun seedWallpaper() {
        if (Look.read(this).photo.isNotEmpty()) return
        Thread {
            val uri = WallpaperGrab.ensure(this)
            if (uri.isNotEmpty()) Look.write(this, Look.read(this).copy(photo = uri))
        }.start()
    }

    private fun takePairFrom(intent: Intent?) {
        if (Store.applyPairUri(this, intent?.data)) {
            Toast.makeText(this, "PC 와 연결됐어요", Toast.LENGTH_SHORT).show()
            sentToPair = true   // QR 로 방금 붙였다 — 옵션으로 보낼 필요 없다
            reload()
        }
    }
}
