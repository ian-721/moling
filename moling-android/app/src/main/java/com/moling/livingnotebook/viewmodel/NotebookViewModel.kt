package com.moling.livingnotebook.viewmodel

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.moling.livingnotebook.drawing.Stroke
import com.moling.livingnotebook.drawing.StrokePoint
import java.util.UUID

private const val RECENT_CONTEXT_TURNS = 3

enum class InkPhase { Idle, Sending, Absorbing }

class NotebookViewModel {

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

    /** 用户开始写新一段时自增，用于清除上一条 AI 回复残影。 */
    var replyDismissTrigger by mutableStateOf(0)
        private set

    var isLoading by mutableStateOf(false)
        private set

    var errorMessage by mutableStateOf<String?>(null)
        private set

    var inkPhase by mutableStateOf(InkPhase.Idle)
        private set

    val turnHistory = mutableListOf<NotebookTurn>()

    /** 点击"回应"那一刻纸面上的笔迹 id 快照；吸收动画结束后只清这批，不误删新写的字。 */
    private var sendingStrokeIds: Set<String> = emptySet()

    fun beginStroke(x: Float, y: Float) {
        // 用户开始写新一段：清除上一条 AI 回复残影，避免堆叠
        if (aiReplyText.isNotEmpty() && inkPhase == InkPhase.Idle) {
            replyDismissTrigger += 1
        }
        currentStroke = Stroke(
            id = UUID.randomUUID().toString(),
            points = listOf(StrokePoint(x, y))
        )
    }

    fun appendPoint(x: Float, y: Float) {
        val stroke = currentStroke ?: return
        currentStroke = stroke.copy(points = stroke.points + StrokePoint(x, y))
    }

    fun endStroke() {
        val stroke = currentStroke ?: return
        currentStroke = null
        if (stroke.points.isNotEmpty()) {
            strokes.add(stroke)
        }
    }

    fun undo() {
        if (strokes.isNotEmpty()) {
            strokes.removeAt(strokes.lastIndex)
        }
    }

    fun clear() {
        strokes.clear()
        currentStroke = null
        aiReplyText = ""
        recognizedText = null
        recognitionSource = null
        errorMessage = null
        inkPhase = InkPhase.Idle
        sendingStrokeIds = emptySet()
    }

    fun beginRespond() {
        isLoading = true
        errorMessage = null
        inkPhase = InkPhase.Sending
        sendingStrokeIds = strokes.map { it.id }.toSet()
    }

    /** ML Kit 本地识别成功后先记录识别结果（此时后端还没返回）。 */
    fun onLocalRecognition(text: String, source: String) {
        recognizedText = text
        recognitionSource = source
    }

    fun onRespondSuccess(recognizedText: String, aiReply: String, recognitionSource: String) {
        isLoading = false
        this.recognizedText = recognizedText
        this.recognitionSource = recognitionSource
        aiReplyText = aiReply
        replyRevealTrigger += 1
        turnHistory.add(NotebookTurn(recognizedText = recognizedText, aiReply = aiReply))
        inkPhase = InkPhase.Absorbing
    }

    fun onRespondFailure(reason: String, source: String = "error") {
        isLoading = false
        errorMessage = reason
        recognitionSource = source
        inkPhase = InkPhase.Idle
        sendingStrokeIds = emptySet()
    }

    /** 吸收动画播完后由 UI 调用：只清除发送那一刻存在的笔迹，保留动画期间新写的。 */
    fun finishAbsorb() {
        strokes.removeAll { it.id in sendingStrokeIds }
        sendingStrokeIds = emptySet()
        inkPhase = InkPhase.Idle
    }

    fun buildRecentContext(): String? {
        if (turnHistory.isEmpty()) return null
        return turnHistory.takeLast(RECENT_CONTEXT_TURNS).joinToString("\n\n") { turn ->
            "我写：${turn.recognizedText}\n墨灵：${turn.aiReply}"
        }
    }
}
