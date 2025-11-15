// Application State
const state = {
    conversations: [],
    currentConversation: null,
    currentVersion: null,
    searchQuery: '',
    searchResults: [],
    isSearching: false,
    audioElement: null,
};

// API Base URL
const API_BASE = '/api/v1';

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

async function initializeApp() {
    setupEventListeners();
    await loadConversations();
}

// Setup Event Listeners
function setupEventListeners() {
    const searchBtn = document.getElementById('searchBtn');
    const resetSearchBtn = document.getElementById('resetSearchBtn');
    const searchInput = document.getElementById('searchInput');

    searchBtn.addEventListener('click', handleSearch);
    resetSearchBtn.addEventListener('click', clearSearch);

    // Search on Enter key
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            handleSearch();
        }
    });

    // Show/hide reset button based on input
    searchInput.addEventListener('input', (e) => {
        if (e.target.value.trim()) {
            resetSearchBtn.classList.add('visible');
        } else {
            resetSearchBtn.classList.remove('visible');
        }
    });
}

// Load Conversations
async function loadConversations() {
    try {
        showLoading();
        const response = await fetch(`${API_BASE}/conversations`);

        if (!response.ok) {
            throw new Error('Failed to load conversations');
        }

        state.conversations = await response.json();
        renderConversationsList(state.conversations);
    } catch (error) {
        console.error('Error loading conversations:', error);
        showError('Failed to load conversations. Please try again.');
    }
}

// Render Conversations List
function renderConversationsList(conversations) {
    const listContainer = document.getElementById('conversationsList');

    if (conversations.length === 0) {
        listContainer.innerHTML = '<div class="empty-state"><p>No conversations found</p></div>';
        return;
    }

    const html = conversations.map(conv => `
        <div class="conversation-item" data-id="${conv.conversation_id}" onclick="loadConversationDetails('${conv.conversation_id}')">
            <h3>${escapeHtml(conv.title)}</h3>
            <div class="conversation-meta">
                <span>${formatDate(conv.updated_at)}</span>
                <span class="version-badge">${conv.version_count} version${conv.version_count !== 1 ? 's' : ''}</span>
            </div>
        </div>
    `).join('');

    listContainer.innerHTML = html;
}

// Load Conversation Details
async function loadConversationDetails(conversationId) {
    try {
        const response = await fetch(`${API_BASE}/conversations/${conversationId}`);

        if (!response.ok) {
            throw new Error('Failed to load conversation details');
        }

        state.currentConversation = await response.json();
        state.currentVersion = state.currentConversation.latest_version;

        renderConversationDetails();
        highlightActiveConversation(conversationId);
    } catch (error) {
        console.error('Error loading conversation details:', error);
        showError('Failed to load conversation details. Please try again.');
    }
}

// Render Conversation Details
function renderConversationDetails() {
    const detailsContainer = document.getElementById('conversationDetails');
    const template = document.getElementById('conversationDetailTemplate');
    const clone = template.content.cloneNode(true);

    // Set conversation title
    clone.querySelector('.conversation-title').textContent = state.currentConversation.title;

    // Populate version dropdown
    const versionDropdown = clone.querySelector('#versionDropdown');
    const totalVersions = state.currentConversation.versions.length;
    state.currentConversation.versions.forEach((version, index) => {
        const option = document.createElement('option');
        option.value = version.version_id;
        const versionNumber = totalVersions - index;
        const dateStr = formatDate(version.transcription.created_at);
        option.textContent = version.is_latest
            ? `Latest (v${versionNumber} - ${dateStr})`
            : `v${versionNumber} - ${dateStr}`;
        if (version.version_id === state.currentVersion.version_id) {
            option.selected = true;
        }
        versionDropdown.appendChild(option);
    });

    versionDropdown.addEventListener('change', (e) => {
        const selectedVersion = state.currentConversation.versions.find(
            v => v.version_id === e.target.value
        );
        if (selectedVersion) {
            state.currentVersion = selectedVersion;
            updateConversationContent();
        }
    });

    // Clear and append
    detailsContainer.innerHTML = '';
    detailsContainer.appendChild(clone);

    // Setup audio player
    setupAudioPlayer();

    // Setup tabs
    setupTabs();

    // Load content
    updateConversationContent();
}

