// Application State
const state = {
    conversations: [],
    currentConversation: null,
    currentVersion: null,
    searchQuery: '',
    searchResults: [],
    isSearching: false,
    audioElement: null,
    // Infinite scroll state
    pageSize: 30,
    totalPages: 0,
    totalItems: 0,
    loadedPages: new Set(), // Track which pages are loaded
    pageItems: new Map(), // Map page number -> array of items
    minLoadedPage: 1,
    maxLoadedPage: 1,
    isLoadingPage: false,
    scrollThreshold: 200, // pixels from top/bottom to trigger load
    // Date/time filter state
    dateFilter: {
        enabled: false,
        startDateTime: null,
        endDateTime: null
    }
};

// API Base URL
const API_BASE = '/api/v1';

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

async function initializeApp() {
    setupEventListeners();
    setupScrollListener();
    loadSearchFromURL();
    loadFilterFromURL();

    // Load either search results or conversations based on URL
    if (state.isSearching) {
        await handleSearch();
    } else {
        await loadPage(1);
    }
}

// Load search query from URL
function loadSearchFromURL() {
    const params = new URLSearchParams(window.location.search);
    const query = params.get('q') || '';

    if (query) {
        document.getElementById('searchInput').value = query;
        document.getElementById('resetSearchBtn').classList.add('visible');
        state.searchQuery = query;
        state.isSearching = true;
    }
}

// Load filter parameters from URL
function loadFilterFromURL() {
    const params = new URLSearchParams(window.location.search);
    const startDateTime = params.get('startDateTime');
    const endDateTime = params.get('endDateTime');

    if (startDateTime || endDateTime) {
        state.dateFilter.enabled = true;
        state.dateFilter.startDateTime = startDateTime;
        state.dateFilter.endDateTime = endDateTime;

        // Update UI
        if (startDateTime) document.getElementById('startDateTime').value = startDateTime;
        if (endDateTime) document.getElementById('endDateTime').value = endDateTime;
    }
}

