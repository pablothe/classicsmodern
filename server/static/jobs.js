/**
 * Jobs Dashboard — monitors background tasks (downloads, translations,
 * audiobook generation, cover art). Polls every 2 seconds only while
 * there are active (running/pending) jobs; stops when idle.
 * Supports filtering by type/status and a detail modal with cancel.
 */

const API_BASE = '/api';
const REFRESH_INTERVAL = 2000; // 2 seconds

let refreshTimer = null;
let currentFilters = {
    type: '',
    status: ''
};

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    loadJobs();
    loadStats(); // will start auto-refresh if there are active jobs
});

// Event Listeners
function setupEventListeners() {
    // Refresh button
    document.getElementById('refresh-btn').addEventListener('click', () => {
        loadJobs();
        loadStats();
        showToast('Jobs refreshed', 'info');
    });

    // Cleanup button
    document.getElementById('cleanup-btn').addEventListener('click', cleanupOldJobs);

    // Filters
    document.getElementById('filter-type').addEventListener('change', (e) => {
        currentFilters.type = e.target.value;
        loadJobs();
    });

    document.getElementById('filter-status').addEventListener('change', (e) => {
        currentFilters.status = e.target.value;
        loadJobs();
    });

    // Modal close
    document.getElementById('modal-close').addEventListener('click', closeModal);
    document.getElementById('modal-close-btn').addEventListener('click', closeModal);
    document.getElementById('modal-cancel-btn').addEventListener('click', cancelCurrentJob);

    // Click outside modal to close
    document.getElementById('job-modal').addEventListener('click', (e) => {
        if (e.target.id === 'job-modal') {
            closeModal();
        }
    });
}

/** Fetch jobs from /api/jobs with current type/status filters and re-render the list. */
async function loadJobs() {
    try {
        const params = new URLSearchParams();
        if (currentFilters.type) params.append('job_type', currentFilters.type);
        if (currentFilters.status) params.append('status', currentFilters.status);

        const response = await fetch(`${API_BASE}/jobs?${params}`);
        const data = await response.json();

        renderJobs(data.jobs);
    } catch (error) {
        console.error('Failed to load jobs:', error);
        showToast('Failed to load jobs', 'error');
    }
}

/** Fetch aggregate job counts from /api/jobs/stats and update the summary cards.
 *  Also starts or stops auto-refresh based on whether there are active jobs. */
