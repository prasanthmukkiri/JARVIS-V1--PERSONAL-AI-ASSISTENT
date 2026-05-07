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

    const brainMode = window.location.pathname === '/brain' || new URLSearchParams(window.location.search).get('open_kg') === '1';
    if (brainMode) {
        setTimeout(() => {
            if (typeof openKGModal === 'function') {
                openKGModal();
            }
        }, 350);
    }
    
    // Start polling
    setInterval(refreshStatus, UPDATE_INTERVAL);
    setInterval(refreshLogs, LOGS_POLL_INTERVAL);
    setInterval(updateFooterTime, 1000);
    setInterval(refreshGuardian, 10000);
    
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
    refreshGuardian();
}

async function refreshGuardian() {
    try {
        const res  = await fetch('/api/guardian');
        const data = await res.json();
        if (!data.success) return;
        const s = data.snapshot || {};

        // Disk free
        const diskEl   = document.getElementById('disk-percent');
        const diskFill = document.getElementById('disk-usage');
        if (diskEl && s.disk_free !== undefined) {
            const free = Math.round(s.disk_free);
            diskEl.textContent = free + '% free';
            if (diskFill) {
                diskFill.style.width = free + '%';
                diskFill.style.background = free < 15
                    ? 'var(--error-color)'
                    : free < 30 ? '#ff9800' : 'var(--accent-primary)';
            }
        }

        // Battery
        const batRow  = document.getElementById('battery-row');
        const batEl   = document.getElementById('battery-percent');
        const batFill = document.getElementById('battery-usage');
        if (batRow && s.battery !== undefined) {
            batRow.style.display = '';
            const pct = Math.round(s.battery);
            if (batEl) batEl.textContent = pct + '%' + (s.plugged ? ' ⚡' : '');
            if (batFill) {
                batFill.style.width = pct + '%';
                batFill.style.background = pct < 20 ? 'var(--error-color)'
                    : pct < 40 ? '#ff9800' : '#69ff47';
            }
        }

        // Temperature
        const tempRow = document.getElementById('temp-row');
        const tempEl  = document.getElementById('temp-value');
        if (tempRow && s.temp !== undefined) {
            tempRow.style.display = '';
            const t = Math.round(s.temp);
            if (tempEl) {
                tempEl.textContent = t + '°C';
                tempEl.style.color = t >= 85 ? 'var(--error-color)'
                    : t >= 70 ? '#ff9800' : '#69ff47';
            }
        }

        // Guardian badge — show when any metric is in warning zone
        const badge = document.getElementById('guardian-badge');
        if (badge) {
            const warn = (s.cpu >= 85) || (s.ram >= 88) || (s.disk_free <= 10)
                || (s.battery !== undefined && !s.plugged && s.battery <= 20)
                || (s.temp !== undefined && s.temp >= 85);
            badge.style.display = warn ? 'inline-block' : 'none';
        }
    } catch (e) { /* silent */ }
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
        // Start chain polling when chains tab is active
        if (tabName === 'chains') {
            onChainsTabShown();
        } else {
            stopChainPoll();
        }
        // Load memory when memory tab is active
        if (tabName === 'memory') {
            loadMemoryTab();
        }
    }

    // Mark button as active if the tab switch was triggered by a click.
    if (typeof event !== 'undefined' && event && event.target) {
        event.target.classList.add('active');
    }
}

