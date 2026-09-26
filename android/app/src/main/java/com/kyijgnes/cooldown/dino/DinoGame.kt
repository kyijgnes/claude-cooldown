package com.kyijgnes.cooldown.dino

import kotlin.random.Random
import com.kyijgnes.cooldown.dino.DinoSpec as S

/**
 * 공룡 점프 규칙 — `pc/cooldown_dino.py` 의 `Game` 을 **손으로 옮긴 것**이다(크롬 공룡 게임).
 * 그림표·수치는 생성기가 뽑은 `DinoSpec` 을 쓰고, 여기는 움직임만 맡는다.
 * ★ **규칙을 고치면 PC(`cooldown_dino.py`)도 같이 고친다.** 둘이 어긋나면 같은 게임이 아니다.
 *
 * 상태는 셋 — `ready`(기다림) · `run`(달리는 중) · `over`(부딪힘).
 * `step()` 한 번이 1/60초. 그리는 쪽(`DinoView`)은 흐른 시간만큼 `step` 을 부른다.
 * 폰은 `touch = true` — 새가 두 높이뿐이다(크롬도 휴대폰에선 그렇다. 숙일 단추가 없어서).
 */
class DinoGame(seed: Long? = null, best: Int = 0, touch: Boolean = true) {

    private val rng = if (seed != null) Random(seed) else Random.Default
    var best = best
        private set
    private val lifts = if (touch) S.BIRD_LIFTS_TOUCH else S.BIRD_LIFTS

    var t = 0
        private set
    var state = "ready"
        private set
    var speed = S.SPEED0
        private set
    private var distance = 0f
    var runT = 0
        private set
    var h = 0f                     // 공룡이 땅에서 뜬 높이 (위가 +)
        private set
    private var vy = 0f
    var jumping = false
        private set
    private var reachedMin = false
    private var fastDrop = false
    private var holding = false
    private var down = false
    var ducking = false
        private set
    val obstacles = ArrayList<Obstacle>()
    private val history = ArrayList<String>()
    var overT = 0
        private set
    private var flash = 0
    private var flashScore = 0
    var night = 0
        private set
    private var blink = 0
    private var nextBlink = 0
    var newBest = false
        private set
    /** 구름 [x, y] */
    val clouds = ArrayList<FloatArray>()
    private var cloudGap = 0f
    /** 땅의 자갈 [x, 땅 아래 깊이, 폭] — 흘러가다 왼쪽으로 빠지면 오른쪽에서 다시 나온다. */
    val pebbles = ArrayList<FloatArray>()

    init {
        reset()
        state = "ready"
    }

    private fun rnd(a: Float, b: Float) = a + (b - a) * rng.nextFloat()
    private fun rndInt(a: Int, b: Int) = rng.nextInt(a, b + 1)      // 양끝 포함 (파이썬 randint)
    private fun <T> pick(xs: List<T>) = xs[rng.nextInt(xs.size)]

    // -------------------------------------------------- 판 새로
    private fun reset() {
        state = "run"
        speed = S.SPEED0
        distance = 0f
        runT = 0
        h = 0f
        vy = 0f
        jumping = false
        reachedMin = false
        fastDrop = false
        holding = false
        down = false
        ducking = false
        obstacles.clear()
        history.clear()
        overT = 0
        flash = 0
        flashScore = 0
        night = 0
        blink = 0
        nextBlink = rndInt(S.BLINK_EVERY[0], S.BLINK_EVERY[1])
        newBest = false
        clouds.clear()
        clouds.add(floatArrayOf(rnd(S.W * 0.3f, S.W), rnd(S.CLOUD_SKY[0].toFloat(), S.CLOUD_SKY[1].toFloat())))
        cloudGap = rnd(S.CLOUD_GAP[0].toFloat(), S.CLOUD_GAP[1].toFloat())
        pebbles.clear()
        repeat(18) {
            pebbles.add(floatArrayOf(rnd(0f, S.W), pick(DEPTHS), pick(WIDTHS)))
        }
    }

    // -------------------------------------------------- 누르기
    fun pressJump() {
        when (state) {
            "ready" -> { reset(); jump() }             // 첫 누르기 — 뛰어오르며 출발
            "run" -> if (!jumping && !ducking) jump()
            "over" -> if (overT >= S.OVER_WAIT) reset()   // 다시 하기 — 뛰지 않고 그냥 달린다
        }
        holding = true
    }

    fun releaseJump() {
        holding = false
        if (jumping) endJump()
    }

    fun pressDuck() {
        down = true
        if (state != "run") return
        if (jumping) {                // 공중이면 빨리 떨어진다 (내려앉으면 그대로 숙인다)
            if (!fastDrop) { fastDrop = true; vy = -1f }
        } else {
            ducking = true
        }
    }

