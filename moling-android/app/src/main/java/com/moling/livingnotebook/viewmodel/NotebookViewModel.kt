package com.moling.livingnotebook.viewmodel

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.moling.livingnotebook.data.NotebookRepository
import com.moling.livingnotebook.data.ReplyOutboxRepository
import com.moling.livingnotebook.drawing.Stroke
import com.moling.livingnotebook.drawing.StrokePoint
import java.util.UUID
import kotlinx.coroutines.launch

private const val RECENT_CONTEXT_TURNS = 3
const val DEFAULT_PAGE_ID = "page-home"

enum class InkPhase { Idle, Sending, Absorbing }

data class PreparedReply(
    val requestId: String,
    val pageId: String,
    val strokeIds: List<String>,
    val recognizedText: String?,
    val recognitionSource: String?
)

internal fun shouldApplyResponse(
    activeRequestId: String?,
    incomingRequestId: String
): Boolean = activeRequestId == incomingRequestId

internal fun formatRecentContext(
    turns: List<NotebookTurn>,
    assistantName: String
): String? {
    if (turns.isEmpty()) return null
    return turns.takeLast(RECENT_CONTEXT_TURNS).joinToString("\n\n") { turn ->
        "我写：${turn.recognizedText}\n$assistantName：${turn.aiReply}"
    }
}