async function openKnowledgeGraph() {
    const memoryTab = document.getElementById('memory-tab');
    if (!memoryTab) return;

    if (!memoryTab.classList.contains('active')) {
        const memoryButton = Array.from(document.querySelectorAll('.tab-button'))
            .find(btn => (btn.textContent || '').includes('MEMORY'));
        if (memoryButton) {
            memoryButton.click();
        } else {
            switchTab('memory');
        }
    }

    await loadKnowledgeGraph();

    const panel = document.getElementById('kg-panel');
    if (panel && typeof panel.scrollIntoView === 'function') {
        panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
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

// ── Chain Runner ───────────────────────────────────────────────────────────────

let _chainPollTimer = null;

function onChainsTabShown() {
    chainPoll();
    if (_chainPollTimer) clearInterval(_chainPollTimer);
    _chainPollTimer = setInterval(() => {
        const tab = document.getElementById('chains-tab');
        if (tab && tab.classList.contains('active')) {
            chainPoll();
        } else {
            stopChainPoll();
        }
    }, 2000);
}

function stopChainPoll() {
    if (_chainPollTimer) {
        clearInterval(_chainPollTimer);
        _chainPollTimer = null;
    }
}

async function chainPoll() {
    const data = await apiCall('/chains');
    if (data && data.success) {
        renderChains(data.chains || []);
    }
}

async function executeChain(goalOverride) {
    const input = document.getElementById('chain-goal-input');
    const goal = goalOverride || (input ? input.value.trim() : '');
    if (!goal) {
        showNotification('Enter a multi-step command first', 'warning');
        return;
    }

    const msg = document.getElementById('chain-status-msg');
    if (msg) {
        msg.style.display = 'block';
        msg.textContent = 'Parsing chain with JARVIS AI...';
        msg.className = 'chain-status-msg chain-status-pending';
    }

    const result = await apiCall('/chain', 'POST', { goal });
    if (result && result.success) {
        if (input) input.value = '';
        if (msg) {
            msg.textContent = `Chain ${result.chain_id} started — ${result.steps_count} step(s) queued.`;
            msg.className = 'chain-status-msg chain-status-running';
        }
        chainPoll();
    } else {
        if (msg) {
            msg.textContent = 'Failed to start chain.';
            msg.className = 'chain-status-msg chain-status-failed';
        }
        showNotification('Failed to start chain', 'error');
    }
}

function handleChainKeypress(event) {
    if (event.key === 'Enter') executeChain();
}

function renderChains(chains) {
    const listEl = document.getElementById('chain-list');
    if (!listEl) return;
    if (!chains || chains.length === 0) {
        listEl.innerHTML = '<div class="chain-empty">No chains executed yet. Enter a multi-step command above.</div>';
        return;
    }
    listEl.innerHTML = chains.map(renderChainCard).join('');
}

function renderChainCard(chain) {
    const stepsHtml = (chain.steps || []).map(renderStepCard).join('');
    const age = chain.created_at ? _chainAge(chain.created_at) : '';
    return `
        <div class="chain-card chain-status-${chain.status}">
            <div class="chain-card-header">
                <span class="chain-goal">${escapeHtml((chain.goal || '').substring(0, 90))}${(chain.goal || '').length > 90 ? '…' : ''}</span>
                <div class="chain-meta">
                    <span class="chain-badge chain-badge-${chain.status}">${chain.status.toUpperCase()}</span>
                    <span class="chain-age">${age}</span>
                    <span class="chain-id">#${chain.id}</span>
                </div>
            </div>
            <div class="chain-steps">
                ${stepsHtml || '<div class="step-empty">No steps parsed.</div>'}
            </div>
        </div>`;
}

function renderStepCard(step) {
    const dur = (step.started_at && step.ended_at)
        ? `${((step.ended_at - step.started_at) * 1000).toFixed(0)}ms` : '';
    const resultHtml = step.result
        ? `<div class="step-result">${escapeHtml(step.result.substring(0, 120))}${step.result.length > 120 ? '…' : ''}</div>` : '';
    const errorHtml = step.error
        ? `<div class="step-error">${escapeHtml(step.error.substring(0, 120))}</div>` : '';
    return `
        <div class="step-card step-${step.status}">
            <div class="step-header">
                <span class="step-tool">${escapeHtml(step.tool || '')}</span>
                <span class="step-badge step-badge-${step.status}">${step.status.toUpperCase()}</span>
                ${dur ? `<span class="step-duration">${dur}</span>` : ''}
            </div>
            <div class="step-desc">${escapeHtml(step.description || '')}</div>
            ${resultHtml}${errorHtml}
        </div>`;
}

function _chainAge(ts) {
    const d = Date.now() / 1000 - ts;
    if (d < 60) return `${Math.floor(d)}s ago`;
    if (d < 3600) return `${Math.floor(d / 60)}m ago`;
    return `${Math.floor(d / 3600)}h ago`;
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// ── Memory Tab ──────────────────────────────────────────────────────────────────

const MEMORY_CATEGORY_LABELS = {
    identity:      'Identity',
    preferences:   'Preferences',
    relationships: 'Relationships',
    projects:      'Projects',
    wishes:        'Wishes',
    notes:         'Notes',
};

async function loadMemoryTab() {
    const list = document.getElementById('memory-list');
    if (!list) return;
    list.innerHTML = '<div class="memory-empty">Loading...</div>';
    try {
        const res = await fetch('/api/memory');
        const data = await res.json();
        if (!data.success) throw new Error(data.error);
        renderMemory(data.memory);
    } catch (e) {
        list.innerHTML = `<div class="memory-empty">Error: ${escapeHtml(e.message)}</div>`;
    }
    loadEpisodeHistory();
    loadFollowups();
    loadMoodHistory();
    loadKnowledgeGraph();
    loadFileStats();
}

const MOOD_EMOJI = {
    happy: '😊', stressed: '😟', tired: '😴',
    sad: '😢', frustrated: '😠', bored: '😑',
};
const MOOD_COLOR = {
    happy: '#69ff47', stressed: '#ff9800', tired: '#90a4ae',
    sad: '#64b5f6', frustrated: '#ff5252', bored: '#bdbdbd',
};

async function loadMoodHistory() {
    const listEl    = document.getElementById('mood-list');
    const summaryEl = document.getElementById('mood-summary');
    if (!listEl) return;
    try {
        const res  = await fetch('/api/mood');
        const data = await res.json();
        if (!data.success) throw new Error(data.error);

        const log     = data.log     || [];
        const pattern = data.pattern || {};

        // Summary badge
        if (summaryEl && pattern.dominant) {
            const streak  = pattern.streak || 0;
            const trend   = pattern.trend  || '';
            const color   = MOOD_COLOR[pattern.dominant] || '#aaa';
            const emoji   = MOOD_EMOJI[pattern.dominant] || '';
            summaryEl.innerHTML = `
                <div class="mood-badge" style="border-color:${color}33;background:${color}11;">
                    <span style="color:${color};font-size:1.1rem;">${emoji}</span>
                    <span style="color:${color};font-weight:600;">${pattern.dominant}</span>
                    ${streak >= 2 ? `<span class="mood-streak">${streak} days</span>` : ''}
                    ${trend === 'improving' ? '<span class="mood-trend mood-up">↑ improving</span>' : ''}
                    ${trend === 'declining' ? '<span class="mood-trend mood-down">↓ declining</span>' : ''}
                </div>`;
        } else if (summaryEl) {
            summaryEl.innerHTML = '<div class="memory-empty" style="padding:.4rem 0;">No mood data yet — start talking to Jarvis.</div>';
        }

        if (!log.length) {
            listEl.innerHTML = '<div class="memory-empty">No mood history yet.</div>';
            return;
        }

        listEl.innerHTML = log.slice(0, 14).map(entry => {
            const dom   = entry.dominant || 'unknown';
            const color = MOOD_COLOR[dom] || '#aaa';
            const emoji = MOOD_EMOJI[dom] || '•';
            const count = (entry.emotions || []).length;
            return `<div class="mood-entry">
                <span class="mood-date">${escapeHtml(entry.date)}</span>
                <span class="mood-dot" style="background:${color};">${emoji}</span>
                <span class="mood-label" style="color:${color};">${escapeHtml(dom)}</span>
                <span class="mood-count">${count} reading${count !== 1 ? 's' : ''}</span>
            </div>`;
        }).join('');
    } catch (e) {
        if (listEl) listEl.innerHTML = '<div class="memory-empty">Error loading mood data.</div>';
    }
}

async function loadFollowups() {
    const el = document.getElementById('followup-list');
    if (!el) return;
    try {
        const res  = await fetch('/api/followups');
        const data = await res.json();
        if (!data.success) throw new Error(data.error);

        const all     = data.followups || [];
        const pending = all.filter(f => f.status === 'pending');
        const done    = all.filter(f => f.status === 'done');

        if (all.length === 0) {
            el.innerHTML = '<div class="memory-empty">No follow-ups yet. Talk to Jarvis — he\'ll track things you plan to do.</div>';
            return;
        }

        const renderItem = (f, isDone) => `
            <div class="followup-entry ${isDone ? 'followup-done' : ''}">
                <div class="followup-info">
                    <span class="followup-intention">${escapeHtml(f.intention)}</span>
                    ${f.due_hint && f.due_hint !== 'unspecified' ? `<span class="followup-due">${escapeHtml(f.due_hint)}</span>` : ''}
                    <span class="followup-meta">detected ${escapeHtml(f.detected_on)} · asked ${f.asked_count}x</span>
                </div>
                ${!isDone ? `
                <div class="followup-actions">
                    <button class="followup-btn followup-done-btn" onclick="markFollowupDone('${f.id}')">DONE</button>
                    <button class="followup-btn followup-dismiss-btn" onclick="dismissFollowup('${f.id}')">DISMISS</button>
                </div>` : ''}
            </div>`;

        let html = '';
        if (pending.length) html += pending.map(f => renderItem(f, false)).join('');
        if (done.length) {
            html += `<div class="followup-section-label">Completed</div>`;
            html += done.slice(-5).map(f => renderItem(f, true)).join('');
        }
        el.innerHTML = html;
    } catch (e) {
        el.innerHTML = `<div class="memory-empty">Error loading follow-ups.</div>`;
    }
}

async function markFollowupDone(id) {
    await fetch('/api/followups/done', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({id}) });
    loadFollowups();
}

async function dismissFollowup(id) {
    await fetch('/api/followups/dismiss', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({id}) });
    loadFollowups();
}

async function loadEpisodeHistory() {
    const el = document.getElementById('memory-history-list');
    if (!el) return;
    try {
        const res = await fetch('/api/memory/history');
        const data = await res.json();
        if (!data.success || !data.episodes.length) {
            el.innerHTML = '<div class="memory-empty">No session history yet. Jarvis will log summaries after conversations.</div>';
            return;
        }
        el.innerHTML = data.episodes.map(ep => `
            <div class="episode-entry">
                <span class="episode-date">${escapeHtml(ep.date)} ${escapeHtml(ep.time || '')}</span>
                <span class="episode-summary">${escapeHtml(ep.summary)}</span>
            </div>
        `).join('');
    } catch (e) {
        el.innerHTML = `<div class="memory-empty">Error loading history.</div>`;
    }
}

function renderMemory(memory) {
    const list = document.getElementById('memory-list');
    if (!list) return;
    const categories = Object.keys(MEMORY_CATEGORY_LABELS);
    let html = '';
    let totalEntries = 0;

    for (const cat of categories) {
        const entries = memory[cat] || {};
        const keys = Object.keys(entries);
        if (keys.length === 0) continue;
        totalEntries += keys.length;

        html += `<div class="mem-section">
            <div class="mem-section-title">${MEMORY_CATEGORY_LABELS[cat]}</div>
            <div class="mem-entries">`;

        for (const key of keys) {
            const entry = entries[key];
            const val = typeof entry === 'object' ? entry.value : entry;
            const updated = typeof entry === 'object' ? (entry.updated || '') : '';
            html += `<div class="mem-entry" id="mem-${cat}-${escapeHtml(key)}">
                <div class="mem-entry-info">
                    <span class="mem-key">${escapeHtml(key.replace(/_/g, ' '))}</span>
                    <span class="mem-val">${escapeHtml(val)}</span>
                    ${updated ? `<span class="mem-date">${updated}</span>` : ''}
                </div>
                <button class="mem-forget-btn" onclick="forgetMemory('${escapeHtml(cat)}','${escapeHtml(key)}')">FORGET</button>
            </div>`;
        }

        html += `</div></div>`;
    }

    if (totalEntries === 0) {
        list.innerHTML = '<div class="memory-empty">No memories stored yet. Jarvis will learn as you talk to him.</div>';
        return;
    }
    list.innerHTML = html;
}

async function addMemory() {
    const category = document.getElementById('mem-category').value;
    const key = document.getElementById('mem-key').value.trim().replace(/\s+/g, '_');
    const value = document.getElementById('mem-value').value.trim();
    if (!key || !value) { alert('Enter both key and value.'); return; }

    try {
        const res = await fetch('/api/memory/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ category, key, value }),
        });
        const data = await res.json();
        if (!data.success) throw new Error(data.error);
        document.getElementById('mem-key').value = '';
        document.getElementById('mem-value').value = '';
        await loadMemoryTab();
    } catch (e) {
        alert('Save failed: ' + e.message);
    }
}

