package com.moling.livingnotebook.ui.theme

import android.content.Context
import android.graphics.Typeface
import android.util.Log
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle

private const val TAG = "MolingInkFont"

data class InkFontStyle(
    val fontFamily: FontFamily,
    val isHandwritingFont: Boolean
)

fun resolveInkFontStyle(context: Context, selectedFontAssetPath: String?): InkFontStyle {
    val loadedTypeface = loadInkTypeface(context, selectedFontAssetPath)
    return InkFontStyle(
        fontFamily = FontFamily(loadedTypeface.typeface),
        isHandwritingFont = loadedTypeface.loadedFromAsset
    )
}

fun resolveInkFontStyle(context: Context): InkFontStyle = resolveInkFontStyle(context, null)

fun resolveInkTypeface(context: Context, selectedFontAssetPath: String?): Typeface {
    return loadInkTypeface(context, selectedFontAssetPath).typeface
}

fun resolveInkTypeface(context: Context): Typeface = resolveInkTypeface(context, null)

private fun loadInkTypeface(context: Context, selectedFontAssetPath: String?): LoadedTypeface {
    val assetPath = selectedFontAssetPath?.takeIf { it.hasUsableAssetPath() }
    if (assetPath != null) {
        val typeface = runCatching {
            Typeface.createFromAsset(context.assets, assetPath)
        }.onFailure { error ->
            Log.w(TAG, "Failed to load asset font: $assetPath; using default font.", error)
        }.getOrNull()

        if (typeface != null) {
            return LoadedTypeface(typeface = typeface, loadedFromAsset = true)
        }
    }
    return LoadedTypeface(typeface = defaultInkTypeface(), loadedFromAsset = false)
}

@Composable
fun rememberInkFontStyle(selectedFontAssetPath: String? = null): InkFontStyle {
    val context = LocalContext.current
    return remember(context, selectedFontAssetPath) {
        resolveInkFontStyle(context, selectedFontAssetPath)
    }
}

@Composable
fun rememberInkFontFamily(selectedFontAssetPath: String? = null): FontFamily =
    rememberInkFontStyle(selectedFontAssetPath).fontFamily

fun inkFontStyleForCompose(isHandwritingFont: Boolean): FontStyle =
    if (isHandwritingFont) FontStyle.Normal else FontStyle.Italic

private fun String?.hasUsableAssetPath(): Boolean =
    !isNullOrBlank() && this != "default"

private fun defaultInkTypeface(): Typeface =
    Typeface.create(Typeface.SERIF, Typeface.ITALIC)

private data class LoadedTypeface(
    val typeface: Typeface,
    val loadedFromAsset: Boolean
)
