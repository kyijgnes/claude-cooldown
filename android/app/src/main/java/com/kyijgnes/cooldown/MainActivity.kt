package com.kyijgnes.cooldown

import android.Manifest
import android.app.Activity
import android.app.WallpaperManager
import android.content.ComponentName
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.text.format.DateFormat
import android.widget.Button
import android.widget.CompoundButton
import android.widget.EditText
import android.widget.ImageView
import android.widget.Switch
import android.widget.TextView
import android.widget.Toast
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning
import com.kyijgnes.cooldown.notify.NotifyController
import com.kyijgnes.cooldown.wallpaper.CooldownWallpaperService
import com.kyijgnes.cooldown.work.RefreshWorker
import com.kyijgnes.cooldown.work.ResetAlarm

/**
 * 한 화면에 다 있다 — 지금 값, PC 연결, 어디에 보일지.
 * 설명 문단을 두지 않고 **항목 이름과 지금 상태**로 알게 한다.
 */
class MainActivity : Activity() {

    private lateinit var gauge: ImageView
    private lateinit var status: TextView
    private lateinit var url: EditText
    private lateinit var key: EditText
    private lateinit var notify: Switch
    private lateinit var notifyNote: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        gauge = findViewById(R.id.gauge)
        status = findViewById(R.id.status)
        url = findViewById(R.id.url)
        key = findViewById(R.id.key)
        notify = findViewById(R.id.notify)
        notifyNote = findViewById(R.id.notify_note)

        findViewById<Button>(R.id.refresh).setOnClickListener { refresh() }
        findViewById<Button>(R.id.save).setOnClickListener { save() }
        findViewById<Button>(R.id.scan).setOnClickListener { scan() }
        findViewById<Button>(R.id.wallpaper).setOnClickListener { pickWallpaper() }
        findViewById<Button>(R.id.customize).setOnClickListener {
            startActivity(Intent(this, CustomizeActivity::class.java))
        }

        notify.setOnCheckedChangeListener { _: CompoundButton, on: Boolean ->
            Store.setNotifyOn(this, on)
            if (on) askNotificationPermission()
            NotifyController.update(this)
        }

        takePairFrom(intent)
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
        refresh()
    }

    // ---------------------------------------------------------------- 화면

    private fun showValues() {
        url.setText(Store.url(this))
        key.setText(Store.key(this))
        notify.isChecked = Store.notifyOn(this)
        // 이 기기에서 실제로 어떻게 보이는지를 그대로 적는다 (설명 문단 대신).
        // 안드로이드 16 미만에서도 AOD 알림 아이콘 줄에 숫자가 뜬다 — S20 Ultra 실측 확인.
        notifyNote.text =
            if (NotifyController.canPromote(this)) "상태바 칩 · 잠금화면 · AOD 진행바"
            else "상태바 · 잠금화면 · AOD 에 숫자"

        drawGauge()
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
        if (!Store.paired(this)) return "PC 연결 필요 — 주소와 키를 넣으세요"
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

    private fun refresh() {
        Thread {
            Refresher.refresh(this)
            runOnUiThread { if (!isFinishing) showValues() }
        }.start()
    }

    private fun save() {
        val u = Store.normalizeUrl(url.text.toString())
        val k = key.text.toString().trim()
        if (u.isEmpty()) {
            toast("서버 주소를 알아볼 수 없어요")
            return
        }
        if (k.length != 32) {
            toast("키는 32자리예요")
            return
        }
        Store.setPair(this, u, k)
        showValues()
        refresh()
    }

    private fun scan() {
        val options = GmsBarcodeScannerOptions.Builder()
            .setBarcodeFormats(Barcode.FORMAT_QR_CODE)
            .build()
        GmsBarcodeScanning.getClient(this, options).startScan()
            .addOnSuccessListener { code ->
                val raw = code.rawValue ?: return@addOnSuccessListener
                if (Store.applyPairUri(this, android.net.Uri.parse(raw))) {
                    showValues()
                    refresh()
                } else {
                    toast("클로드 쿨다운 QR 이 아니에요")
                }
            }
            .addOnFailureListener { toast("QR 을 못 읽었어요 — 아래에 직접 넣어 주세요") }
    }

    private fun pickWallpaper() {
        val intent = Intent(WallpaperManager.ACTION_CHANGE_LIVE_WALLPAPER).putExtra(
            WallpaperManager.EXTRA_LIVE_WALLPAPER_COMPONENT,
            ComponentName(this, CooldownWallpaperService::class.java),
        )
        try {
            startActivity(intent)
        } catch (e: Exception) {
            toast("배경화면 설정을 열 수 없어요")
        }
    }

    private fun takePairFrom(intent: Intent?) {
        if (Store.applyPairUri(this, intent?.data)) {
            toast("PC 와 연결됐어요")
            refresh()
        }
    }

    private fun askNotificationPermission() {
        if (Build.VERSION.SDK_INT < 33) return
        if (checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
            == PackageManager.PERMISSION_GRANTED
        ) return
        requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray,
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        NotifyController.update(this)
        showValues()
    }

    private fun toast(text: String) = Toast.makeText(this, text, Toast.LENGTH_SHORT).show()
}
