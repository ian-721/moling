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
import com.moling.livingnotebook.data.recognition.InkRecognitionResult
import com.moling.livingnotebook.data.recognition.InkRecognitionService
import com.moling.livingnotebook.data.remote.BackendConfig
import com.moling.livingnotebook.data.remote.NotebookApiClient
import com.moling.livingnotebook.data.remote.NotebookReplyResult
import com.moling.livingnotebook.drawing.renderStrokesToBitmap
import com.moling.livingnotebook.drawing.toPngBase64
import com.moling.livingnotebook.settings.AssetFontScanner
import com.moling.livingnotebook.settings.FontOption
import com.moling.livingnotebook.settings.MolingSettings
import com.moling.livingnotebook.settings.SettingsRepository
import com.moling.livingnotebook.ui.components.ErrorHint
import com.moling.livingnotebook.ui.components.InkReplyOverlay
import com.moling.livingnotebook.ui.components.InkToolbar
import com.moling.livingnotebook.ui.components.PaperCanvas
import com.moling.livingnotebook.ui.components.SettingsSheet
import com.moling.livingnotebook.viewmodel.InkPhase
import com.moling.livingnotebook.viewmodel.NotebookViewModel
import kotlinx.coroutines.launch

private const val NETWORK_FAILURE_MESSAGE =
    "\u58a8\u8ff9\u6ca1\u6709\u56de\u5e94\u3002\u68c0\u67e5\u540e\u7aef\u662f\u5426\u5f00\u542f\u3002"

private const val SENDING_INK_ALPHA = 0.55f
private const val SENDING_FADE_MS = 500
private const val ABSORB_FADE_MS = 1000
private const val RESTORE_FADE_MS = 300

@Composable
fun NotebookPageScreen(modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val viewModel = remember { NotebookViewModel() }
    val settingsRepository = remember(context) { SettingsRepository(context) }
    val settings by settingsRepository.settings.collectAsState(initial = MolingSettings())
    val coroutineScope = rememberCoroutineScope()
    var canvasSize by remember { mutableStateOf(IntSize.Zero) }
    val inkAlpha = remember { Animatable(1f) }
    var showSettingsSheet by remember { mutableStateOf(false) }
    var fontOptions by remember { mutableStateOf(listOf(FontOption.Default)) }

    LaunchedEffect(Unit) {
        InkRecognitionService.preloadModel()
    }

    LaunchedEffect(context) {
        fontOptions = AssetFontScanner.scan(context.assets)
    }

    LaunchedEffect(viewModel.inkPhase) {
        when (viewModel.inkPhase) {
            InkPhase.Sending -> inkAlpha.animateTo(SENDING_INK_ALPHA, tween(SENDING_FADE_MS))
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

    fun respond() {
        coroutineScope.launch {
            viewModel.beginRespond()
            val deviceProfileId = settingsRepository.getOrCreateDeviceProfileId()

            when (val recognition = InkRecognitionService.recognize(viewModel.strokes.toList())) {
                is InkRecognitionResult.Success -> {
                    viewModel.onLocalRecognition(recognition.text, "mlkit")
                    when (
                        val result = NotebookApiClient.requestNotebookReply(
                            baseUrl = BackendConfig.BASE_URL,
                            recognizedText = recognition.text,
                            recognitionSource = "mlkit",
                            recentContext = viewModel.buildRecentContext(),
                            deviceProfileId = deviceProfileId,
                            assistantName = settings.assistantName
                        )
                    ) {
                        is NotebookReplyResult.Success -> viewModel.onRespondSuccess(
                            result.recognizedText,
                            result.aiReply,
                            result.recognitionSource
                        )
                        is NotebookReplyResult.Failure -> viewModel.onRespondFailure(
                            NETWORK_FAILURE_MESSAGE
                        )
                    }
                }

                is InkRecognitionResult.Failure -> {
                    if (BackendConfig.ENABLE_VISION_FALLBACK_FOR_DEV) {
                        val bitmap = renderStrokesToBitmap(
                            strokes = viewModel.strokes,
                            widthPx = canvasSize.width,
                            heightPx = canvasSize.height
                        )
                        when (
                            val result = NotebookApiClient.requestNotebookReply(
                                baseUrl = BackendConfig.BASE_URL,
                                imageBase64 = bitmap.toPngBase64(),
                                recentContext = viewModel.buildRecentContext(),
                                deviceProfileId = deviceProfileId,
                                assistantName = settings.assistantName
                            )
                        ) {
                            is NotebookReplyResult.Success -> viewModel.onRespondSuccess(
                                result.recognizedText,
                                result.aiReply,
                                result.recognitionSource
                            )
                            is NotebookReplyResult.Failure -> viewModel.onRespondFailure(
                                NETWORK_FAILURE_MESSAGE
                            )
                        }
                    } else {
                        viewModel.onRespondFailure(recognition.reason)
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
                Text(
                    text = "\u8bbe\u7f6e",
                    color = Color(0xFF7A705F)
                )
            }
        }

        val recognizedText = viewModel.recognizedText
        if (settings.showDebugInfo && (recognizedText != null || viewModel.recognitionSource != null)) {
            val source = viewModel.recognitionSource ?: "unknown"
            val textPart = when {
                recognizedText == null -> "-"
                recognizedText.isBlank() -> "\u8bc6\u522b\u4e3a\u7a7a"
                else -> recognizedText
            }
            Text(
                text = "\u8bc6\u522b($source): $textPart",
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
            onReplyFontSizeChange = { option ->
                coroutineScope.launch {
                    settingsRepository.setReplyFontSize(option)
                }
            },
            onFontChange = { assetPath ->
                coroutineScope.launch {
                    settingsRepository.setSelectedFontAssetPath(assetPath)
                }
            },
            onPaperBackgroundChange = { option ->
                coroutineScope.launch {
                    settingsRepository.setPaperBackground(option)
                }
            },
            onShowDebugInfoChange = { show ->
                coroutineScope.launch {
                    settingsRepository.setShowDebugInfo(show)
                }
            },
            onDismiss = { showSettingsSheet = false }
        )
    }
}
