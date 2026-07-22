package com.moling.livingnotebook.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalContext

private val DarkColorScheme = darkColorScheme(
    primary = ParchmentInk,
    secondary = ParchmentInk,
    tertiary = ParchmentInk,
    background = DeskDark,
    surface = DeskDark,
    onBackground = ParchmentInk,
    onSurface = ParchmentInk
)

private val LightColorScheme = lightColorScheme(
    primary = InkPrimary,
    secondary = InkFaded,
    tertiary = InkFaded,
    background = DeskLight,
    surface = DeskLight,
    onBackground = InkPrimary,
    onSurface = InkPrimary
)

@Composable
fun MolingTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = false,
    content: @Composable () -> Unit
) {
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }

        darkTheme -> DarkColorScheme
        else -> LightColorScheme
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        content = content
    )
}
