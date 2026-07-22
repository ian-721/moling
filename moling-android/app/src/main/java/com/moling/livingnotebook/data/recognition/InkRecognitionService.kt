package com.moling.livingnotebook.data.recognition

import com.google.mlkit.common.model.DownloadConditions
import com.google.mlkit.common.model.RemoteModelManager
import com.google.mlkit.vision.digitalink.recognition.Ink
import com.google.mlkit.vision.digitalink.recognition.DigitalInkRecognition
import com.google.mlkit.vision.digitalink.recognition.DigitalInkRecognitionModel
import com.google.mlkit.vision.digitalink.recognition.DigitalInkRecognitionModelIdentifier
import com.google.mlkit.vision.digitalink.recognition.DigitalInkRecognizerOptions
import com.moling.livingnotebook.drawing.Stroke
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume

sealed class InkRecognitionResult {
    data class Success(val text: String) : InkRecognitionResult()
    data class Failure(val reason: String) : InkRecognitionResult()
}

/**
 * ML Kit Digital Ink Recognition 封装：用 stroke 数据在本地识别手写文字，
 * 不经过任何图片上传，也不接触 OpenAI API Key。
 *
 * 中文模型 tag 说明：ML Kit Digital Ink 没有 zh-Hans 模型，
 * 中文手写识别使用 Han 字系模型：优先 zh-Hani-CN（大陆变体），不可用时回退 zh-Hani（汉字通用）。
 *
 * 模型约 20MB，通过 RemoteModelManager 动态下载，依赖 Google Play Services；
 * 无 GMS 的设备（如部分华为 Pad）下载会失败，此时返回明确 Failure，不静默降级。
 */
object InkRecognitionService {

    private val remoteModelManager = RemoteModelManager.getInstance()

    private val model: DigitalInkRecognitionModel? by lazy {
        val identifier = DigitalInkRecognitionModelIdentifier.fromLanguageTag("zh-Hani-CN")
            ?: DigitalInkRecognitionModelIdentifier.fromLanguageTag("zh-Hani")
        identifier?.let { DigitalInkRecognitionModel.builder(it).build() }
    }

    /** 进入页面时可调用一次做后台预热下载；失败静默，真正识别时再报错。 */
    suspend fun preloadModel() {
        val m = model ?: return
        runCatching { ensureModelDownloaded(m) }
    }

    suspend fun recognize(strokes: List<Stroke>): InkRecognitionResult {
        if (strokes.isEmpty()) {
            return InkRecognitionResult.Failure("这页还没有墨迹。")
        }
        val m = model
            ?: return InkRecognitionResult.Failure("这台设备暂时没有认出这页墨迹。")

        try {
            if (!ensureModelDownloaded(m)) {
                return InkRecognitionResult.Failure("这台设备暂时没有认出这页墨迹。")
            }
        } catch (e: Exception) {
            return InkRecognitionResult.Failure("这台设备暂时没有认出这页墨迹。")
        }

        val inkBuilder = Ink.builder()
        strokes.forEach { stroke ->
            val strokeBuilder = Ink.Stroke.builder()
            stroke.points.forEach { point ->
                strokeBuilder.addPoint(Ink.Point.create(point.x, point.y, point.timestamp))
            }
            inkBuilder.addStroke(strokeBuilder.build())
        }
        val ink = inkBuilder.build()

        return try {
            val recognizer = DigitalInkRecognition.getClient(
                DigitalInkRecognizerOptions.builder(m).build()
            )
            suspendCancellableCoroutine { continuation ->
                recognizer.recognize(ink)
                    .addOnSuccessListener { result ->
                        val text = result.candidates.firstOrNull()?.text.orEmpty()
                        if (text.isBlank()) {
                            continuation.resume(
                                InkRecognitionResult.Failure("这页墨迹有些模糊，能不能写得更大一点？")
                            )
                        } else {
                            continuation.resume(InkRecognitionResult.Success(text))
                        }
                    }
                    .addOnFailureListener {
                        continuation.resume(
                            InkRecognitionResult.Failure("这台设备暂时没有认出这页墨迹。")
                        )
                    }
            }
        } catch (e: Exception) {
            InkRecognitionResult.Failure("这台设备暂时没有认出这页墨迹。")
        }
    }

    /** 已下载直接返回 true；未下载则同步等待下载完成（约 20MB，首次较慢）。 */
    private suspend fun ensureModelDownloaded(m: DigitalInkRecognitionModel): Boolean {
        val downloaded = suspendCancellableCoroutine { continuation ->
            remoteModelManager.isModelDownloaded(m)
                .addOnSuccessListener { continuation.resume(it) }
                .addOnFailureListener { continuation.resume(false) }
        }
        if (downloaded) return true

        return suspendCancellableCoroutine { continuation ->
            remoteModelManager.download(m, DownloadConditions.Builder().build())
                .addOnSuccessListener { continuation.resume(true) }
                .addOnFailureListener { continuation.resume(false) }
        }
    }
}
