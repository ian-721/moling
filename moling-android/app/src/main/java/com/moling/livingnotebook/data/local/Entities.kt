package com.moling.livingnotebook.data.local

import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

enum class LocalRequestState {
    DRAFT,
    RECOGNIZING,
    READY_TO_SEND,
    SENDING,
    SUCCEEDED,
    RETRYABLE_FAILED,
    PERMANENT_FAILED,
    ABSORBED
}

@Entity(tableName = "pages")
data class PageEntity(
    @PrimaryKey val pageId: String,
    val createdAt: Long,
    val updatedAt: Long,
    val state: String
)

@Entity(
    tableName = "strokes",
    foreignKeys = [
        ForeignKey(
            entity = PageEntity::class,
            parentColumns = ["pageId"],
            childColumns = ["pageId"],
            onDelete = ForeignKey.CASCADE
        )
    ],
    indices = [Index("pageId"), Index(value = ["pageId", "strokeOrder"], unique = true)]
)
data class StrokeEntity(
    @PrimaryKey val strokeId: String,
    val pageId: String,
    val strokeOrder: Long,
    val pointsJson: String,
    val color: Long,
    val width: Float,
    val createdAt: Long,
    val state: String
)

@Entity(
    tableName = "notebook_turns",
    foreignKeys = [
        ForeignKey(
            entity = PageEntity::class,
            parentColumns = ["pageId"],
            childColumns = ["pageId"],
            onDelete = ForeignKey.CASCADE
        )
    ],
    indices = [Index("pageId"), Index(value = ["requestId"], unique = true)]
)
data class NotebookTurnEntity(
    @PrimaryKey val turnId: String,
    val pageId: String,
    val requestId: String,
    val recognizedText: String,
    val recognitionSource: String,
    val aiReply: String?,
    val replyMode: String?,
    val safetyLevel: String?,
    val state: String,
    val createdAt: Long,
    val updatedAt: Long
)

@Entity(
    tableName = "reply_outbox",
    foreignKeys = [
        ForeignKey(
            entity = PageEntity::class,
            parentColumns = ["pageId"],
            childColumns = ["pageId"],
            onDelete = ForeignKey.CASCADE
        )
    ],
    indices = [Index("pageId"), Index("state")]
)
data class ReplyOutboxEntity(
    @PrimaryKey val requestId: String,
    val pageId: String,
    val strokeIdsJson: String,
    val state: String,
    val attemptCount: Int,
    val lastErrorCategory: String?,
    val nextRetryAt: Long?,
    val createdAt: Long,
    val updatedAt: Long
)
