// Server Logs Viewer JavaScript

const API_BASE = '/api';
const REFRESH_INTERVAL = 5000;

let refreshTimer = null;
let autoRefresh = false;

document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    loadLogs();
});

function setupEventListeners() {
    document.getElementById('refresh-btn').addEventListener('click', loadLogs);
    document.getElementById('auto-refresh-btn').addEventListener('click', toggleAutoRefresh);

    ['filter-file', 'filter-level'].forEach(id => {
        document.getElementById(id).addEventListener('change', loadLogs);
    });
    document.getElementById('filter-since').addEventListener('change', loadLogs);
}

async function loadLogs() {
    const file = document.getElementById('filter-file').value;
    const level = document.getElementById('filter-level').value;
    const since = document.getElementById('filter-since').value;

    const params = new URLSearchParams({ file, limit: '500' });
    if (level) params.append('level', level);
    if (since) params.append('since', since);

    try {
        const response = await fetch(`${API_BASE}/logs?${params}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        renderLogs(data.entries, data.total, file);
    } catch (error) {
        console.error('Failed to load logs:', error);
        document.getElementById('logs-count').textContent = 'Failed to load logs';
        document.getElementById('logs-body').innerHTML = '';
        document.getElementById('empty-state').style.display = 'block';
    }
}

function renderLogs(entries, total, file) {
    const tbody = document.getElementById('logs-body');
    const emptyState = document.getElementById('empty-state');
    const countEl = document.getElementById('logs-count');

    if (!entries || entries.length === 0) {
        tbody.innerHTML = '';
        emptyState.style.display = 'block';
        countEl.textContent = `${file}.log — no entries`;
        return;
    }

    emptyState.style.display = 'none';
    countEl.textContent = `${file}.log — showing ${entries.length} entries (newest first)`;

    tbody.innerHTML = entries.map(entry => {
        const ts = escapeHtml(entry.timestamp);
        const lvl = escapeHtml(entry.level);
        const mod = escapeHtml(entry.module);
        const msg = escapeHtml(entry.message);
        return `<tr>
            <td>${ts}</td>
            <td class="level-${lvl}">${lvl}</td>
            <td title="${mod}">${mod}</td>
            <td>${msg}</td>
        </tr>`;
    }).join('');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function toggleAutoRefresh() {
    autoRefresh = !autoRefresh;
    const btn = document.getElementById('auto-refresh-btn');

    if (autoRefresh) {
        btn.textContent = 'Auto-refresh: ON';
        btn.classList.add('btn-active');
        refreshTimer = setInterval(loadLogs, REFRESH_INTERVAL);
    } else {
        btn.textContent = 'Auto-refresh: OFF';
        btn.classList.remove('btn-active');
        if (refreshTimer) {
            clearInterval(refreshTimer);
            refreshTimer = null;
        }
    }
}
