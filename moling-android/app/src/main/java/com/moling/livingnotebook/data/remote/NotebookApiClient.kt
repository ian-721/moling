package com.moling.livingnotebook.data.remote

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

data class RemoteProfile(
    val assistantName: String,
    val updatedAt: String
)

data class RegisteredSession(
    val accessToken: String,
    val expiresAt: String,
    val profile: RemoteProfile
)

data class NotebookReply(
    val requestId: String,
    val recognizedText: String,
    val aiReply: String,
    val responseMode: String,
    val recognitionSource: String,
    val safetyLevel: String
)

sealed class RemoteResult<out T> {
    data class Success<T>(val value: T) : RemoteResult<T>()
    data class Failure(
        val statusCode: Int?,
        val code: String,
        val reason: String,
        val retryable: Boolean
    ) : RemoteResult<Nothing>() {
        val unauthorized: Boolean get() = statusCode == 401
    }
}

open class NotebookApiClient(private val baseUrl: String) {
    private val connectTimeoutMs = 15_000
    private val readTimeoutMs = 45_000

    open suspend fun registerDevice(
        installationId: String,
        rotationToken: String? = null
    ): RemoteResult<RegisteredSession> = request(
        method = "POST",
        path = "/api/auth/device/register",
        token = rotationToken,
        body = JSONObject().put("installationId", installationId)
    ) { json ->
        val profile = json.getJSONObject("profile")
        RegisteredSession(
            accessToken = json.getString("accessToken"),
            expiresAt = json.getString("expiresAt"),
            profile = RemoteProfile(
                assistantName = profile.getString("assistantName"),
                updatedAt = profile.getString("updatedAt")
            )
        )
    }

    open suspend fun getProfile(token: String): RemoteResult<RemoteProfile> = request(
        method = "GET",
        path = "/api/profile",
        token = token
    ) { json ->
        RemoteProfile(
            assistantName = json.getString("assistantName"),
            updatedAt = json.getString("updatedAt")
        )
    }

    open suspend fun patchProfile(
        token: String,
        assistantName: String
    ): RemoteResult<RemoteProfile> = request(
        method = "PATCH",
        path = "/api/profile",
        token = token,
        body = JSONObject().put("assistantName", assistantName)
    ) { json ->
        RemoteProfile(
            assistantName = json.getString("assistantName"),
            updatedAt = json.getString("updatedAt")
        )
    }

    open suspend fun requestNotebookReply(
        token: String,
        requestId: String,
        recognizedText: String? = null,
        recognitionSource: String? = null,
        recentContext: String? = null,
        imageBase64: String? = null,
        pageId: String? = null,
        deepMode: Boolean = false
    ): RemoteResult<NotebookReply> = request(
        method = "POST",
        path = "/api/notebook/reply",
        token = token,
        body = JSONObject().apply {
            put("requestId", requestId)
            put("pageId", pageId ?: JSONObject.NULL)
            put("recognizedText", recognizedText ?: JSONObject.NULL)
            put("recognitionSource", recognitionSource ?: JSONObject.NULL)
            put("recentContext", recentContext ?: JSONObject.NULL)
            put("imageBase64", imageBase64 ?: JSONObject.NULL)
            put("deepMode", deepMode)
        }
    ) { json ->
        NotebookReply(
            requestId = json.getString("requestId"),
            recognizedText = json.optString("recognizedText", ""),
            aiReply = json.optString("aiReply", ""),
            responseMode = json.optString("responseMode", ""),
            recognitionSource = json.optString("recognitionSource", ""),
            safetyLevel = json.optString("safetyLevel", "normal")
        )
    }

    private suspend fun <T> request(
        method: String,
        path: String,
        token: String? = null,
        body: JSONObject? = null,
        parse: (JSONObject) -> T
    ): RemoteResult<T> = withContext(Dispatchers.IO) {
        var connection: HttpURLConnection? = null
        try {
            connection = (URL("$baseUrl$path").openConnection() as HttpURLConnection).apply {
                requestMethod = method
                connectTimeout = connectTimeoutMs
                readTimeout = readTimeoutMs
                setRequestProperty("Accept", "application/json")
                if (token != null) setRequestProperty("Authorization", "Bearer $token")
                if (body != null) {
                    doOutput = true
                    setRequestProperty("Content-Type", "application/json; charset=utf-8")
                }
            }
            if (body != null) {
                OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use { writer ->
                    writer.write(body.toString())
                }
            }
            val status = connection.responseCode
            val stream = if (status in 200..299) {
                connection.inputStream
            } else {
                connection.errorStream
            }
            val responseText =
                stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
            if (status !in 200..299) {
                return@withContext parseFailure(status, responseText)
            }
            RemoteResult.Success(parse(JSONObject(responseText)))
        } catch (_: Exception) {
            RemoteResult.Failure(
                statusCode = null,
                code = "network_error",
                reason = "网络请求失败，笔迹已保留",
                retryable = true
            )
        } finally {
            connection?.disconnect()
        }
    }

    internal fun parseFailure(status: Int, responseText: String): RemoteResult.Failure {
        val detail = runCatching {
            JSONObject(responseText).getJSONObject("detail")
        }.getOrNull()
        val code = detail?.optString("code")?.takeIf { it.isNotBlank() }
            ?: Regex("\"code\"\\s*:\\s*\"([A-Za-z0-9._:-]+)\"")
                .find(responseText)
                ?.groupValues
                ?.get(1)
            ?: "http_$status"
        val message = detail?.optString("message")?.takeIf { it.isNotBlank() }
            ?: when (status) {
                401 -> "会话已失效"
                429 -> "回应太频繁，请稍后再试"
                502, 503 -> "模型服务暂时不可用"
                else -> "后端返回错误（$status）"
            }
        val retryable = when {
            status == 409 -> code == "request_in_progress"
            status == 401 || status == 408 || status == 429 -> true
            status >= 500 -> true
            else -> false
        }
        return RemoteResult.Failure(
            statusCode = status,
            code = code,
            reason = message,
            retryable = retryable
        )
    }
}
