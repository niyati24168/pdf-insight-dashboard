const state = {
    files: [],
    activeTab: 'summary',
    apiKey: localStorage.getItem('gemini_api_key') || '',
    chatHistory: [],
    charts: {
        topics: null,
        sentiment: null
    },
    isAnalyzing: false
};

const DOM = {
    themeToggleBtn: document.getElementById('themeToggleBtn'),
    sunIcon: document.getElementById('sunIcon'),
    moonIcon: document.getElementById('moonIcon'),
    
    
    apiKeyStatus: document.getElementById('apiKeyStatus'),
    btnConfigApiKey: document.getElementById('btnConfigApiKey'),
    apiKeyModal: document.getElementById('apiKeyModal'),
    btnModalClose: document.getElementById('btnModalClose'),
    apiKeyInput: document.getElementById('apiKeyInput'),
    btnTogglePassword: document.getElementById('btnTogglePassword'),
    btnCancelApiKey: document.getElementById('btnCancelApiKey'),
    btnSaveApiKey: document.getElementById('btnSaveApiKey'),
    
    
    dropZone: document.getElementById('dropZone'),
    fileInput: document.getElementById('fileInput'),
    fileCountBadge: document.getElementById('fileCountBadge'),
    fileListContainer: document.getElementById('fileListContainer'),
    fileEmptyState: document.getElementById('fileEmptyState'),
    btnClearAll: document.getElementById('btnClearAll'),
    
   
    tabs: document.querySelectorAll('.tab-link'),
    panels: document.querySelectorAll('.tab-panel'),
    
    
    summaryState: document.getElementById('summaryState'),
    summaryContentContainer: document.getElementById('summaryContentContainer'),
    summaryTextContent: document.getElementById('summaryTextContent'),
    btnRefreshSummary: document.getElementById('btnRefreshSummary'),
    
    
    dashboardState: document.getElementById('dashboardState'),
    dashboardContentContainer: document.getElementById('dashboardContentContainer'),
    statTotalPages: document.getElementById('statTotalPages'),
    statWordCount: document.getElementById('statWordCount'),
    statRiskCount: document.getElementById('statRiskCount'),
    statSentiment: document.getElementById('statSentiment'),
    takeawaysListContainer: document.getElementById('takeawaysListContainer'),
    
    
    chatDocSubtitle: document.getElementById('chatDocSubtitle'),
    chatMessagesContainer: document.getElementById('chatMessagesContainer'),
    chatSuggestionsContainer: document.getElementById('chatSuggestionsContainer'),
    chatForm: document.getElementById('chatForm'),
    chatInput: document.getElementById('chatInput'),
    btnSendChat: document.getElementById('btnSendChat'),
    chips: document.querySelectorAll('.chip')
};

document.addEventListener('DOMContentLoaded', () => {

    lucide.createIcons();
    

    updateApiKeyUI();
    

    initTabs();
    

    initTheme();
    

    initFileUpload();
    
  
    initApiKeyModal();
    

    initChat();

    DOM.btnClearAll.addEventListener('click', clearAllFiles);
    DOM.btnRefreshSummary.addEventListener('click', analyzeDocuments);
});

function initTheme() {
  
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcons(savedTheme);
    
    DOM.themeToggleBtn.addEventListener('click', () => {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        updateThemeIcons(newTheme);
    });
}
function updateThemeIcons(theme) {
    if (theme === 'light') {
        DOM.sunIcon.classList.add('hidden');
        DOM.moonIcon.classList.remove('hidden');
    } else {
        DOM.sunIcon.classList.remove('hidden');
        DOM.moonIcon.classList.add('hidden');
    }
}

