package com.moling.livingnotebook.ui

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.moling.livingnotebook.data.MolingAppContainer
import com.moling.livingnotebook.data.ProfileUpdateResult
import com.moling.livingnotebook.data.auth.AuthResult
import com.moling.livingnotebook.data.recognition.InkRecognitionResult
import com.moling.livingnotebook.data.recognition.InkRecognitionService
import com.moling.livingnotebook.data.remote.BackendConfig
import com.moling.livingnotebook.data.remote.NotebookReply
import com.moling.livingnotebook.data.remote.RemoteResult
import com.moling.livingnotebook.drawing.renderStrokesToBitmap
import com.moling.livingnotebook.drawing.toPngBase64
import com.moling.livingnotebook.settings.AssetFontScanner
import com.moling.livingnotebook.settings.FontOption
import com.moling.livingnotebook.settings.MolingSettings
import com.moling.livingnotebook.ui.components.ErrorHint
import com.moling.livingnotebook.ui.components.InkReplyOverlay
import com.moling.livingnotebook.ui.components.InkToolbar
import com.moling.livingnotebook.ui.components.PaperCanvas
import com.moling.livingnotebook.ui.components.ProfileSaveState
import com.moling.livingnotebook.ui.components.SettingsSheet
import com.moling.livingnotebook.viewmodel.InkPhase
import com.moling.livingnotebook.viewmodel.NotebookViewModel
import com.moling.livingnotebook.viewmodel.NotebookViewModelFactory
import com.moling.livingnotebook.viewmodel.PreparedReply
import kotlinx.coroutines.launch

private const val SENDING_INK_ALPHA = 0.55f
private const val SENDING_FADE_MS = 500
private const val ABSORB_FADE_MS = 1000
private const val RESTORE_FADE_MS = 300

