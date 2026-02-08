/**
 * Audiobook Pipeline Frontend
 *
 * Handles the complete audiobook generation workflow:
 * - Multi-step form for configuration
 * - Language detection
 * - Real-time progress tracking
 * - Job management
 */

class AudiobookPipeline {
    constructor() {
        this.currentBookId = null;
        this.currentJobId = null;
        this.pollInterval = null;
        this.formStep = 1;
        this.formData = {};
    }

    /**
     * Open generation modal for a book
     */
    async openGenerationModal(bookId) {
        this.currentBookId = bookId;
        this.formStep = 1;
        this.formData = {
            book_id: bookId,
            translate: false,
            summarize: null,
            voice: 'bf_emma',
            speed: 1.0,
            generate_cover: true
        };

        // Fetch available source files
        try {
            const response = await fetch(`/api/pipeline/source-files/${bookId}`);
            if (!response.ok) throw new Error('Failed to load source files');

            const data = await response.json();
            this.showSourceSelection(data.files);
        } catch (error) {
            console.error('Error loading source files:', error);
            this.showError('Failed to load source files');
        }
    }

    /**
     * Show source file selection step
     */
    showSourceSelection(files) {
        const modal = document.getElementById('pipeline-modal');
        const content = document.getElementById('pipeline-modal-content');

        if (!files || files.length === 0) {
            content.innerHTML = `
                <div class="pipeline-step">
                    <h3>No Source Files Found</h3>
                    <p>This book doesn't have any source markdown files to process.</p>
                    <button onclick="pipeline.closeModal()" class="btn-primary">Close</button>
                </div>
            `;
            modal.style.display = 'block';
            return;
        }

        content.innerHTML = `
            <div class="pipeline-step">
                <h3>Step 1: Select Source File</h3>
                <p>Choose the source text file to process:</p>

                <div class="source-file-list">
                    ${files.map(file => `
                        <div class="source-file-item" onclick="pipeline.selectSourceFile('${file.filename}')">
                            <div class="file-name">${file.filename}</div>
                            <div class="file-info">${file.size_kb} KB</div>
                        </div>
                    `).join('')}
                </div>

                <button onclick="pipeline.closeModal()" class="btn-secondary">Cancel</button>
            </div>
        `;

        modal.style.display = 'block';
    }

    /**
     * Select source file and detect language
     */
    async selectSourceFile(filename) {
        this.formData.source_file = filename;

        // Show loading
        const content = document.getElementById('pipeline-modal-content');
        content.innerHTML = `
            <div class="pipeline-step">
                <h3>Detecting Language...</h3>
                <div class="spinner"></div>
            </div>
        `;

        // Detect language
        try {
            const response = await fetch(`/api/pipeline/detect-language/${this.currentBookId}/${encodeURIComponent(filename)}`);
            if (!response.ok) throw new Error('Language detection failed');

            const result = await response.json();
            this.formData.detected_language = result.language;
            this.formData.language_confidence = result.confidence;
            this.formData.needs_translation = result.needs_translation;

            this.showTranslationStep(result);
        } catch (error) {
            console.error('Language detection error:', error);
            this.showError('Language detection failed. Please try again.');
        }
    }