// Update Conversation Content (for version changes)
function updateConversationContent() {
    const trans = state.currentVersion.transcription;

    // Update raw transcription
    const rawContent = document.querySelector('#rawTab .transcription-content');
    rawContent.textContent = trans.raw_transcription || 'No transcription available';

    // Update timecodes
    const timecodesContent = document.querySelector('#timecodesTab .timecodes-list');
    if (trans.transcription_with_timecodes && trans.transcription_with_timecodes.length > 0) {
        const timecodesHtml = trans.transcription_with_timecodes.map(tc => `
            <div class="timecode-entry" onclick="jumpToTimecode(${tc.start_time})">
                <div class="timecode-time">${formatTime(tc.start_time)} - ${formatTime(tc.end_time)}</div>
                <div class="timecode-text">${escapeHtml(tc.text)}</div>
            </div>
        `).join('');
        timecodesContent.innerHTML = timecodesHtml;
    } else {
        timecodesContent.innerHTML = '<div class="empty-state"><p>No timecodes available</p></div>';
    }

    // Update LLM output
    const llmContent = document.querySelector('#llmTab .llm-content');
    llmContent.textContent = trans.llm_output || 'No LLM output available';

    // Update audio source
    updateAudioSource();
}

// Setup Audio Player
function setupAudioPlayer() {
    state.audioElement = document.getElementById('audioElement');
    const playPauseBtn = document.getElementById('playPauseBtn');
    const backwardBtn = document.getElementById('backwardBtn');
    const forwardBtn = document.getElementById('forwardBtn');
    const timelineSlider = document.getElementById('timelineSlider');
    const speedBtns = document.querySelectorAll('.speed-btn');

    console.log('[Audio Player] Setting up audio player');

    // Play/Pause
    playPauseBtn.addEventListener('click', togglePlayPause);

    // Backward/Forward
    backwardBtn.addEventListener('click', (e) => {
        e.preventDefault();
        console.log('[Audio Player] Backward button clicked');
        skip(-10);
    });
    forwardBtn.addEventListener('click', (e) => {
        e.preventDefault();
        console.log('[Audio Player] Forward button clicked');
        skip(10);
    });

    // Timeline slider handling
    let isSeeking = false;
    let wasPlaying = false;

    // When user starts interacting with slider
    timelineSlider.addEventListener('mousedown', () => {
        isSeeking = true;
        wasPlaying = !state.audioElement.paused;
        console.log('[Timeline] Mouse down - isSeeking:', isSeeking, 'wasPlaying:', wasPlaying, 'currentTime:', state.audioElement.currentTime);
        if (wasPlaying) {
            state.audioElement.pause();
        }
    });

    // Handle touch events for mobile
    timelineSlider.addEventListener('touchstart', () => {
        isSeeking = true;
        wasPlaying = !state.audioElement.paused;
        console.log('[Timeline] Touch start - isSeeking:', isSeeking, 'wasPlaying:', wasPlaying);
        if (wasPlaying) {
            state.audioElement.pause();
        }
    });

    // While dragging, just update the time display
    timelineSlider.addEventListener('input', (e) => {
        if (isSeeking) {
            const time = (parseFloat(e.target.value) / 100) * state.audioElement.duration;
            console.log('[Timeline] Input - slider value:', e.target.value, 'calculated time:', time, 'duration:', state.audioElement.duration);
            if (!isNaN(time) && isFinite(time)) {
                document.getElementById('currentTime').textContent = formatTime(time);
            }
        }
    });

    // When user releases the slider
    const handleSeekEnd = (e) => {
        console.log('[Timeline] Seek end - isSeeking:', isSeeking, 'slider value:', e.target.value);
        if (!isSeeking) {
            console.log('[Timeline] Not seeking, ignoring');
            return;
        }

        // Check if audio is loaded enough to seek
        if (state.audioElement.readyState < 2) {
            console.warn('[Timeline] Cannot seek - audio not loaded enough (readyState:', state.audioElement.readyState, ')');
            isSeeking = false;
            return;
        }

        const time = (parseFloat(e.target.value) / 100) * state.audioElement.duration;
        console.log('[Timeline] Calculated seek time:', time, 'duration:', state.audioElement.duration, 'currentTime before:', state.audioElement.currentTime, 'readyState:', state.audioElement.readyState);

        if (!isNaN(time) && isFinite(time) && state.audioElement.duration > 0) {
            console.log('[Timeline] Setting currentTime to:', time);
            try {
                state.audioElement.currentTime = time;
                console.log('[Timeline] currentTime after set:', state.audioElement.currentTime);
            } catch (e) {
                console.error('[Timeline] Error setting currentTime:', e);
            }
        } else {
            console.warn('[Timeline] Invalid time value:', { time, duration: state.audioElement.duration, isNaN: isNaN(time), isFinite: isFinite(time) });
        }

        isSeeking = false;

        if (wasPlaying) {
            console.log('[Timeline] Resuming playback');
            state.audioElement.play();
        }
    };

    timelineSlider.addEventListener('mouseup', handleSeekEnd);
    timelineSlider.addEventListener('touchend', handleSeekEnd);

    // Speed controls
    speedBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const speed = parseFloat(e.target.dataset.speed);
            state.audioElement.playbackRate = speed;

            speedBtns.forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
        });
    });

    // Audio events
    state.audioElement.addEventListener('timeupdate', () => {
        if (!isSeeking) {
            updateTimeDisplay();
        }
    });

    state.audioElement.addEventListener('loadedmetadata', () => {
        const duration = state.audioElement.duration;
        console.log('[Audio Player] Metadata loaded - duration:', duration, 'readyState:', state.audioElement.readyState);
        if (!isNaN(duration) && isFinite(duration)) {
            document.getElementById('totalTime').textContent = formatTime(duration);
        }
    });

    state.audioElement.addEventListener('loadeddata', () => {
        console.log('[Audio Player] Data loaded - readyState:', state.audioElement.readyState, 'currentTime:', state.audioElement.currentTime);
    });

    state.audioElement.addEventListener('canplay', () => {
        console.log('[Audio Player] Can play - readyState:', state.audioElement.readyState, 'currentTime:', state.audioElement.currentTime);
    });

    state.audioElement.addEventListener('canplaythrough', () => {
        console.log('[Audio Player] Can play through - readyState:', state.audioElement.readyState);
    });

    state.audioElement.addEventListener('play', () => {
        console.log('[Audio Player] Playing - currentTime:', state.audioElement.currentTime);
        playPauseBtn.textContent = '⏸';
    });

    state.audioElement.addEventListener('pause', () => {
        console.log('[Audio Player] Paused - currentTime:', state.audioElement.currentTime);
        playPauseBtn.textContent = '▶';
    });

    state.audioElement.addEventListener('seeked', () => {
        console.log('[Audio Player] Seeked event - currentTime:', state.audioElement.currentTime);
    });

    state.audioElement.addEventListener('seeking', () => {
        console.log('[Audio Player] Seeking event - currentTime:', state.audioElement.currentTime);
    });

    state.audioElement.addEventListener('loadstart', () => {
        console.log('[Audio Player] Load start event - currentTime:', state.audioElement.currentTime);
        console.log('[Audio Player] Load start stack trace:', new Error().stack);
    });

    state.audioElement.addEventListener('emptied', () => {
        console.log('[Audio Player] Emptied event - audio was reset');
        console.log('[Audio Player] Emptied stack trace:', new Error().stack);
    });
}