    fun releaseDuck() {
        down = false
        ducking = false
        fastDrop = false
    }

    private fun jump() {
        jumping = true
        reachedMin = false
        fastDrop = false
        vy = S.JUMP_V + speed / 10f
    }

    private fun endJump() {
        if (reachedMin && vy > S.DROP_V) vy = S.DROP_V
    }

    // -------------------------------------------------- 한 걸음
    fun step() {
        t++
        if (state == "ready") { stepBlink(); return }
        if (state == "over") { overT++; return }
        runT++
        if (jumping) stepJump()
        if (speed < S.SPEED_MAX) speed = minOf(S.SPEED_MAX, speed + S.ACCEL)
        distance += speed
        stepObstacles()
        stepScenery()
        val before = flashScore
        flashScore = score / S.FLASH_EVERY * S.FLASH_EVERY
        if (flashScore > before && flashScore > 0) {
            flash = S.FLASH_FRAMES
            if (flashScore % S.NIGHT_EVERY == 0) night = S.NIGHT_FRAMES
        } else if (flash > 0) {
            flash--
        }
        if (night > 0) night--
        if (collides()) crash()
    }

    private fun stepJump() {
        h += vy * (if (fastDrop) S.FAST_DROP else 1)
        vy -= S.GRAVITY
        if (h > S.MIN_JUMP || fastDrop) reachedMin = true
        if (h > S.MAX_JUMP || fastDrop) endJump() else if (!holding) endJump()
        if (h <= 0f) {                // 내려앉았다 — ↓ 를 누른 채면 그대로 숙인다
            h = 0f
            vy = 0f
            jumping = false
            fastDrop = false
            ducking = down
        }
    }

    private fun stepBlink() {
        if (blink > 0) { blink--; return }
        nextBlink--
        if (nextBlink <= 0) {
            blink = 8
            nextBlink = rndInt(S.BLINK_EVERY[0], S.BLINK_EVERY[1])
        }
    }

    private fun stepObstacles() {
        for (ob in obstacles) {
            ob.x -= speed + ob.wobble
            if (ob.kind == "bird" && t % S.FLAP_BEAT == 0) ob.frame = ob.frame xor 1
        }
        obstacles.removeAll { it.x + it.w <= 0f }
        if (runT < S.CLEAR_FRAMES) return
        val last = obstacles.lastOrNull()
        if (last == null) {
            addObstacle()
        } else if (!last.follow && last.x + last.w + last.gap < S.W) {
            last.follow = true
            addObstacle()
        }
    }

    private fun addObstacle() {
        val kinds = S.KINDS.filter { speed >= it.value.minSpeed }.keys.toList()
        var kind = pick(kinds)
        for (i in 0 until 10) {
            kind = pick(kinds)
            val recent = history.takeLast(S.MAX_DUP)
            if (recent.size == S.MAX_DUP && recent.all { it == kind }) continue
            break
        }
        val spec = S.KINDS.getValue(kind)
        val count = if (speed > spec.multi) rndInt(1, S.MAX_GROUP) else 1
        var lift = 0
        var wobble = 0f
        if (kind == "bird") {
            lift = lifts[rng.nextInt(lifts.size)]
            wobble = if (rng.nextBoolean()) -S.BIRD_WOBBLE else S.BIRD_WOBBLE
        }
        val oneW = Art.width(spec.art[0])
        val minGap = Math.round(oneW * count * speed + spec.minGap * S.GAP_COEF)
        val gap = rndInt(minGap, Math.round(minGap * S.GAP_MAX))
        obstacles.add(Obstacle(kind, S.W, count, lift, wobble, gap))
        history.add(kind)
        while (history.size > S.MAX_DUP) history.removeAt(0)
    }

    private fun stepScenery() {
        val drift = speed * S.CLOUD_SPEED
        for (c in clouds) c[0] -= drift
        val cw = Art.width(S.CLOUD)
        clouds.removeAll { it[0] + cw <= 0f }
        val last = clouds.lastOrNull()
        if (clouds.size < S.CLOUD_MAX && (last == null || last[0] < S.W - cloudGap)) {
            clouds.add(floatArrayOf(S.W, rnd(S.CLOUD_SKY[0].toFloat(), S.CLOUD_SKY[1].toFloat())))
            cloudGap = rnd(S.CLOUD_GAP[0].toFloat(), S.CLOUD_GAP[1].toFloat())
        }
        for (p in pebbles) {
            p[0] -= speed
            if (p[0] + p[2] < 0f) {
                p[0] += S.W + rnd(0f, 40f)
                p[1] = pick(DEPTHS)
                p[2] = pick(WIDTHS)
            }
        }
    }