@Composable
fun NotebookPageScreen(modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val container = remember(context) { MolingAppContainer(context) }
    val viewModel: NotebookViewModel = viewModel(
        factory = remember(container) {
            NotebookViewModelFactory(
                container.notebookRepository,
                container.replyOutboxRepository
            )
        }
    )
    val settings by container.settingsRepository.settings.collectAsState(
        initial = MolingSettings()
    )
    val coroutineScope = rememberCoroutineScope()
    var canvasSize by remember { mutableStateOf(IntSize.Zero) }
    val inkAlpha = remember { Animatable(1f) }
    var showSettingsSheet by remember { mutableStateOf(false) }
    var fontOptions by remember { mutableStateOf(listOf(FontOption.Default)) }
    var profileSaveState by remember {
        mutableStateOf<ProfileSaveState>(ProfileSaveState.Idle)
    }

    LaunchedEffect(Unit) {
        viewModel.restore()
        InkRecognitionService.preloadModel()
        // Registration is started once; failures do not loop.
        container.authSessionRepository.accessToken()
    }

    LaunchedEffect(context) {
        fontOptions = AssetFontScanner.scan(context.assets)
    }

    LaunchedEffect(viewModel.inkPhase) {
        when (viewModel.inkPhase) {
            InkPhase.Sending -> inkAlpha.animateTo(
                SENDING_INK_ALPHA,
                tween(SENDING_FADE_MS)
            )
            InkPhase.Absorbing -> {
                inkAlpha.animateTo(0f, tween(ABSORB_FADE_MS))
                viewModel.finishAbsorb()
                inkAlpha.snapTo(1f)
            }
            InkPhase.Idle -> {
                if (inkAlpha.value < 1f) {
                    inkAlpha.animateTo(1f, tween(RESTORE_FADE_MS))
                }
            }
        }
    }

    suspend fun sendReply(
        prepared: PreparedReply,
        recognizedText: String?,
        recognitionSource: String?,
        imageBase64: String?
    ) {
        val firstAuth = container.authSessionRepository.accessToken()
        if (firstAuth !is AuthResult.Success) {
            viewModel.onRespondFailure(
                prepared.requestId,
                (firstAuth as AuthResult.Failure).reason,
                "authentication_failed",
                true
            )
            return
        }
        viewModel.markSending(prepared.requestId)

        suspend fun call(token: String): RemoteResult<NotebookReply> =
            container.apiClient.requestNotebookReply(
                token = token,
                requestId = prepared.requestId,
                recognizedText = recognizedText,
                recognitionSource = recognitionSource,
                recentContext = viewModel.buildRecentContext(settings.assistantName),
                imageBase64 = imageBase64,
                pageId = prepared.pageId
            )

        var result = call(firstAuth.accessToken)
        if (result is RemoteResult.Failure && result.unauthorized) {
            result = when (
                val recovered = container.authSessionRepository.recoverAfterUnauthorized()
            ) {
                is AuthResult.Success -> call(recovered.accessToken)
                is AuthResult.Failure -> RemoteResult.Failure(
                    statusCode = null,
                    code = "authentication_failed",
                    reason = recovered.reason,
                    retryable = true
                )
            }
        }
        when (result) {
            is RemoteResult.Success -> viewModel.onRespondSuccess(
                requestId = prepared.requestId,
                recognizedText = result.value.recognizedText,
                aiReply = result.value.aiReply,
                recognitionSource = result.value.recognitionSource,
                replyMode = result.value.responseMode,
                safetyLevel = result.value.safetyLevel
            )
            is RemoteResult.Failure -> viewModel.onRespondFailure(
                requestId = prepared.requestId,
                reason = result.reason,
                category = result.code,
                retryable = result.retryable
            )
        }
    }

    fun respond() {
        coroutineScope.launch {
            val prepared = viewModel.prepareReply() ?: return@launch
            val selectedStrokes = viewModel.strokesFor(prepared.strokeIds)
            if (prepared.recognizedText != null) {
                sendReply(
                    prepared,
                    prepared.recognizedText,
                    prepared.recognitionSource,
                    null
                )
                return@launch
            }
            when (val recognition = InkRecognitionService.recognize(selectedStrokes)) {
                is InkRecognitionResult.Success -> {
                    viewModel.onLocalRecognition(
                        prepared.requestId,
                        recognition.text,
                        "mlkit"
                    )
                    sendReply(prepared, recognition.text, "mlkit", null)
                }
                is InkRecognitionResult.Failure -> {
                    if (BackendConfig.ENABLE_VISION_FALLBACK_FOR_DEV) {
                        val bitmap = renderStrokesToBitmap(
                            strokes = selectedStrokes,
                            widthPx = canvasSize.width,
                            heightPx = canvasSize.height
                        )
                        sendReply(
                            prepared,
                            null,
                            null,
                            bitmap.toPngBase64()
                        )
                    } else {
                        viewModel.onRespondFailure(
                            prepared.requestId,
                            recognition.reason,
                            "recognition_failed",
                            true
                        )
                    }
                }
            }
        }
    }

    Column(modifier = modifier.fillMaxSize()) {
        Box(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
                .padding(horizontal = 32.dp, vertical = 24.dp)
        ) {
            PaperCanvas(
                viewModel = viewModel,
                modifier = Modifier.fillMaxSize(),
                strokeAlpha = inkAlpha.value,
                paperBackground = settings.paperBackground,
                onSizeChanged = { canvasSize = it }
            )
            InkReplyOverlay(
                fullText = viewModel.aiReplyText,
                revealTrigger = viewModel.replyRevealTrigger,
                dismissTrigger = viewModel.replyDismissTrigger,
                fontSizeSp = settings.replyFontSize.sizeSp,
                lineHeightSp = settings.replyFontSize.lineHeightSp,
                selectedFontAssetPath = settings.selectedFontAssetPath,
                modifier = Modifier.align(Alignment.BottomStart)
            )
            TextButton(
                onClick = { showSettingsSheet = true },
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .padding(8.dp)
            ) {
                Text(text = "设置", color = Color(0xFF7A705F))
            }
        }

        val recognizedText = viewModel.recognizedText
        if (
            settings.showDebugInfo &&
            (recognizedText != null || viewModel.recognitionSource != null)
        ) {
            val source = viewModel.recognitionSource ?: "unknown"
            val textPart = when {
                recognizedText == null -> "-"
                recognizedText.isBlank() -> "识别为空"
                else -> recognizedText
            }
            Text(
                text = "识别($source): $textPart",
                color = Color(0xFF9B9585),
                fontSize = 12.sp,
                modifier = Modifier.padding(horizontal = 28.dp, vertical = 2.dp)
            )
        }

        ErrorHint(message = viewModel.errorMessage)
        InkToolbar(
            onClear = viewModel::clear,
            onUndo = viewModel::undo,
            onRespond = ::respond,
            isLoading = viewModel.isLoading
        )
    }

    if (showSettingsSheet) {
        SettingsSheet(
            settings = settings,
            fontOptions = fontOptions,
            profileSaveState = profileSaveState,
            onAssistantNameSave = { name ->
                coroutineScope.launch {
                    profileSaveState = ProfileSaveState.Saving
                    profileSaveState = when (
                        val result = container.profileRepository.updateAssistantName(name)
                    ) {
                        is ProfileUpdateResult.Success ->
                            ProfileSaveState.Saved(result.assistantName)
                        is ProfileUpdateResult.Failure ->
                            ProfileSaveState.Failed(result.reason)
                    }
                }
            },
            onReplyFontSizeChange = { option ->
                coroutineScope.launch {
                    container.settingsRepository.setReplyFontSize(option)
                }
            },
            onFontChange = { assetPath ->
                coroutineScope.launch {
                    container.settingsRepository.setSelectedFontAssetPath(assetPath)
                }
            },
            onPaperBackgroundChange = { option ->
                coroutineScope.launch {
                    container.settingsRepository.setPaperBackground(option)
                }
            },
            onShowDebugInfoChange = { show ->
                coroutineScope.launch {
                    container.settingsRepository.setShowDebugInfo(show)
                }
            },
            onDismiss = {
                profileSaveState = ProfileSaveState.Idle
                showSettingsSheet = false
            }
        )
    }
}