// Update Audio Source
function updateAudioSource() {
    if (!state.currentConversation || !state.currentVersion) {
        console.log('[Audio Player] updateAudioSource called but no conversation/version loaded');
        return;
    }

    const audioUrl = `${API_BASE}/conversations/${state.currentConversation.conversation_id}/audio/${state.currentVersion.version_id}`;
    const currentSrc = state.audioElement.src;
    const currentTime = state.audioElement.currentTime;

    console.log('[Audio Player] updateAudioSource called');
    console.log('[Audio Player] Current src:', currentSrc);
    console.log('[Audio Player] Current time:', currentTime);
    console.log('[Audio Player] New URL:', audioUrl);
    console.log('[Audio Player] Stack trace:', new Error().stack);

    // Compare URLs properly - src returns absolute URL, so check if it ends with our relative URL
    const shouldUpdate = !currentSrc || !currentSrc.endsWith(audioUrl);

    console.log('[Audio Player] Should update?', shouldUpdate);

    if (shouldUpdate) {
        console.log('[Audio Player] Source changed, loading new audio (this will reset currentTime)');
        state.audioElement.src = audioUrl;
        state.audioElement.load();
    } else {
        console.log('[Audio Player] Source unchanged, skipping reload (currentTime preserved)');
    }
}

// Toggle Play/Pause
function togglePlayPause() {
    if (state.audioElement.paused) {
        state.audioElement.play();
    } else {
        state.audioElement.pause();
    }
}

