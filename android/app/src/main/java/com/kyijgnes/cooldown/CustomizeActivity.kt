package com.kyijgnes.cooldown

import android.app.Activity
import android.app.WallpaperManager
import android.content.ComponentName
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Canvas
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.util.TypedValue
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
 *
 * ★ **손댄 것은 `저장` 을 눌러야 실제로 걸린다.** 화면이 들고 있는 `draft` 만 바뀌고
 *   미리보기도 그걸로 그린다. 저장 버튼 글씨가 곧 상태다 — `저장` / `저장됨`.
 */
class CustomizeActivity : Activity() {

    private lateinit var preview: ImageView
    private lateinit var controls: LinearLayout
    private lateinit var save: Button

    /** 저장 전 값. 화면·미리보기는 전부 이걸 본다. */
    private var draft = Look.DEFAULT
    private var saved = Look.DEFAULT

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
        controls = findViewById(R.id.controls)
        save = findViewById(R.id.save)

        saved = Look.read(this)
        draft = saved

        sizePreview()
        preview.setOnTouchListener { _, ev -> drag(ev) }

        save.setOnClickListener { apply() }
        findViewById<Button>(R.id.reset).setOnClickListener {
            // 고른 사진은 남긴다 — 다시 고르게 만들 일이 아니다
            change(Look.DEFAULT.copy(photo = draft.photo))
        }