async function forgetMemory(category, key) {
    if (!confirm(`Forget "${key.replace(/_/g,' ')}" from ${category}?`)) return;
    try {
        const res = await fetch('/api/memory/forget', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ category, key }),
        });
        const data = await res.json();
        if (!data.success) throw new Error(data.error);
        await loadMemoryTab();
    } catch (e) {
        alert('Forget failed: ' + e.message);
    }
}

// ── File Brain (RAG) ───────────────────────────────────────────────────────────

let _fbIndexed = false;

async function loadFileStats() {
    try {
        const res  = await fetch('/api/files/stats');
        const data = await res.json();
        if (!data.success) return;
        const s = data.stats || {};
        const filesEl  = document.getElementById('fb-stat-files');
        const chunksEl = document.getElementById('fb-stat-chunks');
        if (filesEl)  filesEl.textContent  = s.total_files  ?? '0';
        if (chunksEl) chunksEl.textContent = s.total_chunks ?? '0';
        _fbIndexed = s.files || [];

        // Show watched folders as chips
        const foldersRow = document.getElementById('fb-folders-row');
        if (foldersRow && s.watched_folders?.length) {
            foldersRow.innerHTML = s.watched_folders.map(f => {
                const name = f.split(/[\\/]/).pop() || f;
                return `<span class="fb-folder-chip" title="${escapeHtml(f)}">${escapeHtml(name)}</span>`;
            }).join('');
        }
    } catch(e) { console.error('[FileBrain] stats error:', e); }
}

async function addCustomFolder() {
    const input = document.getElementById('fb-folder-input');
    if (!input) return;
    const folder = input.value.trim();
    if (!folder) return;
    input.disabled = true;
    try {
        const res  = await fetch('/api/files/index-folder', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({folder}),
        });
        const data = await res.json();
        if (data.success) {
            input.value = '';
            input.placeholder = `Indexing ${folder.split(/[\\/]/).pop()}... (runs in background)`;
            setTimeout(() => {
                loadFileStats();
                input.placeholder = 'Add folder path  e.g. C:\\Users\\you\\Projects';
            }, 5000);
        } else {
            alert('Error: ' + (data.error || 'Unknown'));
        }
    } catch(e) { alert('Error: ' + e.message); }
    input.disabled = false;
}