async function loadStats() {
    try {
        const response = await fetch(`${API_BASE}/jobs/stats`);
        const stats = await response.json();

        document.getElementById('stat-total').textContent = stats.total || 0;
        document.getElementById('stat-running').textContent = stats.by_status?.running || 0;
        document.getElementById('stat-pending').textContent = stats.by_status?.pending || 0;
        document.getElementById('stat-completed').textContent = stats.by_status?.completed || 0;
        document.getElementById('stat-failed').textContent = stats.by_status?.failed || 0;

        // Only poll while there are active jobs
        const activeCount = (stats.by_status?.running || 0) + (stats.by_status?.pending || 0);
        if (activeCount > 0) {
            startAutoRefresh();
        } else {
            stopAutoRefresh();
        }
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}

/** Render an array of job objects as clickable cards, or show empty state. */
function renderJobs(jobs) {
    const jobsList = document.getElementById('jobs-list');
    const emptyState = document.getElementById('empty-state');

    if (jobs.length === 0) {
        jobsList.innerHTML = '';
        emptyState.style.display = 'block';
        return;
    }

    emptyState.style.display = 'none';
    jobsList.innerHTML = jobs.map(job => createJobCard(job)).join('');

    // Add click handlers
    document.querySelectorAll('.job-card').forEach(card => {
        card.addEventListener('click', () => {
            const jobId = card.dataset.jobId;
            showJobDetails(jobId);
        });
    });
}

/** Build the HTML string for a single job card (progress bar shown when running). */
function createJobCard(job) {
    const typeIcon = getTypeIcon(job.job_type);
    const typeClass = `job-type-${job.job_type}`;
    const statusClass = `status-${job.status}`;
    const progress = job.progress || 0;
    const eta = formatETA(job.eta_seconds);
    const createdAt = formatDate(job.created_at);

    let progressHTML = '';
    if (job.status === 'running') {
        const message = job.state?.message || 'Processing...';
        progressHTML = `
            <div class="job-progress">
                <div class="progress-bar-container">
                    <div class="progress-bar" style="width: ${progress}%"></div>
                    <div class="progress-text">${progress}% - ${message}</div>
                </div>
            </div>
        `;
    }

    return `
        <div class="job-card" data-job-id="${job.job_id}">
            <div class="job-header">
                <div class="job-title">
                    <span class="job-type-badge ${typeClass}">${typeIcon} ${job.job_type}</span>
                    <span>${getJobTitle(job)}</span>
                </div>
                <div class="job-status ${statusClass}">${job.status}</div>
            </div>
            <div class="job-info">
                ${getJobDescription(job)}
            </div>
            ${progressHTML}
            <div class="job-meta">
                <span>Created: ${createdAt}</span>
                ${eta ? `<span>ETA: ${eta}</span>` : ''}
                ${job.error ? `<span style="font-weight: 700">× ${job.error.substring(0, 50)}...</span>` : ''}
            </div>
        </div>
    `;
}

// Get job title
function getJobTitle(job) {
    const config = job.config || {};

    switch (job.job_type) {
        case 'download':
            return config.book_slug || 'Unknown Book';
        case 'translate':
            return config.book_id || 'Unknown Book';
        case 'audiobook':
            return config.book_id || 'Unknown Book';
        default:
            return 'Job';
    }
}

// Get job description
function getJobDescription(job) {
    const config = job.config || {};

    switch (job.job_type) {
        case 'download':
            return `Downloading from Gutenberg #${config.gutenberg_id || '?'}`;
        case 'translate':
            return `Translating from ${config.source_language || '?'} to ${config.target_language || '?'}`;
        case 'audiobook':
            const steps = [];
            if (config.translate) steps.push('translate');
            if (config.summarize) steps.push(`summarize (${config.summarize}%)`);
            steps.push(`audio (${config.voice || 'bf_emma'})`);
            if (config.generate_cover) steps.push('cover');
            return steps.join(' → ');
        default:
            return 'Processing...';
    }
}

// Get type icon
function getTypeIcon(type) {
    switch (type) {
        case 'download': return '↓';
        case 'translate': return 'T';
        case 'audiobook': return '+';
        default: return '·';
    }
}

// Format date
function formatDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes} min ago`;
    if (hours < 24) return `${hours} hour${hours > 1 ? 's' : ''} ago`;
    return `${days} day${days > 1 ? 's' : ''} ago`;
}

// Format ETA
function formatETA(seconds) {
    if (!seconds) return null;

    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);

    if (hours > 0) {
        return `${hours}h ${minutes % 60}m`;
    } else if (minutes > 0) {
        return `${minutes}m`;
    } else {
        return `${seconds}s`;
    }
}

/** Open a modal showing full details for a job (config, result, error, cancel button). */
async function showJobDetails(jobId) {
    try {
        const response = await fetch(`${API_BASE}/jobs/${jobId}`);
        const job = await response.json();

        const modalTitle = document.getElementById('modal-title');
        const modalBody = document.getElementById('modal-body');
        const cancelBtn = document.getElementById('modal-cancel-btn');

        modalTitle.textContent = `${getTypeIcon(job.job_type)} ${getJobTitle(job)}`;

        // Build details HTML
        const detailsHTML = `
            <div class="detail-row">
                <div class="detail-label">Job ID</div>
                <div class="detail-value">${job.job_id}</div>
            </div>
            <div class="detail-row">
                <div class="detail-label">Type</div>
                <div class="detail-value">${job.job_type}</div>
            </div>
            <div class="detail-row">
                <div class="detail-label">Status</div>
                <div class="detail-value">
                    <span class="job-status status-${job.status}">${job.status}</span>
                </div>
            </div>
            <div class="detail-row">
                <div class="detail-label">Progress</div>
                <div class="detail-value">${job.progress}%</div>
            </div>
            ${job.state?.message ? `
                <div class="detail-row">
                    <div class="detail-label">Current Stage</div>
                    <div class="detail-value">${job.state.message}</div>
                </div>
            ` : ''}
            <div class="detail-row">
                <div class="detail-label">Created</div>
                <div class="detail-value">${new Date(job.created_at).toLocaleString()}</div>
            </div>
            ${job.started_at ? `
                <div class="detail-row">
                    <div class="detail-label">Started</div>
                    <div class="detail-value">${new Date(job.started_at).toLocaleString()}</div>
                </div>
            ` : ''}
            ${job.completed_at ? `
                <div class="detail-row">
                    <div class="detail-label">Completed</div>
                    <div class="detail-value">${new Date(job.completed_at).toLocaleString()}</div>
                </div>
            ` : ''}
            ${job.error ? `
                <div class="detail-row">
                    <div class="detail-label">Error</div>
                    <div class="detail-value" style="font-weight: 700">
                        <div class="detail-code">${job.error}</div>
                    </div>
                </div>
            ` : ''}
            ${Object.keys(job.result || {}).length > 0 ? `
                <div class="detail-row">
                    <div class="detail-label">Result</div>
                    <div class="detail-value">
                        <div class="detail-code">${JSON.stringify(job.result, null, 2)}</div>
                    </div>
                </div>
            ` : ''}
            <div class="detail-row">
                <div class="detail-label">Configuration</div>
                <div class="detail-value">
                    <div class="detail-code">${JSON.stringify(job.config, null, 2)}</div>
                </div>
            </div>
        `;

        modalBody.innerHTML = detailsHTML;

        // Show/hide cancel button
        if (job.status === 'pending' || job.status === 'running') {
            cancelBtn.style.display = 'inline-block';
            cancelBtn.dataset.jobId = jobId;
        } else {
            cancelBtn.style.display = 'none';
        }

        document.getElementById('job-modal').style.display = 'flex';
    } catch (error) {
        console.error('Failed to load job details:', error);
        showToast('Failed to load job details', 'error');
    }
}

// Close modal
function closeModal() {
    document.getElementById('job-modal').style.display = 'none';
}

// Cancel job
async function cancelCurrentJob() {
    const jobId = document.getElementById('modal-cancel-btn').dataset.jobId;

    if (!jobId || !confirm('Are you sure you want to cancel this job?')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/jobs/${jobId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            showToast('Job cancelled', 'success');
            closeModal();
            loadJobs();
            loadStats();
        } else {
            throw new Error('Failed to cancel job');
        }
    } catch (error) {
        console.error('Failed to cancel job:', error);
        showToast('Failed to cancel job', 'error');
    }
}

// Cleanup old jobs
async function cleanupOldJobs() {
    if (!confirm('Delete all completed/failed jobs older than 24 hours?')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/jobs/cleanup`, {
            method: 'POST'
        });

        const result = await response.json();
        showToast(`Cleaned up ${result.cleaned} old jobs`, 'success');
        loadJobs();
        loadStats();
    } catch (error) {
        console.error('Failed to cleanup jobs:', error);
        showToast('Failed to cleanup jobs', 'error');
    }
}

// Auto-refresh (only while there are active jobs)
function startAutoRefresh() {
    if (refreshTimer) return; // already polling
    refreshTimer = setInterval(() => {
        loadJobs();
        loadStats();
    }, REFRESH_INTERVAL);
}

function stopAutoRefresh() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
    }
}

// Toast notification
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;

    container.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 3000);
}