// Skip Forward/Backward
function skip(seconds) {
    if (!state.audioElement || isNaN(state.audioElement.duration)) {
        console.warn('[Audio Player] Cannot skip - audio not ready');
        return;
    }

    // Check if audio is loaded enough to seek
    // readyState: 0=nothing, 1=metadata, 2=current, 3=future, 4=enough
    if (state.audioElement.readyState < 2) {
        console.warn('[Audio Player] Cannot skip - audio not loaded enough (readyState:', state.audioElement.readyState, ')');
        return;
    }

    const oldTime = state.audioElement.currentTime;
    const newTime = state.audioElement.currentTime + seconds;
    const clampedTime = Math.max(0, Math.min(newTime, state.audioElement.duration));

    console.log('[Audio Player] Skip:', seconds, 'seconds - from:', oldTime, 'to:', clampedTime, 'readyState:', state.audioElement.readyState);

    // Log seekable ranges for debugging (but don't block on them)
    if (state.audioElement.seekable && state.audioElement.seekable.length > 0) {
        for (let i = 0; i < state.audioElement.seekable.length; i++) {
            const start = state.audioElement.seekable.start(i);
            const end = state.audioElement.seekable.end(i);
            console.log('[Audio Player] Seekable range', i, ':', start, 'to', end);
        }
    } else {
        console.log('[Audio Player] No seekable ranges available yet');
    }

    try {
        // Set currentTime and let the browser handle the seek
        state.audioElement.currentTime = clampedTime;
        console.log('[Audio Player] After skip, currentTime:', state.audioElement.currentTime);
    } catch (e) {
        console.error('[Audio Player] Error during skip:', e);
    }
}

// Jump to Timecode
function jumpToTimecode(time) {
    if (!state.audioElement || isNaN(state.audioElement.duration)) {
        console.warn('[Audio Player] Cannot jump to timecode - audio not ready');
        return;
    }

    // Check if audio is loaded enough to seek
    if (state.audioElement.readyState < 2) {
        console.warn('[Audio Player] Cannot jump - audio not loaded enough (readyState:', state.audioElement.readyState, ')');
        return;
    }

    console.log('[Audio Player] Jump to timecode:', time, 'readyState:', state.audioElement.readyState);

    try {
        state.audioElement.currentTime = time;
        console.log('[Audio Player] After jump, currentTime:', state.audioElement.currentTime);
        state.audioElement.play();
    } catch (e) {
        console.error('[Audio Player] Error during jump:', e);
    }
}

// Update Time Display
function updateTimeDisplay() {
    if (!state.audioElement) return;

    const currentTime = state.audioElement.currentTime;
    const duration = state.audioElement.duration;

    if (isNaN(currentTime) || isNaN(duration)) return;

    document.getElementById('currentTime').textContent = formatTime(currentTime);

    const timelineSlider = document.getElementById('timelineSlider');
    if (timelineSlider && duration > 0) {
        const percentage = (currentTime / duration) * 100;
        if (isFinite(percentage)) {
            timelineSlider.value = percentage;
        }
    }
}