async function triggerFileIndex() {
    const btn = document.getElementById('fb-index-btn');
    if (btn) { btn.textContent = '⟳ INDEXING...'; btn.disabled = true; }
    try {
        await fetch('/api/files/index', { method: 'POST' });
        setTimeout(async () => {
            await loadFileStats();
            if (btn) { btn.innerHTML = '✓ DONE'; btn.disabled = false; }
            setTimeout(() => {
                if (btn) { btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 14 14" fill="none" style="margin-right:5px"><path d="M7 1v3M7 10v3M1 7h3M10 7h3M3 3l2 2M9 9l2 2M3 11l2-2M9 5l2-2" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>INDEX FILES`; }
            }, 3000);
        }, 4000);
    } catch(e) {
        if (btn) { btn.textContent = 'INDEX FILES'; btn.disabled = false; }
    }
}

function handleFBSearchKey(e) { if (e.key === 'Enter') fileSearch(); }

async function fileSearch() {
    const input    = document.getElementById('fb-search-input');
    const resultsEl = document.getElementById('fb-results');
    if (!input || !resultsEl) return;
    const query = input.value.trim();
    if (!query) return;

    resultsEl.innerHTML = '<div class="memory-empty">Searching files...</div>';
    try {
        const res  = await fetch(`/api/files/search?q=${encodeURIComponent(query)}&top_k=6`);
        const data = await res.json();
        if (!data.success || !data.results?.length) {
            resultsEl.innerHTML = '<div class="memory-empty">No matching files found. Try indexing first.</div>';
            return;
        }
        const EXT_ICON = { '.py':'🐍', '.js':'🟨', '.ts':'🔷', '.pdf':'📕', '.docx':'📝',
            '.txt':'📄', '.md':'📋', '.json':'{}', '.csv':'📊', '.html':'🌐', '.css':'🎨' };
        resultsEl.innerHTML = data.results.map(r => {
            const score = Math.round((r.score || 0) * 100);
            const color = score >= 80 ? '#69ff47' : score >= 65 ? '#00e5ff' : '#f5a623';
            const icon  = EXT_ICON[r.file_ext || ''] || '📄';
            const text  = escapeHtml((r.text || '').substring(0, 280));
            const chunk = r.total_chunks > 1 ? ` · chunk ${(r.chunk_idx||0)+1}/${r.total_chunks}` : '';
            return `<div class="sem-result fb-result">
                <div class="sem-result-header">
                    <span class="sem-result-source" style="color:${color}">${icon} ${escapeHtml(r.file_name||'')}</span>
                    <span class="sem-result-date">${escapeHtml(r.date||'')}${chunk}</span>
                    <span class="sem-result-score" style="color:${color}">${score}% match</span>
                </div>
                <div class="sem-result-text">${text}</div>
            </div>`;
        }).join('');
    } catch(e) {
        resultsEl.innerHTML = `<div class="memory-empty">Error: ${escapeHtml(e.message)}</div>`;
    }
}

function toggleIndexedFiles() {
    const list   = document.getElementById('fb-file-list');
    const btn    = document.getElementById('fb-toggle-btn');
    const inner  = document.getElementById('fb-file-list-inner');
    if (!list) return;
    const open = list.style.display === 'none';
    list.style.display = open ? 'block' : 'none';
    if (btn) btn.textContent = open ? '▾ Hide indexed files' : '▸ Show indexed files';
    if (open && inner && _fbIndexed && _fbIndexed.length) {
        const EXT_ICON = { '.py':'🐍', '.js':'🟨', '.ts':'🔷', '.pdf':'📕', '.docx':'📝',
            '.txt':'📄', '.md':'📋', '.json':'{}', '.csv':'📊', '.html':'🌐', '.css':'🎨' };
        inner.innerHTML = _fbIndexed.map(f => {
            const icon = EXT_ICON[f.ext || ''] || '📄';
            return `<div class="fb-file-row">
                <span class="fb-file-icon">${icon}</span>
                <span class="fb-file-name">${escapeHtml(f.name)}</span>
                <span class="fb-file-meta">${f.size_kb} KB · ${f.chunks} chunk${f.chunks!==1?'s':''}</span>
            </div>`;
        }).join('');
    } else if (open && inner) {
        inner.innerHTML = '<div class="memory-empty">No files indexed yet. Click INDEX FILES to start.</div>';
    }
}

// ── Semantic Memory Search ─────────────────────────────────────────────────────

function handleSemSearchKey(e) {
    if (e.key === 'Enter') semanticSearch();
}

async function semanticSearch() {
    const input = document.getElementById('sem-search-input');
    const resultsEl = document.getElementById('sem-results');
    if (!input || !resultsEl) return;
    const q = input.value.trim();
    if (!q) return;

    resultsEl.innerHTML = '<div class="memory-empty">Searching neural memory...</div>';
    try {
        const res = await fetch(`/api/semantic/search?q=${encodeURIComponent(q)}&top_k=8`);
        const data = await res.json();
        if (!data.success) throw new Error(data.error || 'Search failed');
        const results = data.results || [];
        if (!results.length) {
            resultsEl.innerHTML = '<div class="memory-empty">No relevant memories found. Talk to Jarvis more to build up the semantic index.</div>';
            return;
        }
        resultsEl.innerHTML = results.map(r => {
            const score = (r.score * 100).toFixed(0);
            const srcBadge = r.source === 'episode' ? 'SESSION' : r.source.toUpperCase();
            const color = r.source === 'episode' ? 'var(--accent)' : '#69ff47';
            return `<div class="sem-result">
                <div class="sem-result-header">
                    <span class="sem-result-source" style="color:${color};">${srcBadge}</span>
                    <span class="sem-result-date">${escapeHtml(r.date || '')}</span>
                    <span class="sem-result-score">${score}% match</span>
                </div>
                <div class="sem-result-text">${escapeHtml(r.text || '')}</div>
            </div>`;
        }).join('');
    } catch (e) {
        resultsEl.innerHTML = `<div class="memory-empty">Error: ${escapeHtml(e.message)}</div>`;
    }
}

// ── Knowledge Graph ────────────────────────────────────────────────────────────

let _kgData = null;
let _kgSelectedNode = null;
let _kgActiveFilter = null;
let _kgPos      = {};
let _kgVel      = {};
let _kgZoom     = { scale: 1, tx: 0, ty: 0 };
let _kgDrag     = { active: false, lastX: 0, lastY: 0, moved: false };
let _kgAnimFrame = null;
let _kgParticles = [];
let _kgEdgesAnim = [];
let _kgNodesDom  = {};
let _kgByType    = {};
let _kgSimAlpha  = 1.0;
let _kgFrameN    = 0;
const KG_SVG_W = 1200, KG_SVG_H = 820;

const KG_TYPE_COLOR = {
    person:  '#69ff47',
    place:   '#00e5ff',
    project: '#f5a623',
    org:     '#bb86fc',
    tool:    '#ff6b9d',
    concept: '#90a4ae',
};
const KG_TYPE_ICON = {
    person: '👤', place: '📍', project: '🚀', org: '🏢', tool: '🔧', concept: '💡',
};

async function loadKnowledgeGraph() {
    try {
        const res = await fetch('/api/knowledge-graph');
        const data = await res.json();
        if (!data.success) throw new Error(data.error || 'Failed');
        _kgData = data.graph || { nodes: {}, edges: [] };
        updateKGBanner(_kgData);
    } catch (e) {
        console.error('[KG] load error:', e);
    }
}

function updateKGBanner(graph) {
    const nodes = graph.nodes || {};
    const names = Object.keys(nodes);
    const types = new Set(names.map(n => nodes[n].type || 'concept'));
    const nodesEl = document.getElementById('kg-stat-nodes');
    const edgesEl = document.getElementById('kg-stat-edges');
    const typesEl = document.getElementById('kg-stat-types');
    if (nodesEl) nodesEl.textContent = names.length;
    if (edgesEl) edgesEl.textContent = (graph.edges || []).length;
    if (typesEl) typesEl.textContent = types.size;
}

// ── KG Modal ──────────────────────────────────────────────────────────────────

async function openKGModal() {
    const modal = document.getElementById('kg-modal');
    if (!modal) return;
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
    _kgZoom = { scale: 1, tx: 0, ty: 0 };

    if (!_kgData) {
        try {
            const res = await fetch('/api/knowledge-graph');
            const data = await res.json();
            _kgData = data.graph || { nodes: {}, edges: [] };
        } catch(e) { _kgData = { nodes: {}, edges: [] }; }
    }

    renderKGModal(_kgData);
    document.addEventListener('keydown', _kgEscHandler);
}

function closeKGModal() {
    if (_kgAnimFrame) { cancelAnimationFrame(_kgAnimFrame); _kgAnimFrame = null; }
    _kgParticles.forEach(p => { if (p.el) p.el.remove(); });
    _kgParticles = [];
    const modal = document.getElementById('kg-modal');
    if (modal) modal.style.display = 'none';
    document.body.style.overflow = '';
    document.removeEventListener('keydown', _kgEscHandler);
    window.removeEventListener('mousemove', _kgOnDragMove);
    window.removeEventListener('mouseup', _kgOnDragUp);
    _kgDrag.active = false;
}

function handleKGModalClick(e) {
    if (e.target.id === 'kg-modal') closeKGModal();
}

function _kgEscHandler(e) {
    if (e.key === 'Escape') closeKGModal();
}

// ── KG Zoom / Pan ─────────────────────────────────────────────────────────────

function _kgApplyZoom() {
    const vp  = document.getElementById('kg-viewport');
    const lvl = document.getElementById('kg-zoom-level');
    if (vp) vp.setAttribute('transform', `translate(${_kgZoom.tx.toFixed(1)},${_kgZoom.ty.toFixed(1)}) scale(${_kgZoom.scale.toFixed(3)})`);
    if (lvl) lvl.textContent = Math.round(_kgZoom.scale * 100) + '%';
}

function kgZoomIn()    { _kgZoom.scale = Math.min(5, _kgZoom.scale * 1.3); _kgApplyZoom(); }
function kgZoomOut()   { _kgZoom.scale = Math.max(0.15, _kgZoom.scale / 1.3); _kgApplyZoom(); }
function kgZoomReset() { _kgZoom = { scale: 1, tx: 0, ty: 0 }; _kgApplyZoom(); }

function _kgOnDragMove(e) {
    if (!_kgDrag.active) return;
    const svgEl = document.getElementById('kg-svg-main');
    if (!svgEl) return;
    const rect = svgEl.getBoundingClientRect();
    const dx = (e.clientX - _kgDrag.lastX) * (KG_SVG_W / rect.width);
    const dy = (e.clientY - _kgDrag.lastY) * (KG_SVG_H / rect.height);
    _kgZoom.tx += dx;
    _kgZoom.ty += dy;
    _kgDrag.lastX = e.clientX;
    _kgDrag.lastY = e.clientY;
    _kgDrag.moved = true;
    _kgApplyZoom();
}

function _kgOnDragUp() {
    if (!_kgDrag.active) return;
    _kgDrag.active = false;
    const svgEl = document.getElementById('kg-svg-main');
    if (svgEl) svgEl.style.cursor = 'grab';
}

function _kgSetupZoomPan(svgEl) {
    svgEl.style.cursor = 'grab';

    svgEl.addEventListener('wheel', (e) => {
        e.preventDefault();
        const rect = svgEl.getBoundingClientRect();
        const mx = (e.clientX - rect.left) / rect.width  * KG_SVG_W;
        const my = (e.clientY - rect.top)  / rect.height * KG_SVG_H;
        const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
        const ns = Math.min(5, Math.max(0.15, _kgZoom.scale * factor));
        _kgZoom.tx = mx - (mx - _kgZoom.tx) * (ns / _kgZoom.scale);
        _kgZoom.ty = my - (my - _kgZoom.ty) * (ns / _kgZoom.scale);
        _kgZoom.scale = ns;
        _kgApplyZoom();
    }, { passive: false });

    svgEl.addEventListener('mousedown', (e) => {
        if (e.button !== 0) return;
        _kgDrag.active = true;
        _kgDrag.lastX  = e.clientX;
        _kgDrag.lastY  = e.clientY;
        _kgDrag.moved  = false;
        svgEl.style.cursor = 'grabbing';
    });

    window.addEventListener('mousemove', _kgOnDragMove);
    window.addEventListener('mouseup',   _kgOnDragUp);
}

function filterKGNodes(query) {
    if (!_kgData) return;
    const svgEl = document.getElementById('kg-svg-main');
    if (!svgEl) return;
    const q = query.toLowerCase().trim();
    svgEl.querySelectorAll('.kg-node-group').forEach(g => {
        const name = g.dataset.node || '';
        const match = !q || name.includes(q);
        g.style.opacity = match ? '1' : '0.15';
    });
}

function setKGTypeFilter(type) {
    _kgActiveFilter = _kgActiveFilter === type ? null : type;
    document.querySelectorAll('.kg-type-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.type === _kgActiveFilter);
    });
    filterKGByType(_kgActiveFilter);
}

function filterKGByType(type) {
    const svgEl = document.getElementById('kg-svg-main');
    if (!svgEl || !_kgData) return;
    svgEl.querySelectorAll('.kg-node-group').forEach(g => {
        const name = g.dataset.node || '';
        const nodeType = (_kgData.nodes[name] || {}).type || 'concept';
        g.style.opacity = !type || nodeType === type ? '1' : '0.1';
    });
}