    /**
     * Show translation configuration step
     */
    showTranslationStep(langResult) {
        const content = document.getElementById('pipeline-modal-content');

        const needsTranslation = langResult.needs_translation;
        const detectedLang = langResult.language;
        const confidence = (langResult.confidence * 100).toFixed(0);

        content.innerHTML = `
            <div class="pipeline-step">
                <h3>Step 2: Translation</h3>

                <div class="detection-result ${needsTranslation ? 'needs-translation' : 'no-translation'}">
                    <strong>Detected Language:</strong> ${detectedLang} (${confidence}% confident)
                </div>

                ${needsTranslation ? `
                    <div class="form-group">
                        <label>
                            <input type="checkbox" id="enable-translation" checked onchange="pipeline.toggleTranslation()">
                            Translate to English
                        </label>
                    </div>

                    <div id="translation-options">
                        <div class="form-group">
                            <label>Source Language:</label>
                            <input type="text" id="source-language" value="${detectedLang}" class="form-input">
                        </div>

                        <div class="form-group">
                            <label>Target Language:</label>
                            <select id="target-language" class="form-select">
                                <option value="Modern English" selected>Modern English</option>
                                <option value="Simplified English">Simplified English</option>
                            </select>
                        </div>

                        <div class="form-group">
                            <label>Translation Model:</label>
                            <select id="translation-model" class="form-select">
                                <option value="o3-mini-high" selected>OpenAI o3-mini (High Quality) ⭐</option>
                                <option value="o3-mini">OpenAI o3-mini (Balanced)</option>
                                <option value="gpt-4o-mini">OpenAI GPT-4o Mini (Fast)</option>
                            </select>
                        </div>
                    </div>
                ` : `
                    <p>✅ No translation needed - book is already in English</p>
                `}

                <div class="step-buttons">
                    <button onclick="pipeline.goBack()" class="btn-secondary">← Back</button>
                    <button onclick="pipeline.proceedToSummarization()" class="btn-primary">Next →</button>
                </div>
            </div>
        `;

        this.formData.translate = needsTranslation;
        this.formData.source_language = detectedLang;
        this.formData.target_language = 'Modern English';
        this.formData.translation_model = 'o3-mini-high';
    }

    /**
     * Toggle translation options
     */
    toggleTranslation() {
        const enabled = document.getElementById('enable-translation').checked;
        document.getElementById('translation-options').style.display = enabled ? 'block' : 'none';
        this.formData.translate = enabled;
    }

    /**
     * Show summarization configuration step
     */
    proceedToSummarization() {
        // Update form data from translation step
        if (this.formData.translate) {
            this.formData.source_language = document.getElementById('source-language')?.value || this.formData.source_language;
            this.formData.target_language = document.getElementById('target-language')?.value || this.formData.target_language;
            this.formData.translation_model = document.getElementById('translation-model')?.value || this.formData.translation_model;
        }

        const content = document.getElementById('pipeline-modal-content');

        content.innerHTML = `
            <div class="pipeline-step">
                <h3>Step 3: Summarization (Optional)</h3>

                <div class="form-group">
                    <label>
                        <input type="checkbox" id="enable-summarization" onchange="pipeline.toggleSummarization()">
                        Summarize this book
                    </label>
                    <p class="help-text">Condense the book while preserving key themes and plot</p>
                </div>

                <div id="summarization-options" style="display: none;">
                    <div class="form-group">
                        <label>Target Length: <span id="summary-percentage-display">50%</span></label>
                        <input type="range" id="summary-percentage" min="10" max="90" value="50" step="5"
                               oninput="pipeline.updateSummaryPreview()" class="form-slider">
                    </div>

                    <div class="summary-preview" id="summary-preview">
                        Original: ~100,000 words<br>
                        Summarized: ~50,000 words
                    </div>
                </div>

                <div class="step-buttons">
                    <button onclick="pipeline.showTranslationStep({language: '${this.formData.source_language}', confidence: ${this.formData.language_confidence}, needs_translation: ${this.formData.needs_translation}})" class="btn-secondary">← Back</button>
                    <button onclick="pipeline.proceedToAudioSettings()" class="btn-primary">Next →</button>
                </div>
            </div>
        `;
    }

    /**
     * Toggle summarization options
     */
    toggleSummarization() {
        const enabled = document.getElementById('enable-summarization').checked;
        document.getElementById('summarization-options').style.display = enabled ? 'block' : 'none';
        this.formData.summarize = enabled ? 50 : null;
    }