function initApiKeyModal() {
    DOM.btnConfigApiKey.addEventListener('click', () => {
        DOM.apiKeyInput.value = state.apiKey;
        DOM.apiKeyModal.classList.remove('hidden');
    });
    
    const closeModal = () => DOM.apiKeyModal.classList.add('hidden');
    DOM.btnModalClose.addEventListener('click', closeModal);
    DOM.btnCancelApiKey.addEventListener('click', closeModal);
    
    DOM.btnSaveApiKey.addEventListener('click', () => {
        const value = DOM.apiKeyInput.value.trim();
        state.apiKey = value;
        localStorage.setItem('gemini_api_key', value);
        updateApiKeyUI();
        closeModal();
        
      
        if (state.files.length > 0) {
            analyzeDocuments();
        }
    });
    
    
    DOM.btnTogglePassword.addEventListener('click', () => {
        const type = DOM.apiKeyInput.getAttribute('type') === 'password' ? 'text' : 'password';
        DOM.apiKeyInput.setAttribute('type', type);
        
        
        const icon = DOM.btnTogglePassword.querySelector('i');
        if (type === 'text') {
            icon.setAttribute('data-lucide', 'eye-off');
        } else {
            icon.setAttribute('data-lucide', 'eye');
        }
        lucide.createIcons();
    });
}
function updateApiKeyUI() {
    const indicator = DOM.apiKeyStatus.querySelector('.status-indicator');
    const text = DOM.apiKeyStatus.querySelector('.status-text');
    
    if (state.apiKey) {
        indicator.className = 'status-indicator success';
        text.textContent = 'API Key Configured';
        DOM.apiKeyStatus.title = 'Key: ' + '*'.repeat(state.apiKey.length - 4) + state.apiKey.slice(-4);
    } else {
        indicator.className = 'status-indicator error';
        text.textContent = 'API Key Missing';
        DOM.apiKeyStatus.title = 'Please configure your Gemini API key to run analysis.';
    }
}

function initTabs() {
    DOM.tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetTab = tab.getAttribute('data-tab');
            
            
            DOM.tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            
            DOM.panels.forEach(panel => {
                panel.classList.remove('active');
                if (panel.id === `panel${targetTab.charAt(0).toUpperCase() + targetTab.slice(1)}`) {
                    panel.classList.add('active');
                }
            });
            
            state.activeTab = targetTab;
        });
    });
}

