package com.moling.livingnotebook.data.auth

import com.moling.livingnotebook.data.remote.NotebookApiClient
import com.moling.livingnotebook.data.remote.RegisteredSession
import com.moling.livingnotebook.data.remote.RemoteResult
import com.moling.livingnotebook.settings.SettingsRepository
import java.time.Instant

sealed class AuthResult {
    data class Success(val accessToken: String) : AuthResult()
    data class Failure(val reason: String) : AuthResult()
}

class AuthSessionRepository(
    private val api: NotebookApiClient,
    private val tokenStore: TokenStore,
    private val settingsRepository: SettingsRepository,
    private val now: () -> Long = System::currentTimeMillis
) {
    suspend fun accessToken(): AuthResult {
        val stored = tokenStore.read()
        if (stored != null && stored.expiresAtEpochMillis > now() + EXPIRY_SKEW_MS) {
            return AuthResult.Success(stored.value)
        }
        if (stored != null && stored.expiresAtEpochMillis > now()) {
            return rotateCurrentSession(stored)
        }
        clearSession()
        return registerFreshInstallation(rotateInstallation = true)
    }

    suspend fun recoverAfterUnauthorized(): AuthResult {
        clearSession()
        // A lost token cannot safely rotate an existing installation because the
        // installation ID is not an authentication credential. Start a new
        // anonymous principal instead of exposing the previous one.
        return registerFreshInstallation(rotateInstallation = true)
    }

    private suspend fun rotateCurrentSession(stored: StoredAccessToken): AuthResult {
        val installationId = settingsRepository.getOrCreateInstallationId()
        return when (
            val result = api.registerDevice(
                installationId = installationId,
                rotationToken = stored.value
            )
        ) {
            is RemoteResult.Success -> persist(result.value)
            is RemoteResult.Failure -> {
                if (result.unauthorized) {
                    clearSession()
                    registerFreshInstallation(rotateInstallation = true)
                } else {
                    // The current token is still valid. Preserve identity and let
                    // the protected request decide whether 401 recovery is needed.
                    AuthResult.Success(stored.value)
                }
            }
        }
    }

    suspend fun clearSession() {
        tokenStore.clear()
        settingsRepository.clearIdentityProfile()
    }

    private suspend fun registerFreshInstallation(
        rotateInstallation: Boolean
    ): AuthResult {
        val installationId = if (rotateInstallation) {
            settingsRepository.rotateInstallationId()
        } else {
            settingsRepository.getOrCreateInstallationId()
        }
        return when (val result = api.registerDevice(installationId)) {
            is RemoteResult.Success -> persist(result.value)
            is RemoteResult.Failure -> AuthResult.Failure(result.reason)
        }
    }

    private suspend fun persist(session: RegisteredSession): AuthResult {
        val expiresAt = runCatching {
            Instant.parse(session.expiresAt).toEpochMilli()
        }.getOrElse { return AuthResult.Failure("服务端令牌过期时间无效") }
        tokenStore.write(
            StoredAccessToken(
                value = session.accessToken,
                expiresAtEpochMillis = expiresAt
            )
        )
        settingsRepository.setAssistantName(session.profile.assistantName)
        return AuthResult.Success(session.accessToken)
    }

    private companion object {
        const val EXPIRY_SKEW_MS = 60_000L
    }
}
