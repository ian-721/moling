package com.moling.livingnotebook.data.remote

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID

sealed class NotebookReplyResult {
    data class Success(
        val recognizedText: String,
        val aiReply: String,
        val responseMode: String,
        val recognitionSource: String
    ) : NotebookReplyResult()

    data class Failure(val reason: String) : NotebookReplyResult()
}

/**
 * 只用 HttpURLConnection + org.json（Android SDK 自带），不引入 OkHttp/Retrofit 等网络依赖。
 * App 全程只知道 baseUrl，不接触任何 OpenAI API Key。
 *
 * v0.5 主路径：客户端用 ML Kit 识别出 recognizedText 后直接发文本；
 * imageBase64 仅在明确开启 Vision fallback 时才携带。
 */
object NotebookApiClient {

    private const val CONNECT_TIMEOUT_MS = 15_000
    private const val READ_TIMEOUT_MS = 30_000

    suspend fun requestNotebookReply(
        baseUrl: String,
        recognizedText: String? = null,
        recognitionSource: String? = null,
        recentContext: String? = null,
        imageBase64: String? = null,
        pageId: String? = null,
        deviceProfileId: String,
        assistantName: String
    ): NotebookReplyResult = withContext(Dispatchers.IO) {
        var connection: HttpURLConnection? = null
        try {
            val url = URL("$baseUrl/api/notebook/reply")
            connection = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                doOutput = true
                connectTimeout = CONNECT_TIMEOUT_MS
                readTimeout = READ_TIMEOUT_MS
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
            }

            val requestBody = JSONObject().apply {
                put("requestId", UUID.randomUUID().toString())
                put("pageId", pageId ?: JSONObject.NULL)
                put("deviceProfileId", deviceProfileId)
                put("assistantName", assistantName)
                put("recognizedText", recognizedText ?: JSONObject.NULL)
                put("recognitionSource", recognitionSource ?: JSONObject.NULL)
                put("recentContext", recentContext ?: JSONObject.NULL)
                put("imageBase64", imageBase64 ?: JSONObject.NULL)
            }

            OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use { writer ->
                writer.write(requestBody.toString())
            }

            val responseCode = connection.responseCode
            val stream = if (responseCode in 200..299) connection.inputStream else connection.errorStream
            val responseText = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() } ?: ""

            if (responseCode !in 200..299) {
                return@withContext NotebookReplyResult.Failure(errorMessage(responseCode, responseText))
            }

            val json = JSONObject(responseText)
            NotebookReplyResult.Success(
                recognizedText = json.optString("recognizedText", ""),
                aiReply = json.optString("aiReply", ""),
                responseMode = json.optString("responseMode", ""),
                recognitionSource = json.optString("recognitionSource", "")
            )
        } catch (e: Exception) {
            NotebookReplyResult.Failure(e.message ?: "网络请求失败")
        } finally {
            connection?.disconnect()
        }
    }

    internal fun errorMessage(responseCode: Int, responseText: String): String {
        val detail = runCatching {
            val raw = JSONObject(responseText).opt("detail")
            when (raw) {
                is JSONObject -> raw.optString("message")
                is String -> raw
                else -> null
            }
        }.getOrNull()
        return detail?.takeIf { it.isNotBlank() } ?: when (responseCode) {
            429 -> "\u56de\u5e94\u592a\u9891\u7e41\uff0c\u7a0d\u540e\u518d\u8bd5"
            502, 503 -> "\u6a21\u578b\u670d\u52a1\u6682\u65f6\u4e0d\u53ef\u7528"
            else -> "\u540e\u7aef\u8fd4\u56de\u9519\u8bef\uff08$responseCode\uff09"
        }
    }
}