// Setup Event Listeners
function setupEventListeners() {
    const searchBtn = document.getElementById('searchBtn');
    const resetSearchBtn = document.getElementById('resetSearchBtn');
    const searchInput = document.getElementById('searchInput');
    const applyFilterBtn = document.getElementById('applyFilterBtn');
    const clearFilterBtn = document.getElementById('clearFilterBtn');

    searchBtn.addEventListener('click', handleSearch);
    resetSearchBtn.addEventListener('click', clearSearch);
    applyFilterBtn.addEventListener('click', applyDateFilter);
    clearFilterBtn.addEventListener('click', clearDateFilter);

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

// Apply date/time filter
async function applyDateFilter() {
    const startDateTime = document.getElementById('startDateTime').value;
    const endDateTime = document.getElementById('endDateTime').value;

    // At least one datetime must be provided
    if (!startDateTime && !endDateTime) {
        alert('Please select at least a start or end date/time');
        return;
    }

    // Update state
    state.dateFilter.enabled = true;
    state.dateFilter.startDateTime = startDateTime;
    state.dateFilter.endDateTime = endDateTime;

    // Update URL
    updateURL();

    // Clear and reload
    clearList();
    if (state.isSearching) {
        await loadSearchPage(1);
    } else {
        await loadPage(1);
    }
}

// Clear date/time filter
async function clearDateFilter() {
    // Reset state
    state.dateFilter.enabled = false;
    state.dateFilter.startDateTime = null;
    state.dateFilter.endDateTime = null;

    // Clear UI
    document.getElementById('startDateTime').value = '';
    document.getElementById('endDateTime').value = '';

    // Update URL
    updateURL();

    // Clear and reload
    clearList();
    if (state.isSearching) {
        await loadSearchPage(1);
    } else {
        await loadPage(1);
    }
}

// Setup scroll listener for infinite scrolling
function setupScrollListener() {
    const scrollContainer = document.querySelector('.conversations-panel');

    let scrollTimeout;
    scrollContainer.addEventListener('scroll', () => {
        // Debounce scroll events
        clearTimeout(scrollTimeout);
        scrollTimeout = setTimeout(handleScroll, 100);
    });
}

// Handle scroll events for infinite loading
async function handleScroll() {
    if (state.isLoadingPage) return;

    const scrollContainer = document.querySelector('.conversations-panel');
    const scrollTop = scrollContainer.scrollTop;
    const scrollHeight = scrollContainer.scrollHeight;
    const clientHeight = scrollContainer.clientHeight;

    // Near bottom - load next page
    if (scrollHeight - scrollTop - clientHeight < state.scrollThreshold) {
        if (state.maxLoadedPage < state.totalPages) {
            if (state.isSearching) {
                await loadNextSearchPage();
            } else {
                await loadNextPage();
            }
        }
    }

    // Near top - load previous page
    if (scrollTop < state.scrollThreshold) {
        if (state.minLoadedPage > 1) {
            if (state.isSearching) {
                await loadPreviousSearchPage();
            } else {
                await loadPreviousPage();
            }
        }
    }
}

// Build filter parameters for URL
function buildFilterParams() {
    const params = new URLSearchParams();

    if (state.dateFilter.startDateTime) {
        const startTimestamp = Math.floor(new Date(state.dateFilter.startDateTime).getTime() / 1000);
        params.set('start_timestamp', startTimestamp);
    }

    if (state.dateFilter.endDateTime) {
        const endTimestamp = Math.floor(new Date(state.dateFilter.endDateTime).getTime() / 1000);
        params.set('end_timestamp', endTimestamp);
    }

    return params.toString();
}

// Show loading indicator
function showLoadingIndicator(position = 'bottom') {
    const listContainer = document.getElementById('conversationsList');
    const loadingHTML = '<div class="loading-indicator">Loading...</div>';

    if (position === 'top') {
        listContainer.insertAdjacentHTML('afterbegin', loadingHTML);
    } else {
        listContainer.insertAdjacentHTML('beforeend', loadingHTML);
    }
}

// Remove loading indicator
function removeLoadingIndicator() {
    const indicators = document.querySelectorAll('.loading-indicator');
    indicators.forEach(indicator => indicator.remove());
}

// Load a specific page
async function loadPage(page, prepend = false) {
    if (state.isLoadingPage || state.loadedPages.has(page)) return;

    try {
        state.isLoadingPage = true;
        showLoadingIndicator(prepend ? 'top' : 'bottom');

        // Build URL with pagination and optional date filter
        let url = `${API_BASE}/conversations?page=${page}&page_size=${state.pageSize}`;

        // Add date filter parameters if enabled
        if (state.dateFilter.enabled) {
            const params = buildFilterParams();
            url += `&${params}`;
        }

        const response = await fetch(url);

        if (!response.ok) {
            throw new Error('Failed to load conversations');
        }

        const data = await response.json();

        // Update state with paginated data
        state.totalPages = data.pagination.total_pages;
        state.totalItems = data.pagination.total_items;

        // Store page items
        state.pageItems.set(page, data.items);
        state.loadedPages.add(page);

        // Update loaded page range
        state.minLoadedPage = Math.min(state.minLoadedPage, page);
        state.maxLoadedPage = Math.max(state.maxLoadedPage, page);

        // Render the items
        if (prepend) {
            prependPageItems(page, data.items);
        } else {
            appendPageItems(page, data.items);
        }

        // Cleanup distant pages (keep only current +/- 1 page)
        cleanupDistantPages(page);

    } catch (error) {
        console.error('Error loading page:', error);
        showError('Failed to load conversations. Please try again.');
    } finally {
        removeLoadingIndicator();
        state.isLoadingPage = false;
    }
}

// Load next page and append
async function loadNextPage() {
    const nextPage = state.maxLoadedPage + 1;
    await loadPage(nextPage, false);
}

// Load previous page and prepend
async function loadPreviousPage() {
    const listContainer = document.getElementById('conversationsList');
    const scrollBefore = listContainer.scrollHeight;

    const prevPage = state.minLoadedPage - 1;
    await loadPage(prevPage, true);

    // Preserve scroll position after prepending
    requestAnimationFrame(() => {
        const scrollAfter = listContainer.scrollHeight;
        listContainer.scrollTop += (scrollAfter - scrollBefore);
    });
}

// Append items to the list
function appendPageItems(page, items) {
    const listContainer = document.getElementById('conversationsList');

    const html = items.map(conv => createConversationItemHTML(conv, page)).join('');
    listContainer.insertAdjacentHTML('beforeend', html);
}

// Prepend items to the list
function prependPageItems(page, items) {
    const listContainer = document.getElementById('conversationsList');

    const html = items.map(conv => createConversationItemHTML(conv, page)).join('');
    listContainer.insertAdjacentHTML('afterbegin', html);
}

// Create HTML for a conversation item
function createConversationItemHTML(conv, page) {
    return `
        <div class="conversation-item" data-id="${conv.conversation_id}" data-page="${page}" onclick="loadConversationDetails('${conv.conversation_id}')">
            <h3>${escapeHtml(conv.title)}</h3>
            <div class="conversation-meta">
                <span>${formatDate(conv.updated_at)}</span>
                <span class="version-badge">${conv.version_count} version${conv.version_count !== 1 ? 's' : ''}</span>
            </div>
        </div>
    `;
}

// Cleanup pages that are too far from current view
function cleanupDistantPages(currentPage) {
    const pagesToKeep = new Set();

    // Keep current page and +/- 1 page
    for (let p = currentPage - 1; p <= currentPage + 1; p++) {
        if (p >= 1 && p <= state.totalPages) {
            pagesToKeep.add(p);
        }
    }

    // Remove pages not in keep set
    const listContainer = document.getElementById('conversationsList');

    for (const page of state.loadedPages) {
        if (!pagesToKeep.has(page)) {
            // Remove items from this page
            const itemsToRemove = listContainer.querySelectorAll(`[data-page="${page}"]`);
            itemsToRemove.forEach(item => item.remove());

            // Remove from state
            state.loadedPages.delete(page);
            state.pageItems.delete(page);
        }
    }

    // Update min/max loaded pages
    if (state.loadedPages.size > 0) {
        state.minLoadedPage = Math.min(...state.loadedPages);
        state.maxLoadedPage = Math.max(...state.loadedPages);
    }
}

// Clear list and reset state
function clearList() {
    const listContainer = document.getElementById('conversationsList');
    listContainer.innerHTML = '';
    state.loadedPages.clear();
    state.pageItems.clear();
    state.minLoadedPage = 1;
    state.maxLoadedPage = 1;
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

    // Setup LLM copy button
    setupLLMCopyButton();

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
    const llmText = trans.llm_output || 'No LLM output available';

    // Store original markdown in data attribute for copying
    llmContent.dataset.markdown = llmText;

    // Parse and render markdown
    if (typeof marked !== 'undefined' && typeof DOMPurify !== 'undefined') {
        const rawHtml = marked.parse(llmText);
        const cleanHtml = DOMPurify.sanitize(rawHtml);
        llmContent.innerHTML = cleanHtml;
    } else {
        // Fallback to plain text if libraries not loaded
        llmContent.textContent = llmText;
    }

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
    console.log('[Audio Player] Audio element details:', {
        src: state.audioElement.src,
        duration: state.audioElement.duration,
        networkState: state.audioElement.networkState,
        readyState: state.audioElement.readyState,
        paused: state.audioElement.paused,
        error: state.audioElement.error
    });

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

    console.log('[Audio Player] BEFORE setting currentTime:', state.audioElement.currentTime);
    console.log('[Audio Player] ATTEMPTING to set currentTime to:', clampedTime);

    try {
        // Set currentTime and let the browser handle the seek
        state.audioElement.currentTime = clampedTime;
        console.log('[Audio Player] IMMEDIATELY AFTER set, currentTime:', state.audioElement.currentTime);

        // Check again after a tick
        setTimeout(() => {
            console.log('[Audio Player] After setTimeout, currentTime:', state.audioElement.currentTime);
        }, 0);
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

// Setup LLM Copy Button
function setupLLMCopyButton() {
    const copyBtn = document.getElementById('copyMarkdownBtn');
    if (!copyBtn) return;

    copyBtn.addEventListener('click', async () => {
        const llmContent = document.querySelector('#llmTab .llm-content');
        const markdown = llmContent.dataset.markdown || llmContent.textContent;

        try {
            await navigator.clipboard.writeText(markdown);

            // Visual feedback
            const originalText = copyBtn.innerHTML;
            copyBtn.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <path d="M13.5 3L5.5 11L2 7.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                Copied!
            `;
            copyBtn.classList.add('copied');

            setTimeout(() => {
                copyBtn.innerHTML = originalText;
                copyBtn.classList.remove('copied');
            }, 2000);
        } catch (err) {
            console.error('Failed to copy:', err);
            alert('Failed to copy to clipboard');
        }
    });
}

// Handle Search
async function handleSearch() {
    const searchInput = document.getElementById('searchInput');
    const query = searchInput.value.trim();

    if (!query) return;

    state.searchQuery = query;
    state.isSearching = true;

    // Update URL
    updateURL();

    // Clear and reload
    clearList();
    await loadSearchPage(1);
}

// Load a specific search page
async function loadSearchPage(page, prepend = false) {
    if (state.isLoadingPage || state.loadedPages.has(page)) return;

    try {
        state.isLoadingPage = true;
        showLoadingIndicator(prepend ? 'top' : 'bottom');

        // Build URL with pagination and optional date filter
        let url = `${API_BASE}/conversations/search?q=${encodeURIComponent(state.searchQuery)}&page=${page}&page_size=${state.pageSize}`;

        // Add date filter parameters if enabled
        if (state.dateFilter.enabled) {
            const params = buildFilterParams();
            url += `&${params}`;
        }

        const response = await fetch(url);

        if (!response.ok) {
            throw new Error('Search failed');
        }

        const data = await response.json();

        // Update state
        state.totalPages = data.pagination.total_pages;
        state.totalItems = data.pagination.total_items;

        // Store page items
        state.pageItems.set(page, data.items);
        state.loadedPages.add(page);

        // Update loaded page range
        state.minLoadedPage = Math.min(state.minLoadedPage, page);
        state.maxLoadedPage = Math.max(state.maxLoadedPage, page);

        // Render the items
        if (prepend) {
            prependSearchItems(page, data.items);
        } else {
            appendSearchItems(page, data.items);
        }

        // Cleanup distant pages
        cleanupDistantPages(page);

    } catch (error) {
        console.error('Error searching:', error);
        showError('Search failed. Please try again.');
    } finally {
        removeLoadingIndicator();
        state.isLoadingPage = false;
    }
}

// Append search items to the list
function appendSearchItems(page, items) {
    const listContainer = document.getElementById('conversationsList');

    const html = items.map(result => createSearchItemHTML(result, page)).join('');
    listContainer.insertAdjacentHTML('beforeend', html);
}

// Prepend search items to the list
function prependSearchItems(page, items) {
    const listContainer = document.getElementById('conversationsList');

    const html = items.map(result => createSearchItemHTML(result, page)).join('');
    listContainer.insertAdjacentHTML('afterbegin', html);
}

// Create HTML for a search result item
function createSearchItemHTML(result, page) {
    const matchesHTML = result.matches.slice(0, 3).map(match =>
        `<div class="search-match">${match}</div>`
    ).join('');

    return `
        <div class="conversation-item" data-id="${result.conversation_id}" data-page="${page}" onclick="loadConversationDetails('${result.conversation_id}')">
            <h3>${escapeHtml(result.title)}</h3>
            <div class="conversation-meta">
                <span>${formatDate(result.latest_timestamp * 1000)}</span>
                <span class="version-badge">${result.version_count} version${result.version_count !== 1 ? 's' : ''}</span>
            </div>
            ${matchesHTML}
        </div>
    `;
}

// Load next search page
async function loadNextSearchPage() {
    const nextPage = state.maxLoadedPage + 1;
    await loadSearchPage(nextPage, false);
}

// Load previous search page
async function loadPreviousSearchPage() {
    const listContainer = document.getElementById('conversationsList');
    const scrollBefore = listContainer.scrollHeight;

    const prevPage = state.minLoadedPage - 1;
    await loadSearchPage(prevPage, true);

    // Preserve scroll position
    requestAnimationFrame(() => {
        const scrollAfter = listContainer.scrollHeight;
        listContainer.scrollTop += (scrollAfter - scrollBefore);
    });
}

// Clear Search
function clearSearch() {
    state.searchQuery = '';
    state.isSearching = false;

    const searchInput = document.getElementById('searchInput');
    const resetSearchBtn = document.getElementById('resetSearchBtn');

    searchInput.value = '';
    resetSearchBtn.classList.remove('visible');

    // Update URL
    updateURL();

    // Clear and reload conversations
    clearList();
    loadPage(1);
}

// Update URL with current state
function updateURL() {
    const params = new URLSearchParams();

    if (state.searchQuery) {
        params.set('q', state.searchQuery);
    }

    if (state.dateFilter.enabled) {
        if (state.dateFilter.startDateTime) {
            params.set('startDateTime', state.dateFilter.startDateTime);
        }
        if (state.dateFilter.endDateTime) {
            params.set('endDateTime', state.dateFilter.endDateTime);
        }
    }

    const newURL = params.toString() ? `?${params.toString()}` : window.location.pathname;
    window.history.pushState({}, '', newURL);
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