function renderKGModal(graph) {
    if (_kgAnimFrame) { cancelAnimationFrame(_kgAnimFrame); _kgAnimFrame = null; }
    _kgParticles.forEach(p => { if (p.el) p.el.remove(); });
    _kgParticles = []; _kgEdgesAnim = []; _kgNodesDom = {}; _kgByType = {};
    _kgSimAlpha = 1.0; _kgFrameN = 0;

    const graphWrap = document.getElementById('kg-modal-graph');
    const statsEl   = document.getElementById('kg-modal-stats');
    const legendEl  = document.getElementById('kg-modal-legend');
    const filtersEl = document.getElementById('kg-type-filters');
    if (!graphWrap) return;

    const nodes = graph.nodes || {};
    const edges = graph.edges || [];
    const names = Object.keys(nodes);

    if (!names.length) {
        graphWrap.innerHTML = `<div class="kg-empty-state"><div class="kg-empty-icon">◎</div>
            <p>No entities yet.</p>
            <p style="opacity:.6;font-size:.8rem;margin-top:.4rem">Jarvis extracts entities from conversations automatically.</p></div>`;
        return;
    }

    const typeCounts = {};
    names.forEach(n => { const t = nodes[n].type||'concept'; typeCounts[t] = (typeCounts[t]||0)+1; });
    if (statsEl) statsEl.innerHTML = [
        `<div class="kg-stat-row"><span>Entities</span><strong>${names.length}</strong></div>`,
        `<div class="kg-stat-row"><span>Relationships</span><strong>${edges.length}</strong></div>`,
        ...Object.entries(typeCounts).map(([t,c]) =>
            `<div class="kg-stat-row"><span style="color:${KG_TYPE_COLOR[t]||'#aaa'}">${KG_TYPE_ICON[t]||'•'} ${t}</span><strong>${c}</strong></div>`),
    ].join('');
    if (legendEl) legendEl.innerHTML = Object.entries(KG_TYPE_COLOR).map(([t,c]) =>
        `<div class="kg-legend-row"><span class="kg-legend-dot" style="background:${c}"></span>${KG_TYPE_ICON[t]||''} ${t}</div>`).join('');
    if (filtersEl) filtersEl.innerHTML = Object.keys(typeCounts).map(t =>
        `<button class="kg-type-btn" data-type="${t}" style="--tc:${KG_TYPE_COLOR[t]||'#aaa'}" onclick="setKGTypeFilter('${t}')">${KG_TYPE_ICON[t]||''} ${t}</button>`).join('');

    const W = KG_SVG_W, H = KG_SVG_H;
    const sorted = [...names].sort((a,b) => (nodes[b].mentions||1) - (nodes[a].mentions||1));

    // Brain-region cluster anchors — spread across canvas
    const ANCHORS = {
        person:  {x: W*.50, y: H*.17},
        project: {x: W*.80, y: H*.30},
        place:   {x: W*.78, y: H*.72},
        concept: {x: W*.50, y: H*.83},
        tool:    {x: W*.20, y: H*.30},
        org:     {x: W*.22, y: H*.72},
    };

    // Cluster groups for weak-edge web
    sorted.forEach(n => { const t = nodes[n].type||'concept'; (_kgByType[t] = _kgByType[t]||[]).push(n); });

    // Initial positions scattered around cluster anchors
    _kgPos = {}; _kgVel = {};
    sorted.forEach(name => {
        const type   = nodes[name].type || 'concept';
        const anchor = ANCHORS[type] || {x: W/2, y: H/2};
        const a = Math.random() * Math.PI * 2;
        const d = 30 + Math.random() * 80;
        _kgPos[name] = {
            x: Math.max(85, Math.min(W-85, anchor.x + Math.cos(a)*d)),
            y: Math.max(60, Math.min(H-85, anchor.y + Math.sin(a)*d)),
        };
        _kgVel[name] = {vx: 0, vy: 0};
    });

    // Starfield background
    const stars = Array.from({length: 240}, () => {
        const x  = (Math.random()*W).toFixed(1);
        const y  = (Math.random()*H).toFixed(1);
        const r  = (Math.random()*1.4+0.2).toFixed(1);
        const op = (Math.random()*0.45+0.07).toFixed(2);
        return `<circle cx="${x}" cy="${y}" r="${r}" fill="white" opacity="${op}"/>`;
    }).join('');

    // Guide rings
    const gridRings = Array.from({length: 5}, (_,i) =>
        `<circle cx="${W/2}" cy="${H/2}" r="${95+i*140}" fill="none" stroke="rgba(0,229,255,0.04)" stroke-width="1" stroke-dasharray="3 18"/>`
    ).join('') +
    `<line x1="${W/2-24}" y1="${H/2}" x2="${W/2+24}" y2="${H/2}" stroke="rgba(0,229,255,0.1)" stroke-width="1"/>
     <line x1="${W/2}" y1="${H/2-24}" x2="${W/2}" y2="${H/2+24}" stroke="rgba(0,229,255,0.1)" stroke-width="1"/>`;

    const defs = `<defs>
      <filter id="kgGlow" x="-80%" y="-80%" width="260%" height="260%">
        <feGaussianBlur stdDeviation="6" result="b"/>
        <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
      </filter>
      <filter id="kgGlowHub" x="-120%" y="-120%" width="340%" height="340%">
        <feGaussianBlur stdDeviation="14" result="b"/>
        <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
      </filter>
      <filter id="kgGlowEdge" x="-80%" y="-80%" width="260%" height="260%">
        <feGaussianBlur stdDeviation="4"/>
      </filter>
      <filter id="kgGlowPart" x="-400%" y="-400%" width="900%" height="900%">
        <feGaussianBlur stdDeviation="5"/>
      </filter>
      <radialGradient id="kgCenterAura" cx="50%" cy="50%" r="42%">
        <stop offset="0%"   stop-color="rgba(0,160,255,0.07)"/>
        <stop offset="100%" stop-color="rgba(0,0,0,0)"/>
      </radialGradient>
    </defs>`;

    graphWrap.innerHTML = `<svg id="kg-svg-main" class="kg-modal-svg"
        viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg"
        preserveAspectRatio="xMidYMid meet">
      ${defs}
      <rect width="${W}" height="${H}" fill="#040b18"/>
      <g id="kg-starfield">${stars}</g>
      <rect width="${W}" height="${H}" fill="url(#kgCenterAura)"/>
      <g id="kg-viewport">
        <g id="kg-grid-layer">${gridRings}</g>
        <g id="kg-weak-edges-layer"></g>
        <g id="kg-edges-layer"></g>
        <g id="kg-particles-layer"></g>
        <g id="kg-nodes-layer"></g>
      </g>
    </svg>`;

    const NS         = 'http://www.w3.org/2000/svg';
    const weakLayer  = document.getElementById('kg-weak-edges-layer');
    const edgesLayer = document.getElementById('kg-edges-layer');
    const nodesLayer = document.getElementById('kg-nodes-layer');

    // Weak same-type web lines (visual density, no particles)
    Object.entries(_kgByType).forEach(([type, members]) => {
        const color = KG_TYPE_COLOR[type] || '#334466';
        for (let i = 0; i < members.length; i++) {
            for (let j = i+1; j < members.length; j++) {
                const path = document.createElementNS(NS, 'path');
                path.setAttribute('fill', 'none');
                path.setAttribute('stroke', color);
                path.setAttribute('stroke-opacity', '0');
                path.setAttribute('stroke-width', '0.7');
                weakLayer.appendChild(path);
            }
        }
    });

    // Actual KG edges (brighter, with animated particles)
    _kgEdgesAnim = [];
    edges.forEach(e => {
        if (!_kgPos[e.from] || !_kgPos[e.to]) return;
        const color = KG_TYPE_COLOR[(nodes[e.from]||{}).type] || '#446688';

        const glow = document.createElementNS(NS, 'path');
        glow.setAttribute('fill', 'none');
        glow.setAttribute('stroke', color);
        glow.setAttribute('stroke-width', '6');
        glow.setAttribute('stroke-opacity', '0.07');
        glow.setAttribute('filter', 'url(#kgGlowEdge)');

        const main = document.createElementNS(NS, 'path');
        main.setAttribute('fill', 'none');
        main.setAttribute('stroke', color);
        main.setAttribute('stroke-width', '1.4');
        main.setAttribute('stroke-opacity', '0.4');

        edgesLayer.appendChild(glow);
        edgesLayer.appendChild(main);
        _kgEdgesAnim.push({from: e.from, to: e.to, color, glowEl: glow, mainEl: main});
    });

    // Node SVG elements — brain-orb style
    _kgNodesDom = {};
    sorted.forEach((name, idx) => {
        const node  = nodes[name];
        const color = KG_TYPE_COLOR[node.type||'concept'] || '#90a4ae';
        const isHub = idx === 0;
        const r     = isHub ? 17 : Math.max(7, Math.min(6 + (node.mentions||1)*2.5, 14));
        const label = (name.length > 15 ? name.slice(0,14)+'…' : name).toUpperCase();
        const rW    = Math.max(72, label.length*7.2 + 22);
        const rH    = 20; const rY = r+9;

        const g = document.createElementNS(NS, 'g');
        g.setAttribute('class', 'kg-node-group');
        g.setAttribute('data-node', name);
        g.style.cursor = 'pointer';
        g.addEventListener('click', () => selectKGNode(name));

        // Halo (pulsed on select/hover)
        const halo = document.createElementNS(NS, 'circle');
        halo.setAttribute('class', 'kg-node-halo');
        halo.setAttribute('r', isHub ? 40 : r+18);
        halo.setAttribute('fill', color);
        halo.setAttribute('opacity', '0');
        halo.setAttribute('filter', 'url(#kgGlowHub)');

        // Main glowing orb
        const circ = document.createElementNS(NS, 'circle');
        circ.setAttribute('r', r);
        circ.setAttribute('fill', 'rgba(3,7,18,0.92)');
        circ.setAttribute('stroke', color);
        circ.setAttribute('stroke-width', isHub ? '2.8' : '1.8');
        circ.setAttribute('filter', isHub ? 'url(#kgGlowHub)' : 'url(#kgGlow)');

        // Bright core dot
        const core = document.createElementNS(NS, 'circle');
        core.setAttribute('r', isHub ? 6 : 2.5);
        core.setAttribute('fill', color);
        core.setAttribute('opacity', '0.95');

        // Label card background
        const lRect = document.createElementNS(NS, 'rect');
        lRect.setAttribute('x', -(rW/2)); lRect.setAttribute('y', rY);
        lRect.setAttribute('width', rW);  lRect.setAttribute('height', rH);
        lRect.setAttribute('rx', '2');
        lRect.setAttribute('fill', 'rgba(3,7,18,0.88)');
        lRect.setAttribute('stroke', color);
        lRect.setAttribute('stroke-width', '0.8');
        lRect.setAttribute('stroke-opacity', '0.5');

        // Label text
        const lText = document.createElementNS(NS, 'text');
        lText.setAttribute('text-anchor', 'middle');
        lText.setAttribute('x', '0'); lText.setAttribute('y', rY+13);
        lText.setAttribute('fill', color);
        lText.setAttribute('font-size', isHub ? '9.5' : '8');
        lText.setAttribute('font-family', "'Courier New',monospace");
        lText.setAttribute('font-weight', isHub ? '700' : '600');
        lText.setAttribute('letter-spacing', '0.6');
        lText.textContent = label;

        // Sub-label: type · mentions
        const sub = document.createElementNS(NS, 'text');
        sub.setAttribute('text-anchor', 'middle');
        sub.setAttribute('x', '0'); sub.setAttribute('y', rY+rH+11);
        sub.setAttribute('fill', 'rgba(150,190,220,0.32)');
        sub.setAttribute('font-size', '6.5');
        sub.setAttribute('font-family', "'Courier New',monospace");
        sub.textContent = `${node.type||'concept'} · ${node.mentions||1}×`;

        g.append(halo, circ, core, lRect, lText, sub);
        nodesLayer.appendChild(g);
        _kgNodesDom[name] = g;

        const p = _kgPos[name];
        g.setAttribute('transform', `translate(${p.x.toFixed(1)},${p.y.toFixed(1)})`);
    });

    // Initial edge positions
    _kgUpdateEdgePaths();
    _kgUpdateWeakEdges();

    const svgEl = document.getElementById('kg-svg-main');
    if (svgEl) { _kgSetupZoomPan(svgEl); _kgApplyZoom(); }
    if (sorted[0]) selectKGNode(sorted[0]);

    _kgAnimLoop();
}

