package com.moling.livingnotebook.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update

@Dao
interface NotebookDao {
    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insertPage(page: PageEntity)

    @Query("SELECT * FROM pages WHERE pageId = :pageId")
    suspend fun page(pageId: String): PageEntity?

    @Update
    suspend fun updatePage(page: PageEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertStroke(stroke: StrokeEntity)

    @Query("SELECT COALESCE(MAX(strokeOrder), 0) + 1 FROM strokes WHERE pageId = :pageId")
    suspend fun nextStrokeOrder(pageId: String): Long

    @Query("SELECT * FROM strokes WHERE pageId = :pageId ORDER BY strokeOrder")
    suspend fun strokes(pageId: String): List<StrokeEntity>

    @Query(
        "SELECT * FROM strokes WHERE pageId = :pageId AND strokeId IN (:strokeIds)"
    )
    suspend fun snapshotStrokes(
        pageId: String,
        strokeIds: List<String>
    ): List<StrokeEntity>

    @Query(
        "SELECT * FROM strokes WHERE pageId = :pageId AND state = 'ACTIVE' " +
            "ORDER BY strokeOrder DESC LIMIT 1"
    )
    suspend fun latestEditableStroke(pageId: String): StrokeEntity?

    @Query("DELETE FROM strokes WHERE strokeId = :strokeId")
    suspend fun deleteStroke(strokeId: String)

    @Query("DELETE FROM strokes WHERE pageId = :pageId")
    suspend fun deleteStrokes(pageId: String)

    @Query("DELETE FROM strokes WHERE pageId = :pageId AND state = 'ACTIVE'")
    suspend fun deleteEditableStrokes(pageId: String)

    @Query("DELETE FROM strokes WHERE strokeId IN (:strokeIds)")
    suspend fun deleteStrokesById(strokeIds: List<String>)

    @Query("UPDATE strokes SET state = :state WHERE strokeId IN (:strokeIds)")
    suspend fun updateStrokeState(strokeIds: List<String>, state: String)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertTurn(turn: NotebookTurnEntity)

    @Query("SELECT * FROM notebook_turns WHERE pageId = :pageId ORDER BY createdAt")
    suspend fun turns(pageId: String): List<NotebookTurnEntity>

    @Query(
        "SELECT * FROM notebook_turns WHERE pageId = :pageId AND state = 'SUCCEEDED' " +
            "ORDER BY updatedAt DESC LIMIT 1"
    )
    suspend fun latestUnabsorbedSuccess(pageId: String): NotebookTurnEntity?

    @Query("SELECT * FROM notebook_turns WHERE requestId = :requestId")
    suspend fun turnForRequest(requestId: String): NotebookTurnEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertOutbox(outbox: ReplyOutboxEntity)

    @Query("SELECT * FROM reply_outbox WHERE requestId = :requestId")
    suspend fun outbox(requestId: String): ReplyOutboxEntity?

    @Query("SELECT * FROM reply_outbox WHERE state = 'SENDING'")
    suspend fun sendingOutbox(): List<ReplyOutboxEntity>

    @Query(
        "SELECT * FROM reply_outbox WHERE pageId = :pageId AND " +
            "state IN ('RECOGNIZING','READY_TO_SEND','SENDING','RETRYABLE_FAILED') " +
            "ORDER BY createdAt LIMIT 1"
    )
    suspend fun pendingOutbox(pageId: String): ReplyOutboxEntity?

}
