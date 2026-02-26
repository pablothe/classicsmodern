/**
 * Audiobook Pipeline Frontend
 *
 * Single-screen generation modal with smart defaults.
 * Auto-selects source file, detects language, and pre-fills settings.
 * User reviews and clicks "Generate."
 */

class AudiobookPipeline {
    constructor() {
        this.currentBookId = null;
        this.currentJobId = null;
        this.pollInterval = null;
        this.formData = {};
        this.sourceFiles = [];
        this.langResult = null;
    }

    /**
     * Open generation modal — fetches data, auto-selects defaults, renders single screen
     */
    async openGenerationModal(bookId) {
        this.currentBookId = bookId;
        this.formData = {
            book_id: bookId,
            translate: false,
            summarize: null,
            voice: 'bf_emma',
            speed: 1.0,
            generate_cover: true
        };

        // Show modal immediately with loading state
        const modal = document.getElementById('pipeline-modal');
        const content = document.getElementById('pipeline-modal-content');
        content.innerHTML = `
            <div class="pipeline-loading-state">
                <div class="spinner"></div>
                <p>Preparing settings...</p>
            </div>
        `;
        modal.style.display = 'block';

        try {
            // Fetch source files
            const filesResp = await fetch(`/api/pipeline/source-files/${bookId}`);
            if (!filesResp.ok) throw new Error('Failed to load source files');
            const filesData = await filesResp.json();

            if (!filesData.files || filesData.files.length === 0) {
                this.showError('No source markdown files found for this book.');
                return;
            }

            const files = filesData.files;
            this.sourceFiles = files;

            // Auto-select best source file: book.md > only file > most recent
            let selectedFile = files[0]; // already sorted by most recent
            const bookMd = files.find(f => f.filename === 'book.md');
            if (bookMd) selectedFile = bookMd;

            this.formData.source_file = selectedFile.filename;

            // Detect language
            let langResult = null;
            try {
                const preferredLang = state.settings?.preferredLanguage || 'en';
                const langResp = await fetch(
                    `/api/pipeline/detect-language/${bookId}/${encodeURIComponent(selectedFile.filename)}?preferred_language=${preferredLang}`
                );
                if (langResp.ok) {
                    langResult = await langResp.json();
                }
            } catch (langErr) {
                console.warn('Language detection failed, using defaults:', langErr);
            }
            this.langResult = langResult;

            // Check if cover already exists
            const book = state.books?.find(b => b.book_id === bookId) || state.currentBook;
            const alreadyHasCover = !!(book?.has_cover && book?.cover_image);

            // Render the single-screen form
            this.renderForm(files, selectedFile, langResult, alreadyHasCover);

        } catch (error) {
            console.error('Error loading pipeline data:', error);
            this.showError('Failed to load book data. Please try again.');
        }
    }

