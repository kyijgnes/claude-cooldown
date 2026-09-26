package com.kyijgnes.cooldown.dino

import android.app.Activity
import android.os.Bundle

/**
 * 공룡 점프 — 클로디를 **아주 오래 꾹 누르면**(끝까지 납작해진 뒤로도 더) 공룡으로 변신해 여기로 온다.
 * 꾸미기 화면의 미리보기에서 된다(홈 화면에서는 런처가 길게 누르기를 채 간다).
 * 뒤로 가면 닫히고, 돌아간 화면의 클로디가 펑 하고 돌아온다.
 *
 * 최고 기록은 `dino` 저장소의 `best` 하나.
 */
class DinoActivity : Activity() {

    private lateinit var board: DinoView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val prefs = getSharedPreferences(PREFS, MODE_PRIVATE)
        board = DinoView(this, prefs.getInt(BEST, 0))
        board.onBest = { best -> prefs.edit().putInt(BEST, best).apply() }
        setContentView(board)
    }

    override fun onResume() {
        super.onResume()
        board.resume()
    }

    override fun onPause() {
        board.pause()
        super.onPause()
    }

    companion object {
        const val PREFS = "dino"
        const val BEST = "best"
    }
}
