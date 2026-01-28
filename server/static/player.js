/**
 * Audiobook Player - Variant-based
 *
 * Features:
 * - Book library with multiple variants per book
 * - Variant selection (full, summary, deduped)
 * - Speed control, auto-save position per variant
 * - Chapter navigation
 */

// ============================================================================
// State Management
// ============================================================================

const state = {
    books: [],
    currentBook: null,
    currentVariant: null,
    currentFileIndex: 0,
    deviceId: null,
    isPlaying: false,
    saveInterval: null,
    sleepTimer: {
        timeoutId: null,
        endTime: null,
        type: null, // 'timer' or 'end-of-chapter'
        updateIntervalId: null
    },
    currentChapterIndex: null
};

// ============================================================================
// API Client
// ============================================================================

const API = {
    baseURL: window.location.origin,

    async getBooks() {
        const response = await fetch(`${this.baseURL}/api/books`);
        if (!response.ok) throw new Error('Failed to fetch books');
        const data = await response.json();
        return data.books;
    },

    async getBook(bookId) {
        const response = await fetch(`${this.baseURL}/api/books/${bookId}`);
        if (!response.ok) throw new Error('Failed to fetch book details');
        return response.json();
    },

    getAudioURL(bookId, variantId, fileIndex) {
        return `${this.baseURL}/api/books/${bookId}/variants/${variantId}/audio/${fileIndex}`;
    },

    async getPlaybackPosition(bookId, variantId) {
        const response = await fetch(
            `${this.baseURL}/api/playback/${bookId}/${variantId}`,
            {
                headers: {
                    'X-Device-ID': state.deviceId
                }
            }
        );
        if (!response.ok) return null;
        return response.json();
    },

    async savePlaybackPosition(bookId, variantId, position, speed, fileIndex) {
        const response = await fetch(
            `${this.baseURL}/api/playback/${bookId}/${variantId}`,
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Device-ID': state.deviceId
                },
                body: JSON.stringify({
                    position,
                    speed,
                    file_index: fileIndex
                })
            }
        );
        return response.ok;
    }
};

// ============================================================================
// Device ID Management
// ============================================================================

function getOrCreateDeviceId() {
    let deviceId = localStorage.getItem('audiobook_device_id');
    if (!deviceId) {
        deviceId = 'device_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
        localStorage.setItem('audiobook_device_id', deviceId);
    }
    return deviceId;
}

// ============================================================================
// UI Elements
// ============================================================================

const ui = {
    // Views
    libraryView: document.getElementById('library-view'),
    variantView: document.getElementById('variant-view'),
    playerView: document.getElementById('player-view'),

    // Library
    bookList: document.getElementById('book-list'),
    bookCount: document.getElementById('book-count'),

    // Variant selection
    variantBackBtn: document.getElementById('variant-back-btn'),
    variantBookTitle: document.getElementById('variant-book-title'),
    variantTitle: document.getElementById('variant-title'),
    variantAuthor: document.getElementById('variant-author'),
    variantList: document.getElementById('variant-list'),

    // Player
    backBtn: document.getElementById('back-btn'),
    playerBookTitle: document.getElementById('player-book-title'),

    // Audio
    audio: document.getElementById('audio-player'),
    playPauseBtn: document.getElementById('play-pause-btn'),
    prevFileBtn: document.getElementById('prev-file-btn'),
    nextFileBtn: document.getElementById('next-file-btn'),
    rewindBtn: document.getElementById('rewind-btn'),
    forwardBtn: document.getElementById('forward-btn'),

    // Progress
    progressBar: document.getElementById('progress-bar'),
    currentTime: document.getElementById('current-time'),
    timeRemaining: document.getElementById('time-remaining'),

    // Speed
    speedSlider: document.getElementById('speed-slider'),
    speedDisplay: document.getElementById('speed-display'),
    speedBtn: document.getElementById('speed-btn'),
    speedModal: document.getElementById('speed-modal'),

    // Sleep Timer
    sleepTimerBtn: document.getElementById('sleep-timer-btn'),
    sleepTimerBackdrop: document.getElementById('sleep-timer-backdrop'),
    sleepTimerModal: document.getElementById('sleep-timer-modal'),
    closeSleepTimerBtn: document.getElementById('close-sleep-timer-btn'),

    // Chapters
    secondaryControls: document.getElementById('secondary-controls-grid'),
    chaptersBtn: document.getElementById('chapters-btn'),
    chaptersBackdrop: document.getElementById('chapters-backdrop'),
    chaptersModal: document.getElementById('chapters-modal'),
    closeChaptersBtn: document.getElementById('close-chapters-btn'),
    chaptersList: document.getElementById('chapters-list'),
    currentChapterName: document.getElementById('current-chapter-name')
};