function initFileUpload() {
    
    ['dragenter', 'dragover'].forEach(eventName => {
        DOM.dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            DOM.dropZone.classList.add('dragging');
        }, false);
    });
    ['dragleave', 'drop'].forEach(eventName => {
        DOM.dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            DOM.dropZone.classList.remove('dragging');
        }, false);
    });
    
    DOM.dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFilesSelection(files);
    });
    DOM.dropZone.addEventListener('click', (e) => {
        if (e.target === DOM.fileInput) return;
        DOM.fileInput.click();
    });
    DOM.fileInput.addEventListener('change', (e) => {
        handleFilesSelection(e.target.files);
    });
}
function handleFilesSelection(fileList) {
    if (state.files.length >= 10) {
        alert('You have reached the maximum limit of 10 documents.');
        return;
    }
    const availableSlots = 10 - state.files.length;
    const filesToUpload = Array.from(fileList).slice(0, availableSlots);
    
    if (fileList.length > availableSlots) {
        alert(`Only the first ${availableSlots} files will be uploaded (Limit 10).`);
    }
    filesToUpload.forEach(file => {
        if (file.type !== 'application/pdf' && !file.name.endsWith('.pdf')) {
            alert(`File "${file.name}" is not a PDF. Only PDFs are allowed.`);
            return;
        }
        
        
        if (file.size > 10 * 1024 * 1024) {
            alert(`File "${file.name}" exceeds the 10MB size limit.`);
            return;
        }
        uploadFile(file);
    });
}
async function uploadFile(file) {
    const fileId = 'file_' + Math.random().toString(36).substring(2, 9);
    
    
    const fileState = {
        id: fileId,
        name: file.name,
        size: formatBytes(file.size),
        status: 'pending', 
        errorMsg: ''
    };
    state.files.push(fileState);
    renderFileList();
    
    const formData = new FormData();
    formData.append('file', file);
    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            fileState.status = 'success';
            fileState.pageCount = data.page_count;
            fileState.wordCount = data.word_count;
        } else {
            fileState.status = 'error';
            fileState.errorMsg = data.detail || 'Failed to parse file';
        }
    } catch (err) {
        console.error('Upload error:', err);
        fileState.status = 'error';
        fileState.errorMsg = 'Server connection error';
    }
    renderFileList();
    
    
    const allProcessed = state.files.every(f => f.status !== 'pending');
    const hasSuccessful = state.files.some(f => f.status === 'success');
    if (allProcessed && hasSuccessful) {
        analyzeDocuments();
    }
}
function renderFileList() {
    DOM.fileCountBadge.textContent = `${state.files.length}/10`;
    DOM.btnClearAll.disabled = state.files.length === 0;
    if (state.files.length === 0) {
        DOM.fileEmptyState.classList.remove('hidden');
        DOM.fileListContainer.querySelectorAll('.file-card').forEach(c => c.remove());
        return;
    }
    DOM.fileEmptyState.classList.add('hidden');
    
    
    DOM.fileListContainer.innerHTML = '';
    
    state.files.forEach(file => {
        const card = document.createElement('div');
        card.className = 'file-card';
        card.innerHTML = `
            <div class="file-card-info">
                <div class="file-icon">
                    <i data-lucide="file-text"></i>
                </div>
                <div class="file-card-details">
                    <div class="file-name" title="${file.name}">${file.name}</div>
                    <div class="file-meta">
                        <span>${file.size}</span>
                        <span>•</span>
                        <span class="file-status ${file.status}">
                            ${getFileStatusHTML(file)}
                        </span>
                    </div>
                </div>
            </div>
            <button class="file-action-btn" title="Remove Document" onclick="removeFile('${file.id}')">
                <i data-lucide="x"></i>
            </button>
        `;
        DOM.fileListContainer.appendChild(card);
    });
    lucide.createIcons();
}
function getFileStatusHTML(file) {
    if (file.status === 'pending') {
        return `<span class="icon-pulse">Parsing...</span>`;
    } else if (file.status === 'success') {
        return `Loaded (${file.pageCount} pgs)`;
    } else {
        return `Error: ${file.errorMsg}`;
    }
}
window.removeFile = function(fileId) {
    state.files = state.files.filter(f => f.id !== fileId);
    renderFileList();
    
    
    if (state.files.length > 0 && state.files.some(f => f.status === 'success')) {
        analyzeDocuments();
    } else {
        resetDashboardAndSummary();
    }
};
async function clearAllFiles() {
    state.files = [];
    renderFileList();
    resetDashboardAndSummary();
    
    
    try {
        await fetch('/api/clear', { method: 'POST' });
    } catch (err) {
        console.error('Clear endpoint error:', err);
    }
}
function resetDashboardAndSummary() {
    
    DOM.summaryContentContainer.classList.add('hidden');
    DOM.summaryState.classList.remove('hidden');
    
    DOM.dashboardContentContainer.classList.add('hidden');
    DOM.dashboardState.classList.remove('hidden');
    
    DOM.btnRefreshSummary.disabled = true;
    DOM.chatDocSubtitle.textContent = 'No documents selected';
    
    
    DOM.chatInput.disabled = true;
    DOM.btnSendChat.disabled = true;
}

