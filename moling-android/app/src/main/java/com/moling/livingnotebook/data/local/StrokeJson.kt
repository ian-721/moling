package com.moling.livingnotebook.data.local

import com.moling.livingnotebook.drawing.StrokePoint
import org.json.JSONArray
import org.json.JSONObject

fun encodeStrokePoints(points: List<StrokePoint>): String =
    JSONArray().apply {
        points.forEach { point ->
            put(
                JSONObject().apply {
                    put("x", point.x.toDouble())
                    put("y", point.y.toDouble())
                    put("timestamp", point.timestamp)
                    put("pressure", point.pressure.toDouble())
                }
            )
        }
    }.toString()

fun decodeStrokePoints(value: String): List<StrokePoint> {
    val array = JSONArray(value)
    return buildList {
        for (index in 0 until array.length()) {
            val point = array.getJSONObject(index)
            add(
                StrokePoint(
                    x = point.getDouble("x").toFloat(),
                    y = point.getDouble("y").toFloat(),
                    timestamp = point.getLong("timestamp"),
                    pressure = point.getDouble("pressure").toFloat()
                )
            )
        }
    }
}

fun encodeIds(ids: Collection<String>): String =
    JSONArray().apply { ids.forEach(::put) }.toString()

fun decodeIds(value: String): List<String> {
    val array = JSONArray(value)
    return buildList {
        for (index in 0 until array.length()) add(array.getString(index))
    }
}