// ── KG Neural Physics + Particle Engine ───────────────────────────────────────

function _kgBezCtrl(x1, y1, x2, y2) {
    const mx = (x1+x2)*0.5, my = (y1+y2)*0.5;
    const dx = x2-x1, dy = y2-y1;
    const len = Math.sqrt(dx*dx+dy*dy) || 1;
    const curve = Math.min(len*0.22, 95);
    return { cx: mx - (dy/len)*curve, cy: my + (dx/len)*curve };
}

function _kgBezPt(t, x1, y1, cx, cy, x2, y2) {
    const u = 1-t;
    return { x: u*u*x1+2*u*t*cx+t*t*x2, y: u*u*y1+2*u*t*cy+t*t*y2 };
}

function _kgUpdateEdgePaths() {
    _kgEdgesAnim.forEach(e => {
        const s = _kgPos[e.from], t = _kgPos[e.to];
        if (!s || !t) return;
        const {cx, cy} = _kgBezCtrl(s.x, s.y, t.x, t.y);
        const d = `M${s.x.toFixed(1)},${s.y.toFixed(1)} Q${cx.toFixed(1)},${cy.toFixed(1)} ${t.x.toFixed(1)},${t.y.toFixed(1)}`;
        if (e.mainEl) e.mainEl.setAttribute('d', d);
        if (e.glowEl) e.glowEl.setAttribute('d', d);
    });
}

function _kgUpdateWeakEdges() {
    const weakLayer = document.getElementById('kg-weak-edges-layer');
    if (!weakLayer) return;
    const paths = weakLayer.querySelectorAll('path');
    let idx = 0;
    Object.values(_kgByType).forEach(members => {
        for (let i = 0; i < members.length; i++) {
            for (let j = i+1; j < members.length; j++) {
                if (idx >= paths.length) return;
                const s = _kgPos[members[i]], t = _kgPos[members[j]];
                if (!s || !t) { idx++; continue; }
                const dist = Math.sqrt((s.x-t.x)**2 + (s.y-t.y)**2);
                const op   = dist < 270 ? (0.1*(1-dist/270)).toFixed(3) : '0';
                paths[idx].setAttribute('d', `M${s.x.toFixed(1)},${s.y.toFixed(1)} L${t.x.toFixed(1)},${t.y.toFixed(1)}`);
                paths[idx].setAttribute('stroke-opacity', op);
                idx++;
            }
        }
    });
}

function _kgForceStep() {
    const nodes  = _kgData?.nodes || {};
    const nlist  = Object.keys(_kgPos);
    if (nlist.length < 2) return;
    const W = KG_SVG_W, H = KG_SVG_H;
    const alpha    = _kgSimAlpha;
    const REPEL    = 3400;
    const SPRING_K = 0.0028;
    const REST_LEN = 170;
    const CLUSTER_K= 0.0045;
    const CENTER_K = 0.0004;
    const DAMP     = 0.87;
    const ANCHORS  = {
        person:  {x: W*.50, y: H*.17},
        project: {x: W*.80, y: H*.30},
        place:   {x: W*.78, y: H*.72},
        concept: {x: W*.50, y: H*.83},
        tool:    {x: W*.20, y: H*.30},
        org:     {x: W*.22, y: H*.72},
    };

    const fx = {}, fy = {};
    nlist.forEach(n => { fx[n] = 0; fy[n] = 0; });

    // Repulsion between all node pairs
    for (let i = 0; i < nlist.length; i++) {
        for (let j = i+1; j < nlist.length; j++) {
            const a = nlist[i], b = nlist[j];
            const pa = _kgPos[a], pb = _kgPos[b];
            const dx = pa.x-pb.x, dy = pa.y-pb.y;
            const d2 = Math.max(dx*dx+dy*dy, 120);
            const d  = Math.sqrt(d2);
            const f  = (REPEL/d2) * alpha;
            fx[a] += dx/d*f; fy[a] += dy/d*f;
            fx[b] -= dx/d*f; fy[b] -= dy/d*f;
        }
    }

    // Spring along actual KG edges
    _kgEdgesAnim.forEach(e => {
        const s = _kgPos[e.from], t = _kgPos[e.to];
        if (!s || !t) return;
        const dx = t.x-s.x, dy = t.y-s.y;
        const d  = Math.sqrt(dx*dx+dy*dy) || 1;
        const f  = SPRING_K * (d-REST_LEN) * alpha;
        const nx = dx/d, ny = dy/d;
        fx[e.from] += nx*f; fy[e.from] += ny*f;
        fx[e.to]   -= nx*f; fy[e.to]   -= ny*f;
    });

    // Cluster gravity — pull toward type anchor
    nlist.forEach(name => {
        const type   = (nodes[name]||{}).type || 'concept';
        const anchor = ANCHORS[type] || {x: W/2, y: H/2};
        const p = _kgPos[name];
        fx[name] += (anchor.x-p.x) * CLUSTER_K * alpha;
        fy[name] += (anchor.y-p.y) * CLUSTER_K * alpha;
    });

    // Gentle center pull
    nlist.forEach(name => {
        const p = _kgPos[name];
        fx[name] += (W/2-p.x) * CENTER_K * alpha;
        fy[name] += (H/2-p.y) * CENTER_K * alpha;
    });

    // Integrate
    nlist.forEach(name => {
        if (!_kgVel[name]) _kgVel[name] = {vx:0,vy:0};
        const v = _kgVel[name];
        v.vx = (v.vx + fx[name]) * DAMP;
        v.vy = (v.vy + fy[name]) * DAMP;
        const p = _kgPos[name];
        p.x = Math.max(75, Math.min(W-75, p.x+v.vx));
        p.y = Math.max(58, Math.min(H-85, p.y+v.vy));
    });
}

