package com.moling.livingnotebook.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import com.moling.livingnotebook.data.NotebookRepository
import com.moling.livingnotebook.data.ReplyOutboxRepository

class NotebookViewModelFactory(
    private val notebookRepository: NotebookRepository,
    private val outboxRepository: ReplyOutboxRepository
) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        require(modelClass.isAssignableFrom(NotebookViewModel::class.java))
        return NotebookViewModel(notebookRepository, outboxRepository) as T
    }
}