    /**
     * Update summary preview
     */
    updateSummaryPreview() {
        const percentage = parseInt(document.getElementById('summary-percentage').value);
        document.getElementById('summary-percentage-display').textContent = percentage + '%';

        const preview = document.getElementById('summary-preview');
        const originalWords = 100000; // Placeholder, could calculate from file size
        const summarizedWords = Math.round(originalWords * (percentage / 100));

        preview.innerHTML = `
            Original: ~${originalWords.toLocaleString()} words<br>
            Summarized: ~${summarizedWords.toLocaleString()} words
        `;

        this.formData.summarize = percentage;
    }

    /**
     * Show audio settings step
     */
    proceedToAudioSettings() {
        // Update form data from summarization step
        const summarizeEnabled = document.getElementById('enable-summarization')?.checked;
        if (summarizeEnabled) {
            this.formData.summarize = parseInt(document.getElementById('summary-percentage').value);
        } else {
            this.formData.summarize = null;
        }

        const content = document.getElementById('pipeline-modal-content');

        content.innerHTML = `
            <div class="pipeline-step">
                <h3>Step 4: Audio Settings</h3>

                <div class="form-group">
                    <label>Voice:</label>
                    <select id="voice-select" class="form-select">
                        <optgroup label="British (Recommended for Classics)">
                            <option value="bf_emma" selected>British Female - Emma ⭐</option>
                            <option value="bm_george">British Male - George</option>
                            <option value="bf_isabella">British Female - Isabella</option>
                        </optgroup>
                        <optgroup label="American">
                            <option value="af_sky">American Female - Sky</option>
                            <option value="am_adam">American Male - Adam</option>
                            <option value="am_onyx">American Male - Onyx (Deep)</option>
                        </optgroup>
                    </select>
                </div>

                <div class="form-group">
                    <label>Playback Speed: <span id="speed-display">1.0x</span></label>
                    <input type="range" id="speed-slider" min="0.8" max="1.5" value="1.0" step="0.05"
                           oninput="pipeline.updateSpeed()" class="form-slider">
                    <div class="speed-presets">
                        <button onclick="pipeline.setSpeed(0.9)" class="preset-btn-small">0.9x</button>
                        <button onclick="pipeline.setSpeed(1.0)" class="preset-btn-small">1.0x</button>
                        <button onclick="pipeline.setSpeed(1.1)" class="preset-btn-small">1.1x</button>
                        <button onclick="pipeline.setSpeed(1.25)" class="preset-btn-small">1.25x</button>
                    </div>
                </div>

                <div class="form-group">
                    <label>
                        <input type="checkbox" id="generate-cover" checked>
                        Generate cover art
                    </label>
                </div>

                <div class="step-buttons">
                    <button onclick="pipeline.proceedToSummarization()" class="btn-secondary">← Back</button>
                    <button onclick="pipeline.showConfirmation()" class="btn-primary">Review →</button>
                </div>
            </div>
        `;
    }

    /**
     * Update speed display
     */
    updateSpeed() {
        const speed = parseFloat(document.getElementById('speed-slider').value);
        document.getElementById('speed-display').textContent = speed.toFixed(2) + 'x';
        this.formData.speed = speed;
    }

    /**
     * Set specific speed
     */
    setSpeed(speed) {
        document.getElementById('speed-slider').value = speed;
        this.updateSpeed();
    }

