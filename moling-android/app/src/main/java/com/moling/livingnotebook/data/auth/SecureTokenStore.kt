package com.moling.livingnotebook.data.auth

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

data class StoredAccessToken(
    val value: String,
    val expiresAtEpochMillis: Long
)

interface TokenStore {
    fun read(): StoredAccessToken?
    fun write(token: StoredAccessToken)
    fun clear()
}

class AndroidKeystoreTokenStore(context: Context) : TokenStore {
    private val preferences = context.applicationContext.getSharedPreferences(
        "moling_secure_session",
        Context.MODE_PRIVATE
    )

    override fun read(): StoredAccessToken? = runCatching {
        val cipherText = preferences.getString(KEY_CIPHER_TEXT, null) ?: return null
        val iv = preferences.getString(KEY_IV, null) ?: return null
        val expiresAt = preferences.getLong(KEY_EXPIRES_AT, 0L)
        if (expiresAt <= 0L) return null
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(
            Cipher.DECRYPT_MODE,
            getOrCreateKey(),
            GCMParameterSpec(128, Base64.decode(iv, Base64.NO_WRAP))
        )
        StoredAccessToken(
            value = cipher.doFinal(
                Base64.decode(cipherText, Base64.NO_WRAP)
            ).toString(Charsets.UTF_8),
            expiresAtEpochMillis = expiresAt
        )
    }.getOrElse {
        clear()
        null
    }

    override fun write(token: StoredAccessToken) {
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, getOrCreateKey())
        val cipherText = cipher.doFinal(token.value.toByteArray(Charsets.UTF_8))
        preferences.edit()
            .putString(KEY_CIPHER_TEXT, Base64.encodeToString(cipherText, Base64.NO_WRAP))
            .putString(KEY_IV, Base64.encodeToString(cipher.iv, Base64.NO_WRAP))
            .putLong(KEY_EXPIRES_AT, token.expiresAtEpochMillis)
            .apply()
    }

    override fun clear() {
        preferences.edit().clear().apply()
    }

    private fun getOrCreateKey(): SecretKey {
        val keyStore = KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }
        (keyStore.getKey(KEY_ALIAS, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(
            KeyProperties.KEY_ALGORITHM_AES,
            ANDROID_KEYSTORE
        ).apply {
            init(
                KeyGenParameterSpec.Builder(
                    KEY_ALIAS,
                    KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
                )
                    .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                    .setKeySize(256)
                    .build()
            )
        }.generateKey()
    }

    private companion object {
        const val ANDROID_KEYSTORE = "AndroidKeyStore"
        const val TRANSFORMATION = "AES/GCM/NoPadding"
        const val KEY_ALIAS = "moling_access_token_v1"
        const val KEY_CIPHER_TEXT = "cipher_text"
        const val KEY_IV = "iv"
        const val KEY_EXPIRES_AT = "expires_at"
    }
}
