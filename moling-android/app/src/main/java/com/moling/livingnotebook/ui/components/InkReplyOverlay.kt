package com.moling.livingnotebook.ui.components

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.moling.livingnotebook.ui.theme.InkPrimary
import com.moling.livingnotebook.ui.theme.inkFontStyleForCompose
import com.moling.livingnotebook.ui.theme.rememberInkFontStyle
import kotlin.random.Random
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private const val CHAR_STAGGER_MS = 110L
private const val REVEAL_DURATION_MS = 520
private const val HOLD_MS = 6500L
private const val FADE_DURATION_MS = 3200
private const val RESIDUAL_ALPHA = 0.12f
private const val DISMISS_DURATION_MS = 480
private const val RISE_DISTANCE_PX = 12f
private const val START_SCALE = 0.96f

private data class InkCharJitter(
    val offsetYPx: Float,
    val rotationDeg: Float,
    val delayJitterMs: Long,
    val darkenBias: Float
)

private fun inkCharJitter(seed: String, index: Int): InkCharJitter {
    val random = Random(seed.hashCode() * 31 + index * 17)
    return InkCharJitter(
        offsetYPx = random.nextFloat() * 6f - 3f,
        rotationDeg = random.nextFloat() * 6f - 3f,
        delayJitterMs = (random.nextFloat() * 40f).toLong(),
        darkenBias = 0.85f + random.nextFloat() * 0.15f
    )
}

/**
 * Ink-style reply reveal animation. The font is loaded from the selected
 * assets/fonts path, with a safe Serif Italic fallback.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun InkReplyOverlay(
    fullText: String,
    revealTrigger: Int,
    dismissTrigger: Int,
    fontSizeSp: Int,
    lineHeightSp: Int,
    selectedFontAssetPath: String?,
    modifier: Modifier = Modifier
) {
    if (fullText.isEmpty()) return

    val charAlphas = remember(fullText, revealTrigger) { fullText.map { Animatable(0f) } }
    val charRises = remember(fullText, revealTrigger) { fullText.map { Animatable(1f) } }
    val jitters = remember(fullText) { fullText.indices.map { inkCharJitter(fullText, it) } }
    val inkFontStyle = rememberInkFontStyle(selectedFontAssetPath)
    val composeFontStyle = inkFontStyleForCompose(inkFontStyle.isHandwritingFont)

    LaunchedEffect(fullText, revealTrigger) {
        charAlphas.forEach { it.snapTo(0f) }
        charRises.forEach { it.snapTo(1f) }

        coroutineScope {
            fullText.indices.forEach { index ->
                val jitter = jitters[index]
                launch {
                    delay(index * CHAR_STAGGER_MS + jitter.delayJitterMs)
                    charAlphas[index].animateTo(
                        targetValue = jitter.darkenBias,
                        animationSpec = tween(REVEAL_DURATION_MS, easing = FastOutSlowInEasing)
                    )
                }
                launch {
                    delay(index * CHAR_STAGGER_MS + jitter.delayJitterMs)
                    charRises[index].animateTo(
                        targetValue = 0f,
                        animationSpec = tween(REVEAL_DURATION_MS, easing = FastOutSlowInEasing)
                    )
                }
            }
        }

        delay(HOLD_MS)

        coroutineScope {
            charAlphas.forEach { anim ->
                launch {
                    anim.animateTo(RESIDUAL_ALPHA, tween(FADE_DURATION_MS, easing = LinearEasing))
                }
            }
        }
    }

    LaunchedEffect(dismissTrigger) {
        if (dismissTrigger > 0) {
            coroutineScope {
                charAlphas.forEach { anim ->
                    launch {
                        anim.animateTo(0f, tween(DISMISS_DURATION_MS, easing = LinearEasing))
                    }
                }
            }
        }
    }

    if (charAlphas.all { it.value <= 0.005f } && dismissTrigger > 0) return

    Box(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 28.dp, vertical = 24.dp)
    ) {
        FlowRow(modifier = Modifier.fillMaxWidth()) {
            fullText.forEachIndexed { index, char ->
                InkChar(
                    char = char,
                    alpha = charAlphas[index].value,
                    rise = charRises[index].value,
                    jitter = jitters[index],
                    fontFamily = inkFontStyle.fontFamily,
                    fontStyle = composeFontStyle,
                    fontSizeSp = fontSizeSp,
                    lineHeightSp = lineHeightSp
                )
            }
        }
    }
}

@Composable
private fun InkChar(
    char: Char,
    alpha: Float,
    rise: Float,
    jitter: InkCharJitter,
    fontFamily: FontFamily,
    fontStyle: FontStyle,
    fontSizeSp: Int,
    lineHeightSp: Int
) {
    val scale = START_SCALE + (1f - rise) * (1f - START_SCALE)
    Text(
        text = char.toString(),
        fontFamily = fontFamily,
        fontStyle = fontStyle,
        fontSize = fontSizeSp.sp,
        lineHeight = lineHeightSp.sp,
        color = InkPrimary,
        modifier = Modifier.graphicsLayer(
            alpha = alpha,
            translationY = jitter.offsetYPx + rise * RISE_DISTANCE_PX,
            rotationZ = jitter.rotationDeg * rise,
            scaleX = scale,
            scaleY = scale
        )
    )
}
