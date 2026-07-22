package com.moling.livingnotebook.settings

import android.content.res.AssetManager
import android.util.Log
import java.io.IOException

private const val TAG = "AssetFontScanner"
private const val FONT_ROOT = "fonts"

object AssetFontScanner {
    fun scan(assetManager: AssetManager): List<FontOption> {
        val fontPaths = mutableListOf<String>()
        runCatching {
            scanPath(assetManager, FONT_ROOT, fontPaths)
        }.onFailure { error ->
            Log.w(TAG, "Failed to scan assets/fonts; using default font only.", error)
        }

        if (fontPaths.isEmpty()) return listOf(FontOption.Default)

        val sortedPaths = fontPaths.distinct().sorted()
        val folderCounts = sortedPaths.groupingBy { it.parentFolderName() }.eachCount()
        val options = sortedPaths.map { path ->
            val folderName = path.parentFolderName()
            val fileName = path.fileNameWithoutExtension()
            val displayName = if ((folderCounts[folderName] ?: 0) > 1) {
                "$folderName / $fileName"
            } else {
                folderName.takeIf { it.isNotBlank() && it != FONT_ROOT } ?: fileName
            }
            FontOption(
                id = path,
                displayName = displayName,
                assetPath = path
            )
        }

        return listOf(FontOption.Default) + options
    }

    private fun scanPath(
        assetManager: AssetManager,
        path: String,
        fontPaths: MutableList<String>
    ) {
        val children = try {
            assetManager.list(path).orEmpty()
        } catch (error: IOException) {
            emptyArray()
        }

        if (children.isEmpty()) {
            if (path.isFontFile()) {
                fontPaths.add(path)
            }
            return
        }

        children.forEach { child ->
            scanPath(assetManager, "$path/$child", fontPaths)
        }
    }

    private fun String.isFontFile(): Boolean {
        val lower = lowercase()
        return lower.endsWith(".ttf") || lower.endsWith(".otf")
    }

    private fun String.parentFolderName(): String =
        substringBeforeLast('/', missingDelimiterValue = FONT_ROOT)
            .substringAfterLast('/', missingDelimiterValue = FONT_ROOT)

    private fun String.fileNameWithoutExtension(): String =
        substringAfterLast('/')
            .substringBeforeLast('.', missingDelimiterValue = substringAfterLast('/'))
}