// ============================================================================
// Library Functions
// ============================================================================

async function loadLibrary() {
    try {
        state.books = await API.getBooks();
        renderLibrary();
    } catch (error) {
        console.error('Failed to load library:', error);
        ui.bookList.innerHTML = '<div class="error">Failed to load books. Please check server connection.</div>';
    }
}

function renderLibrary() {
    if (state.books.length === 0) {
        ui.bookList.innerHTML = '<div class="loading">No audiobooks found</div>';
        ui.bookCount.textContent = '0 books available';
        return;
    }

    ui.bookCount.textContent = `${state.books.length} book${state.books.length !== 1 ? 's' : ''} available`;

    // Generate different gradient colors for each book
    const gradients = [
        'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
        'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
        'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
        'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
        'linear-gradient(135deg, #30cfd0 0%, #330867 100%)',
        'linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)',
        'linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%)',
        'linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%)',
        'linear-gradient(135deg, #ff6e7f 0%, #bfe9ff 100%)'
    ];

    ui.bookList.innerHTML = state.books.map((book, index) => {
        const gradient = gradients[index % gradients.length];
        const hasCover = book.has_cover && book.cover_image;
        const coverURL = hasCover ? `${API.baseURL}/api/books/${book.book_id}/cover` : null;

        return `
            <div class="book-item" data-book-id="${book.book_id}">
                <div class="book-cover-card" style="background: ${gradient}">
                    ${hasCover ? `
                        <img src="${coverURL}" alt="${book.title} cover" class="book-cover-image" />
                    ` : `
                        <div class="book-cover-content">
                            <div class="book-cover-icon">📚</div>
                        </div>
                    `}
                </div>
                <div class="book-info-bottom">
                    <h3 class="book-title">${book.title}</h3>
                    ${book.author || book.year ? `
                        <p class="book-author">
                            ${book.author || 'Unknown Author'}${book.year ? ` (${book.year})` : ''}
                        </p>
                    ` : ''}
                    <div class="book-meta">
                        ${book.language ? `<span class="language-badge">${book.language}</span>` : ''}
                        <span>📋 ${book.variant_count}</span>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    // Add click handlers
    document.querySelectorAll('.book-item').forEach(item => {
        item.addEventListener('click', () => {
            const bookId = item.dataset.bookId;
            showVariants(bookId);
        });
    });
}

function showLibrary() {
    ui.libraryView.classList.add('active');
    ui.variantView.classList.remove('active');
    ui.playerView.classList.remove('active');

    // Pause playback when returning to library
    if (state.isPlaying) {
        ui.audio.pause();
    }
}

// ============================================================================
// Variant Selection Functions
// ============================================================================

async function showVariants(bookId) {
    try {
        const book = state.books.find(b => b.book_id === bookId);
        if (!book) return;

        state.currentBook = book;

        // Update header
        ui.variantTitle.textContent = book.title;
        ui.variantAuthor.textContent = book.author || '';

        // Update cover image in variant view
        const variantCoverContainer = document.getElementById('variant-cover-container');
        if (book.has_cover && book.cover_image) {
            const coverURL = `${API.baseURL}/api/books/${book.book_id}/cover`;
            variantCoverContainer.innerHTML = `<img src="${coverURL}" alt="${book.title} cover" class="variant-cover-image" />`;
        } else {
            variantCoverContainer.innerHTML = '<div class="variant-cover-placeholder">📚</div>';
        }

        // Render variants
        renderVariants();

        // Show variant view
        ui.libraryView.classList.remove('active');
        ui.variantView.classList.add('active');
        ui.playerView.classList.remove('active');

    } catch (error) {
        console.error('Failed to load variants:', error);
        alert('Failed to load book versions');
    }
}

function renderVariants() {
    const book = state.currentBook;

    ui.variantList.innerHTML = book.variants.map(variant => {
        const typeBadge = variant.type === 'summary' && variant.summary_pct
            ? `${variant.summary_pct}% Summary`
            : variant.type === 'deduped'
            ? 'Full (Deduped)'
            : 'Full Translation';

        const date = new Date(variant.created_at).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });

        // Language info
        let langInfo = '';
        if (variant.source_lang && variant.target_lang) {
            langInfo = `${variant.source_lang} → ${variant.target_lang}`;
        } else if (variant.target_lang) {
            langInfo = variant.target_lang;
        } else if (book.language) {
            langInfo = book.language;
        }

        return `
            <div class="variant-item" data-variant-id="${variant.variant_id}">
                <div class="variant-header">
                    <div class="variant-title">
                        <h4>${typeBadge}</h4>
                        <p class="variant-subtitle">
                            ${langInfo ? `${langInfo} • ` : ''}${date}
                        </p>
                    </div>
                    <div class="variant-badges">
                        <span class="variant-badge ${variant.type}">${variant.type}</span>
                        ${variant.is_combined ? '<span class="variant-badge combined">Single File</span>' : ''}
                    </div>
                </div>
                <div class="variant-meta">
                    <span>📁 ${variant.file_count} file${variant.file_count !== 1 ? 's' : ''}</span>
                    <span>💾 ${variant.size_mb} MB</span>
                </div>
            </div>
        `;
    }).join('');

    // Add click handlers
    document.querySelectorAll('.variant-item').forEach(item => {
        item.addEventListener('click', () => {
            const variantId = item.dataset.variantId;
            openVariant(variantId);
        });
    });
}

function showVariantSelection() {
    ui.libraryView.classList.remove('active');
    ui.variantView.classList.add('active');
    ui.playerView.classList.remove('active');

    // Pause playback
    if (state.isPlaying) {
        ui.audio.pause();
    }
}

// ============================================================================
// Player Functions
// ============================================================================

async function openVariant(variantId) {
    try {
        const book = state.currentBook;
        const variant = book.variants.find(v => v.variant_id === variantId);
        if (!variant) {
            console.error('[openVariant] Variant not found:', variantId);
            return;
        }

        console.log('[openVariant]', {
            variantId: variantId,
            variant: variant,
            audio_files_count: variant.audio_files ? variant.audio_files.length : 0
        });

        state.currentVariant = variant;
        state.currentFileIndex = 0;

        // Load saved position
        const savedPosition = await API.getPlaybackPosition(book.book_id, variantId);
        if (savedPosition) {
            // Validate saved file index is within bounds
            const savedFileIndex = savedPosition.file_index || 0;
            if (savedFileIndex >= 0 && savedFileIndex < variant.audio_files.length) {
                state.currentFileIndex = savedFileIndex;
            } else {
                console.warn('[openVariant] Saved file index out of bounds:', savedFileIndex, 'max:', variant.audio_files.length - 1);
                state.currentFileIndex = 0;
            }
        }

        renderPlayer();
        loadAudioFile();

        // Restore saved position and speed
        if (savedPosition) {
            ui.audio.playbackRate = savedPosition.speed || 1.0;
            ui.speedSlider.value = savedPosition.speed || 1.0;
            updateSpeedDisplay();

            // Set position after metadata loads
            ui.audio.addEventListener('loadedmetadata', () => {
                ui.audio.currentTime = savedPosition.position || 0;
            }, { once: true });
        }

        // Show player view
        ui.libraryView.classList.remove('active');
        ui.variantView.classList.remove('active');
        ui.playerView.classList.add('active');

    } catch (error) {
        console.error('Failed to open variant:', error);
        alert('Failed to load audiobook');
    }
}

function renderPlayer() {
    const book = state.currentBook;
    const variant = state.currentVariant;

    ui.playerBookTitle.textContent = book.title;

    // Update narrator info
    const narratorEl = document.getElementById('player-narrator');
    if (book.author) {
        narratorEl.textContent = `Narrated by ${book.author}`;
        narratorEl.style.display = 'block';
    } else {
        narratorEl.style.display = 'none';
    }

    // Update book cover in player
    const bookCoverDiv = document.querySelector('.book-cover');
    if (book.has_cover && book.cover_image) {
        const coverURL = `${API.baseURL}/api/books/${book.book_id}/cover`;
        bookCoverDiv.innerHTML = `<img src="${coverURL}" alt="${book.title} cover" style="width: 100%; height: 100%; object-fit: cover; border-radius: 12px;" />`;
    } else {
        bookCoverDiv.textContent = '🎧';
    }

    // Always show secondary controls (speed, timer, and optionally chapters)
    ui.secondaryControls.style.display = 'grid';

    // Show/hide chapters button based on availability
    if (book.has_chapters && book.chapters) {
        ui.chaptersBtn.style.display = 'block';
        renderChapters();
        updateCurrentChapterDisplay();
    } else {
        ui.chaptersBtn.style.display = 'none';
        ui.currentChapterName.style.display = 'none';
    }

    // Update navigation buttons
    updateNavigationButtons();
}

function updateNavigationButtons() {
    const variant = state.currentVariant;
    ui.prevFileBtn.disabled = state.currentFileIndex === 0;
    ui.nextFileBtn.disabled = state.currentFileIndex >= variant.audio_files.length - 1;
}

function loadAudioFile() {
    const book = state.currentBook;
    const variant = state.currentVariant;
    const audioURL = API.getAudioURL(book.book_id, variant.variant_id, state.currentFileIndex);

    console.log('[loadAudioFile]', {
        book_id: book.book_id,
        variant_id: variant.variant_id,
        fileIndex: state.currentFileIndex,
        audioURL: audioURL
    });

    ui.audio.src = audioURL;
    ui.audio.load();

    updateNavigationButtons();
}

function renderChapters() {
    const chapters = state.currentBook.chapters;
    const variant = state.currentVariant;

    console.log('[renderChapters]', {
        totalChapters: chapters.length,
        totalAudioFiles: variant.audio_files.length,
        chapters: chapters
    });

    ui.chaptersList.innerHTML = chapters.map((chapter, index) => {
        const isActive = state.currentChapterIndex === index;
        const chapterTitle = chapter.title || `Chapter ${chapter.number || index + 1}`;

        // Calculate chapter duration from audio files
        let duration = '';
        if (variant && variant.audio_files) {
            // Get the audio file for this chapter
            const audioFile = variant.audio_files[chapter.file_index];
            if (audioFile) {
                // If we have duration metadata, use it
                // For now, we'll show a placeholder or calculate from next chapter
                if (chapters[index + 1]) {
                    const nextChapter = chapters[index + 1];
                    if (chapter.file_index === nextChapter.file_index) {
                        // Same file, calculate duration
                        const durationSeconds = nextChapter.timestamp - chapter.timestamp;
                        duration = formatTime(durationSeconds);
                    }
                }
            }
        }

        // Clean, Audible-style layout: title on left, duration on right
        return `
            <div class="chapter-item ${isActive ? 'active' : ''}" data-chapter-index="${index}">
                <div class="chapter-item-info">
                    <div class="chapter-item-title">${chapterTitle}</div>
                </div>
                ${duration ? `<div class="chapter-item-duration">${duration}</div>` : ''}
            </div>
        `;
    }).join('');

    // Add click handlers
    document.querySelectorAll('.chapter-item').forEach(item => {
        item.addEventListener('click', () => {
            const chapterIndex = parseInt(item.dataset.chapterIndex);
            jumpToChapter(chapterIndex);
            closeChaptersModal();
        });
    });
}

function openChaptersModal() {
    ui.chaptersBackdrop.style.display = 'block';
    ui.chaptersModal.style.display = 'block';
    renderChapters(); // Re-render to update active state
}

function closeChaptersModal() {
    ui.chaptersBackdrop.style.display = 'none';
    ui.chaptersModal.style.display = 'none';
}

function jumpToChapter(chapterIndex) {
    const chapters = state.currentBook.chapters;
    if (!chapters || chapterIndex >= chapters.length) {
        console.error('Invalid chapter index:', chapterIndex);
        return;
    }

    const chapter = chapters[chapterIndex];
    const variant = state.currentVariant;

    // Find which audio file contains this chapter
    // Chapter data contains file_index and timestamp
    if (chapter.file_index !== undefined) {
        state.currentFileIndex = chapter.file_index;
        loadAudioFile();

        // Wait for audio to load, then seek to chapter timestamp
        ui.audio.addEventListener('loadedmetadata', () => {
            if (chapter.timestamp !== undefined) {
                ui.audio.currentTime = chapter.timestamp;
            }
            // Auto-play when jumping to chapter
            if (state.isPlaying || !ui.audio.paused) {
                ui.audio.play();
            }
        }, { once: true });

        // Update current chapter tracking
        state.currentChapterIndex = chapterIndex;
        updateChapterHighlight();
    } else {
        console.warn('Chapter does not have file_index:', chapter);
    }
}

function updateChapterHighlight() {
    // Update active chapter in UI
    document.querySelectorAll('.chapter-item').forEach((item, index) => {
        if (index === state.currentChapterIndex) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });
}

function detectCurrentChapter() {
    // Auto-detect which chapter we're in based on current file and time
    if (!state.currentBook || !state.currentBook.chapters) return;

    const chapters = state.currentBook.chapters;
    const currentFile = state.currentFileIndex;
    const currentTime = ui.audio.currentTime;

    // Find the chapter that matches current file and is before current time
    for (let i = chapters.length - 1; i >= 0; i--) {
        const chapter = chapters[i];
        if (chapter.file_index === currentFile && chapter.timestamp <= currentTime) {
            if (state.currentChapterIndex !== i) {
                state.currentChapterIndex = i;
                updateChapterHighlight();
                updateCurrentChapterDisplay();
            }
            return;
        }
    }
}

function updateCurrentChapterDisplay() {
    // Update the current chapter name shown below book title
    if (!state.currentBook || !state.currentBook.chapters || state.currentChapterIndex === null) {
        ui.currentChapterName.style.display = 'none';
        return;
    }

    const chapter = state.currentBook.chapters[state.currentChapterIndex];
    const chapterTitle = chapter.title || `Chapter ${chapter.number || state.currentChapterIndex + 1}`;

    ui.currentChapterName.textContent = chapterTitle;
    ui.currentChapterName.style.display = 'block';
}

// ============================================================================
// Audio Controls
// ============================================================================

function togglePlayPause() {
    if (ui.audio.paused) {
        ui.audio.play();
    } else {
        ui.audio.pause();
    }
}

function playPreviousFile() {
    if (state.currentFileIndex > 0) {
        state.currentFileIndex--;
        loadAudioFile();
        if (state.isPlaying) {
            ui.audio.play();
        }
    }
}

function playNextFile() {
    const variant = state.currentVariant;
    if (state.currentFileIndex < variant.audio_files.length - 1) {
        state.currentFileIndex++;
        loadAudioFile();
        if (state.isPlaying) {
            ui.audio.play();
        }
    }
}

function rewind() {
    ui.audio.currentTime = Math.max(0, ui.audio.currentTime - 30);
}

function forward() {
    ui.audio.currentTime = Math.min(ui.audio.duration, ui.audio.currentTime + 30);
}

function updateProgress() {
    if (ui.audio.duration) {
        const progress = (ui.audio.currentTime / ui.audio.duration) * 100;
        ui.progressBar.value = progress;

        ui.currentTime.textContent = formatTime(ui.audio.currentTime);

        // Calculate and display time remaining (Audible-style)
        const remaining = ui.audio.duration - ui.audio.currentTime;
        ui.timeRemaining.textContent = formatTimeRemaining(remaining);
    }
}

function seekToPosition(event) {
    if (ui.audio.duration) {
        const percent = event.target.value / 100;
        ui.audio.currentTime = percent * ui.audio.duration;
    }
}

function updateSpeed() {
    const speed = parseFloat(ui.speedSlider.value);
    ui.audio.playbackRate = speed;
    updateSpeedDisplay();
    savePlaybackState();
}

function setSpeedPreset(speed) {
    ui.speedSlider.value = speed;
    updateSpeed();
}

function updateSpeedDisplay() {
    ui.speedDisplay.textContent = `${ui.speedSlider.value}x`;
}

function toggleSpeedModal() {
    const isVisible = ui.speedModal.style.display === 'block';
    ui.speedModal.style.display = isVisible ? 'none' : 'block';
}

function openSleepTimerModal() {
    ui.sleepTimerBackdrop.style.display = 'block';
    ui.sleepTimerModal.style.display = 'block';
}

function closeSleepTimerModal() {
    ui.sleepTimerBackdrop.style.display = 'none';
    ui.sleepTimerModal.style.display = 'none';
}

// ============================================================================
// Playback State Persistence
// ============================================================================

function startAutoSave() {
    // Save position every 5 seconds
    state.saveInterval = setInterval(() => {
        if (state.currentBook && state.currentVariant && !ui.audio.paused) {
            savePlaybackState();
        }
    }, 5000);
}

function stopAutoSave() {
    if (state.saveInterval) {
        clearInterval(state.saveInterval);
        state.saveInterval = null;
    }
}

async function savePlaybackState() {
    if (!state.currentBook || !state.currentVariant) return;

    const success = await API.savePlaybackPosition(
        state.currentBook.book_id,
        state.currentVariant.variant_id,
        ui.audio.currentTime,
        ui.audio.playbackRate,
        state.currentFileIndex
    );

    if (!success) {
        console.warn('Failed to save playback state');
    }
}

// ============================================================================
// Sleep Timer Functions
// ============================================================================

function setSleepTimer(minutes) {
    // Cancel any existing timer
    cancelSleepTimer();

    const endTime = Date.now() + (minutes * 60 * 1000);
    state.sleepTimer.endTime = endTime;
    state.sleepTimer.type = 'timer';

    // Set timeout to pause playback
    state.sleepTimer.timeoutId = setTimeout(() => {
        pauseAndNotify('Sleep timer ended');
    }, minutes * 60 * 1000);

    // Update status display every second
    updateTimerDisplay();
    state.sleepTimer.updateIntervalId = setInterval(updateTimerDisplay, 1000);

    // Show cancel button
    document.getElementById('cancel-timer-btn').style.display = 'block';
}

function setEndOfChapterTimer() {
    // Cancel any existing timer
    cancelSleepTimer();

    state.sleepTimer.type = 'end-of-chapter';
    state.sleepTimer.endTime = null;

    // Update status
    const timerStatus = document.getElementById('timer-status');
    timerStatus.textContent = 'Will stop at end of current chapter';
    timerStatus.classList.add('active');

    // Show cancel button
    document.getElementById('cancel-timer-btn').style.display = 'block';
}

function cancelSleepTimer() {
    // Clear timeout
    if (state.sleepTimer.timeoutId) {
        clearTimeout(state.sleepTimer.timeoutId);
        state.sleepTimer.timeoutId = null;
    }

    // Clear update interval
    if (state.sleepTimer.updateIntervalId) {
        clearInterval(state.sleepTimer.updateIntervalId);
        state.sleepTimer.updateIntervalId = null;
    }

    // Reset state
    state.sleepTimer.endTime = null;
    state.sleepTimer.type = null;

    // Update UI
    const timerStatus = document.getElementById('timer-status');
    timerStatus.textContent = 'No timer set';
    timerStatus.classList.remove('active');
    document.getElementById('cancel-timer-btn').style.display = 'none';
}

function updateTimerDisplay() {
    if (state.sleepTimer.type !== 'timer' || !state.sleepTimer.endTime) {
        return;
    }

    const remaining = state.sleepTimer.endTime - Date.now();
    if (remaining <= 0) {
        cancelSleepTimer();
        return;
    }

    const minutes = Math.floor(remaining / 60000);
    const seconds = Math.floor((remaining % 60000) / 1000);

    const timerStatus = document.getElementById('timer-status');
    timerStatus.textContent = `Sleep timer: ${minutes}:${seconds.toString().padStart(2, '0')} remaining`;
    timerStatus.classList.add('active');
}

function pauseAndNotify(message) {
    ui.audio.pause();
    cancelSleepTimer();

    // Optional: Show notification if supported
    if ('Notification' in window && Notification.permission === 'granted') {
        new Notification('Audiobook Player', {
            body: message,
            icon: '/static/icon.png'
        });
    }
}

function checkEndOfChapterTimer() {
    // Check if we should stop at end of chapter
    if (state.sleepTimer.type !== 'end-of-chapter') return;

    if (!state.currentBook || !state.currentBook.chapters) {
        // No chapters, just continue playing
        return;
    }

    const chapters = state.currentBook.chapters;
    const currentFile = state.currentFileIndex;
    const currentTime = ui.audio.currentTime;

    // Check if we're at the end of a chapter
    // Find next chapter
    let nextChapterIndex = null;
    for (let i = 0; i < chapters.length; i++) {
        const chapter = chapters[i];
        if (chapter.file_index > currentFile ||
            (chapter.file_index === currentFile && chapter.timestamp > currentTime)) {
            nextChapterIndex = i;
            break;
        }
    }

    // If no next chapter found, we're in the last chapter
    // Check if we're near the end of the current file
    if (nextChapterIndex === null || nextChapterIndex === state.currentChapterIndex + 1) {
        // We're in the last chapter or approaching next chapter
        // Check if we should stop (within 1 second of next chapter or end of file)
        if (nextChapterIndex !== null) {
            const nextChapter = chapters[nextChapterIndex];
            if (nextChapter.file_index === currentFile) {
                const timeToNextChapter = nextChapter.timestamp - currentTime;
                if (timeToNextChapter <= 1) {
                    pauseAndNotify('End of chapter reached');
                }
            }
        } else if (ui.audio.duration - currentTime <= 1) {
            // Near end of file and no next chapter
            pauseAndNotify('End of chapter reached');
        }
    }
}

// ============================================================================
// Utility Functions
// ============================================================================

function formatTime(seconds) {
    if (!seconds || isNaN(seconds)) return '0:00';

    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    if (hrs > 0) {
        return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function formatTimeRemaining(seconds) {
    if (!seconds || isNaN(seconds) || seconds < 0) return '0m left';

    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);

    // Audible-style format: "4h 45m left" or "23m left"
    if (hrs > 0) {
        return `${hrs}h ${mins}m left`;
    }
    return `${mins}m left`;
}

// ============================================================================
// Event Listeners
// ============================================================================

function setupEventListeners() {
    // Navigation
    ui.variantBackBtn.addEventListener('click', showLibrary);
    ui.backBtn.addEventListener('click', showVariantSelection);

    // Playback controls
    ui.playPauseBtn.addEventListener('click', togglePlayPause);
    ui.prevFileBtn.addEventListener('click', playPreviousFile);
    ui.nextFileBtn.addEventListener('click', playNextFile);
    ui.rewindBtn.addEventListener('click', rewind);
    ui.forwardBtn.addEventListener('click', forward);

    // Progress
    ui.progressBar.addEventListener('input', seekToPosition);

    // Speed
    ui.speedSlider.addEventListener('input', updateSpeed);
    ui.speedBtn.addEventListener('click', toggleSpeedModal);

    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const speed = parseFloat(btn.dataset.speed);
            setSpeedPreset(speed);
        });
    });

    // Sleep timer modal
    ui.sleepTimerBtn.addEventListener('click', openSleepTimerModal);
    ui.closeSleepTimerBtn.addEventListener('click', closeSleepTimerModal);
    ui.sleepTimerBackdrop.addEventListener('click', closeSleepTimerModal);

    // Chapters modal
    ui.chaptersBtn.addEventListener('click', openChaptersModal);
    ui.closeChaptersBtn.addEventListener('click', closeChaptersModal);
    ui.chaptersBackdrop.addEventListener('click', closeChaptersModal);

    // Audio events
    ui.audio.addEventListener('play', () => {
        state.isPlaying = true;
        ui.playPauseBtn.textContent = '⏸️';
        startAutoSave();
    });

    ui.audio.addEventListener('pause', () => {
        state.isPlaying = false;
        ui.playPauseBtn.textContent = '▶️';
        savePlaybackState();
        stopAutoSave();
    });

    ui.audio.addEventListener('timeupdate', () => {
        updateProgress();
        detectCurrentChapter();
        checkEndOfChapterTimer();
    });

    ui.audio.addEventListener('ended', () => {
        // Auto-advance to next file
        const variant = state.currentVariant;
        if (state.currentFileIndex < variant.audio_files.length - 1) {
            playNextFile();
        } else {
            // Finished book
            ui.audio.pause();
            ui.audio.currentTime = 0;
        }
    });

    ui.audio.addEventListener('error', (e) => {
        console.error('[Audio Error]', {
            error: e,
            src: ui.audio.src,
            networkState: ui.audio.networkState,
            readyState: ui.audio.readyState,
            errorCode: ui.audio.error ? ui.audio.error.code : null,
            errorMessage: ui.audio.error ? ui.audio.error.message : null
        });
        console.error(`Failed to load: ${ui.audio.src}`);
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (ui.playerView.classList.contains('active')) {
            switch(e.key) {
                case ' ':
                    e.preventDefault();
                    togglePlayPause();
                    break;
                case 'ArrowLeft':
                    e.preventDefault();
                    rewind();
                    break;
                case 'ArrowRight':
                    e.preventDefault();
                    forward();
                    break;
            }
        }
    });

    // Sleep timer event listeners
    document.querySelectorAll('.timer-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const minutes = btn.dataset.minutes;
            const action = btn.dataset.action;

            if (action === 'end-of-chapter') {
                setEndOfChapterTimer();
            } else if (minutes) {
                setSleepTimer(parseInt(minutes));
            }
        });
    });

    document.getElementById('cancel-timer-btn').addEventListener('click', () => {
        cancelSleepTimer();
    });

    // Request notification permission on first interaction
    if ('Notification' in window && Notification.permission === 'default') {
        document.addEventListener('click', () => {
            Notification.requestPermission();
        }, { once: true });
    }

    // Save state before page unload
    window.addEventListener('beforeunload', () => {
        if (state.currentBook && state.currentVariant) {
            savePlaybackState();
        }
        // Clean up timers
        cancelSleepTimer();
    });
}

// ============================================================================
// Initialization
// ============================================================================

async function init() {
    // Get or create device ID
    state.deviceId = getOrCreateDeviceId();
    console.log('Device ID:', state.deviceId);

    // Setup event listeners
    setupEventListeners();

    // Load library
    await loadLibrary();

    console.log('Audiobook player initialized');
}

// Start the app
init();
