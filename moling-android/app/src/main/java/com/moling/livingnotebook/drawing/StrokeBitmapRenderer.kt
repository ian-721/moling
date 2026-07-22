package com.moling.livingnotebook.drawing

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Path
import android.util.Base64
import java.io.ByteArrayOutputStream

private const val PAPER_BACKGROUND_COLOR = 0xFFF7F1E1.toInt()

/**
 * 直接用已有的 strokes 数据在离屏 Bitmap 上重绘一张纯纸底的图，
 * 而不是截图 Compose 树，避免把阴影/圆角/AI 回复文字一起截进去干扰识别。
 */
fun renderStrokesToBitmap(strokes: List<Stroke>, widthPx: Int, heightPx: Int): Bitmap {
    val safeWidth = widthPx.coerceAtLeast(1)
    val safeHeight = heightPx.coerceAtLeast(1)

    val bitmap = Bitmap.createBitmap(safeWidth, safeHeight, Bitmap.Config.ARGB_8888)
    val canvas = Canvas(bitmap)
    canvas.drawColor(PAPER_BACKGROUND_COLOR)

    val strokePaint = Paint().apply {
        isAntiAlias = true
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
        strokeJoin = Paint.Join.ROUND
    }
    val dotPaint = Paint().apply {
        isAntiAlias = true
        style = Paint.Style.FILL
    }

    strokes.forEach { stroke ->
        val points = stroke.points
        if (points.isEmpty()) return@forEach
        val color = stroke.color.toInt()

        if (points.size == 1) {
            dotPaint.color = color
            canvas.drawCircle(points[0].x, points[0].y, stroke.width / 2f, dotPaint)
            return@forEach
        }

        strokePaint.color = color
        strokePaint.strokeWidth = stroke.width
        val path = Path().apply {
            moveTo(points[0].x, points[0].y)
            for (i in 1 until points.size) {
                lineTo(points[i].x, points[i].y)
            }
        }
        canvas.drawPath(path, strokePaint)
    }

    return bitmap
}

fun Bitmap.toPngBase64(): String {
    val stream = ByteArrayOutputStream()
    compress(Bitmap.CompressFormat.PNG, 100, stream)
    return Base64.encodeToString(stream.toByteArray(), Base64.NO_WRAP)
}
