// Jarvis Dashboard JavaScript

// ── Constants ──────────────────────────────────────────────────────────────────
const API_BASE = '/api';
const UPDATE_INTERVAL = 2000; // 2 seconds
const LOGS_POLL_INTERVAL = 1000; // 1 second

// ── State ──────────────────────────────────────────────────────────────────────
let dashboardState = {
    awake: false,
    listening: false,
    lastCommand: '',
    uptime: 0,
};

let logsCache = [];
let historyCache = [];
let settingsCache = {};

// ── Initialization ─────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    console.log('[Dashboard] Initializing...');
    
    // Load initial data
    refreshData();
    loadSettings();
    
    // Start polling
    setInterval(refreshStatus, UPDATE_INTERVAL);
    setInterval(refreshLogs, LOGS_POLL_INTERVAL);
    setInterval(updateFooterTime, 1000);
    
    // Handle keyboard shortcuts
    document.addEventListener('keydown', handleKeyboard);
    
    console.log('[Dashboard] Ready');
});

// ── API Calls ──────────────────────────────────────────────────────────────────

async function apiCall(endpoint, method = 'GET', data = null) {
    try {
        const options = {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            }
        };
        
        if (data && method !== 'GET') {
            options.body = JSON.stringify(data);
        }
        
        const response = await fetch(API_BASE + endpoint, options);
        
        if (!response.ok) {
            console.error(`[API] ${method} ${endpoint} returned ${response.status}`);
            return null;
        }
        
        return await response.json();
    } catch (error) {
        console.error(`[API] Error: ${error.message}`);
        return null;
    }
}

// ── Data Refresh ───────────────────────────────────────────────────────────────

async function refreshStatus() {
    const data = await apiCall('/status');
    if (!data || !data.success) return;
    
    dashboardState = {
        awake: data.awake,
        listening: data.listening,
        lastCommand: data.last_command,
        uptime: data.uptime_seconds,
        cpuPercent: data.cpu_percent,
        memoryPercent: data.memory_percent,
    };
    
    updateStatusUI();
}

async function refreshLogs() {
    const data = await apiCall('/logs/live');
    if (!data || !data.success) return;
    
    if (data.logs && data.logs.length > 0) {
        logsCache.push(...data.logs);
        
        // Keep only last 500 logs
        if (logsCache.length > 500) {
            logsCache = logsCache.slice(-500);
        }
        
        updateLogsUI();
    }
}

async function refreshData() {
    await refreshStatus();
    await loadHistory();
    await loadSettings();
}

async function loadHistory() {
    const data = await apiCall('/action-history');
    if (!data || !data.success) return;
    
    historyCache = data.actions || [];
    updateHistoryUI();
}

async function loadSettings() {
    const data = await apiCall('/settings');
    if (!data || !data.success) return;
    
    settingsCache = data.settings || {};
    updateSettingsUI();
}

// ── UI Updates ─────────────────────────────────────────────────────────────────

