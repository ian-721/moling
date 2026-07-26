package com.moling.livingnotebook.data

import androidx.room.withTransaction
import com.moling.livingnotebook.data.local.LocalRequestState
import com.moling.livingnotebook.data.local.MolingDatabase
import com.moling.livingnotebook.data.local.PageEntity
import com.moling.livingnotebook.data.local.StrokeEntity
import com.moling.livingnotebook.data.local.decodeStrokePoints
import com.moling.livingnotebook.data.local.encodeStrokePoints
import com.moling.livingnotebook.drawing.Stroke

data class NotebookRestore(
    val pageId: String,
    val strokes: List<Stroke>,
    val latestReply: String?,
    val latestRequestId: String?,
    val turns: List<RestoredTurn>
)

data class RestoredTurn(
    val recognizedText: String,
    val aiReply: String,
    val timestamp: Long
)

class NotebookRepository(
    private val database: MolingDatabase,
    private val clock: () -> Long = System::currentTimeMillis
) {
    private val dao = database.notebookDao()

    suspend fun ensurePage(pageId: String) {
        val now = clock()
        dao.insertPage(
            PageEntity(
                pageId = pageId,
                createdAt = now,
                updatedAt = now,
                state = "ACTIVE"
            )
        )
    }

    suspend fun restore(pageId: String): NotebookRestore {
        ensurePage(pageId)
        dao.recoverSendingAfterRestart(clock())
        val reply = dao.latestUnabsorbedSuccess(pageId)
        return NotebookRestore(
            pageId = pageId,
            strokes = dao.strokes(pageId).map { entity ->
                Stroke(
                    id = entity.strokeId,
                    points = decodeStrokePoints(entity.pointsJson),
                    color = entity.color,
                    width = entity.width
                )
            },
            latestReply = reply?.aiReply,
            latestRequestId = reply?.requestId,
            turns = dao.turns(pageId).mapNotNull { turn ->
                turn.aiReply?.let {
                    RestoredTurn(turn.recognizedText, it, turn.updatedAt)
                }
            }
        )
    }

    suspend fun persistStroke(pageId: String, stroke: Stroke) {
        database.withTransaction {
            ensurePage(pageId)
            dao.insertStroke(
                StrokeEntity(
                    strokeId = stroke.id,
                    pageId = pageId,
                    strokeOrder = dao.nextStrokeOrder(pageId),
                    pointsJson = encodeStrokePoints(stroke.points),
                    color = stroke.color,
                    width = stroke.width,
                    createdAt = clock(),
                    state = "ACTIVE"
                )
            )
        }
    }

    suspend fun undo(pageId: String): String? = database.withTransaction {
        val latest = dao.latestEditableStroke(pageId) ?: return@withTransaction null
        dao.deleteStroke(latest.strokeId)
        latest.strokeId
    }

    suspend fun clearEditable(pageId: String) {
        dao.deleteEditableStrokes(pageId)
    }
}