    /**
     * Show confirmation step
     */
    showConfirmation() {
        // Update form data from audio settings step
        this.formData.voice = document.getElementById('voice-select').value;
        this.formData.speed = parseFloat(document.getElementById('speed-slider').value);
        this.formData.generate_cover = document.getElementById('generate-cover').checked;

        const content = document.getElementById('pipeline-modal-content');

        // Build summary
        let summary = `
            <div class="pipeline-step">
                <h3>Step 5: Confirm & Generate</h3>

                <div class="config-summary">
                    <h4>Configuration Summary</h4>
                    <div class="summary-item">
                        <strong>Source File:</strong> ${this.formData.source_file}
                    </div>
        `;

        if (this.formData.translate) {
            summary += `
                    <div class="summary-item">
                        <strong>Translation:</strong> ${this.formData.source_language} → ${this.formData.target_language}
                        <br><small>Model: ${this.formData.translation_model}</small>
                    </div>
            `;
        }

        if (this.formData.summarize) {
            summary += `
                    <div class="summary-item">
                        <strong>Summarization:</strong> ${this.formData.summarize}% of original length
                    </div>
            `;
        }

        summary += `
                    <div class="summary-item">
                        <strong>Voice:</strong> ${this.formData.voice}
                        <br><strong>Speed:</strong> ${this.formData.speed.toFixed(2)}x
                    </div>
                    <div class="summary-item">
                        <strong>Cover Art:</strong> ${this.formData.generate_cover ? 'Yes' : 'No'}
                    </div>
                </div>

                <div class="estimated-time">
                    ⏱️ Estimated time: ${this.estimateTime()} hours
                    <p class="help-text">You can close this window - generation runs in background</p>
                </div>

                <div class="step-buttons">
                    <button onclick="pipeline.proceedToAudioSettings()" class="btn-secondary">← Back</button>
                    <button onclick="pipeline.startGeneration()" class="btn-primary btn-large">🎬 Start Generation</button>
                </div>
            </div>
        `;

        content.innerHTML = summary;
    }

    /**
     * Estimate generation time based on configuration
     */
    estimateTime() {
        let hours = 1; // Base time

        if (this.formData.translate) hours += 1.5;
        if (this.formData.summarize) hours += 0.5;

        return `${hours.toFixed(1)}-${(hours + 1).toFixed(1)}`;
    }

    /**
     * Start the generation process
     */
    async startGeneration() {
        // Show loading
        const content = document.getElementById('pipeline-modal-content');
        content.innerHTML = `
            <div class="pipeline-step">
                <h3>Starting Generation...</h3>
                <div class="spinner"></div>
            </div>
        `;

        try {
            const response = await fetch('/api/pipeline/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(this.formData)
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to start generation');
            }

            const result = await response.json();
            this.currentJobId = result.job_id;

            // Show progress panel
            this.showProgressPanel();
            this.closeModal();

            // Start polling for progress
            this.startPolling();

        } catch (error) {
            console.error('Generation error:', error);
            this.showError(error.message);
        }
    }

    /**
     * Show progress panel
     */
    showProgressPanel() {
        const panel = document.getElementById('pipeline-progress-panel');
        if (!panel) {
            // Create panel if it doesn't exist
            const newPanel = document.createElement('div');
            newPanel.id = 'pipeline-progress-panel';
            newPanel.className = 'pipeline-progress-panel';
            newPanel.innerHTML = `
                <div class="progress-header">
                    <h4>📥 Audiobook Generation</h4>
                    <button onclick="pipeline.closeProgressPanel()" class="close-btn">✕</button>
                </div>
                <div class="progress-content">
                    <div class="progress-bar-container">
                        <div id="pipeline-progress-bar" class="progress-bar-fill"></div>
                        <span id="pipeline-progress-text" class="progress-text">0%</span>
                    </div>
                    <div id="pipeline-status-message" class="status-message">Starting...</div>
                    <div id="pipeline-stage-info" class="stage-info"></div>
                    <div id="pipeline-eta" class="eta-info"></div>
                </div>
            `;
            document.body.appendChild(newPanel);
        }

        document.getElementById('pipeline-progress-panel').style.display = 'block';
    }

