package com.moling.livingnotebook.settings

import androidx.compose.ui.graphics.Color

data class MolingSettings(
    val replyFontSize: ReplyFontSizeOption = ReplyFontSizeOption.Large,
    val selectedFontAssetPath: String? = null,
    val paperBackground: PaperBackgroundOption = PaperBackgroundOption.Parchment,
    val showDebugInfo: Boolean = true
)

enum class ReplyFontSizeOption(
    val label: String,
    val sizeSp: Int,
    val lineHeightSp: Int
) {
    Small("\u5c0f", 28, 40),
    Medium("\u4e2d", 36, 50),
    Large("\u5927", 44, 60),
    ExtraLarge("\u8d85\u5927", 52, 70);

    companion object {
        fun fromStoredValue(value: String?): ReplyFontSizeOption =
            entries.firstOrNull { it.name == value } ?: Large
    }
}

enum class PaperBackgroundOption(
    val label: String,
    val surface: Color,
    val shadow: Color
) {
    Parchment("\u7f8a\u76ae\u7eb8", Color(0xFFF7F1E1), Color(0xFFEADFC2)),
    RiceWhite("\u7c73\u767d\u7eb8", Color(0xFFFBF7EA), Color(0xFFEFE7D2)),
    DebugWhite("\u7eaf\u767d\u8c03\u8bd5\u7eb8", Color(0xFFFFFFFF), Color(0xFFF0F0F0)),
    DarkPaper("\u6697\u8272\u7eb8", Color(0xFF312D26), Color(0xFF211E19));

    companion object {
        fun fromStoredValue(value: String?): PaperBackgroundOption =
            entries.firstOrNull { it.name == value } ?: Parchment
    }
}

data class FontOption(
    val id: String,
    val displayName: String,
    val assetPath: String?
) {
    companion object {
        val Default = FontOption(
            id = "default",
            displayName = "\u9ed8\u8ba4\u5b57\u4f53",
            assetPath = null
        )
    }
}
