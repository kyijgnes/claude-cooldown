package com.kyijgnes.cooldown.dino

/**
 * 투명 판(`DinoOverlayActivity`)과 배경화면 엔진이 주고받는 것 — 같은 프로세스라 그냥 나눠 쓴다.
 *
 * 홈 화면에서 알을 깨면 판은 **배경화면이 아니라 투명한 화면**이 그린다(2026-09-26). 배경화면은
 * 런처가 길게 누르기를 채 가서, 점프를 조금만 길게 눌러도 홈 화면 편집 메뉴가 떴다. 투명한 화면은
 * 손가락이 끝까지 우리 것이다. 배경화면은 그동안 클로디를 숨기고, 판이 다 열리면 미터기도 숨긴다.
 */
object DinoHost {
    /** 투명 판이 떠 있다 — 배경화면은 그동안 클로디(와 알에서 깬 공룡)를 안 그린다. */
    @Volatile var overlayUp = false

    /** 들어오는 장면이 끝나 판이 다 열렸다 — 배경화면은 그때부터 미터기를 안 그린다(판이 그 자리다). */
    @Volatile var boardSettled = false

    /** 판이 닫혔을 때 한 번 — 판을 부른 배경화면이 걸어 둔다(클로디를 펑 하고 돌려놓는다). */
    @Volatile var onClosed: (() -> Unit)? = null

    // 투명 판에 넘기는 것 (Intent extra 이름)
    const val EXTRA_SOURCE = "dino_source"   // "wallpaper" / "widget"
    const val EXTRA_FROM = "dino_from"       // 알에서 깬 공룡 [가운데 x, 발 y, 도트 한 칸] — 화면 좌표 px
    const val EXTRA_TOP = "dino_top"         // 판 위끝 — 화면 좌표 px (배경화면의 미터기 자리)
}