function _kgAnimLoop() {
    if (!document.getElementById('kg-nodes-layer')) return;
    if (!_kgData) return;
    _kgFrameN++;

    // Force simulation (cooling)
    if (_kgSimAlpha > 0.007) {
        _kgForceStep();
        _kgSimAlpha *= 0.993;
    }

    // Update node transforms
    Object.entries(_kgNodesDom).forEach(([name, el]) => {
        const p = _kgPos[name];
        if (p && el) el.setAttribute('transform', `translate(${p.x.toFixed(1)},${p.y.toFixed(1)})`);
    });

    // Update edge paths every frame
    _kgUpdateEdgePaths();

    // Weak edges — less critical, update every 3 frames
    if (_kgFrameN % 3 === 0) _kgUpdateWeakEdges();

    // Spawn particle on a random real KG edge
    if (_kgEdgesAnim.length > 0 && _kgFrameN % 9 === 0 && _kgParticles.length < 160) {
        const idx = Math.floor(Math.random() * _kgEdgesAnim.length);
        const e   = _kgEdgesAnim[idx];
        _kgParticles.push({edgeIdx: idx, t: 0,
            speed: 0.0035 + Math.random()*0.006,
            color: e.color,
            size:  1.6 + Math.random()*2.8});
    }

    // Move particles
    const NS        = 'http://www.w3.org/2000/svg';
    const partsLayer = document.getElementById('kg-particles-layer');
    if (partsLayer) {
        _kgParticles = _kgParticles.filter(p => {
            p.t += p.speed;
            if (p.t >= 1) { if (p.el) p.el.remove(); return false; }
            return true;
        });
        _kgParticles.forEach(p => {
            const e = _kgEdgesAnim[p.edgeIdx];
            if (!e) return;
            const s = _kgPos[e.from], t = _kgPos[e.to];
            if (!s || !t) return;
            const {cx, cy} = _kgBezCtrl(s.x, s.y, t.x, t.y);
            const pt = _kgBezPt(p.t, s.x, s.y, cx, cy, t.x, t.y);
            if (!p.el) {
                const grp  = document.createElementNS(NS, 'g');
                const glow = document.createElementNS(NS, 'circle');
                glow.setAttribute('r', (p.size*3.2).toFixed(1));
                glow.setAttribute('fill', p.color);
                glow.setAttribute('filter', 'url(#kgGlowPart)');
                const dot = document.createElementNS(NS, 'circle');
                dot.setAttribute('r', p.size.toFixed(1));
                dot.setAttribute('fill', p.color);
                grp.append(glow, dot);
                partsLayer.appendChild(grp);
                p.el = grp; p.glowEl = glow; p.dotEl = dot;
            }
            p.el.setAttribute('transform', `translate(${pt.x.toFixed(1)},${pt.y.toFixed(1)})`);
            const fade = p.t < 0.07 ? p.t/0.07 : p.t > 0.87 ? (1-p.t)/0.13 : 1;
            if (p.dotEl)  p.dotEl.setAttribute('opacity',  (fade*0.95).toFixed(2));
            if (p.glowEl) p.glowEl.setAttribute('opacity', (fade*0.30).toFixed(2));
        });
    }

    // Random node pulse every ~70 frames
    if (_kgFrameN % 70 === 1) {
        const nlist = Object.keys(_kgNodesDom);
        if (nlist.length) {
            const nm   = nlist[Math.floor(Math.random()*nlist.length)];
            const halo = _kgNodesDom[nm]?.querySelector('.kg-node-halo');
            if (halo) {
                halo.setAttribute('opacity', '0.18');
                setTimeout(() => { if (halo) halo.setAttribute('opacity', '0'); }, 450);
            }
        }
    }

    _kgAnimFrame = requestAnimationFrame(_kgAnimLoop);
}

// ── KG Node Selection ─────────────────────────────────────────────────────────

function selectKGNode(name) {
    if (!_kgData) return;
    if (_kgDrag.moved) { _kgDrag.moved = false; return; }
    _kgSelectedNode = name;

    // Smooth pan to node (keep current zoom level)
    const p = _kgPos[name];
    if (p) {
        const targetTx = KG_SVG_W / 2 - _kgZoom.scale * p.x;
        const targetTy = KG_SVG_H / 2 - _kgZoom.scale * p.y;
        const steps = 12;
        let step = 0;
        const fromTx = _kgZoom.tx, fromTy = _kgZoom.ty;
        const anim = () => {
            step++;
            const t = step / steps;
            const ease = 1 - Math.pow(1 - t, 3);
            _kgZoom.tx = fromTx + (targetTx - fromTx) * ease;
            _kgZoom.ty = fromTy + (targetTy - fromTy) * ease;
            _kgApplyZoom();
            if (step < steps) requestAnimationFrame(anim);
        };
        requestAnimationFrame(anim);
    }

    // Highlight in SVG
    const svgEl = document.getElementById('kg-svg-main');
    if (svgEl) {
        svgEl.querySelectorAll('.kg-node-group').forEach(g => {
            g.classList.toggle('kg-node-selected', g.dataset.node === name);
        });
    }

    // Show detail panel
    const detailCard = document.getElementById('kg-modal-detail-card');
    const detailEl   = document.getElementById('kg-modal-detail');
    const titleEl    = document.getElementById('kg-modal-detail-title');
    if (!detailEl || !detailCard) return;

    const node  = (_kgData.nodes || {})[name] || {};
    const edges = (_kgData.edges || []).filter(e => e.from === name || e.to === name);
    const color = KG_TYPE_COLOR[node.type||'concept'] || '#aaa';

    if (titleEl) titleEl.innerHTML = `<span style="color:${color}">${KG_TYPE_ICON[node.type]||'•'}</span> ${escapeHtml(name)}`;

    detailEl.innerHTML = `
        <div class="kg-detail-meta">
            <span class="kg-detail-badge" style="color:${color};border-color:${color}33">${node.type||'concept'}</span>
            <span class="kg-detail-stat">${node.mentions||1} mention${(node.mentions||1)!==1?'s':''}</span>
            ${node.first_seen ? `<span class="kg-detail-stat">since ${node.first_seen}</span>` : ''}
        </div>
        ${edges.length ? `
        <div class="kg-detail-edges-title">Relationships (${edges.length})</div>
        <div class="kg-detail-edges">
        ${edges.map(e => {
            const other = e.from === name ? e.to : e.from;
            const dir   = e.from === name ? '→' : '←';
            const otherColor = KG_TYPE_COLOR[(_kgData.nodes[other]||{}).type] || '#aaa';
            return `<div class="kg-detail-edge-row">
                <span class="kg-detail-dir">${dir}</span>
                <span class="kg-detail-rel">${escapeHtml(e.relation)}</span>
                <span class="kg-detail-other" style="color:${otherColor}">${escapeHtml(other)}</span>
            </div>`;
        }).join('')}
        </div>` : '<div class="kg-detail-no-edges">No relationships yet.</div>'}
    `;
    detailCard.style.display = 'block';
}

