package com.kyijgnes.cooldown

import android.app.Activity
import android.app.WallpaperManager
import android.content.ComponentName
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.TypedValue
import android.view.Gravity
import android.view.MotionEvent
import android.view.ViewGroup
import android.widget.Button
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.SeekBar
import android.widget.Switch
import android.widget.TextView
import android.widget.Toast
import com.kyijgnes.cooldown.wallpaper.CooldownWallpaperService
import com.kyijgnes.cooldown.wallpaper.WallpaperArt

/**
 * 배경화면을 사용자가 직접 꾸미는 화면.
 *
 * **설명 문구 대신 미리보기다** — 고르면 바로 위에서 그대로 바뀌고, 자리는 그 미리보기를
 * 손가락으로 끌어서 정한다. 미터기를 짚으면 미터기가, 그 밖을 짚으면 배경이 따라온다.
 * 값(크기 %)은 칸 이름에 그대로 적는다.
 */
class CustomizeActivity : Activity() {

    private lateinit var preview: ImageView
    private lateinit var hint: TextView
    private lateinit var controls: LinearLayout

    private var frame: Bitmap? = null
    private val handler = Handler(Looper.getMainLooper())
    private val ticker = Runnable { paint() }

    private var lastX = 0f
    private var lastY = 0f
    private var movingMeter = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_customize)

        preview = findViewById(R.id.preview)
        hint = findViewById(R.id.preview_hint)
        controls = findViewById(R.id.controls)

        sizePreview()
        preview.setOnTouchListener { _, ev -> drag(ev) }

        findViewById<Button>(R.id.apply).setOnClickListener { applyWallpaper() }
        findViewById<Button>(R.id.reset).setOnClickListener {
            Look.reset(this)
            buildControls()
            paint()
        }

        buildControls()
    }

    override fun onResume() {
        super.onResume()
        paint()
    }

    override fun onPause() {
        super.onPause()
        handler.removeCallbacks(ticker)
    }

    // ---------------------------------------------------------------- 미리보기

    /** 폰 화면과 같은 비율의 판. 세로는 화면의 36% — 아래 고르는 칸도 같이 보여야 한다. */
    private fun sizePreview() {
        val dm = resources.displayMetrics
        val h = (dm.heightPixels * 0.36f).toInt()
        val w = (h.toFloat() * dm.widthPixels / dm.heightPixels).toInt()
        preview.layoutParams = (preview.layoutParams as LinearLayout.LayoutParams).apply {
            width = w
            height = h
        }
        preview.scaleType = ImageView.ScaleType.FIT_XY
        // 판은 한 장만 만들어 계속 덮어 그린다 — 16fps 로 새로 만들면 GC 가 쉴 틈이 없다
        frame = Bitmap.createBitmap(w.coerceAtLeast(2), h.coerceAtLeast(2), Bitmap.Config.ARGB_8888)
        preview.setImageBitmap(frame)
    }

    private fun paint() {
        val bmp = frame ?: return
        val now = System.currentTimeMillis()
        WallpaperArt.render(this, Canvas(bmp), Store.snapshot(this).settled(now), now)
        preview.invalidate()
        handler.removeCallbacks(ticker)
        handler.postDelayed(ticker, 60L)   // 배경화면과 같은 박자
    }

    /** 미터기를 짚으면 미터기가, 그 밖을 짚으면 배경이 따라온다. */
    private fun drag(ev: MotionEvent): Boolean {
        val bmp = frame ?: return false
        if (preview.width == 0) return false
        val sx = bmp.width.toFloat() / preview.width
        val sy = bmp.height.toFloat() / preview.height
        val x = ev.x * sx
        val y = ev.y * sy
        val w = bmp.width.toFloat()
        val h = bmp.height.toFloat()

        when (ev.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                // 세로로 끌면 스크롤뷰가 채 가는 걸 막는다
                preview.parent?.requestDisallowInterceptTouchEvent(true)
                movingMeter = WallpaperArt.hitsMeter(this, w, h, x, y)
            }

            MotionEvent.ACTION_MOVE -> {
                val dx = x - lastX
                val dy = y - lastY
                if (movingMeter) WallpaperArt.dragMeter(this, w, h, dx, dy)
                else WallpaperArt.dragArt(this, w, h, dx, dy)
                paint()
            }

            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL ->
                preview.parent?.requestDisallowInterceptTouchEvent(false)
        }
        lastX = x
        lastY = y
        return true
    }

    // ---------------------------------------------------------------- 고르는 칸

    private fun buildControls() {
        controls.removeAllViews()
        val scene = Look.scene(this)

        hint.text = when {
            Look.meter(this) == Look.NONE && scene != Look.SEA -> ""
            else -> "끌어서 자리 옮기기"
        }

        section("배경")
        chips(
            listOf("상어 바다" to Look.SEA, "바다색만" to Look.PLAIN, "내 사진" to Look.PHOTO),
            scene,
        ) { pick ->
            Look.setScene(this, pick)
            if (pick == Look.PHOTO && Look.photo(this).isEmpty()) pickPhoto()
            buildControls()
            paint()
        }

        if (scene == Look.PHOTO) {
            button(if (Look.photo(this).isEmpty()) "사진 고르기" else "다른 사진") { pickPhoto() }
        }

        if (scene == Look.SEA) {
            section("상어 얼굴")
            chips(
                listOf("입 다문" to Look.CLOSED, "입 벌린" to Look.OPEN),
                Look.mouth(this),
            ) { pick ->
                Look.setMouth(this, pick)
                buildControls()
                paint()
            }
            slider("상어 크기", Look.artSize(this), Look.ART_MIN, Look.ART_MAX) {
                Look.setArtSize(this, it)
            }
        }

        section("미터기")
        chips(
            listOf(
                "막대" to Look.BARS, "링" to Look.RINGS,
                "숫자만" to Look.NUMBERS, "없음" to Look.NONE,
            ),
            Look.meter(this),
        ) { pick ->
            Look.setMeter(this, pick)
            buildControls()
            paint()
        }

        if (Look.meter(this) != Look.NONE) {
            slider("미터기 크기", Look.meterSize(this), Look.METER_MIN, Look.METER_MAX) {
                Look.setMeterSize(this, it)
            }
            toggle("글씨 뒤 판", Look.plate(this)) {
                Look.setPlate(this, it)
                paint()
            }
        }
    }

    private fun section(title: String) {
        controls.addView(TextView(this).apply {
            text = title
            setTextColor(getColor(R.color.label))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
            layoutParams = rowParams(top = 20)
        })
    }

    /** 고른 것 하나가 색으로 드러나는 한 줄. 항목 이름이 곧 그 모양의 이름이다. */
    private fun chips(items: List<Pair<String, String>>, chosen: String, onPick: (String) -> Unit) {
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            layoutParams = rowParams(top = 8)
        }
        items.forEachIndexed { i, (label, value) ->
            val on = value == chosen
            row.addView(TextView(this).apply {
                text = label
                gravity = Gravity.CENTER
                // 고른 것만 진하게 뒤집는다. 두 벌 다 배경 대비 10:1 이상 (밝게·어둡게)
                setTextColor(getColor(if (on) R.color.bg else R.color.title))
                setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
                setPadding(0, dp(12), 0, dp(12))
                background = GradientDrawable().apply {
                    cornerRadius = dp(12).toFloat()
                    setColor(getColor(if (on) R.color.sub else R.color.track))
                }
                setOnClickListener { onPick(value) }
                layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
                    .apply { if (i > 0) marginStart = dp(8) }
            })
        }
        controls.addView(row)
    }

    /** 크기 슬라이더. **지금 값은 칸 이름에 그대로 적는다** — 따로 설명하지 않는다. */
    private fun slider(title: String, value: Float, lo: Float, hi: Float, onSet: (Float) -> Unit) {
        val label = TextView(this).apply {
            text = "$title · ${Math.round(value * 100)}%"
            setTextColor(getColor(R.color.label))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
            layoutParams = rowParams(top = 20)
        }
        controls.addView(label)

        val span = hi - lo
        controls.addView(SeekBar(this).apply {
            max = 100
            progress = Math.round((value - lo) / span * 100f).coerceIn(0, 100)
            layoutParams = rowParams(top = 4)
            setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
                override fun onProgressChanged(sb: SeekBar, p: Int, fromUser: Boolean) {
                    val v = lo + span * p / 100f
                    onSet(v)
                    label.text = "$title · ${Math.round(v * 100)}%"
                    paint()
                }

                override fun onStartTrackingTouch(sb: SeekBar) = Unit
                override fun onStopTrackingTouch(sb: SeekBar) = Unit
            })
        })
    }

    private fun toggle(title: String, on: Boolean, onSet: (Boolean) -> Unit) {
        controls.addView(Switch(this).apply {
            text = title
            isChecked = on
            minHeight = dp(48)
            setTextColor(getColor(R.color.title))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f)
            layoutParams = rowParams(top = 12)
            setOnCheckedChangeListener { _, checked -> onSet(checked) }
        })
    }

    private fun button(text: String, onTap: () -> Unit) {
        controls.addView(Button(this).apply {
            this.text = text
            setTextColor(getColor(R.color.title))
            layoutParams = rowParams(top = 8)
            setOnClickListener { onTap() }
        })
    }

    private fun rowParams(top: Int) = LinearLayout.LayoutParams(
        ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT,
    ).apply { topMargin = dp(top) }

    private fun dp(v: Int) = Math.round(v * resources.displayMetrics.density)

    // ---------------------------------------------------------------- 사진 고르기

    private fun pickPhoto() {
        val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = "image/*"
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            addFlags(Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)
        }
        try {
            startActivityForResult(intent, REQ_PHOTO)
        } catch (e: Exception) {
            Toast.makeText(this, "사진을 고를 앱이 없어요", Toast.LENGTH_SHORT).show()
        }
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != REQ_PHOTO || resultCode != RESULT_OK) return
        val uri = data?.data ?: return
        // 앱을 껐다 켜도 계속 읽을 수 있게 — 안 잡아 두면 다음 부팅에 사진이 사라진다
        try {
            contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
        } catch (e: Exception) {
            // 임시 권한만 받은 경우 — 이번 세션에서는 보인다
        }
        Look.setPhoto(this, uri.toString())
        Look.setScene(this, Look.PHOTO)
        WallpaperArt.forgetPhoto()
        buildControls()
        paint()
    }

    // ---------------------------------------------------------------- 걸기

    private fun applyWallpaper() {
        val intent = Intent(WallpaperManager.ACTION_CHANGE_LIVE_WALLPAPER).putExtra(
            WallpaperManager.EXTRA_LIVE_WALLPAPER_COMPONENT,
            ComponentName(this, CooldownWallpaperService::class.java),
        )
        try {
            startActivity(intent)
        } catch (e: Exception) {
            Toast.makeText(this, "배경화면 설정을 열 수 없어요", Toast.LENGTH_SHORT).show()
        }
    }

    private companion object {
        const val REQ_PHOTO = 7
    }
}
