package com.moling.livingnotebook.data

import androidx.room.withTransaction
import com.moling.livingnotebook.data.local.LocalRequestState
import com.moling.livingnotebook.data.local.MolingDatabase
import com.moling.livingnotebook.data.local.NotebookTurnEntity
import com.moling.livingnotebook.data.local.ReplyOutboxEntity
import com.moling.livingnotebook.data.local.decodeIds
import com.moling.livingnotebook.data.local.encodeIds
import java.util.UUID

data class PendingReply(
    val requestId: String,
    val pageId: String,
    val strokeIds: List<String>,
    val recognizedText: String,
    val recognitionSource: String,
    val recentContext: String?,
    val deepMode: Boolean,
    val payloadFrozen: Boolean,
    val isReplayable: Boolean,
    val state: LocalRequestState,
    val attemptCount: Int
)

class ReplyOutboxRepository(
    private val database: MolingDatabase,
    private val clock: () -> Long = System::currentTimeMillis
) {
    private val dao = database.notebookDao()

    suspend fun createSnapshot(
        requestId: String,
        pageId: String,
        strokeIds: List<String>
    ) {
        require(strokeIds.isNotEmpty()) { "reply snapshot requires strokes" }
        val now = clock()
        database.withTransaction {
            val persisted = dao.snapshotStrokes(pageId, strokeIds)
            require(persisted.size == strokeIds.size) {
                "reply snapshot contains strokes that are not persisted"
            }
            require(persisted.all { it.state == "ACTIVE" }) {
                "reply snapshot contains non-editable strokes"
            }
            require(persisted.map { it.strokeId }.toSet() == strokeIds.toSet()) {
                "reply snapshot stroke identity mismatch"
            }
            dao.updateStrokeState(strokeIds, "SENDING")
            dao.upsertTurn(
                NotebookTurnEntity(
                    turnId = UUID.randomUUID().toString(),
                    pageId = pageId,
                    requestId = requestId,
                    recognizedText = "",
                    recognitionSource = "",
                    aiReply = null,
                    replyMode = null,
                    safetyLevel = null,
                    state = LocalRequestState.RECOGNIZING.name,
                    createdAt = now,
                    updatedAt = now
                )
            )
            dao.upsertOutbox(
                ReplyOutboxEntity(
                    requestId = requestId,
                    pageId = pageId,
                    strokeIdsJson = encodeIds(strokeIds),
                    state = LocalRequestState.RECOGNIZING.name,
                    attemptCount = 0,
                    lastErrorCategory = null,
                    nextRetryAt = null,
                    recognizedText = "",
                    recognitionSource = "",
                    recentContext = null,
                    deepMode = false,
                    payloadFrozen = false,
                    isReplayable = true,
                    createdAt = now,
                    updatedAt = now
                )
            )
        }
    }

    suspend fun markRecognized(
        requestId: String,
        text: String,
        source: String,
        recentContext: String?,
        deepMode: Boolean
    ): PendingReply {
        database.withTransaction {
            val turn = requireNotNull(dao.turnForRequest(requestId))
            val outbox = requireNotNull(dao.outbox(requestId))
            val now = clock()
            dao.upsertTurn(
                turn.copy(
                    recognizedText = text,
                    recognitionSource = source,
                    state = LocalRequestState.READY_TO_SEND.name,
                    updatedAt = now
                )
            )
            dao.upsertOutbox(
                outbox.copy(
                    state = LocalRequestState.READY_TO_SEND.name,
                    recognizedText = text,
                    recognitionSource = source,
                    recentContext = recentContext,
                    deepMode = deepMode,
                    payloadFrozen = true,
                    isReplayable = true,
                    updatedAt = now
                )
            )
        }
        return requireNotNull(pendingForRequest(requestId))
    }

    suspend fun markVisionNonReplayable(requestId: String) {
        database.withTransaction {
            val outbox = requireNotNull(dao.outbox(requestId))
            dao.upsertOutbox(
                outbox.copy(
                    payloadFrozen = true,
                    isReplayable = false,
                    updatedAt = clock()
                )
            )
        }
    }

    suspend fun markSending(requestId: String) {
        val outbox = requireNotNull(dao.outbox(requestId))
        database.withTransaction {
            dao.updateStrokeState(decodeIds(outbox.strokeIdsJson), "SENDING")
            dao.upsertOutbox(
                outbox.copy(
                    state = LocalRequestState.SENDING.name,
                    attemptCount = outbox.attemptCount + 1,
                    lastErrorCategory = null,
                    updatedAt = clock()
                )
            )
        }
    }

    suspend fun markSucceeded(
        requestId: String,
        aiReply: String,
        replyMode: String,
        safetyLevel: String
    ) {
        database.withTransaction {
            val turn = requireNotNull(dao.turnForRequest(requestId))
            val outbox = requireNotNull(dao.outbox(requestId))
            val now = clock()
            // Persist the response before the ViewModel exposes it to the ink overlay.
            dao.upsertTurn(
                turn.copy(
                    aiReply = aiReply,
                    replyMode = replyMode,
                    safetyLevel = safetyLevel,
                    state = LocalRequestState.SUCCEEDED.name,
                    updatedAt = now
                )
            )
            dao.upsertOutbox(
                outbox.copy(
                    state = LocalRequestState.SUCCEEDED.name,
                    updatedAt = now
                )
            )
        }
    }

    suspend fun markFailure(
        requestId: String,
        errorCategory: String,
        retryable: Boolean
    ) {
        database.withTransaction {
            val outbox = requireNotNull(dao.outbox(requestId))
            val turn = requireNotNull(dao.turnForRequest(requestId))
            val state = if (retryable) {
                LocalRequestState.RETRYABLE_FAILED
            } else {
                LocalRequestState.PERMANENT_FAILED
            }
            val now = clock()
            dao.updateStrokeState(decodeIds(outbox.strokeIdsJson), "ACTIVE")
            dao.upsertTurn(turn.copy(state = state.name, updatedAt = now))
            dao.upsertOutbox(
                outbox.copy(
                    state = state.name,
                    lastErrorCategory = errorCategory,
                    nextRetryAt = if (retryable) now else null,
                    updatedAt = now
                )
            )
        }
    }

    suspend fun pending(pageId: String): PendingReply? {
        val outbox = dao.pendingOutbox(pageId) ?: return null
        return PendingReply(
            requestId = outbox.requestId,
            pageId = outbox.pageId,
            strokeIds = decodeIds(outbox.strokeIdsJson),
            recognizedText = outbox.recognizedText,
            recognitionSource = outbox.recognitionSource,
            recentContext = outbox.recentContext,
            deepMode = outbox.deepMode,
            payloadFrozen = outbox.payloadFrozen,
            isReplayable = outbox.isReplayable,
            state = LocalRequestState.valueOf(outbox.state),
            attemptCount = outbox.attemptCount
        )
    }

    private suspend fun pendingForRequest(requestId: String): PendingReply? {
        val outbox = dao.outbox(requestId) ?: return null
        return PendingReply(
            requestId = outbox.requestId,
            pageId = outbox.pageId,
            strokeIds = decodeIds(outbox.strokeIdsJson),
            recognizedText = outbox.recognizedText,
            recognitionSource = outbox.recognitionSource,
            recentContext = outbox.recentContext,
            deepMode = outbox.deepMode,
            payloadFrozen = outbox.payloadFrozen,
            isReplayable = outbox.isReplayable,
            state = LocalRequestState.valueOf(outbox.state),
            attemptCount = outbox.attemptCount
        )
    }

    suspend fun strokeIds(requestId: String): List<String> =
        dao.outbox(requestId)?.let { decodeIds(it.strokeIdsJson) }.orEmpty()

    suspend fun absorb(requestId: String) {
        database.withTransaction {
            val outbox = requireNotNull(dao.outbox(requestId))
            val turn = requireNotNull(dao.turnForRequest(requestId))
            val ids = decodeIds(outbox.strokeIdsJson)
            if (ids.isNotEmpty()) dao.deleteStrokesById(ids)
            val now = clock()
            dao.upsertTurn(
                turn.copy(
                    state = LocalRequestState.ABSORBED.name,
                    updatedAt = now
                )
            )
            dao.upsertOutbox(
                outbox.copy(
                    state = LocalRequestState.ABSORBED.name,
                    updatedAt = now
                )
            )
        }
    }
}
