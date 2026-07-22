package com.moling.livingnotebook.viewmodel

data class NotebookTurn(
    val recognizedText: String,
    val aiReply: String,
    val timestamp: Long = System.currentTimeMillis()
)