class NotebookViewModel(
    private val notebookRepository: NotebookRepository,
    private val outboxRepository: ReplyOutboxRepository,
    private val pageId: String = DEFAULT_PAGE_ID
) : ViewModel() {

    val strokes = mutableStateListOf<Stroke>()

    var currentStroke by mutableStateOf<Stroke?>(null)
        private set
    var aiReplyText by mutableStateOf("")
        private set
    var recognizedText by mutableStateOf<String?>(null)
        private set
    var recognitionSource by mutableStateOf<String?>(null)
        private set
    var replyRevealTrigger by mutableStateOf(0)
        private set
    var replyDismissTrigger by mutableStateOf(0)
        private set
    var isLoading by mutableStateOf(false)
        private set
    var errorMessage by mutableStateOf<String?>(null)
        private set
    var inkPhase by mutableStateOf(InkPhase.Idle)
        private set
    var restored by mutableStateOf(false)
        private set

    val turnHistory = mutableListOf<NotebookTurn>()
    private var activeRequestId: String? = null
    private var activeStrokeIds: Set<String> = emptySet()

    fun restore() {
        if (restored) return
        viewModelScope.launch {
            runCatching { notebookRepository.restore(pageId) }
                .onSuccess { state ->
                    strokes.clear()
                    strokes.addAll(state.strokes)
                    turnHistory.clear()
                    turnHistory.addAll(
                        state.turns.map {
                            NotebookTurn(it.recognizedText, it.aiReply, it.timestamp)
                        }
                    )
                    state.latestReply?.let { reply ->
                        aiReplyText = reply
                        activeRequestId = state.latestRequestId
                        activeStrokeIds = state.latestRequestId
                            ?.let { outboxRepository.strokeIds(it).toSet() }
                            .orEmpty()
                        replyRevealTrigger += 1
                        inkPhase = InkPhase.Absorbing
                    }
                    restored = true
                }
                .onFailure {
                    errorMessage = "本地笔记恢复失败，暂时不要清除应用数据"
                    restored = true
                }
        }
    }

    fun beginStroke(x: Float, y: Float, pressure: Float = 1f) {
        if (aiReplyText.isNotEmpty() && inkPhase == InkPhase.Idle) {
            replyDismissTrigger += 1
        }
        currentStroke = Stroke(
            id = UUID.randomUUID().toString(),
            points = listOf(StrokePoint(x, y, pressure = pressure))
        )
    }

    fun appendPoint(x: Float, y: Float, pressure: Float = 1f) {
        val stroke = currentStroke ?: return
        currentStroke = stroke.copy(
            points = stroke.points + StrokePoint(x, y, pressure = pressure)
        )
    }

    fun endStroke() {
        val stroke = currentStroke ?: return
        currentStroke = null
        if (stroke.points.isEmpty()) return
        strokes.add(stroke)
        viewModelScope.launch {
            runCatching { notebookRepository.persistStroke(pageId, stroke) }
                .onFailure {
                    errorMessage = "这笔墨迹尚未安全保存，请停止继续操作并重试"
                }
        }
    }

    fun undo() {
        viewModelScope.launch {
            val removedId = runCatching { notebookRepository.undo(pageId) }.getOrNull()
            if (removedId != null) strokes.removeAll { it.id == removedId }
        }
    }

    fun clear() {
        viewModelScope.launch {
            runCatching { notebookRepository.clearEditable(pageId) }
                .onSuccess {
                    strokes.removeAll { it.id !in activeStrokeIds }
                    currentStroke = null
                    if (activeRequestId == null) {
                        aiReplyText = ""
                        recognizedText = null
                        recognitionSource = null
                    }
                    errorMessage = null
                }
                .onFailure { errorMessage = "纸面清理失败，墨迹仍保留在本地" }
        }
    }

    suspend fun prepareReply(): PreparedReply? {
        val pending = outboxRepository.pending(pageId)
        if (pending != null) {
            activeRequestId = pending.requestId
            activeStrokeIds = pending.strokeIds.toSet()
            isLoading = true
            errorMessage = null
            inkPhase = InkPhase.Sending
            return PreparedReply(
                requestId = pending.requestId,
                pageId = pending.pageId,
                strokeIds = pending.strokeIds,
                recognizedText = pending.recognizedText.takeIf { it.isNotBlank() },
                recognitionSource = pending.recognitionSource.takeIf { it.isNotBlank() }
            )
        }
        val ids = strokes.map { it.id }
        if (ids.isEmpty()) {
            errorMessage = "先写下一段话，再让墨灵回应"
            return null
        }
        val requestId = UUID.randomUUID().toString()
        return runCatching {
            outboxRepository.createSnapshot(requestId, pageId, ids)
            activeRequestId = requestId
            activeStrokeIds = ids.toSet()
            isLoading = true
            errorMessage = null
            inkPhase = InkPhase.Sending
            PreparedReply(requestId, pageId, ids, null, null)
        }.getOrElse {
            errorMessage = "请求快照保存失败，笔迹未发送"
            null
        }
    }

    suspend fun onLocalRecognition(requestId: String, text: String, source: String) {
        outboxRepository.markRecognized(requestId, text, source)
        if (requestId == activeRequestId) {
            recognizedText = text
            recognitionSource = source
        }
    }

    suspend fun markSending(requestId: String) {
        outboxRepository.markSending(requestId)
    }

    suspend fun onRespondSuccess(
        requestId: String,
        recognizedText: String,
        aiReply: String,
        recognitionSource: String,
        replyMode: String,
        safetyLevel: String
    ) {
        outboxRepository.markSucceeded(
            requestId,
            aiReply,
            replyMode,
            safetyLevel
        )
        // A late response is retained in its turn but cannot replace the active UI.
        if (!shouldApplyResponse(activeRequestId, requestId)) return
        isLoading = false
        this.recognizedText = recognizedText
        this.recognitionSource = recognitionSource
        aiReplyText = aiReply
        replyRevealTrigger += 1
        turnHistory.add(NotebookTurn(recognizedText = recognizedText, aiReply = aiReply))
        inkPhase = InkPhase.Absorbing
    }

    suspend fun onRespondFailure(
        requestId: String,
        reason: String,
        category: String,
        retryable: Boolean
    ) {
        outboxRepository.markFailure(requestId, category, retryable)
        if (!shouldApplyResponse(activeRequestId, requestId)) return
        isLoading = false
        errorMessage = reason
        recognitionSource = "error"
        inkPhase = InkPhase.Idle
        activeRequestId = null
        activeStrokeIds = emptySet()
    }

    fun finishAbsorb() {
        val requestId = activeRequestId ?: return
        val ids = activeStrokeIds
        viewModelScope.launch {
            runCatching { outboxRepository.absorb(requestId) }
                .onSuccess {
                    strokes.removeAll { it.id in ids }
                    activeRequestId = null
                    activeStrokeIds = emptySet()
                    inkPhase = InkPhase.Idle
                }
                .onFailure {
                    errorMessage = "回应已保存，但墨迹吸收状态尚未落盘"
                    inkPhase = InkPhase.Idle
                }
        }
    }

    fun strokesFor(ids: List<String>): List<Stroke> =
        strokes.filter { it.id in ids.toSet() }

    fun buildRecentContext(assistantName: String): String? {
        return formatRecentContext(turnHistory, assistantName)
    }
}
