package com.moling.livingnotebook.ui.components

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private val ErrorInkColor = Color(0xFF7A3B2E)

/**
 * 请求失败时的温和提示，走纸边小字风格，不用 Toast/弹窗/气泡。
 */
@Composable
fun ErrorHint(
    message: String?,
    modifier: Modifier = Modifier
) {
    AnimatedVisibility(
        visible = message != null,
        enter = fadeIn(),
        exit = fadeOut(),
        modifier = modifier
    ) {
        Text(
            text = message.orEmpty(),
            color = ErrorInkColor,
            fontStyle = FontStyle.Italic,
            fontSize = 15.sp,
            modifier = Modifier.padding(horizontal = 28.dp, vertical = 8.dp)
        )
    }
}