function updateStatusUI() {
    const awakeEl = document.getElementById('agent-state');
    const listeningEl = document.getElementById('agent-listening');
    const lastCmdEl = document.getElementById('last-command');
    const uptimeEl = document.getElementById('uptime');
    const statusBadge = document.getElementById('status-indicator');
    const cpuEl = document.getElementById('cpu-percent');
    const memEl = document.getElementById('memory-percent');
    const reactorCard = document.querySelector('.reactor-card');
    const reactorCore = document.getElementById('reactor-core');
    const reactorStatus = document.getElementById('reactor-status');
    const reactorMeterFill = document.getElementById('reactor-meter-fill');
    const signalCard = document.querySelector('.signal-card');
    const signalState = document.getElementById('signal-state');
    const signalWave = document.getElementById('signal-wave');
    const bannerPulse = document.getElementById('banner-pulse');
    const bannerProtocol = document.getElementById('banner-protocol');
    const bannerQueue = document.getElementById('banner-queue');
    const telemetryMode = document.getElementById('telemetry-mode');
    const telemetrySignal = document.getElementById('telemetry-signal');
    const telemetryQueue = document.getElementById('telemetry-queue');
    
    if (awakeEl) {
        awakeEl.textContent = dashboardState.awake ? 'Awake' : 'Sleeping';
    }
    
    if (listeningEl) {
        listeningEl.textContent = dashboardState.listening ? 'On' : 'Off';
    }
    
    if (lastCmdEl) {
        lastCmdEl.textContent = dashboardState.lastCommand || 'None';
    }
    
    if (uptimeEl) {
        uptimeEl.textContent = formatUptime(dashboardState.uptime);
    }
    
    if (statusBadge) {
        statusBadge.classList.remove('status-awake', 'status-sleeping');
        statusBadge.classList.add(dashboardState.awake ? 'status-awake' : 'status-sleeping');
        statusBadge.textContent = dashboardState.awake ? 'Awake' : 'Sleeping';
    }
    
    if (cpuEl) {
        cpuEl.textContent = Math.round(dashboardState.cpuPercent) + '%';
        const cpuFill = document.getElementById('cpu-usage');
        if (cpuFill) {
            cpuFill.style.width = Math.min(100, dashboardState.cpuPercent) + '%';
        }
    }
    
    if (memEl) {
        memEl.textContent = Math.round(dashboardState.memoryPercent) + '%';
        const memFill = document.getElementById('memory-usage');
        if (memFill) {
            memFill.style.width = Math.min(100, dashboardState.memoryPercent) + '%';
        }
    }

    if (telemetryMode) {
        telemetryMode.textContent = dashboardState.awake ? 'ACTIVE' : 'STANDBY';
    }

    if (telemetrySignal) {
        telemetrySignal.textContent = dashboardState.listening ? 'LOCKED' : 'IDLE';
    }

    if (telemetryQueue) {
        telemetryQueue.textContent = `${logsCache.length} EVENTS`;
    }

    if (bannerPulse) {
        const pulse = Math.round(
            (dashboardState.cpuPercent * 0.35) +
            (dashboardState.memoryPercent * 0.2) +
            (dashboardState.awake ? 25 : 6) +
            (dashboardState.listening ? 12 : 0)
        );
        bannerPulse.textContent = `${Math.min(100, Math.max(8, pulse))}`;
    }

    if (bannerProtocol) {
        bannerProtocol.textContent = dashboardState.awake ? (dashboardState.listening ? 'LISTENING' : 'ONLINE') : 'STANDBY';
    }

    if (bannerQueue) {
        bannerQueue.textContent = String(logsCache.length).padStart(2, '0');
    }

    if (reactorCard) {
        reactorCard.classList.remove('reactor-awake', 'reactor-listening', 'reactor-speaking', 'reactor-thinking');

        let state = 'reactor-thinking';
        let label = 'THINKING';
        let meterWidth = '42%';

        if (dashboardState.awake && dashboardState.listening) {
            state = 'reactor-listening';
            label = 'LISTENING';
            meterWidth = '66%';
        } else if (dashboardState.awake) {
            state = 'reactor-awake';
            label = 'AWAKE';
            meterWidth = '58%';
        } else {
            label = 'STANDBY';
            meterWidth = '24%';
        }

        reactorCard.classList.add(state);

        if (reactorCore) {
            reactorCore.classList.remove('reactor-awake', 'reactor-listening', 'reactor-speaking', 'reactor-thinking');
            reactorCore.classList.add(state);
        }

        if (reactorStatus) {
            reactorStatus.textContent = label;
        }

        if (reactorMeterFill) {
            reactorMeterFill.style.width = meterWidth;
        }
    }

    if (signalCard) {
        signalCard.classList.remove('signal-active', 'signal-listening', 'signal-speaking');

        let signalClass = '';
        let signalLabel = 'Quiet';

        if (dashboardState.awake && dashboardState.listening) {
            signalClass = 'signal-listening';
            signalLabel = 'Listening';
        } else if (dashboardState.awake) {
            signalClass = 'signal-active';
            signalLabel = 'Active';
        }

        if (dashboardState.awake && !dashboardState.listening && dashboardState.lastCommand) {
            signalClass = 'signal-speaking';
            signalLabel = 'Speaking';
        }

        signalCard.classList.add(signalClass);

        if (signalState) {
            signalState.textContent = signalLabel;
        }

        if (signalWave) {
            const bars = signalWave.querySelectorAll('span');
            bars.forEach((bar, index) => {
                const base = dashboardState.awake ? 0.45 : 0.22;
                const listeningBoost = dashboardState.listening ? 0.28 : 0.1;
                const commandBoost = dashboardState.lastCommand ? 0.14 : 0;
                const height = base + listeningBoost + commandBoost + ((index % 4) * 0.06);
                bar.style.height = `${Math.min(1, height) * 100}%`;
                bar.style.animationDelay = `${index * 0.08}s`;
            });
        }
    }
}

