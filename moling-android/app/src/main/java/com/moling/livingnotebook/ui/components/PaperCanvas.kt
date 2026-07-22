package com.moling.livingnotebook.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke as DrawStroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import com.moling.livingnotebook.drawing.Stroke
import com.moling.livingnotebook.settings.PaperBackgroundOption
import com.moling.livingnotebook.viewmodel.NotebookViewModel

private val PaperShape = RoundedCornerShape(20.dp)

@Composable
fun PaperCanvas(
    viewModel: NotebookViewModel,
    modifier: Modifier = Modifier,
    strokeAlpha: Float = 1f,
    paperBackground: PaperBackgroundOption = PaperBackgroundOption.Parchment,
    onSizeChanged: (IntSize) -> Unit = {}
) {
    val paperBrush = Brush.verticalGradient(
        colors = listOf(paperBackground.surface, paperBackground.shadow)
    )

    Canvas(
        modifier = modifier
            .fillMaxSize()
            .shadow(elevation = 6.dp, shape = PaperShape, clip = false)
            .clip(PaperShape)
            .background(paperBrush)
            .onSizeChanged(onSizeChanged)
            .pointerInput(viewModel) {
                awaitEachGesture {
                    val down = awaitFirstDown(requireUnconsumed = false)
                    viewModel.beginStroke(down.position.x, down.position.y)
                    down.consume()
                    val pointerId = down.id
                    while (true) {
                        val event = awaitPointerEvent()
                        val change = event.changes.firstOrNull { it.id == pointerId } ?: break
                        if (!change.pressed) {
                            change.consume()
                            break
                        }
                        viewModel.appendPoint(change.position.x, change.position.y)
                        change.consume()
                    }
                    viewModel.endStroke()
                }
            }
    ) {
        viewModel.strokes.forEach { stroke -> drawInkStroke(stroke, strokeAlpha) }
        viewModel.currentStroke?.let { drawInkStroke(it, strokeAlpha) }
    }
}

private fun DrawScope.drawInkStroke(stroke: Stroke, alpha: Float = 1f) {
    val points = stroke.points
    if (points.isEmpty()) return
    val inkColor = Color(stroke.color).copy(alpha = alpha.coerceIn(0f, 1f))

    if (points.size == 1) {
        drawCircle(
            color = inkColor,
            radius = stroke.width / 2f,
            center = Offset(points[0].x, points[0].y)
        )
        return
    }

    val path = Path().apply {
        moveTo(points[0].x, points[0].y)
        for (i in 1 until points.size) {
            lineTo(points[i].x, points[i].y)
        }
    }

    drawPath(
        path = path,
        color = inkColor,
        style = DrawStroke(
            width = stroke.width,
            cap = StrokeCap.Round,
            join = StrokeJoin.Round
        )
    )
}
