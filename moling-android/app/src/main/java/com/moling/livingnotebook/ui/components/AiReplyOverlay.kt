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
import com.moling.livingnotebook.ui.theme.rememberInkFontFamily
import kotlin.random.Random
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private const val CHAR_STAGGER_MS = 45L
private const val REVEAL_DURATION_MS = 260
private const val HOLD_MS = 6000L
private const val FADE_DURATION_MS = 3000
private const val RESIDUAL_ALPHA = 0.15f
private const val RISE_DISTANCE_PX = 14f

private data class CharJitter(val offsetYPx: Float, val rotationDeg: Float)

private fun charJitter(seed: String, index: Int): CharJitter {
    val random = Random(seed.hashCode() * 31 + index)
    val offsetY = random.nextFloat() * 4f - 2f
    val rotation = random.nextFloat() * 6f - 3f
    return CharJitter(offsetY, rotation)
}

/**
 * mock 回复的墨迹浮现：逐字 alpha 淡入 + 极轻微上浮/倾斜，
 * 完整出现后停留一段时间，再整体淡去到一个残留的淡墨透明度，而不是消失。
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun AiReplyOverlay(
    fullText: String,
    revealTrigger: Int,
    modifier: Modifier = Modifier
) {
    if (fullText.isEmpty()) return

    val charAlphas = remember(fullText) { fullText.map { Animatable(0f) } }
    val charRises = remember(fullText) { fullText.map { Animatable(1f) } }
    val jitters = remember(fullText) { fullText.indices.map { index -> charJitter(fullText, index) } }
    val inkFont = rememberInkFontFamily()

    LaunchedEffect(fullText, revealTrigger) {
        charAlphas.forEach { it.snapTo(0f) }
        charRises.forEach { it.snapTo(1f) }

        coroutineScope {
            fullText.indices.forEach { index ->
                launch {
                    delay(index * CHAR_STAGGER_MS)
                    charAlphas[index].animateTo(1f, tween(REVEAL_DURATION_MS, easing = FastOutSlowInEasing))
                }
                launch {
                    delay(index * CHAR_STAGGER_MS)
                    charRises[index].animateTo(0f, tween(REVEAL_DURATION_MS, easing = FastOutSlowInEasing))
                }
            }
        }

        delay(HOLD_MS)

        coroutineScope {
            charAlphas.forEach { anim ->
                launch { anim.animateTo(RESIDUAL_ALPHA, tween(FADE_DURATION_MS, easing = LinearEasing)) }
            }
        }
    }

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
                    fontFamily = inkFont
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
    jitter: CharJitter,
    fontFamily: FontFamily
) {
    Text(
        text = char.toString(),
        fontFamily = fontFamily,
        fontStyle = FontStyle.Italic,
        fontSize = 20.sp,
        lineHeight = 28.sp,
        color = InkPrimary,
        modifier = Modifier.graphicsLayer(
            alpha = alpha,
            translationY = jitter.offsetYPx + rise * RISE_DISTANCE_PX,
            rotationZ = jitter.rotationDeg
        )
    )
}