    // -------------------------------------------------- 부딪힘
    /** 도트 칸끼리 겹치나 — 그림 테두리가 겹칠 때만 칸을 본다. */
    private fun collides(): Boolean {
        val rows = S.POSES.getValue(pose)
        val dx0 = S.DINO_X
        val dy0 = dinoY
        val dw = Art.width(rows)
        val dh = Art.height(rows)
        val mine = Art.runs(rows, false)
        for (ob in obstacles) {
            if (ob.x >= dx0 + dw || ob.x + ob.w <= dx0 || ob.y >= dy0 + dh || ob.y + ob.h <= dy0) continue
            for (i in 0 until ob.count) {
                val art = ob.art()
                val ox0 = ob.x + i * ob.oneW
                val theirs = Art.runs(art, i % 2 == 1)
                var a = 0
                while (a < theirs.size) {
                    val ox = ox0 + theirs[a]; val oy = ob.y + theirs[a + 1]
                    val ow = theirs[a + 2]; val oh = theirs[a + 3]
                    var b = 0
                    while (b < mine.size) {
                        val mx = dx0 + mine[b]; val my = dy0 + mine[b + 1]
                        if (ox < mx + mine[b + 2] && mx < ox + ow && oy < my + mine[b + 3] && my < oy + oh) {
                            return true
                        }
                        b += 4
                    }
                    a += 4
                }
            }
        }
        return false
    }

    private fun crash() {
        state = "over"
        overT = 0
        jumping = false
        holding = false
        ducking = false
        fastDrop = false
        if (score > best) {
            best = score
            newBest = true
        }
    }

    // -------------------------------------------------- 그리는 쪽이 읽는 것
    val score: Int get() = (distance * S.SCORE_COEF).toInt()

    /** 지금 자세 — `DinoSpec.POSES` 의 열쇠. */
    val pose: String
        get() {
            if (state != "run" || jumping) return "stand"
            val beat = (runT / S.RUN_BEAT) % 2
            if (ducking) return if (beat == 1) "duck2" else "duck1"
            return if (beat == 1) "run2" else "run1"
        }

    val eye: String
        get() = when {
            state == "over" -> "dead"
            state == "ready" && blink > 0 -> "blink"
            else -> "open"
        }

    /** 공룡 그림 위끝. */
    val dinoY: Float get() = S.GROUND - h - Art.height(S.POSES.getValue(pose))

    /** 화면에 적을 점수 — 100점을 넘길 때마다 그 숫자에서 반짝인다. */
    val shownScore: Int get() = if (flash > 0) flashScore else score

    /** 반짝이는 동안 켜졌다 꺼졌다 한다 (1/4초마다). */
    val scoreVisible: Boolean get() = flash <= 0 || (flash / 15) % 2 == 0

    /** 미리보기·테스트용 — 지금 자리에서 곧바로 부딪힌 것으로 한다. */
    fun crashForPreview() { if (state == "run") crash() }

    private companion object {
        val DEPTHS = listOf(2f, 4f, 6f)
        val WIDTHS = listOf(2f, 2f, 4f)
    }
}

/** 판 위의 장애물 하나 (선인장 여럿이 붙은 무리도 하나다). */
class Obstacle(
    val kind: String, var x: Float, val count: Int, val lift: Int, val wobble: Float, val gap: Int,
) {
    var frame = 0                 // 새 날갯짓 (0/1)
    var follow = false            // 다음 장애물을 이미 불렀나
    private val arts = S.KINDS.getValue(kind).art
    val oneW = Art.width(arts[0])
    val h = Art.height(arts[0])
    val w = oneW * count
    /** 그림 위끝 */
    val y: Float get() = S.GROUND - lift - h
    fun art(): Array<String> = arts[frame % arts.size]
}

/** 도트 표 → 줄마다 이어진 칸 덩이 `[x, y, w, h, ...]` (px). 그리기와 충돌이 같이 쓴다. */
object Art {
    private val cache = HashMap<Pair<Array<String>, Boolean>, FloatArray>()

    fun width(rows: Array<String>) = rows.maxOf { it.length } * S.U
    fun height(rows: Array<String>) = rows.size * S.U

    fun runs(rows: Array<String>, flip: Boolean): FloatArray = cache.getOrPut(rows to flip) {
        val out = ArrayList<Float>()
        val width = rows.maxOf { it.length }
        for ((r, raw) in rows.withIndex()) {
            val padded = raw.padEnd(width, '.')
            val line = if (flip) padded.reversed() else padded
            var c = 0
            while (c < width) {
                if (line[c] != '#') { c++; continue }
                var n = 1
                while (c + n < width && line[c + n] == '#') n++
                out += listOf(c * S.U, r * S.U, n * S.U, S.U)
                c += n
            }
        }
        out.toFloatArray()
    }
}
