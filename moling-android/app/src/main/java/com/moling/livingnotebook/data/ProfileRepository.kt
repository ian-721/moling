package com.moling.livingnotebook.data

import com.moling.livingnotebook.data.auth.AuthResult
import com.moling.livingnotebook.data.auth.AuthSessionRepository
import com.moling.livingnotebook.data.remote.NotebookApiClient
import com.moling.livingnotebook.data.remote.RemoteResult
import com.moling.livingnotebook.settings.SettingsRepository

sealed class ProfileUpdateResult {
    data class Success(val assistantName: String) : ProfileUpdateResult()
    data class Failure(val reason: String) : ProfileUpdateResult()
}

class ProfileRepository(
    private val auth: AuthSessionRepository,
    private val api: NotebookApiClient,
    private val settings: SettingsRepository
) {
    suspend fun updateAssistantName(name: String): ProfileUpdateResult {
        val token = when (val authResult = auth.accessToken()) {
            is AuthResult.Success -> authResult.accessToken
            is AuthResult.Failure -> return ProfileUpdateResult.Failure(authResult.reason)
        }
        return when (val result = api.patchProfile(token, name)) {
            is RemoteResult.Success -> {
                settings.setAssistantName(result.value.assistantName)
                ProfileUpdateResult.Success(result.value.assistantName)
            }
            is RemoteResult.Failure -> {
                if (result.unauthorized) auth.clearSession()
                ProfileUpdateResult.Failure(result.reason)
            }
        }
    }
}