    /**
     * Start polling for job progress
     */
    startPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
        }

        this.pollInterval = setInterval(() => {
            this.updateProgress();
        }, 2000);

        // Immediate update
        this.updateProgress();
    }

    /**
     * Update progress from API
     */
    async updateProgress() {
        if (!this.currentJobId) return;

        try {
            const response = await fetch(`/api/pipeline/jobs/${this.currentJobId}`);
            if (!response.ok) throw new Error('Failed to fetch job status');

            const job = await response.json();

            // Update progress bar
            const progressBar = document.getElementById('pipeline-progress-bar');
            const progressText = document.getElementById('pipeline-progress-text');
            if (progressBar && progressText) {
                progressBar.style.width = job.progress + '%';
                progressText.textContent = job.progress + '%';
            }

            // Update status message
            const statusMsg = document.getElementById('pipeline-status-message');
            if (statusMsg) {
                const stageMsg = job.stage_progress?.message || job.current_stage;
                statusMsg.textContent = stageMsg;
            }

            // Update stage info
            const stageInfo = document.getElementById('pipeline-stage-info');
            if (stageInfo && job.stage_progress) {
                if (job.stage_progress.current_chunk) {
                    stageInfo.textContent = `Chunk ${job.stage_progress.current_chunk} / ${job.stage_progress.total_chunks}`;
                } else {
                    stageInfo.textContent = '';
                }
            }

            // Update ETA
            const etaInfo = document.getElementById('pipeline-eta');
            if (etaInfo && job.eta_seconds) {
                etaInfo.textContent = `⏱️ ${this.formatETA(job.eta_seconds)} remaining`;
            }

            // Check if completed
            if (job.status === 'completed') {
                this.onJobCompleted(job);
            } else if (job.status === 'failed') {
                this.onJobFailed(job);
            }

        } catch (error) {
            console.error('Progress update error:', error);
        }
    }

    /**
     * Format ETA in human-readable form
     */
    formatETA(seconds) {
        if (seconds < 60) return `${Math.round(seconds)}s`;
        if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.round((seconds % 3600) / 60);
        return `${hours}h ${minutes}m`;
    }

    /**
     * Handle job completion
     */
    onJobCompleted(job) {
        clearInterval(this.pollInterval);

        const statusMsg = document.getElementById('pipeline-status-message');
        if (statusMsg) {
            statusMsg.innerHTML = '✅ <strong>Audiobook Ready!</strong>';
        }

        // Refresh book list
        if (typeof loadBooks === 'function') {
            setTimeout(() => {
                loadBooks();
            }, 2000);
        }

        // Show notification
        this.showNotification('Audiobook generation completed! 🎉', 'success');
    }

    /**
     * Handle job failure
     */
    onJobFailed(job) {
        clearInterval(this.pollInterval);

        const statusMsg = document.getElementById('pipeline-status-message');
        if (statusMsg) {
            statusMsg.innerHTML = `❌ <strong>Generation Failed:</strong> ${job.error || 'Unknown error'}`;
        }

        this.showNotification('Audiobook generation failed', 'error');
    }

    /**
     * Close modal
     */
    closeModal() {
        const modal = document.getElementById('pipeline-modal');
        if (modal) {
            modal.style.display = 'none';
        }
    }

    /**
     * Close progress panel
     */
    closeProgressPanel() {
        const panel = document.getElementById('pipeline-progress-panel');
        if (panel) {
            panel.style.display = 'none';
        }
    }

    /**
     * Go back to previous step
     */
    goBack() {
        // Reload source selection
        this.openGenerationModal(this.currentBookId);
    }

    /**
     * Show error message
     */
    showError(message) {
        const content = document.getElementById('pipeline-modal-content');
        content.innerHTML = `
            <div class="pipeline-step">
                <h3>Error</h3>
                <div class="error-message">${message}</div>
                <button onclick="pipeline.closeModal()" class="btn-primary">Close</button>
            </div>
        `;
    }

    /**
     * Show notification
     */
    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        document.body.appendChild(notification);

        // Auto-remove after 5 seconds
        setTimeout(() => {
            notification.remove();
        }, 5000);
    }
}

// Global instance
const pipeline = new AudiobookPipeline();