    /**
     * Render the single-screen generation form
     */
    renderForm(files, selectedFile, langResult, alreadyHasCover) {
        const content = document.getElementById('pipeline-modal-content');

        const needsTranslation = langResult?.needs_translation || false;
        const detectedLang = langResult?.language || 'Unknown';
        const confidence = langResult ? (langResult.confidence * 100).toFixed(0) : '0';
        const detectionMethod = langResult?.method || 'unknown';

        // Language confidence label
        let langLabel;
        if (!langResult) {
            langLabel = 'Unknown';
        } else if (detectionMethod === 'gutenberg_metadata') {
            langLabel = `${detectedLang} <span class="pipeline-meta">(from Gutenberg catalog)</span>`;
        } else {
            langLabel = `${detectedLang} <span class="pipeline-meta">(${confidence}% confident)</span>`;
        }

        // Source file display: static text if 1 file, dropdown if multiple
        let sourceFileHTML;
        if (files.length === 1) {
            sourceFileHTML = `
                <span>${selectedFile.filename}</span>
                <span class="pipeline-meta">${selectedFile.size_kb} KB</span>
            `;
        } else {
            sourceFileHTML = `
                <select id="pipeline-source-select" class="form-select pipeline-inline-select"
                        onchange="pipeline.onSourceFileChange()">
                    ${files.map(f => `
                        <option value="${f.filename}" ${f.filename === selectedFile.filename ? 'selected' : ''}>
                            ${f.filename} (${f.size_kb} KB)
                        </option>
                    `).join('')}
                </select>
            `;
        }

        // Target language options
        const defaultTarget = state.settings?.targetTranslationLanguage || 'Modern English';
        const targetLanguages = ['Modern English', 'Simplified English', 'Spanish', 'French', 'German'];
        const targetOptions = targetLanguages.map(lang =>
            `<option value="${lang}" ${lang === defaultTarget ? 'selected' : ''}>${lang}</option>`
        ).join('');

        // Cover art label
        const coverLabel = alreadyHasCover ? 'Regenerate cover art (already has cover)' : 'Generate cover art';
        const coverChecked = alreadyHasCover ? '' : 'checked';

        // Update formData defaults
        this.formData.translate = needsTranslation;
        this.formData.source_language = detectedLang;
        this.formData.target_language = defaultTarget;
        this.formData.translation_model = 'zongwei/gemma3-translator:4b';
        this.formData.generate_cover = !alreadyHasCover;

        content.innerHTML = `
            <div class="pipeline-single-screen">
                <!-- Source File -->
                <div class="pipeline-row">
                    <div class="pipeline-row-label">Source</div>
                    <div class="pipeline-row-value">${sourceFileHTML}</div>
                </div>

                <!-- Detected Language -->
                <div class="pipeline-row" id="pipeline-lang-row">
                    <div class="pipeline-row-label">Language</div>
                    <div class="pipeline-row-value" id="pipeline-lang-value">${langLabel}</div>
                </div>

                <!-- Voice -->
                <div class="pipeline-row">
                    <div class="pipeline-row-label">Voice</div>
                    <div class="pipeline-row-value">
                        <select id="pipeline-voice" class="form-select pipeline-inline-select">
                            <optgroup label="British (Recommended for Classics)">
                                <option value="bf_emma" selected>Emma (British Female)</option>
                                <option value="bm_george">George (British Male)</option>
                                <option value="bf_isabella">Isabella (British Female)</option>
                            </optgroup>
                            <optgroup label="American">
                                <option value="af_sky">Sky (American Female)</option>
                                <option value="am_adam">Adam (American Male)</option>
                                <option value="am_onyx">Onyx (American Male, Deep)</option>
                            </optgroup>
                        </select>
                    </div>
                </div>

                <!-- Speed -->
                <div class="pipeline-row">
                    <div class="pipeline-row-label">Speed</div>
                    <div class="pipeline-row-value pipeline-speed-row">
                        <div class="speed-presets">
                            <button class="preset-btn-small" onclick="pipeline.setSpeed(0.9)">0.9x</button>
                            <button class="preset-btn-small preset-active" onclick="pipeline.setSpeed(1.0)">1.0x</button>
                            <button class="preset-btn-small" onclick="pipeline.setSpeed(1.1)">1.1x</button>
                            <button class="preset-btn-small" onclick="pipeline.setSpeed(1.25)">1.25x</button>
                        </div>
                    </div>
                </div>

                <!-- Cover Art -->
                <div class="pipeline-row">
                    <div class="pipeline-row-label">Cover</div>
                    <div class="pipeline-row-value">
                        <label class="pipeline-checkbox">
                            <input type="checkbox" id="pipeline-cover" ${coverChecked}>
                            ${coverLabel}
                        </label>
                    </div>
                </div>

                <!-- Translation (collapsible) -->
                <div class="pipeline-collapsible" id="pipeline-translation-section">
                    <button class="pipeline-collapsible-header" onclick="pipeline.toggleSection('translation')">
                        <span class="pipeline-section-title">
                            <span class="pipeline-section-icon" id="pipeline-translation-icon">${needsTranslation ? '\u2212' : '+'}</span>
                            Translation
                        </span>
                        ${needsTranslation ? '<span class="pipeline-section-badge">Recommended</span>' : ''}
                    </button>
                    <div class="pipeline-collapsible-body" id="pipeline-translation-body"
                         style="${needsTranslation ? '' : 'display: none;'}">
                        <div class="form-group">
                            <label>
                                <input type="checkbox" id="pipeline-translate-enabled"
                                       ${needsTranslation ? 'checked' : ''}
                                       onchange="pipeline.onTranslateToggle()">
                                Translate this book
                            </label>
                        </div>
                        <div id="pipeline-translate-options" style="${needsTranslation ? '' : 'display: none;'}">
                            <div class="form-group">
                                <label>Source Language</label>
                                <input type="text" id="pipeline-source-lang" class="form-input" value="${detectedLang}">
                            </div>
                            <div class="form-group">
                                <label>Target Language</label>
                                <select id="pipeline-target-lang" class="form-select">
                                    ${targetOptions}
                                </select>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Summarization (collapsible) -->
                <div class="pipeline-collapsible" id="pipeline-summarization-section">
                    <button class="pipeline-collapsible-header" onclick="pipeline.toggleSection('summarization')">
                        <span class="pipeline-section-title">
                            <span class="pipeline-section-icon" id="pipeline-summarization-icon">+</span>
                            Summarization
                        </span>
                    </button>
                    <div class="pipeline-collapsible-body" id="pipeline-summarization-body" style="display: none;">
                        <div class="form-group">
                            <label>
                                <input type="checkbox" id="pipeline-summarize-enabled"
                                       onchange="pipeline.onSummarizeToggle()">
                                Summarize this book
                            </label>
                            <p class="help-text">Condense while preserving key themes and plot</p>
                        </div>
                        <div id="pipeline-summarize-options" style="display: none;">
                            <div class="form-group">
                                <label>Target Length: <span id="pipeline-summary-pct">50%</span></label>
                                <input type="range" id="pipeline-summary-slider" class="form-slider"
                                       min="10" max="90" value="50" step="5"
                                       oninput="pipeline.onSummarySlider()">
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Estimate + Actions -->
                <div class="pipeline-estimate" id="pipeline-estimate"></div>

                <div class="pipeline-actions">
                    <button onclick="pipeline.closeModal()" class="btn-secondary">Cancel</button>
                    <button onclick="pipeline.startGeneration()" class="btn-primary btn-large" id="pipeline-generate-btn">
                        Generate Audiobook
                    </button>
                </div>
            </div>
        `;

        this.updateEstimate();
    }