function updateLogsUI() {
    const logsList = document.getElementById('logs-list');
    if (!logsList) return;
    
    if (logsCache.length === 0) {
        logsList.innerHTML = '<div class="log-empty">No logs yet. Waiting for activity...</div>';
        return;
    }
    
    // Show last 50 logs
    const displayLogs = logsCache.slice(-50);
    logsList.innerHTML = displayLogs.map(log => `
        <div class="log-entry">
            <span class="log-time">${formatTime(log.timestamp)}</span>
            <span class="log-message">${escapeHtml(log.message)}</span>
        </div>
    `).join('');
    
    // Auto-scroll to bottom
    logsList.scrollTop = logsList.scrollHeight;
}

function updateHistoryUI() {
    const tbody = document.getElementById('history-body');
    if (!tbody) return;
    
    if (historyCache.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty">No history yet</td></tr>';
        return;
    }
    
    tbody.innerHTML = historyCache.map(action => `
        <tr>
            <td>${formatTime(action.timestamp)}</td>
            <td>${escapeHtml(action.command.substring(0, 30))}</td>
            <td>${action.tool}</td>
            <td><span class="status-${action.status}">${action.status}</span></td>
            <td>${action.duration_ms}ms</td>
        </tr>
    `).join('');
}

function updateSettingsUI() {
    const wakeWordsEl = document.getElementById('wake-words');
    const sleepWordsEl = document.getElementById('sleep-words');
    const timeoutEl = document.getElementById('timeout-seconds');
    const energyEl = document.getElementById('energy-threshold');
    const vadEl = document.getElementById('vad-aggressiveness');
    
    if (wakeWordsEl && settingsCache.wake_words) {
        wakeWordsEl.value = settingsCache.wake_words.join(', ');
    }
    
    if (sleepWordsEl && settingsCache.sleep_words) {
        sleepWordsEl.value = settingsCache.sleep_words.join(', ');
    }
    
    if (timeoutEl && settingsCache.active_timeout_s) {
        timeoutEl.value = settingsCache.active_timeout_s;
    }
    
    if (energyEl && settingsCache.energy_threshold) {
        energyEl.value = settingsCache.energy_threshold;
    }
    
    if (vadEl && settingsCache.vad_aggressiveness !== undefined) {
        vadEl.value = settingsCache.vad_aggressiveness;
    }
}

// ── Tab Navigation ────────────────────────────────────────────────────────────

function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Remove active from all buttons
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected tab
    const tabEl = document.getElementById(tabName + '-tab');
    if (tabEl) {
        tabEl.classList.add('active');
        
        // Load analytics data when switching to analytics tab
        if (tabName === 'analytics') {
            onAnalyticsTabShown();
        }
    }
    
    // Mark button as active
    event.target.classList.add('active');
}

// ── Actions ────────────────────────────────────────────────────────────────────

async function sendCommand(command) {
    const result = await apiCall('/command', 'POST', { command });
    if (result && result.success) {
        showNotification('Command sent: ' + command);
    } else {
        showNotification('Failed to send command', 'error');
    }
}

function sendManualCommand() {
    const input = document.getElementById('command-input');
    if (!input || !input.value.trim()) {
        showNotification('Please enter a command', 'warning');
        return;
    }
    
    sendCommand(input.value.trim());
    input.value = '';
}

function handleCommandKeypress(event) {
    if (event.key === 'Enter') {
        sendManualCommand();
    }
}

async function toggleState() {
    // TODO: Implement toggle (wake/sleep)
    showNotification('Toggle not yet implemented', 'warning');
}