        buildControls()
    }

    override fun onResume() {
        super.onResume()
        // 권한 화면에서 돌아왔을 수 있다 — 아직 못 떠 왔고 이제 읽을 수 있으면 그때 떠 온다
        if (WallpaperGrab.saved(this).isEmpty() && canReadWallpaper()) takeWallpaper()
        paint()
    }

    override fun onPause() {
        super.onPause()
        handler.removeCallbacks(ticker)
    }

    // ---------------------------------------------------------------- 값 바꾸기

    /** 저장 전 값만 바꾼다. 실제 배경화면은 `저장` 을 눌러야 바뀐다. */
    private fun change(next: Look.Values, rebuild: Boolean = true) {
        draft = next
        if (rebuild) buildControls() else syncSave()
        paint()
    }

    /**
     * 저장 버튼 **글씨가 곧 상태**다.
     * ★ 아직 배경화면으로 안 걸었으면 손댄 게 없어도 눌러야 한다 — `저장됨`으로 잠가 두면
     *   기본 모양이 마음에 든 사람은 **배경화면을 걸 길이 없다**(실제로 막혔던 자리).
     */
    private fun syncSave() {
        val dirty = draft != saved
        val hung = WallpaperManager.getInstance(this).wallpaperInfo?.packageName == packageName
        save.text = if (!hung) "배경화면으로 걸기" else if (dirty) "저장" else "저장됨"
        save.isEnabled = !hung || dirty
    }

    private fun apply() {
        // ★ **보여 줄 배경이 아예 없는 채로 걸지 않는다.** 그대로 걸면 쓰던 배경화면이
        //   밋밋한 바탕색으로 바뀌어 버린다 — 먼저 쓰던 배경화면을 가져오게 한다.
        if (draft.photo.isEmpty() && WallpaperGrab.saved(this).isEmpty()) {
            takeWallpaper()
            return
        }
        Look.write(this, draft)
        saved = draft
        syncSave()
        // 아직 배경화면으로 안 걸었으면 고르는 화면을 띄운다. 이미 걸려 있으면 그대로 반영된다.
        if (WallpaperManager.getInstance(this).wallpaperInfo?.packageName == packageName) {
            Toast.makeText(this, "배경화면에 반영됐어요", Toast.LENGTH_SHORT).show()
        } else {
            pickWallpaper()
        }
    }

    private fun pickWallpaper() {
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
        WallpaperArt.render(this, Canvas(bmp), Store.snapshot(this).settled(now), now, draft)
        preview.invalidate()
        handler.removeCallbacks(ticker)
        handler.postDelayed(ticker, 60L)   // 배경화면과 같은 박자
    }

    /** 미터기를 짚으면 미터기가, 그 밖을 짚으면 배경이 따라온다. */
    private fun drag(ev: MotionEvent): Boolean {
        val bmp = frame ?: return false
        if (preview.width == 0) return false
        val x = ev.x * bmp.width / preview.width
        val y = ev.y * bmp.height / preview.height
        val w = bmp.width.toFloat()
        val h = bmp.height.toFloat()

        when (ev.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                // 세로로 끌면 스크롤뷰가 채 가는 걸 막는다
                preview.parent?.requestDisallowInterceptTouchEvent(true)
                movingMeter = WallpaperArt.hitsMeter(w, h, draft, x, y)
            }

            MotionEvent.ACTION_MOVE -> {
                val dx = x - lastX
                val dy = y - lastY
                change(
                    if (movingMeter) WallpaperArt.dragMeter(w, h, draft, dx, dy)
                    else WallpaperArt.dragBg(this, w, h, draft, dx, dy),
                    rebuild = false,
                )
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
        syncSave()

        // 배경은 사진 한 갈래다 — 폰에서 떠 온 배경을 쓰는 중이면 버튼이 `사진 고르기`,
        // 직접 고른 사진을 쓰는 중이면 `다른 사진` + `쓰던 배경으로`. 설명 문구는 두지 않는다.
        // ★ **사진은 사용자가 고를 때만 바뀐다** — 우리가 임의로 바꾸지 않는다.
        val grabbed = WallpaperGrab.saved(this)
        val ownWallpaper = grabbed.isNotEmpty() && (draft.photo.isEmpty() || draft.photo == grabbed)

        section("배경")
        // 아직 못 떠 왔으면 그것부터 — 버튼 이름이 곧 하는 일이다(권한 화면으로 간다)
        if (grabbed.isEmpty()) button("쓰던 배경화면 가져오기") { takeWallpaper() }
        button(if (draft.photo.isEmpty() || ownWallpaper) "사진 고르기" else "다른 사진") { pickPhoto() }
        if (!ownWallpaper && grabbed.isNotEmpty()) {
            button("쓰던 배경으로") {
                WallpaperArt.forgetPhoto()
                change(draft.copy(photo = grabbed, photoX = 0.5f, photoY = 0.5f))
            }
        }

        section("미터기")
        chips(
            listOf(
                "막대" to Look.BARS, "링" to Look.RINGS,
                "숫자만" to Look.NUMBERS, "없음" to Look.NONE,
            ),
            draft.meter,
        ) { pick -> change(draft.copy(meter = pick)) }

        if (draft.meter != Look.NONE) {
            slider("미터기 크기", draft.meterSize, Look.METER_MIN, Look.METER_MAX) {
                change(
                    draft.copy(meterSize = it.coerceIn(Look.METER_MIN, Look.METER_MAX)),
                    rebuild = false,
                )
            }
            toggle("글씨 뒤 판", draft.plateOn) { change(draft.withPlate(it), rebuild = false) }
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

    private fun chips(items: List<Pair<String, String>>, chosen: String, onPick: (String) -> Unit) {
        val row = LinearLayout(this).apply { layoutParams = rowParams(top = 8) }
        Chips.fill(row, items, chosen, onPick)
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

    // ---------------------------------------------------------------- 쓰던 배경화면 가져오기

    /**
     * 폰에 걸려 있는 배경화면을 한 장 떠 와 배경으로 쓴다.
     *
     * ★ **안드로이드 11 부터는 '모든 파일 접근' 이 있어야 읽힌다** — 없으면
     * `WallpaperManager.getDrawable()` 이 SecurityException 으로 막힌다(13 실기 확인).
     * 그래서 권한이 없으면 **시스템 설정 화면으로 보내고**, 돌아왔을 때 `onResume` 이
     * 다시 떠 온다. 우리가 하는 일은 배경화면 한 장을 뜨는 것뿐이다.
     */
    private fun takeWallpaper() {
        if (!canReadWallpaper()) {
            askAllFiles()
            return
        }
        val uri = WallpaperGrab.ensure(this)
        if (uri.isEmpty()) {
            Toast.makeText(this, "배경화면을 못 가져왔어요", Toast.LENGTH_SHORT).show()
            return
        }
        WallpaperArt.forgetPhoto()
        change(draft.copy(photo = uri, photoX = 0.5f, photoY = 0.5f))
    }

    /** ★ `isExternalStorageManager()` 는 저장소가 없는 환경(테스트·일부 기기)에서 던진다 — 감싼다. */
    private fun canReadWallpaper(): Boolean = try {
        Build.VERSION.SDK_INT < Build.VERSION_CODES.R || Environment.isExternalStorageManager()
    } catch (e: Exception) {
        false
    }

    private fun askAllFiles() {
        val intent = Intent(
            Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
            Uri.parse("package:$packageName"),
        )
        try {
            startActivity(intent)
        } catch (e: Exception) {
            try {
                startActivity(Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION))
            } catch (e2: Exception) {
                Toast.makeText(this, "권한 화면을 열 수 없어요", Toast.LENGTH_SHORT).show()
            }
        }
    }

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
        WallpaperArt.forgetPhoto()
        change(draft.copy(photo = uri.toString(), photoX = 0.5f, photoY = 0.5f))
    }

    private companion object {
        const val REQ_PHOTO = 7
    }
}