    /**
     * Toggle a collapsible section
     */
    toggleSection(section) {
        const body = document.getElementById(`pipeline-${section}-body`);
        const icon = document.getElementById(`pipeline-${section}-icon`);
        if (!body || !icon) return;

        const isOpen = body.style.display !== 'none';
        body.style.display = isOpen ? 'none' : 'block';
        icon.textContent = isOpen ? '+' : '\u2212';
    }

    /**
     * Handle source file dropdown change — re-detect language
     */
    async onSourceFileChange() {
        const select = document.getElementById('pipeline-source-select');
        if (!select) return;

        const filename = select.value;
        this.formData.source_file = filename;

        // Show inline spinner next to language
        const langValue = document.getElementById('pipeline-lang-value');
        if (langValue) {
            langValue.innerHTML = 'Detecting... <span class="pipeline-inline-spinner"></span>';
        }

        try {
            const preferredLang = state.settings?.preferredLanguage || 'en';
            const resp = await fetch(
                `/api/pipeline/detect-language/${this.currentBookId}/${encodeURIComponent(filename)}?preferred_language=${preferredLang}`
            );
            if (!resp.ok) throw new Error('Detection failed');

            const result = await resp.json();
            this.langResult = result;

            const detectedLang = result.language;
            const confidence = (result.confidence * 100).toFixed(0);
            const method = result.method || 'unknown';

            // Update language display
            if (langValue) {
                if (method === 'gutenberg_metadata') {
                    langValue.innerHTML = `${detectedLang} <span class="pipeline-meta">(from Gutenberg catalog)</span>`;
                } else {
                    langValue.innerHTML = `${detectedLang} <span class="pipeline-meta">(${confidence}% confident)</span>`;
                }
            }

            // Update translation defaults
            this.formData.source_language = detectedLang;
            this.formData.needs_translation = result.needs_translation;

            const sourceLangInput = document.getElementById('pipeline-source-lang');
            if (sourceLangInput) sourceLangInput.value = detectedLang;

            // Auto-expand/collapse translation section based on new detection
            const translateCheckbox = document.getElementById('pipeline-translate-enabled');
            if (result.needs_translation) {
                // Expand and check
                document.getElementById('pipeline-translation-body').style.display = 'block';
                document.getElementById('pipeline-translation-icon').textContent = '\u2212';
                if (translateCheckbox) {
                    translateCheckbox.checked = true;
                    this.formData.translate = true;
                    document.getElementById('pipeline-translate-options').style.display = 'block';
                }
            } else {
                // Collapse and uncheck
                document.getElementById('pipeline-translation-body').style.display = 'none';
                document.getElementById('pipeline-translation-icon').textContent = '+';
                if (translateCheckbox) {
                    translateCheckbox.checked = false;
                    this.formData.translate = false;
                    document.getElementById('pipeline-translate-options').style.display = 'none';
                }
            }

            this.updateEstimate();

        } catch (err) {
            console.warn('Language re-detection failed:', err);
            if (langValue) {
                langValue.innerHTML = 'Unknown <span class="pipeline-meta">(detection failed)</span>';
            }
        }
    }