async function saveSettings() {
    const settings = {
        wake_words: document.getElementById('wake-words').value.split(',').map(s => s.trim()),
        sleep_words: document.getElementById('sleep-words').value.split(',').map(s => s.trim()),
        active_timeout_s: parseInt(document.getElementById('timeout-seconds').value),
        energy_threshold: parseInt(document.getElementById('energy-threshold').value),
        vad_aggressiveness: parseInt(document.getElementById('vad-aggressiveness').value),
    };
    
    const result = await apiCall('/settings', 'POST', settings);
    if (result && result.success) {
        showNotification('Settings saved successfully');
        settingsCache = settings;
    } else {
        showNotification('Failed to save settings', 'error');
    }
}

function clearLogs() {
    logsCache = [];
    updateLogsUI();
    showNotification('Logs cleared');
}

// ── Utilities ──────────────────────────────────────────────────────────────────

function formatTime(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', { hour12: false });
}

function formatUptime(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

function updateFooterTime() {
    const el = document.getElementById('footer-time');
    if (el) {
        const now = new Date();
        el.textContent = now.toLocaleTimeString('en-US', { hour12: false });
    }
}

function showNotification(message, type = 'success') {
    // Simple console notification (can be replaced with toast library)
    console.log(`[${type.toUpperCase()}] ${message}`);
    
    // TODO: Add toast notification UI
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function handleKeyboard(event) {
    // Ctrl+Shift+K: Focus command input
    if (event.ctrlKey && event.shiftKey && event.key === 'K') {
        document.getElementById('command-input')?.focus();
        event.preventDefault();
    }
    
    // Ctrl+R: Refresh data
    if (event.ctrlKey && event.key === 'r') {
        refreshData();
        event.preventDefault();
    }
}

// -- Analytics Functions -------------------------------------------------------

const analyticsCharts = {};
let analyticsRefreshTimer = null;

function getChartCanvasId(chartType) {
    const canvasMap = {
        success_rates: 'success-rates-canvas',
        tool_usage: 'tool-usage-canvas',
        execution_times: 'execution-times-canvas',
        failures: 'failures-canvas',
    };

    return canvasMap[chartType] || null;
}

function destroyChart(chartType) {
    const chart = analyticsCharts[chartType];
    if (chart) {
        chart.destroy();
        delete analyticsCharts[chartType];
    }
}

async function refreshAnalytics() {
    try {
        const analyticsData = await apiCall('/analytics');
        if (analyticsData && analyticsData.success) {
            updateAnalyticsUI(analyticsData);
        }

        const insightsData = await apiCall('/insights');
        if (insightsData && insightsData.success) {
            updateInsightsUI(insightsData.insights);
        }

        await Promise.all([
            loadChart('success_rates'),
            loadChart('tool_usage'),
            loadChart('execution_times'),
            loadChart('failures'),
        ]);
    } catch (error) {
        console.error('[Analytics] Error:', error);
    }
}

async function loadChart(chartType) {
    try {
        const chartData = await apiCall(`/chart/${chartType}`);
        if (chartData && chartData.success) {
            renderChart(chartType, chartData.data || {});
        }
    } catch (error) {
        console.error(`[Chart] Error loading ${chartType}:`, error);
    }
}

function renderChart(chartType, data) {
    const canvasId = getChartCanvasId(chartType);
    if (!canvasId) return;

    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    destroyChart(chartType);

    if (typeof Chart === 'undefined') {
        const ctx = canvas.getContext('2d');
        if (!ctx) return;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = '#9eb7cf';
        ctx.font = '14px Segoe UI';
        ctx.textAlign = 'center';
        ctx.fillText('Chart.js unavailable', canvas.width / 2, canvas.height / 2);
        return;
    }

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let config = null;

    if (chartType === 'success_rates') {
        config = {
            type: 'bar',
            data: {
                labels: data.labels || [],
                datasets: [{
                    label: 'Success %',
                    data: data.values || [],
                    backgroundColor: 'rgba(72, 232, 255, 0.55)',
                    borderColor: '#48e8ff',
                    borderWidth: 1,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: { color: '#9eb7cf' },
                        grid: { color: 'rgba(158, 183, 207, 0.15)' },
                    },
                    x: {
                        ticks: { color: '#9eb7cf' },
                        grid: { display: false },
                    },
                },
            },
        };
    } else if (chartType === 'tool_usage') {
        config = {
            type: 'bar',
            data: {
                labels: data.labels || [],
                datasets: [{
                    label: 'Executions',
                    data: data.values || [],
                    backgroundColor: 'rgba(33, 255, 131, 0.5)',
                    borderColor: '#21ff83',
                    borderWidth: 1,
                }],
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: {
                        beginAtZero: true,
                        ticks: { color: '#9eb7cf' },
                        grid: { color: 'rgba(158, 183, 207, 0.15)' },
                    },
                    y: {
                        ticks: { color: '#9eb7cf' },
                        grid: { display: false },
                    },
                },
            },
        };
    } else if (chartType === 'execution_times') {
        config = {
            type: 'line',
            data: {
                labels: data.labels || [],
                datasets: [
                    {
                        label: 'Mean',
                        data: data.means || [],
                        borderColor: '#48e8ff',
                        backgroundColor: 'rgba(72, 232, 255, 0.12)',
                        tension: 0.3,
                    },
                    {
                        label: 'p95',
                        data: data.p95 || [],
                        borderColor: '#ffcf4a',
                        backgroundColor: 'rgba(255, 207, 74, 0.12)',
                        tension: 0.3,
                    },
                    {
                        label: 'p99',
                        data: data.p99 || [],
                        borderColor: '#ff5f75',
                        backgroundColor: 'rgba(255, 95, 117, 0.12)',
                        tension: 0.3,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { labels: { color: '#effcff' } } },
                scales: {
                    y: {
                        ticks: { color: '#9eb7cf' },
                        grid: { color: 'rgba(158, 183, 207, 0.15)' },
                    },
                    x: {
                        ticks: { color: '#9eb7cf' },
                        grid: { display: false },
                    },
                },
            },
        };
    } else if (chartType === 'failures') {
        config = {
            type: 'doughnut',
            data: {
                labels: data.labels || [],
                datasets: [{
                    data: data.values || [],
                    backgroundColor: ['#ff5f75', '#ffcf4a', '#48e8ff', '#21ff83', '#009dff'],
                    borderColor: '#030817',
                    borderWidth: 2,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { labels: { color: '#effcff' } } },
            },
        };
    }

    if (!config) return;
    analyticsCharts[chartType] = new Chart(ctx, config);
}

function updateAnalyticsUI(analyticsData) {
    const data = analyticsData.summary || {};

    const healthPercent = document.getElementById('health-percent');
    if (healthPercent) {
        healthPercent.textContent = Math.round(data.health_score || 0) + '%';
    }

    const statsBody = document.getElementById('stats-body');
    if (statsBody) {
        const toolStats = analyticsData.tool_stats || {};
        const successRates = analyticsData.success_rates || {};
        let html = '';

        for (const [tool, stats] of Object.entries(toolStats)) {
            const executions = stats.count ?? 0;
            const meanMs = ((stats.mean ?? 0) * 1000).toFixed(1);
            const p95Ms = ((stats.p95 ?? 0) * 1000).toFixed(1);
            const rate = successRates[tool] ?? 0;

            html += `
                <tr>
                    <td>${escapeHtml(tool)}</td>
                    <td>${executions}</td>
                    <td>${meanMs}</td>
                    <td>${p95Ms}</td>
                    <td>${rate.toFixed(1)}%</td>
                </tr>
            `;
        }

        if (html) {
            statsBody.innerHTML = html;
        }
    }
}

function updateInsightsUI(insights) {
    const panel = document.getElementById('insights-panel');
    if (!panel) return;

    if (!insights || insights.length === 0) {
        panel.innerHTML = '<div class="insight-item insight-info"><span>All systems nominal</span></div>';
        return;
    }

    let html = '';
    for (const insight of insights) {
        const type = insight.type || 'info';
        const title = insight.title || 'Insight';
        const message = insight.message || '';
        html += `
            <div class="insight-item insight-${type}">
                <span><strong>${escapeHtml(title)}:</strong> ${escapeHtml(message)}</span>
            </div>
        `;
    }
    panel.innerHTML = html;
}

function onAnalyticsTabShown() {
    refreshEmotionStats();
    refreshAnalytics();

    if (analyticsRefreshTimer) {
        clearInterval(analyticsRefreshTimer);
    }

    analyticsRefreshTimer = setInterval(() => {
        const analyticsTab = document.getElementById('analytics-tab');
        if (analyticsTab && analyticsTab.classList.contains('active')) {
            refreshAnalytics();
            refreshEmotionStats();
        } else {
            clearInterval(analyticsRefreshTimer);
            analyticsRefreshTimer = null;
        }
    }, 5000);
}

// -- Emotion Detection Functions ------------------------------------------------

async function startEmotionDetection() {
    try {
        const result = await apiCall('/emotion/start', 'POST', { duration: 5.0 });
        if (result && result.success) {
            showNotification('Emotion recording started for 5 seconds...');
            setTimeout(stopEmotionDetection, 5500);
        } else {
            showNotification('Emotion detection not available', 'warning');
        }
    } catch (error) {
        console.error('[Emotion] Error:', error);
        showNotification('Failed to start emotion detection', 'error');
    }
}

async function stopEmotionDetection() {
    try {
        const result = await apiCall('/emotion/stop', 'POST');
        if (result && result.success) {
            updateEmotionUI(result.stats);
            showNotification('Emotion recording stopped');
        }
    } catch (error) {
        console.error('[Emotion] Error:', error);
    }
}

async function refreshEmotionStats() {
    try {
        const result = await apiCall('/emotion/stats');
        if (result && result.success) {
            if (result.enabled) {
                updateEmotionUI(result.stats);
            } else {
                updateEmotionUI({
                    recording: false,
                    total_frames: 0,
                    face_detection_rate: 0,
                    emotions: {},
                    dominant_emotion: null,
                });
            }
        }
    } catch (error) {
        console.error('[Emotion] Error:', error);
    }
}

function updateEmotionUI(stats) {
    if (!stats) return;

    const emotionPanel = document.getElementById('emotion-stats');
    if (!emotionPanel) return;

    let html = '';

    html += '<div class="emotion-stat-row">';
    html += '<span class="emotion-label">Status</span>';
    html += '<span class="emotion-value">' + (stats.recording ? 'Recording' : 'Ready') + '</span>';
    html += '</div>';

    if (stats.total_frames > 0) {
        html += '<div class="emotion-stat-row">';
        html += '<span class="emotion-label">Frames Captured</span>';
        html += '<span class="emotion-value">' + stats.total_frames + '</span>';
        html += '</div>';

        html += '<div class="emotion-stat-row">';
        html += '<span class="emotion-label">Face Detection Rate</span>';
        html += '<span class="emotion-value">' + stats.face_detection_rate + '%</span>';
        html += '</div>';
    }

    if (stats.dominant_emotion) {
        html += '<div class="emotion-stat-row">';
        html += '<span class="emotion-label">Dominant Emotion</span>';
        html += '<span class="emotion-value emotion-badge">' + stats.dominant_emotion.toUpperCase() + '</span>';
        html += '</div>';
    }

    if (stats.emotions && Object.keys(stats.emotions).length > 0) {
        html += '<div style="margin-top: 1rem;">';
        html += '<span class="emotion-label" style="display: block; margin-bottom: 0.5rem;">Emotion Breakdown</span>';

        const totalEmotions = Object.values(stats.emotions).reduce((a, b) => a + b, 0);
        for (const [emotion, count] of Object.entries(stats.emotions)) {
            const percentage = ((count / totalEmotions) * 100).toFixed(0);
            html += '<div style="margin-bottom: 0.5rem;">';
            html += '<span style="font-size: 0.75rem; color: var(--text-secondary);">' + emotion + ' (' + percentage + '%)</span>';
            html += '<div class="emotion-bar"><div class="emotion-bar-fill" style="width: ' + percentage + '%"></div></div>';
            html += '</div>';
        }
        html += '</div>';
    }

    emotionPanel.innerHTML = html || '<p>No emotion data yet</p>';
}