// Setup Tabs
function setupTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabName = btn.dataset.tab;

            // Update active states
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            tabPanes.forEach(pane => pane.classList.remove('active'));
            document.getElementById(`${tabName}Tab`).classList.add('active');
        });
    });
}

// Handle Search
async function handleSearch() {
    const searchInput = document.getElementById('searchInput');
    const query = searchInput.value.trim();

    if (!query) return;

    try {
        state.searchQuery = query;
        state.isSearching = true;

        const response = await fetch(`${API_BASE}/conversations/search?q=${encodeURIComponent(query)}`);

        if (!response.ok) {
            throw new Error('Search failed');
        }

        state.searchResults = await response.json();
        renderSearchResults();
    } catch (error) {
        console.error('Error searching:', error);
        showError('Search failed. Please try again.');
    }
}

// Render Search Results
function renderSearchResults() {
    const listContainer = document.getElementById('conversationsList');

    if (state.searchResults.length === 0) {
        listContainer.innerHTML = '<div class="empty-state"><p>No results found</p></div>';
        return;
    }

    const html = state.searchResults.map(result => `
        <div class="conversation-item" data-id="${result.conversation_id}" onclick="loadConversationDetails('${result.conversation_id}')">
            <h3>${escapeHtml(result.title)}</h3>
            <div class="conversation-meta">
                <span>${formatDate(result.latest_timestamp * 1000)}</span>
                <span class="version-badge">${result.version_count} version${result.version_count !== 1 ? 's' : ''}</span>
            </div>
            ${result.matches.slice(0, 3).map(match => `
                <div class="search-match">${highlightSearchTerm(escapeHtml(match), state.searchQuery)}</div>
            `).join('')}
        </div>
    `).join('');

    listContainer.innerHTML = html;
}

// Clear Search
function clearSearch() {
    state.searchQuery = '';
    state.isSearching = false;
    state.searchResults = [];

    const searchInput = document.getElementById('searchInput');
    const resetSearchBtn = document.getElementById('resetSearchBtn');

    searchInput.value = '';
    resetSearchBtn.classList.remove('visible');

    loadConversations();
}

// Highlight Active Conversation
function highlightActiveConversation(conversationId) {
    document.querySelectorAll('.conversation-item').forEach(item => {
        item.classList.remove('active');
        if (item.dataset.id === conversationId) {
            item.classList.add('active');
        }
    });
}

// Utility Functions
function formatTime(seconds) {
    if (isNaN(seconds)) return '0:00';

    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function formatDate(dateString) {
    if (!dateString) return 'Unknown date';

    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;

    // Less than 1 day ago
    if (diff < 86400000) {
        const hours = Math.floor(diff / 3600000);
        if (hours === 0) {
            const mins = Math.floor(diff / 60000);
            return mins <= 1 ? 'Just now' : `${mins} mins ago`;
        }
        return hours === 1 ? '1 hour ago' : `${hours} hours ago`;
    }

    // Less than 1 week ago
    if (diff < 604800000) {
        const days = Math.floor(diff / 86400000);
        return days === 1 ? 'Yesterday' : `${days} days ago`;
    }

    // Older
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function highlightSearchTerm(text, searchTerm) {
    const regex = new RegExp(`(${escapeRegex(searchTerm)})`, 'gi');
    return text.replace(regex, '<span class="highlight">$1</span>');
}

function escapeRegex(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function showLoading() {
    document.getElementById('conversationsList').innerHTML = '<div class="loading">Loading conversations...</div>';
}

function showError(message) {
    const listContainer = document.getElementById('conversationsList');
    listContainer.innerHTML = `<div class="error">${escapeHtml(message)}</div>`;
}

// Expose jumpToTimecode globally for onclick handlers
window.jumpToTimecode = jumpToTimecode;
window.loadConversationDetails = loadConversationDetails;
