package com.moling.livingnotebook.drawing

data class StrokePoint(
    val x: Float,
    val y: Float,
    val timestamp: Long = System.currentTimeMillis(),
    val pressure: Float = 1f
)

data class Stroke(
    val id: String,
    val points: List<StrokePoint> = emptyList(),
    val color: Long = 0xFF2A2A33,
    val width: Float = 6f
)