async function analyzeDocuments() {
    const successFiles = state.files.filter(f => f.status === 'success');
    if (successFiles.length === 0) return;
    state.isAnalyzing = true;
    DOM.btnRefreshSummary.disabled = true;
    
   
    DOM.summaryState.innerHTML = `
        <div class="state-illustration">
            <i data-lucide="loader-2" class="icon-pulse" style="animation-duration: 1.5s;"></i>
        </div>
        <h3>Analyzing Documents</h3>
        <p>DIRS AI is digesting page text, aggregating software metrics, and configuring your dashboard. This may take a few seconds...</p>
    `;
    DOM.summaryState.classList.remove('hidden');
    DOM.summaryContentContainer.classList.add('hidden');
    DOM.dashboardState.innerHTML = `
        <div class="state-illustration">
            <i data-lucide="loader-2" class="icon-pulse" style="animation-duration: 1.5s;"></i>
        </div>
        <h3>Extracting Chart Metrics</h3>
        <p>Connecting to Gemini to pull structured analysis statistics...</p>
    `;
    DOM.dashboardState.classList.remove('hidden');
    DOM.dashboardContentContainer.classList.add('hidden');
    try {
        const response = await fetch('/api/summary', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Gemini-API-Key': state.apiKey
            }
        });
        const data = await response.json();
        if (response.ok) {
            
            DOM.summaryState.classList.add('hidden');
            DOM.summaryContentContainer.classList.remove('hidden');
            
            
            DOM.summaryTextContent.innerHTML = marked.parse(data.summary);
            
            DOM.dashboardState.classList.add('hidden');
            DOM.dashboardContentContainer.classList.remove('hidden');
            
            DOM.statTotalPages.textContent = data.stats.pageCount || 0;
            DOM.statWordCount.textContent = formatNumber(data.stats.wordCount || 0);
            DOM.statRiskCount.textContent = data.stats.riskCount || 0;
            DOM.statSentiment.textContent = data.stats.sentiment || 'Neutral';
            DOM.statSentiment.className = `stat-value sentiment-${(data.stats.sentiment || 'Neutral').toLowerCase()}`;
            
            DOM.takeawaysListContainer.innerHTML = '';
            if (data.takeaways && data.takeaways.length > 0) {
                data.takeaways.forEach(takeaway => {
                    const li = document.createElement('li');
                    li.className = `takeaway-item takeaway-item-${takeaway.type || 'primary'}`;
                    li.innerHTML = `
                        <i data-lucide="${takeaway.icon || 'chevron-right'}"></i>
                        <div>${takeaway.text}</div>
                    `;
                    DOM.takeawaysListContainer.appendChild(li);
                });
                lucide.createIcons();
            }
            
            renderCharts(data.topics, data.sentimentBreakdown);
            
            DOM.chatDocSubtitle.textContent = `Analyzing ${successFiles.length} file(s)`;
            DOM.chatInput.disabled = false;
            DOM.btnSendChat.disabled = false;
            
            DOM.btnRefreshSummary.disabled = false;
        } else {
            
            const errorMsg = data.detail || 'Analysis failed';
            showAnalysisError(errorMsg);
        }
    } catch (err) {
        console.error('Analysis error:', err);
        showAnalysisError('Connection to server lost. Please check if backend is running.');
    } finally {
        state.isAnalyzing = false;
    }
}
function showAnalysisError(msg) {
    const errorHTML = `
        <div class="state-illustration" style="color: var(--accent-danger); background-color: var(--accent-danger-glow);">
            <i data-lucide="alert-triangle"></i>
        </div>
        <h3>Analysis Failed</h3>
        <p>${msg}</p>
        ${msg.includes('API key') || msg.includes('KEY') ? 
          `<button class="btn btn-primary" style="margin-top: 16px;" onclick="DOM.btnConfigApiKey.click()">Configure API Key</button>` : 
          `<button class="btn btn-primary" style="margin-top: 16px;" onclick="analyzeDocuments()">Retry Analysis</button>`}
    `;
    DOM.summaryState.innerHTML = errorHTML;
    DOM.dashboardState.innerHTML = errorHTML;
    lucide.createIcons();
}

function renderCharts(topicsData, sentimentData) {
    const theme = document.documentElement.getAttribute('data-theme') || 'dark';
    const gridColor = theme === 'dark' ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)';
    const textColor = theme === 'dark' ? '#94a3b8' : '#475569';
    
    if (state.charts.topics) state.charts.topics.destroy();
    if (state.charts.sentiment) state.charts.sentiment.destroy();
    
    const ctxTopics = document.getElementById('topicsChart').getContext('2d');
    state.charts.topics = new Chart(ctxTopics, {
        type: 'bar',
        data: {
            labels: topicsData.labels || [],
            datasets: [{
                label: 'Relevance Score (%)',
                data: topicsData.values || [],
                backgroundColor: 'rgba(124, 58, 237, 0.75)',
                borderColor: 'rgb(124, 58, 237)',
                borderWidth: 1,
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    grid: { color: gridColor },
                    ticks: { color: textColor },
                    beginAtZero: true,
                    max: 100
                },
                x: {
                    grid: { display: false },
                    ticks: { color: textColor }
                }
            }
        }
    });
   
    const ctxSentiment = document.getElementById('sentimentChart').getContext('2d');
    state.charts.sentiment = new Chart(ctxSentiment, {
        type: 'doughnut',
        data: {
            labels: sentimentData.labels || ['Positive', 'Neutral', 'Negative'],
            datasets: [{
                data: sentimentData.values || [0, 0, 0],
                backgroundColor: [
                    'rgba(16, 185, 129, 0.75)', 
                    'rgba(245, 158, 11, 0.75)', 
                    'rgba(239, 68, 68, 0.75)'   
                ],
                borderColor: theme === 'dark' ? '#0f172a' : '#ffffff',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: textColor }
                }
            },
            cutout: '65%'
        }
    });
}