function renderKGNodes(graph) {
    const nodesEl = document.getElementById('kg-nodes');
    if (!nodesEl) return;
    const nodes = graph.nodes || {};
    const names = Object.keys(nodes);
    if (!names.length) {
        nodesEl.innerHTML = '<div class="memory-empty">No entities yet. Jarvis will extract them from conversations automatically.</div>';
        return;
    }

    const TYPE_COLOR = {
        person: '#69ff47', place: '#00e5ff', project: '#f5a623',
        org: '#bb86fc', tool: '#ff6b9d', concept: '#90a4ae',
    };

    const graphEntries = names.sort((a, b) => (nodes[b].mentions || 1) - (nodes[a].mentions || 1));
    const nodeSet = new Set(graphEntries);
    const edges = (_kgData?.edges || []).filter(edge => nodeSet.has(edge.from) || nodeSet.has(edge.to));
    const width = 1100;
    const height = 720;
    const centerX = width / 2;
    const centerY = height / 2;

    const hubName = graphEntries[0];
    const typeOrder = ['person', 'project', 'place', 'concept', 'org', 'tool'];
    const typeAnchors = {
        person: { x: centerX, y: 165 },
        project: { x: 860, y: 245 },
        place: { x: 850, y: 510 },
        concept: { x: centerX, y: 585 },
        org: { x: 255, y: 510 },
        tool: { x: 250, y: 245 },
    };

    const grouped = {};
    for (const name of graphEntries) {
        const type = nodes[name].type || 'concept';
        if (!grouped[type]) grouped[type] = [];
        grouped[type].push(name);
    }

    const layoutNodes = [];
    const clusterCount = {};
    for (const name of graphEntries) {
        const node = nodes[name];
        const type = node.type || 'concept';
        const color = TYPE_COLOR[type] || '#aaa';

        if (name === hubName) {
            layoutNodes.push({
                id: name,
                name,
                type,
                mentions: node.mentions || 1,
                color,
                x: centerX,
                y: centerY,
                size: 42,
            });
            continue;
        }

        const anchor = typeAnchors[type] || { x: centerX, y: centerY };
        const idx = clusterCount[type] || 0;
        clusterCount[type] = idx + 1;
        const ring = 74 + Math.min(idx * 28, 120);
        const angleStep = Math.PI / Math.max(3, (grouped[type] || []).length + 1);
        const baseAngle = (typeOrder.indexOf(type) >= 0 ? typeOrder.indexOf(type) : 3) * (Math.PI / 3) - Math.PI / 2;
        const angle = baseAngle + (idx % 2 === 0 ? 1 : -1) * angleStep * Math.ceil((idx + 1) / 2);

        layoutNodes.push({
            id: name,
            name,
            type,
            mentions: node.mentions || 1,
            color,
            x: anchor.x + Math.cos(angle) * ring,
            y: anchor.y + Math.sin(angle) * ring,
            size: Math.max(18, Math.min(20 + (node.mentions || 1) * 4, 38)),
        });
    }

    const byId = new Map(layoutNodes.map(node => [node.id, node]));
    const linkData = edges
        .map(edge => ({
            source: byId.get(edge.from),
            target: byId.get(edge.to),
            relation: edge.relation,
        }))
        .filter(edge => edge.source && edge.target);

    const snapshot = graphEntries.slice(0, 18).map(name => {
        const node = nodes[name];
        return `<div class="kg-legend-item"><span class="kg-legend-dot" style="background:${TYPE_COLOR[node.type] || '#aaa'}"></span>${escapeHtml(name)}</div>`;
    }).join('');

    const svg = [
        `<div class="kg-nodes-label">Interactive graph view of ${names.length} entities</div>`,
        `<div class="kg-graph-shell">`,
        `<div class="kg-workbench">`,
        `<div class="kg-graph-frame">`,
        `<svg class="kg-graph" id="kg-graph-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Knowledge graph">`,
        `<defs>`,
        `<radialGradient id="kgBg" cx="50%" cy="45%" r="70%">`,
        `<stop offset="0%" stop-color="rgba(0,229,255,0.14)"></stop>`,
        `<stop offset="55%" stop-color="rgba(0,229,255,0.04)"></stop>`,
        `<stop offset="100%" stop-color="rgba(0,0,0,0)"></stop>`,
        `</radialGradient>`,
        `<filter id="kgGlow" x="-50%" y="-50%" width="200%" height="200%">`,
        `<feGaussianBlur stdDeviation="4" result="coloredBlur"></feGaussianBlur>`,
        `<feMerge><feMergeNode in="coloredBlur"></feMergeNode><feMergeNode in="SourceGraphic"></feMergeNode></feMerge>`,
        `</filter>`,
        `</defs>`,
        `<rect x="0" y="0" width="${width}" height="${height}" fill="url(#kgBg)"></rect>`,
        `<g class="kg-grid">`,
        Array.from({ length: 10 }).map((_, i) => `<circle cx="${centerX}" cy="${centerY}" r="${80 + i * 48}" fill="none" stroke="rgba(255,255,255,0.05)" stroke-dasharray="6 10"></circle>`).join(''),
        `<line x1="${centerX}" y1="40" x2="${centerX}" y2="${height - 40}" stroke="rgba(255,255,255,0.05)"/>`,
        `<line x1="60" y1="${centerY}" x2="${width - 60}" y2="${centerY}" stroke="rgba(255,255,255,0.05)"/>`,
        `</g>`,
        `<g class="kg-links">`,
        linkData.map((edge, index) => {
            const stroke = edge.source.color || '#555';
            return `<path class="kg-link" data-relation="${escapeHtml(edge.relation)}" d="M ${edge.source.x} ${edge.source.y} Q ${(edge.source.x + edge.target.x) / 2} ${(edge.source.y + edge.target.y) / 2 - 36} ${edge.target.x} ${edge.target.y}" fill="none" stroke="${stroke}" stroke-opacity="0.28" stroke-width="${Math.max(1.3, Math.min(3.2, Math.sqrt((edge.source.mentions || 1) + (edge.target.mentions || 1)) / 2))}"/>`;
        }).join(''),
        `</g>`,
        `<g class="kg-nodes-layer">`,
        layoutNodes.map(node => {
            const size = node.size;
            return `<g class="kg-node-group" data-node="${escapeHtml(node.id)}" transform="translate(${node.x},${node.y})" onclick="showKGEdges('${escapeHtml(node.id)}')" tabindex="0" role="button">`
                + `<circle class="kg-node-core" r="${size}" fill="${node.color}" opacity="0.22" filter="url(#kgGlow)"></circle>`
                + `<circle class="kg-node-ring" r="${size * 0.72}" fill="none" stroke="${node.color}" stroke-width="2.2"></circle>`
                + `<circle class="kg-node-dot" r="${Math.max(4, size * 0.28)}" fill="${node.color}"></circle>`
                + `<text class="kg-node-label" text-anchor="middle" y="${size + 18}">${escapeHtml(node.id)}</text>`
                + `</g>`;
        }).join(''),
        `</g>`,
        `</svg>`,
        `</div>`,
        `<aside class="kg-side-panel">`,
        `<div class="kg-side-card">`,
        `<div class="kg-side-title">Network Summary</div>`,
        `<div class="kg-side-stat"><span>Entities</span><strong>${names.length}</strong></div>`,
        `<div class="kg-side-stat"><span>Relationships</span><strong>${linkData.length}</strong></div>`,
        `<div class="kg-side-stat"><span>Center Node</span><strong>${escapeHtml(hubName || '')}</strong></div>`,
        `</div>`,
        `<div class="kg-side-card">`,
        `<div class="kg-side-title">Types</div>`,
        `<div class="kg-legend">${snapshot}</div>`,
        `</div>`,
        `</aside>`,
        `</div>`,
        `</div>`,
    ].join('');

    nodesEl.innerHTML = svg;

    const centerNode = byId.get(graphEntries[0]);
    if (centerNode) {
        showKGEdges(centerNode.id);
    }
}

function showKGEdges(entityName) {
    if (!_kgData) return;
    const edgesEl = document.getElementById('kg-edges');
    const edgesListEl = document.getElementById('kg-edges-list');
    if (!edgesEl || !edgesListEl) return;

    _kgSelectedNode = entityName;
    const allEdges = (_kgData.edges || []).filter(e =>
        e.from === entityName || e.to === entityName
    );

    if (!allEdges.length) {
        edgesListEl.innerHTML = '<div class="memory-empty">No relationships found for this entity.</div>';
    } else {
        edgesListEl.innerHTML = allEdges.map(e =>
            `<div class="kg-edge-row">
                <span class="kg-edge-from">${escapeHtml(e.from)}</span>
                <span class="kg-edge-rel">— ${escapeHtml(e.relation)} →</span>
                <span class="kg-edge-to">${escapeHtml(e.to)}</span>
                <span class="kg-edge-date">${escapeHtml(e.date || '')}</span>
            </div>`
        ).join('');
    }

    edgesEl.style.display = 'block';
    edgesEl.querySelector('.kg-edges-title').textContent = `Relationships: "${entityName}"`;
}
