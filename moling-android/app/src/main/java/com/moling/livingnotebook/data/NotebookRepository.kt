package com.moling.livingnotebook.data

import androidx.room.withTransaction
import com.moling.livingnotebook.data.local.LocalRequestState
import com.moling.livingnotebook.data.local.MolingDatabase
import com.moling.livingnotebook.data.local.PageEntity
import com.moling.livingnotebook.data.local.StrokeEntity
import com.moling.livingnotebook.data.local.decodeIds
import com.moling.livingnotebook.data.local.decodeStrokePoints
import com.moling.livingnotebook.data.local.encodeStrokePoints
import com.moling.livingnotebook.drawing.Stroke
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async

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
    private val clock: () -> Long = System::currentTimeMillis,
    private val beforeStrokeWrite: suspend () -> Unit = {}
) {
    private val dao = database.notebookDao()
    private val persistenceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val writeLock = Any()
    private var writeTail: Deferred<Result<Unit>>? = null

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
        database.withTransaction {
            dao.sendingOutbox().forEach { outbox ->
                val strokeIds = decodeIds(outbox.strokeIdsJson)
                if (strokeIds.isNotEmpty()) {
                    dao.updateStrokeState(strokeIds, "ACTIVE")
                }
                val replayable = outbox.isReplayable
                dao.turnForRequest(outbox.requestId)?.let { turn ->
                    dao.upsertTurn(
                        turn.copy(
                            state = if (replayable) {
                                LocalRequestState.RETRYABLE_FAILED.name
                            } else {
                                LocalRequestState.PERMANENT_FAILED.name
                            },
                            updatedAt = clock()
                        )
                    )
                }
                dao.upsertOutbox(
                    outbox.copy(
                        state = if (replayable) {
                            LocalRequestState.RETRYABLE_FAILED.name
                        } else {
                            LocalRequestState.PERMANENT_FAILED.name
                        },
                        lastErrorCategory = if (replayable) {
                            "process_restarted"
                        } else {
                            "non_replayable_payload_interrupted"
                        },
                        nextRetryAt = if (replayable) clock() else null,
                        updatedAt = clock()
                    )
                )
            }
        }
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
        beforeStrokeWrite()
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

    fun enqueueStroke(pageId: String, stroke: Stroke): Deferred<Result<Unit>> =
        synchronized(writeLock) {
            val previous = writeTail
            persistenceScope.async {
                val previousResult = previous?.await()
                if (previousResult?.isFailure == true) {
                    previousResult
                } else {
                    runCatching { persistStroke(pageId, stroke) }
                }
            }.also { writeTail = it }
        }

    suspend fun awaitPendingStrokeWrites(): Result<Unit> {
        val pending = synchronized(writeLock) { writeTail }
        return pending?.await() ?: Result.success(Unit)
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
