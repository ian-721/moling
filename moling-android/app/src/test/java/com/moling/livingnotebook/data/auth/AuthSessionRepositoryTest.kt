package com.moling.livingnotebook.data.auth

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import com.moling.livingnotebook.data.ProfileRepository
import com.moling.livingnotebook.data.ProfileUpdateResult
import com.moling.livingnotebook.data.remote.NotebookApiClient
import com.moling.livingnotebook.data.remote.RegisteredSession
import com.moling.livingnotebook.data.remote.RemoteProfile
import com.moling.livingnotebook.data.remote.RemoteResult
import com.moling.livingnotebook.settings.SettingsRepository
import java.time.Instant
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class AuthSessionRepositoryTest {
    private lateinit var settings: SettingsRepository
    private lateinit var tokens: FakeTokenStore
    private lateinit var api: FakeApi
    private lateinit var auth: AuthSessionRepository

    @Before
    fun setUp() = runBlocking {
        val context = ApplicationProvider.getApplicationContext<Context>()
        settings = SettingsRepository(context)
        settings.clearIdentityProfile()
        tokens = FakeTokenStore()
        api = FakeApi()
        auth = AuthSessionRepository(api, tokens, settings) { 1_000L }
    }

    @Test
    fun firstRegistrationStoresTokenAndProfileThenReusesSession() = runBlocking {
        val first = auth.accessToken()
        assertEquals(AuthResult.Success("token-1"), first)
        assertEquals("token-1", tokens.value?.value)
        assertEquals("小墨", settings.settings.first().assistantName)

        val second = auth.accessToken()
        assertEquals(AuthResult.Success("token-1"), second)
        assertEquals(1, api.registrationCount)
    }

    @Test
    fun unauthorizedRecoveryClearsOldTokenAndRegistersOnlyOnce() = runBlocking {
        auth.accessToken()
        val recovered = auth.recoverAfterUnauthorized()
        assertEquals(AuthResult.Success("token-2"), recovered)
        assertEquals("token-2", tokens.value?.value)
        assertEquals(2, api.registrationCount)
    }

    @Test
    fun nearExpirySessionRotatesWithSameInstallationAndValidToken() = runBlocking {
        auth.accessToken()
        val firstInstallationId = api.installationIds.single()
        tokens.value = tokens.value?.copy(expiresAtEpochMillis = 50_000L)

        val rotated = auth.accessToken()

        assertEquals(AuthResult.Success("token-2"), rotated)
        assertEquals(listOf(firstInstallationId, firstInstallationId), api.installationIds)
        assertEquals(listOf(null, "token-1"), api.rotationTokens)
    }

    @Test
    fun profileCacheChangesOnlyAfterServerSuccess() = runBlocking {
        auth.accessToken()
        val profiles = ProfileRepository(auth, api, settings)
        api.patchResult = RemoteResult.Failure(
            statusCode = null,
            code = "network_error",
            reason = "offline",
            retryable = true
        )
        assertTrue(
            profiles.updateAssistantName("未保存")
                is ProfileUpdateResult.Failure
        )
        assertEquals("小墨", settings.settings.first().assistantName)

        api.patchResult = RemoteResult.Success(
            RemoteProfile("已保存", Instant.ofEpochMilli(2_000L).toString())
        )
        assertEquals(
            ProfileUpdateResult.Success("已保存"),
            profiles.updateAssistantName("已保存")
        )
        assertEquals("已保存", settings.settings.first().assistantName)
    }

    private class FakeTokenStore : TokenStore {
        var value: StoredAccessToken? = null
        override fun read(): StoredAccessToken? = value
        override fun write(token: StoredAccessToken) {
            value = token
        }
        override fun clear() {
            value = null
        }
    }

    private class FakeApi : NotebookApiClient("https://example.test") {
        var registrationCount = 0
        val installationIds = mutableListOf<String>()
        val rotationTokens = mutableListOf<String?>()
        var patchResult: RemoteResult<RemoteProfile> = RemoteResult.Success(
            RemoteProfile("小墨", Instant.ofEpochMilli(2_000L).toString())
        )

        override suspend fun registerDevice(
            installationId: String,
            rotationToken: String?
        ): RemoteResult<RegisteredSession> {
            registrationCount += 1
            installationIds += installationId
            rotationTokens += rotationToken
            return RemoteResult.Success(
                RegisteredSession(
                    accessToken = "token-$registrationCount",
                    expiresAt = Instant.ofEpochMilli(100_000L).toString(),
                    profile = RemoteProfile(
                        assistantName = "小墨",
                        updatedAt = Instant.ofEpochMilli(2_000L).toString()
                    )
                )
            )
        }

        override suspend fun patchProfile(
            token: String,
            assistantName: String
        ): RemoteResult<RemoteProfile> = patchResult
    }
}