    /**
     * Toggle translation options visibility
     */
    onTranslateToggle() {
        const enabled = document.getElementById('pipeline-translate-enabled')?.checked;
        const options = document.getElementById('pipeline-translate-options');
        if (options) options.style.display = enabled ? 'block' : 'none';
        this.formData.translate = !!enabled;
        this.updateEstimate();
    }

    /**
     * Toggle summarization options visibility
     */
    onSummarizeToggle() {
        const enabled = document.getElementById('pipeline-summarize-enabled')?.checked;
        const options = document.getElementById('pipeline-summarize-options');
        if (options) options.style.display = enabled ? 'block' : 'none';
        this.formData.summarize = enabled ? 50 : null;
        this.updateEstimate();
    }

    /**
     * Update summary percentage display
     */
    onSummarySlider() {
        const val = document.getElementById('pipeline-summary-slider')?.value;
        const display = document.getElementById('pipeline-summary-pct');
        if (display && val) display.textContent = val + '%';
        this.formData.summarize = parseInt(val);
    }

    /**
     * Set speed and highlight active preset button
     */
    setSpeed(speed) {
        this.formData.speed = speed;

        // Update active state on preset buttons
        document.querySelectorAll('.pipeline-speed-row .preset-btn-small').forEach(btn => {
            const btnSpeed = parseFloat(btn.textContent);
            btn.classList.toggle('preset-active', btnSpeed === speed);
        });
    }

    /**
     * Update estimated time display
     */
    updateEstimate() {
        let hours = 1;
        if (this.formData.translate) hours += 1.5;
        if (this.formData.summarize) hours += 0.5;

        const el = document.getElementById('pipeline-estimate');
        if (el) {
            el.innerHTML = `
                Estimated: ${hours.toFixed(1)}-${(hours + 1).toFixed(1)} hours
                <p class="help-text">Runs in background -- you can close this window</p>
            `;
        }
    }

    /**
     * Collect all form data before submission
     */
    collectFormData() {
        this.formData.voice = document.getElementById('pipeline-voice')?.value || 'bf_emma';
        this.formData.generate_cover = document.getElementById('pipeline-cover')?.checked ?? true;

        const translateEnabled = document.getElementById('pipeline-translate-enabled')?.checked;
        this.formData.translate = !!translateEnabled;
        if (translateEnabled) {
            this.formData.source_language = document.getElementById('pipeline-source-lang')?.value || this.formData.source_language;
            this.formData.target_language = document.getElementById('pipeline-target-lang')?.value || 'Modern English';
            this.formData.translation_model = 'zongwei/gemma3-translator:4b';
        }

        const summarizeEnabled = document.getElementById('pipeline-summarize-enabled')?.checked;
        this.formData.summarize = summarizeEnabled
            ? parseInt(document.getElementById('pipeline-summary-slider')?.value || '50')
            : null;

        // source_file already set from auto-selection or dropdown change
    }