function initChat() {
    DOM.chatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const query = DOM.chatInput.value.trim();
        if (!query) return;
        submitChatQuery(query);
    });
    
    DOM.chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            DOM.chatForm.requestSubmit();
        }
    });
    
    DOM.chatInput.addEventListener('input', () => {
        DOM.chatInput.style.height = 'auto';
        DOM.chatInput.style.height = (DOM.chatInput.scrollHeight) + 'px';
    });
    
    DOM.chips.forEach(chip => {
        chip.addEventListener('click', () => {
            if (DOM.chatInput.disabled) return;
            const query = chip.getAttribute('data-query');
            submitChatQuery(query);
        });
    });
}
async function submitChatQuery(query) {
    
    appendChatMessage('user', query);
    DOM.chatInput.value = '';
    DOM.chatInput.style.height = 'auto';
    DOM.chatInput.disabled = true;
    DOM.btnSendChat.disabled = true;
    
    
    DOM.chatSuggestionsContainer.classList.add('hidden');
    
    const typingBubbleId = appendChatTypingIndicator();
    scrollToChatBottom();
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Gemini-API-Key': state.apiKey
            },
            body: JSON.stringify({
                message: query,
                history: state.chatHistory
            })
        });
        const data = await response.json();
        
        
        removeChatTypingIndicator(typingBubbleId);
        if (response.ok) {
            appendChatMessage('assistant', data.answer);
            
            
            state.chatHistory.push({ role: 'user', content: query });
            state.chatHistory.push({ role: 'assistant', content: data.answer });
        } else {
            appendChatMessage('assistant', `⚠️ **Error:** ${data.detail || 'Could not process query.'}`);
        }
    } catch (err) {
        console.error('Chat API error:', err);
        removeChatTypingIndicator(typingBubbleId);
        appendChatMessage('assistant', '⚠️ **Connection Error:** Lost touch with the server.');
    } finally {
        DOM.chatInput.disabled = false;
        DOM.btnSendChat.disabled = false;
        DOM.chatInput.focus();
        scrollToChatBottom();
    }
}
function appendChatMessage(role, text) {
    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const messageCard = document.createElement('div');
    messageCard.className = `chat-message ${role}`;
    
    let contentHTML = '';
    if (role === 'user') {
        contentHTML = `<p>${escapeHTML(text)}</p>`;
    } else {
        contentHTML = marked.parse(text); 
    }
    messageCard.innerHTML = `
        <div class="message-avatar">
            ${role === 'user' ? 'U' : '<i data-lucide="bot"></i>'}
        </div>
        <div class="message-bubble-wrapper">
            <div class="message-bubble">
                ${contentHTML}
            </div>
            <span class="message-time">${timeStr}</span>
        </div>
    `;
    DOM.chatMessagesContainer.appendChild(messageCard);
    
    if (role === 'assistant') {
        lucide.createIcons();
    }
    
    scrollToChatBottom();
}
function appendChatTypingIndicator() {
    const uniqueId = 'typing_' + Date.now();
    const typingCard = document.createElement('div');
    typingCard.className = 'chat-message assistant';
    typingCard.id = uniqueId;
    typingCard.innerHTML = `
        <div class="message-avatar">
            <i data-lucide="bot"></i>
        </div>
        <div class="message-bubble-wrapper">
            <div class="message-bubble">
                <div class="typing-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        </div>
    `;
    DOM.chatMessagesContainer.appendChild(typingCard);
    lucide.createIcons();
    return uniqueId;
}
function removeChatTypingIndicator(id) {
    const element = document.getElementById(id);
    if (element) element.remove();
}
function scrollToChatBottom() {
    DOM.chatMessagesContainer.scrollTop = DOM.chatMessagesContainer.scrollHeight;
}

function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}
function formatNumber(num) {
    return num.toString().replace(/(\d)(?=(\d{3})+(?!\d))/g, '$1,');
}
function escapeHTML(str) {
    return str.replace(/[&<>'"]/g, 
        tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
    );
}