    /**
     * Start the generation process
     */
    async startGeneration() {
        this.collectFormData();

        const content = document.getElementById('pipeline-modal-content');
        content.innerHTML = `
            <div class="pipeline-loading-state">
                <div class="spinner"></div>
                <p>Starting generation...</p>
            </div>
        `;

        try {
            const response = await fetch('/api/jobs/audiobook', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(this.formData)
            });

            if (response.status === 409) {
                const data = await response.json();
                throw new Error(data.message || 'A job is already running for this book');
            }
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to start generation');
            }

            const result = await response.json();
            this.currentJobId = result.job_id;

            this.showProgressPanel();
            this.closeModal();
            this.startPolling();

        } catch (error) {
            console.error('Generation error:', error);
            this.showError(error.message);
        }
    }

    // ========================================================================
    // Progress tracking (unchanged from original)
    // ========================================================================

    showProgressPanel() {
        const panel = document.getElementById('pipeline-progress-panel');
        if (!panel) {
            const newPanel = document.createElement('div');
            newPanel.id = 'pipeline-progress-panel';
            newPanel.className = 'pipeline-progress-panel';
            newPanel.innerHTML = `
                <div class="progress-header">
                    <h4>Audiobook Generation</h4>
                    <button onclick="pipeline.closeProgressPanel()" class="close-btn">\u2715</button>
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

    startPolling() {
        if (this.pollInterval) clearInterval(this.pollInterval);
        this.pollInterval = setInterval(() => this.updateProgress(), 2000);
        this.updateProgress();
    }

    async updateProgress() {
        if (!this.currentJobId) return;

        try {
            const response = await fetch(`/api/jobs/${this.currentJobId}`);
            if (!response.ok) throw new Error('Failed to fetch job status');

            const job = await response.json();

            const progressBar = document.getElementById('pipeline-progress-bar');
            const progressText = document.getElementById('pipeline-progress-text');
            if (progressBar && progressText) {
                progressBar.style.width = job.progress + '%';
                progressText.textContent = job.progress + '%';
            }

            const statusMsg = document.getElementById('pipeline-status-message');
            if (statusMsg) {
                statusMsg.textContent = job.state?.message || job.state?.stage || '';
            }

            const stageInfo = document.getElementById('pipeline-stage-info');
            const details = job.state?.details;
            if (stageInfo && details) {
                stageInfo.textContent = details.current_chunk
                    ? `Chunk ${details.current_chunk} / ${details.total_chunks}`
                    : '';
            }

            const etaInfo = document.getElementById('pipeline-eta');
            if (etaInfo && job.eta_seconds) {
                etaInfo.textContent = `${this.formatETA(job.eta_seconds)} remaining`;
            }

            if (job.status === 'completed') this.onJobCompleted(job);
            else if (job.status === 'failed') this.onJobFailed(job);

        } catch (error) {
            console.error('Progress update error:', error);
        }
    }

    formatETA(seconds) {
        if (seconds < 60) return `${Math.round(seconds)}s`;
        if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.round((seconds % 3600) / 60);
        return `${hours}h ${minutes}m`;
    }

    onJobCompleted(job) {
        clearInterval(this.pollInterval);
        const statusMsg = document.getElementById('pipeline-status-message');
        if (statusMsg) statusMsg.innerHTML = '<strong>Audiobook Ready</strong>';
        if (typeof loadBooks === 'function') setTimeout(() => loadBooks(), 2000);
        this.showNotification('Audiobook generation completed.', 'success');
    }

    onJobFailed(job) {
        clearInterval(this.pollInterval);
        const statusMsg = document.getElementById('pipeline-status-message');
        if (statusMsg) statusMsg.innerHTML = `<strong>Generation Failed:</strong> ${job.error || 'Unknown error'}`;
        this.showNotification('Audiobook generation failed', 'error');
    }

    // ========================================================================
    // Utilities
    // ========================================================================

    closeModal() {
        const modal = document.getElementById('pipeline-modal');
        if (modal) modal.style.display = 'none';
    }

    closeProgressPanel() {
        const panel = document.getElementById('pipeline-progress-panel');
        if (panel) panel.style.display = 'none';
    }

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

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        document.body.appendChild(notification);
        setTimeout(() => notification.remove(), 5000);
    }
}

// Global instance
const pipeline = new AudiobookPipeline();
