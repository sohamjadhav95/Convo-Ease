/**
 * ConvoEase — Frontend Application v3.5
 * SPA routing, API client, state management, DOM rendering, and theme system.
 * Pure vanilla JavaScript — no frameworks.
 */

// ═══════════════════════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════════════════════
const State = {
    user: null,           // { username, full_name, profile_pic_color, ... }
    groups: [],           // [{ group_id, group_name, admin_username }, ...]
    activeGroupId: null,
    activeGroup: null,    // { group_id, group_name, admin_username, rules, ... }
    messages: [],         // [{ message_id, username, message, timestamp }, ...]
    pendingAppeal: null,  // { message_id, message, reason }
    memberRiskMap: {},    // { username: { trust_score, badge, risk_level } }
    pollTimer: null,
    imageCache: {},       // { message_id: "/media/image/..." } — session-only cache
    audioCache: {},       // { message_id: "/media/audio/..." } — session-only cache
};

// ═══════════════════════════════════════════════════════════════════════════════
// API CLIENT
// ═══════════════════════════════════════════════════════════════════════════════
const API = {
    base: '',  // Same origin

    async request(method, path, body = null) {
        const opts = {
            method,
            headers: { 'Content-Type': 'application/json' },
        };
        if (body) opts.body = JSON.stringify(body);
        const resp = await fetch(this.base + path, opts);
        return resp.json();
    },

    // Auth
    login: (username, password) =>
        API.request('POST', '/api/auth/login', { username, password }),

    register: (username, password, full_name) =>
        API.request('POST', '/api/auth/register', { username, password, full_name }),

    // Groups
    getGroups: (username) =>
        API.request('GET', `/api/groups?username=${encodeURIComponent(username)}`),

    createGroup: (group_name, password, admin_username, rules, moderation_sensitivity) =>
        API.request('POST', '/api/groups', { group_name, password, admin_username, rules, moderation_sensitivity }),

    joinGroup: (group_id, password, username) =>
        API.request('POST', '/api/groups/join', { group_id, password, username }),

    getGroupDetails: (group_id) =>
        API.request('GET', `/api/groups/${group_id}`),

    getGroupMembers: (group_id) =>
        API.request('GET', `/api/groups/${group_id}/members`),

    updateRules: (group_id, rules, username, moderation_sensitivity) =>
        API.request('PUT', `/api/groups/${group_id}/rules`, { rules, username, moderation_sensitivity }),

    // Messages
    getMessages: (group_id) =>
        API.request('GET', `/api/groups/${group_id}/messages`),

    sendMessage: (group_id, username, message) =>
        API.request('POST', `/api/groups/${group_id}/messages`, { username, message }),

    // Images — sends base64, returns message_id + summary + moderation result
    sendImage: (group_id, username, image_data, mime_type) =>
        API.request('POST', `/api/groups/${group_id}/images`, { username, image_data, mime_type }),

    // Audio — sends base64, returns message_id + transcript + moderation result
    sendAudio: (group_id, username, audio_data, mime_type) =>
        API.request('POST', `/api/groups/${group_id}/audio`, { username, audio_data, mime_type }),

    getFlagged: (group_id) =>
        API.request('GET', `/api/groups/${group_id}/messages/flagged`),

    submitAppeal: (group_id, message_id, username, appeal_text) =>
        API.request('POST', `/api/groups/${group_id}/messages/${message_id}/appeal`, { username, appeal_text }),

    reviewAppeal: (group_id, message_id, username, decision, admin_note) =>
        API.request('POST', `/api/groups/${group_id}/messages/${message_id}/appeal/review`, { username, decision, admin_note }),

    getModerationReport: (group_id) =>
        API.request('GET', `/api/groups/${group_id}/report`),

    getCatchUpSummary: (group_id, limit = 25) =>
        API.request('GET', `/api/groups/${group_id}/summary?limit=${limit}`),

    suggestRules: (rules, group_name = '') =>
        API.request('POST', '/api/rules/suggest', { rules, group_name }),

    // Settings
    getSettings: () =>
        API.request('GET', '/api/settings'),
};

// ═══════════════════════════════════════════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════════════════════════════════════════
function getInitials(name) {
    if (!name) return '?';
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return name.substring(0, 2).toUpperCase();
}

const AVATAR_COLORS = ['#EF4444', '#F59E0B', '#10B981', '#3B82F6', '#6366F1', '#8B5CF6', '#EC4899', '#14B8A6', '#F97316'];
function getAvatarColor(name) {
    if (!name) return AVATAR_COLORS[0];
    let hash = 0;
    for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
    return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatTime(timestamp) {
    if (!timestamp || timestamp.length < 16) return '';
    return timestamp.substring(11, 16); // HH:MM
}

function showToast(message, type = '') {
    const toast = document.getElementById('toast');
    const toastMsg = document.getElementById('toast-message');
    toastMsg.textContent = message;
    toast.className = `toast ${type}`;
    toast.classList.remove('hidden');
    clearTimeout(toast._timeout);
    toast._timeout = setTimeout(() => toast.classList.add('hidden'), 3000);
}

function setError(elementId, msg) {
    const el = document.getElementById(elementId);
    el.textContent = msg;
    el.classList.remove('hidden');
}

function clearErrors(...ids) {
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) { el.textContent = ''; el.classList.add('hidden'); }
    });
}

function setLoading(btnId, loading) {
    const btn = document.getElementById(btnId);
    const span = btn.querySelector('span');
    const loader = btn.querySelector('.btn-loader');
    if (loading) {
        btn.disabled = true;
        if (span) span.style.display = 'none';
        if (loader) loader.classList.remove('hidden');
    } else {
        btn.disabled = false;
        if (span) span.style.display = '';
        if (loader) loader.classList.add('hidden');
    }
}

/**
 * Encode a File object as a base64 string.
 */
function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
            // reader.result is "data:<mime>;base64,<data>" — strip the prefix
            const base64 = reader.result.split(',')[1];
            resolve(base64);
        };
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

function debounce(fn, wait = 700) {
    let timer = null;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), wait);
    };
}

function getRiskMeta(username) {
    return State.memberRiskMap[username] || null;
}

function renderRiskBadge(username) {
    const meta = getRiskMeta(username);
    if (!meta || meta.badge === 'trusted') return '';

    const label = meta.badge === 'warning' ? 'High Risk' : 'Watch';
    return `<span class="member-risk-badge ${meta.badge}">${label}</span>`;
}

// ═══════════════════════════════════════════════════════════════════════════════
// THEME MANAGER  — v3.5
// Persists dark/light + accent to localStorage. Applies data-theme / data-accent
// on <html> so CSS variable overrides trigger automatically.
// ═══════════════════════════════════════════════════════════════════════════════
const ThemeManager = {
    LS_THEME: 'ce_theme',   // 'dark' | 'light'
    LS_ACCENT: 'ce_accent',  // 'violet' | 'blue' | 'emerald' | 'rose' | 'amber'

    /** Apply persisted settings immediately on load (called before DOMContentLoaded UI init) */
    applyPersisted() {
        const theme = localStorage.getItem(this.LS_THEME) || 'dark';
        const accent = localStorage.getItem(this.LS_ACCENT) || 'violet';
        this._apply(theme, accent);
    },

    setTheme(theme) {
        localStorage.setItem(this.LS_THEME, theme);
        this._apply(theme, localStorage.getItem(this.LS_ACCENT) || 'violet');
    },

    setAccent(accent) {
        localStorage.setItem(this.LS_ACCENT, accent);
        this._apply(localStorage.getItem(this.LS_THEME) || 'dark', accent);
    },

    _apply(theme, accent) {
        const html = document.documentElement;
        if (theme === 'light') html.setAttribute('data-theme', 'light');
        else html.removeAttribute('data-theme');
        html.setAttribute('data-accent', accent);
    },

    /** Sync the Settings UI controls to current persisted values */
    syncUI() {
        const theme = localStorage.getItem(this.LS_THEME) || 'dark';
        const accent = localStorage.getItem(this.LS_ACCENT) || 'violet';

        const toggle = document.getElementById('toggle-light-mode');
        if (toggle) toggle.checked = (theme === 'light');

        document.querySelectorAll('.accent-swatch').forEach(sw => {
            sw.classList.toggle('active', sw.dataset.accent === accent);
        });
    },

    /** Bind toggle pill + swatch clicks (call once in init) */
    bindControls() {
        const toggle = document.getElementById('toggle-light-mode');
        if (toggle) {
            toggle.addEventListener('change', () => {
                ThemeManager.setTheme(toggle.checked ? 'light' : 'dark');
                ThemeManager.syncUI();
            });
        }

        document.querySelectorAll('.accent-swatch').forEach(sw => {
            sw.addEventListener('click', () => {
                ThemeManager.setAccent(sw.dataset.accent);
                ThemeManager.syncUI();
            });
        });
    },
};

// Apply theme before the page renders (prevents flash)
ThemeManager.applyPersisted();

function showPage(pageId) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.getElementById(pageId).classList.add('active');
}

function navigateTo(page) {
    if (page === 'chat') {
        showPage('page-chat');
    } else if (page === 'settings') {
        showPage('page-settings');
        loadSettings();
    } else {
        showPage('page-auth');
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// AUTH
// ═══════════════════════════════════════════════════════════════════════════════
function initAuth() {
    // Tab switching
    document.querySelectorAll('.auth-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const target = tab.dataset.tab;
            document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            document.querySelectorAll('.auth-form').forEach(f => f.classList.remove('active'));
            document.getElementById(`form-${target}`).classList.add('active');
            clearErrors('login-error', 'register-error', 'register-success');
        });
    });

    // Login
    document.getElementById('form-login').addEventListener('submit', async (e) => {
        e.preventDefault();
        clearErrors('login-error');
        setLoading('btn-login', true);
        const username = document.getElementById('login-username').value.trim();
        const password = document.getElementById('login-password').value.trim();
        try {
            const data = await API.login(username, password);
            if (data.success) {
                State.user = data.user;
                onLoginSuccess();
            } else {
                setError('login-error', data.message || 'Login failed.');
            }
        } catch (err) {
            setError('login-error', 'Connection error. Is the server running?');
        }
        setLoading('btn-login', false);
    });

    // Register
    document.getElementById('form-register').addEventListener('submit', async (e) => {
        e.preventDefault();
        clearErrors('register-error', 'register-success');
        setLoading('btn-register', true);
        const full_name = document.getElementById('reg-fullname').value.trim();
        const username = document.getElementById('reg-username').value.trim();
        const password = document.getElementById('reg-password').value.trim();
        try {
            const data = await API.register(username, password, full_name);
            if (data.success) {
                const el = document.getElementById('register-success');
                el.textContent = 'Account created! Switch to Sign In.';
                el.classList.remove('hidden');
                document.getElementById('form-register').reset();
            } else {
                setError('register-error', data.message || 'Registration failed.');
            }
        } catch (err) {
            setError('register-error', 'Connection error.');
        }
        setLoading('btn-register', false);
    });
}

function onLoginSuccess() {
    navigateTo('chat');
    updateSidebar();
    loadGroups();
}

function logout() {
    State.user = null;
    State.groups = [];
    State.activeGroupId = null;
    State.activeGroup = null;
    State.messages = [];
    State.pendingAppeal = null;
    stopPolling();
    navigateTo('auth');
    document.getElementById('form-login').reset();
    document.getElementById('form-register').reset();
}

// ═══════════════════════════════════════════════════════════════════════════════
// SIDEBAR
// ═══════════════════════════════════════════════════════════════════════════════
function updateSidebar() {
    if (!State.user) return;
    const avatar = document.getElementById('sidebar-avatar');
    const name = document.getElementById('sidebar-name');
    avatar.textContent = getInitials(State.user.full_name);
    avatar.style.backgroundColor = State.user.profile_pic_color || getAvatarColor(State.user.full_name);
    name.textContent = State.user.full_name;
}

async function loadGroups() {
    if (!State.user) return;
    try {
        const data = await API.getGroups(State.user.username);
        if (data.success) {
            State.groups = data.groups;
            renderGroupList();
        }
    } catch (err) {
        console.error('Failed to load groups:', err);
    }
}

function renderGroupList(filter = '') {
    const container = document.getElementById('group-list');
    const filteredGroups = filter
        ? State.groups.filter(g => g.group_name.toLowerCase().includes(filter.toLowerCase()))
        : State.groups;

    if (filteredGroups.length === 0) {
        container.innerHTML = `
            <div style="text-align:center; padding:40px 16px; color:var(--text-muted);">
                <p style="font-size:13px;">No chats yet</p>
                <p style="font-size:12px; margin-top:4px;">Create or join a group to start</p>
            </div>`;
        return;
    }

    container.innerHTML = filteredGroups.map(g => {
        const isActive = g.group_id === State.activeGroupId;
        const color = getAvatarColor(g.group_name);
        const initials = getInitials(g.group_name);
        return `
            <div class="group-item ${isActive ? 'active' : ''}" data-gid="${escapeHtml(g.group_id)}">
                <div class="avatar-circle" style="background:${color}">${initials}</div>
                <div class="group-item-info">
                    <div class="group-item-name">${escapeHtml(g.group_name)}</div>
                    <div class="group-item-preview">ID: ${escapeHtml(g.group_id)}</div>
                </div>
            </div>`;
    }).join('');

    container.querySelectorAll('.group-item').forEach(el => {
        el.addEventListener('click', () => selectGroup(el.dataset.gid));
    });
}

// ═══════════════════════════════════════════════════════════════════════════════
// CHAT
// ═══════════════════════════════════════════════════════════════════════════════
async function selectGroup(groupId) {
    State.activeGroupId = groupId;
    renderGroupList();

    try {
        const detailData = await API.getGroupDetails(groupId);
        if (detailData.success) {
            State.activeGroup = detailData.group;
        }
    } catch (err) {
        console.error('Failed to load group details:', err);
    }

    document.getElementById('chat-empty').classList.add('hidden');
    document.getElementById('chat-active').classList.remove('hidden');

    const group = State.activeGroup || { group_name: 'Unknown', admin_username: '', group_id: groupId };
    document.getElementById('chat-header-name').textContent = group.group_name;
    document.getElementById('chat-header-meta').textContent = `ID: ${group.group_id} • Admin: ${group.admin_username}`;
    const headerAvatar = document.getElementById('chat-header-avatar');
    headerAvatar.textContent = getInitials(group.group_name);
    headerAvatar.style.backgroundColor = getAvatarColor(group.group_name);

    const adminBtn = document.getElementById('btn-admin-panel');
    // Show the panel button for ALL members (admin sees full panel, others see read-only Rules)
    adminBtn.classList.remove('hidden');
    // Update tooltip based on role
    adminBtn.title = (State.user && group.admin_username === State.user.username)
        ? 'Admin Panel' : 'Group Info';

    await loadMemberInsights();
    await loadMessages();
    startPolling();
}

async function loadMemberInsights() {
    if (!State.activeGroupId) return;
    try {
        const data = await API.getModerationReport(State.activeGroupId);
        if (data.success && data.report && Array.isArray(data.report.member_activity)) {
            State.memberRiskMap = Object.fromEntries(
                data.report.member_activity.map(member => [member.username, member])
            );
        }
    } catch (err) {
        console.error('Failed to load member insights:', err);
    }
}

async function loadMessages() {
    if (!State.activeGroupId) return;
    try {
        const data = await API.getMessages(State.activeGroupId);
        if (data.success) {
            const oldCount = State.messages.length;
            const hasChanged = JSON.stringify(State.messages) !== JSON.stringify(data.messages);
            if (hasChanged) {
                State.messages = data.messages;
                renderMessages();
                if (data.messages.length > oldCount) scrollToBottom();
            }
        }
    } catch (err) {
        console.error('Failed to load messages:', err);
    }
}

function renderMessages() {
    const container = document.getElementById('chat-messages');
    if (State.messages.length === 0) {
        container.innerHTML = `
            <div style="text-align:center; padding:60px 20px; color:var(--text-muted);">
                <p>No messages yet. Say hello! 👋</p>
            </div>`;
        return;
    }

    container.innerHTML = State.messages.map(m => {
        const isMe = State.user && m.username === State.user.username;
        const senderHtml = isMe ? '' : `
            <div class="msg-sender-row">
                <div class="msg-sender">${escapeHtml(m.username)}</div>
                ${renderRiskBadge(m.username)}
            </div>`;

        // Detect image messages
        const isImage = m.message && (m.message === '[IMAGE]' || m.message.startsWith('[IMAGE]'));
        // Detect audio messages
        const isAudio = m.message && (m.message === '[AUDIO]' || m.message.startsWith('[AUDIO]'));

        let bubbleContent;
        if (isImage) {
            const inlineSummary = m.summary || m.message.replace(/^\[IMAGE\]\s*/, '');
            const imgSrc = (m.media_url && m.media_url.trim())
                ? m.media_url
                : (State.imageCache[m.message_id] || null);
            if (imgSrc) {
                bubbleContent = `
                    <div class="msg-image-wrapper">
                        <img class="msg-image" src="${imgSrc}" alt="Shared image" loading="lazy">
                    </div>
                    ${inlineSummary ? `<div class="msg-image-caption">🤖 ${escapeHtml(inlineSummary)}</div>` : ''}`;
            } else {
                bubbleContent = `
                    <div class="msg-image-indicator">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                            <circle cx="8.5" cy="8.5" r="1.5"></circle>
                            <polyline points="21 15 16 10 5 21"></polyline>
                        </svg>
                        <span>Image</span>
                    </div>
                    ${inlineSummary ? `<div class="msg-image-summary">${escapeHtml(inlineSummary)}</div>` : ''}`;
            }
        } else if (isAudio) {
            const transcript = m.summary || '';
            // Priority: persisted server URL → session cache
            const audioSrc = (m.media_url && m.media_url.trim())
                ? m.media_url
                : (State.audioCache[m.message_id] || null);
            if (audioSrc) {
                bubbleContent = `
                    <div class="msg-audio-wrapper">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0">
                            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
                            <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                        </svg>
                        <audio class="msg-audio-player" controls src="${audioSrc}" preload="metadata"></audio>
                    </div>
                    ${transcript ? `<div class="msg-audio-transcript">🎤 ${escapeHtml(transcript)}</div>` : ''}`;
            } else {
                bubbleContent = `
                    <div class="msg-audio-indicator">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
                            <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                        </svg>
                        <span>Audio</span>
                    </div>
                    ${transcript ? `<div class="msg-audio-transcript">🎤 ${escapeHtml(transcript)}</div>` : ''}`;
            }
        } else {
            bubbleContent = escapeHtml(m.message);
        }

        return `
            <div class="message-row ${isMe ? 'me' : 'other'}${isImage ? ' image-msg' : ''}${isAudio ? ' audio-msg' : ''}">
                ${senderHtml}
                <div class="msg-bubble">
                    ${bubbleContent}
                    <div class="msg-time">${formatTime(m.timestamp)}</div>
                </div>
            </div>`;
    }).join('');

    scrollToBottom();
}

function scrollToBottom() {
    const container = document.getElementById('chat-messages');
    requestAnimationFrame(() => { container.scrollTop = container.scrollHeight; });
}

async function sendMessage() {
    const input = document.getElementById('message-input');
    const text = input.value.trim();
    if (!text || !State.activeGroupId || !State.user) return;

    input.value = '';
    input.focus();
    showTypingIndicator();

    try {
        const data = await API.sendMessage(State.activeGroupId, State.user.username, text);
        removeTypingIndicator();

        if (data.success && data.status === 'PASS') {
            await loadMessages();
        } else if (data.status === 'FLAGGED') {
            showFlagBanner(data.reason || 'Message was flagged by AI moderation.', {
                message_id: data.message_id,
                message: text,
                reason: data.reason || 'Message was flagged by AI moderation.'
            });
            await loadMessages();
        } else {
            showToast(data.message || 'Failed to send.', 'error');
        }
    } catch (err) {
        removeTypingIndicator();
        showToast('Connection error.', 'error');
    }
}

// ── Audio Upload ─────────────────────────────────────────────────────────────

async function sendAudio(file) {
    if (!file || !State.activeGroupId || !State.user) return;

    const maxSize = 10 * 1024 * 1024; // 10 MB limit
    if (file.size > maxSize) {
        showToast('Audio too large. Max 10 MB.', 'error');
        return;
    }

    showTypingIndicator();
    showToast('Analyzing audio...', '');

    try {
        const base64 = await fileToBase64(file);
        const mimeType = file.type || 'audio/wav';
        const data = await API.sendAudio(State.activeGroupId, State.user.username, base64, mimeType);
        removeTypingIndicator();

        if (data.success && data.status === 'PASS') {
            if (data.message_id && data.media_url) {
                State.audioCache[data.message_id] = data.media_url;
            }
            showToast('Audio sent!', 'success');
            await loadMessages();
        } else if (data.status === 'FLAGGED') {
            showFlagBanner(`Audio blocked: ${data.reason || 'Content violates group rules.'}`, {
                message_id: data.message_id,
                message: data.transcript || '[AUDIO]',
                reason: data.reason || 'Content violates group rules.'
            });
            await loadMessages();
        } else {
            showToast(data.message || 'Failed to send audio.', 'error');
        }
    } catch (err) {
        removeTypingIndicator();
        showToast('Connection error.', 'error');
    }
}

async function sendImage(file) {
    if (!file || !State.activeGroupId || !State.user) return;

    const maxSize = 5 * 1024 * 1024; // 5 MB limit
    if (file.size > maxSize) {
        showToast('Image too large. Max 5 MB.', 'error');
        return;
    }

    showTypingIndicator();
    showToast('Analyzing image...', '');

    try {
        const base64 = await fileToBase64(file);
        const mimeType = file.type || 'image/png';
        const data = await API.sendImage(State.activeGroupId, State.user.username, base64, mimeType);
        removeTypingIndicator();

        if (data.success && data.status === 'PASS') {
            // Store the persisted server URL in the image cache so the image shows
            // immediately after send (before loadMessages polls and gets media_url from DB).
            if (data.message_id && data.media_url) {
                State.imageCache[data.message_id] = data.media_url;
            }
            showToast('Image sent!', 'success');
            await loadMessages();

        } else if (data.status === 'FLAGGED') {
            showFlagBanner(`Image blocked: ${data.reason || 'Content violates group rules.'}`, {
                message_id: data.message_id,
                message: data.summary || '[IMAGE]',
                reason: data.reason || 'Content violates group rules.'
            });
            await loadMessages();
        } else {
            showToast(data.message || 'Failed to send image.', 'error');
        }
    } catch (err) {
        removeTypingIndicator();
        showToast('Connection error.', 'error');
    }
}

function showTypingIndicator() {
    removeTypingIndicator();
    const container = document.getElementById('chat-messages');
    const indicator = document.createElement('div');
    indicator.id = 'typing-indicator';
    indicator.className = 'typing-indicator';
    indicator.innerHTML = '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';
    container.appendChild(indicator);
    scrollToBottom();
}

function removeTypingIndicator() {
    const el = document.getElementById('typing-indicator');
    if (el) el.remove();
}

function showFlagBanner(reason, appealData = null) {
    document.querySelectorAll('.flag-banner').forEach(el => el.remove());

    const banner = document.createElement('div');
    banner.className = 'flag-banner';
    const appealButton = appealData?.message_id
        ? `<button class="btn btn-secondary btn-sm" id="btn-open-appeal" type="button">Appeal</button>`
        : '';
    banner.innerHTML = `
        <div class="flag-banner-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                <line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line>
            </svg>
        </div>
        <div class="flag-banner-text"><strong>Blocked:</strong> ${escapeHtml(reason)}</div>
        ${appealButton}`;

    const messagesArea = document.getElementById('chat-messages');
    messagesArea.parentNode.insertBefore(banner, messagesArea.nextSibling.nextSibling);
    if (appealData?.message_id) {
        banner.querySelector('#btn-open-appeal').addEventListener('click', () => openAppealModal(appealData));
    }
    setTimeout(() => banner.remove(), 6000);
}

function openAppealModal(appealData) {
    State.pendingAppeal = appealData;
    clearErrors('appeal-error', 'appeal-status');
    document.getElementById('appeal-text').value = '';
    document.getElementById('appeal-message-preview').textContent = appealData.message || 'Flagged message';
    document.getElementById('appeal-flag-reason').textContent = appealData.reason || '';
    openModal('modal-appeal');
}

async function submitAppeal() {
    const appeal = State.pendingAppeal;
    if (!appeal?.message_id || !State.activeGroupId || !State.user) return;

    clearErrors('appeal-error', 'appeal-status');
    const appealText = document.getElementById('appeal-text').value.trim();
    if (!appealText) {
        setError('appeal-error', 'Please explain why this message should be reconsidered.');
        return;
    }

    try {
        const data = await API.submitAppeal(State.activeGroupId, appeal.message_id, State.user.username, appealText);
        if (!data.success) {
            setError('appeal-error', data.message || 'Could not submit appeal.');
            return;
        }

        const statusEl = document.getElementById('appeal-status');
        statusEl.textContent = `Appeal submitted. AI recommendation: ${data.ai_status} - ${data.ai_reason}`;
        statusEl.classList.remove('hidden');
        showToast('Appeal submitted for admin review.', 'success');
        setTimeout(() => closeModal('modal-appeal'), 1400);
    } catch (err) {
        setError('appeal-error', 'Connection error while submitting appeal.');
    }
}

async function openCatchUpModal() {
    if (!State.activeGroupId) return;
    openModal('modal-catchup');
    const body = document.getElementById('catchup-body');
    body.innerHTML = '<p class="text-muted">Preparing your catch-up...</p>';

    try {
        const data = await API.getCatchUpSummary(State.activeGroupId, 25);
        if (!data.success) {
            body.innerHTML = '<p class="text-muted">Unable to summarize the recent chat right now.</p>';
            return;
        }

        const summary = data.summary || {};
        const bullets = Array.isArray(summary.bullets) ? summary.bullets : [];
        body.innerHTML = `
            <div class="catchup-card">
                <div class="catchup-headline">${escapeHtml(summary.headline || 'Recent conversation summary')}</div>
                <ul class="catchup-list">
                    ${bullets.map(item => `<li>${escapeHtml(item)}</li>`).join('')}
                </ul>
            </div>`;
    } catch (err) {
        body.innerHTML = '<p class="text-muted">Connection error while generating catch-up.</p>';
    }
}

async function requestRuleSuggestions(source) {
    const isCreate = source === 'create';
    const rulesEl = document.getElementById(isCreate ? 'create-rules' : 'admin-rules');
    const groupNameEl = document.getElementById(isCreate ? 'create-name' : 'chat-header-name');
    const suggestionsEl = document.getElementById(isCreate ? 'create-rule-suggestions' : 'admin-rule-suggestions');
    const previewEl = document.getElementById(isCreate ? 'create-rule-preview' : 'admin-rule-preview');

    const rules = rulesEl.value.trim();
    const groupName = groupNameEl ? groupNameEl.value || groupNameEl.textContent || '' : '';
    if (!rules) {
        suggestionsEl.innerHTML = '<p class="text-muted">Add a few rules first and AI will suggest improvements.</p>';
        previewEl.textContent = '';
        return;
    }

    suggestionsEl.innerHTML = '<p class="text-muted">Reviewing rules...</p>';
    previewEl.textContent = '';

    try {
        const data = await API.suggestRules(rules, groupName.trim());
        if (!data.success) {
            suggestionsEl.innerHTML = '<p class="text-muted">Could not generate suggestions right now.</p>';
            return;
        }

        const suggestions = Array.isArray(data.suggestions) ? data.suggestions : [];
        suggestionsEl.innerHTML = suggestions.length
            ? suggestions.map(item => `<div class="rule-suggestion-item">${escapeHtml(item)}</div>`).join('')
            : '<p class="text-muted">No extra suggestions needed.</p>';
        previewEl.textContent = data.revised_rules || '';
    } catch (err) {
        suggestionsEl.innerHTML = '<p class="text-muted">Connection error while suggesting rules.</p>';
    }
}

// Polling
function startPolling() {
    stopPolling();
    State.pollTimer = setInterval(() => {
        if (State.activeGroupId) loadMessages();
    }, 3000);
}

function stopPolling() {
    if (State.pollTimer) {
        clearInterval(State.pollTimer);
        State.pollTimer = null;
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// SETTINGS
// ═══════════════════════════════════════════════════════════════════════════════
async function loadSettings() {
    if (!State.user) return;

    const avatar = document.getElementById('settings-avatar');
    avatar.textContent = getInitials(State.user.full_name);
    avatar.style.backgroundColor = State.user.profile_pic_color || getAvatarColor(State.user.full_name);
    document.getElementById('settings-fullname').textContent = State.user.full_name;
    document.getElementById('settings-username').textContent = `@${State.user.username}`;

    try {
        const data = await API.getSettings();
        if (data.success) {
            const s = data.settings;
            const modeLabel = `${s.text?.backend || 'n/a'} / ${s.image?.backend || 'n/a'} / ${s.audio?.backend || 'n/a'}`;
            document.getElementById('setting-mode').textContent = modeLabel.toUpperCase();
            document.getElementById('setting-model').textContent = s.text?.api_model_id || s.text?.local_model_path || 'N/A';
            document.getElementById('setting-url').textContent = s.base_url || 'N/A';
            document.getElementById('setting-plugins').textContent = s.plugins.join(', ') || 'None';
            const vmEl = document.getElementById('setting-vision-model');
            if (vmEl) vmEl.textContent = s.image?.api_model_id || s.image?.local_model_path || 'N/A';
        }
    } catch (err) {
        console.error('Failed to load settings:', err);
    }

    // Sync theme controls to stored preferences
    ThemeManager.syncUI();
}

// ═══════════════════════════════════════════════════════════════════════════════
// MODALS
// ═══════════════════════════════════════════════════════════════════════════════
function openModal(modalId) {
    document.getElementById(modalId).classList.remove('hidden');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.add('hidden');
}

async function reviewAppeal(messageId, decision) {
    if (!State.activeGroup || !State.user) return;

    const admin_note = window.prompt(
        decision === 'approve'
            ? 'Optional note for this approval:'
            : 'Optional note for this rejection:',
        ''
    ) || '';

    try {
        const data = await API.reviewAppeal(
            State.activeGroup.group_id,
            messageId,
            State.user.username,
            decision,
            admin_note
        );
        if (!data.success) {
            showToast(data.message || 'Could not review appeal.', 'error');
            return;
        }
        showToast(decision === 'approve' ? 'Appeal approved.' : 'Appeal rejected.', 'success');
        await openAdminPanel();
        await loadMessages();
    } catch (err) {
        showToast('Connection error while reviewing appeal.', 'error');
    }
}

function bindFlaggedActions(container) {
    container.querySelectorAll('[data-appeal-decision]').forEach(btn => {
        btn.addEventListener('click', () => reviewAppeal(btn.dataset.messageId, btn.dataset.appealDecision));
    });
}

function renderFlaggedList(flaggedItems, isAdmin) {
    const container = document.getElementById('flagged-list');
    if (!container) return;

    if (!flaggedItems?.length) {
        container.innerHTML = '<p class="text-muted" style="padding:12px 0; font-size:13px;">Great! No flagged messages.</p>';
        return;
    }

    container.innerHTML = flaggedItems.map(f => {
        const isImg = f.message === '[IMAGE]';
        const isAud = f.message === '[AUDIO]';
        const typeBadge = isImg ? 'Image' : isAud ? 'Audio' : 'Text';
        const displayMsg = isImg
            ? (f.summary || 'Image content')
            : isAud
                ? (f.summary || 'Audio content')
                : f.message;
        const languageLine = f.detected_language ? `<div class="flagged-item-meta">Language: ${escapeHtml(f.detected_language)}</div>` : '';
        const appealLine = f.appeal_text
            ? `<div class="flagged-item-meta"><strong>Appeal:</strong> ${escapeHtml(f.appeal_text)}</div>
               <div class="flagged-item-meta"><strong>AI Re-check:</strong> ${escapeHtml(f.appeal_ai_status || 'Pending')} ${f.appeal_ai_reason ? `- ${escapeHtml(f.appeal_ai_reason)}` : ''}</div>`
            : '';
        const actions = isAdmin && f.appeal_status === 'PENDING_ADMIN'
            ? `
                <div class="flagged-item-actions">
                    <button class="btn btn-primary btn-sm" data-message-id="${escapeHtml(f.message_id)}" data-appeal-decision="approve" type="button">Approve Appeal</button>
                    <button class="btn btn-secondary btn-sm" data-message-id="${escapeHtml(f.message_id)}" data-appeal-decision="reject" type="button">Reject Appeal</button>
                </div>`
            : '';

        return `
            <div class="flagged-item">
                <div class="flagged-item-header">
                    <span class="badge">${typeBadge}</span>
                    <span>${escapeHtml(f.username)}</span>
                    <span>${formatTime(f.timestamp)}</span>
                </div>
                <div class="flagged-item-message">${escapeHtml(displayMsg)}</div>
                <div class="flagged-item-reason">${escapeHtml(f.reason)}</div>
                ${languageLine}
                ${appealLine}
                ${actions}
            </div>`;
    }).join('');

    bindFlaggedActions(container);
}

function initModals() {
    // Close buttons
    document.querySelectorAll('.modal-close').forEach(btn => {
        btn.addEventListener('click', () => closeModal(btn.dataset.modal));
    });

    // Click outside to close
    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closeModal(overlay.id);
        });
    });

    // Modal tabs (Create/Join group) — uses data-modal-tab
    document.querySelectorAll('[data-modal-tab]').forEach(tab => {
        tab.addEventListener('click', () => {
            const target = tab.dataset.modalTab;
            const parent = tab.closest('.modal');
            parent.querySelectorAll('[data-modal-tab]').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            parent.querySelectorAll('.modal-form').forEach(f => f.classList.remove('active'));
            const formEl = document.getElementById(`form-${target}-group`);
            if (formEl) formEl.classList.add('active');
        });
    });

    // Admin panel tabs — uses data-admin-tab
    document.querySelectorAll('[data-admin-tab]').forEach(tab => {
        tab.addEventListener('click', () => {
            const target = tab.dataset.adminTab;

            // Update active tab style
            document.querySelectorAll('[data-admin-tab]').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            // Show/hide tab content
            document.querySelectorAll('.admin-tab-content').forEach(c => c.style.display = 'none');
            const tabEl = document.getElementById(`admin-tab-${target}`);
            if (tabEl) tabEl.style.display = 'block';

            // Load report on-demand
            if (target === 'report' && State.activeGroup) {
                loadModerationReport(State.activeGroup.group_id);
            }
        });
    });

    // Create group form
    document.getElementById('form-create-group').addEventListener('submit', async (e) => {
        e.preventDefault();
        clearErrors('create-group-error');
        const name = document.getElementById('create-name').value.trim();
        const password = document.getElementById('create-password').value.trim();
        const previewRules = document.getElementById('create-rule-preview').value.trim();
        const rules = previewRules || document.getElementById('create-rules').value.trim();
        const moderationSensitivity = document.getElementById('create-sensitivity').value;

        if (!name) { setError('create-group-error', 'Group name is required.'); return; }

        try {
            const data = await API.createGroup(name, password, State.user.username, rules, moderationSensitivity);
            if (data.success) {
                closeModal('modal-group');
                document.getElementById('form-create-group').reset();
                document.getElementById('create-rules').value = 'Be respectful.';
                document.getElementById('create-sensitivity').value = 'Moderate';
                document.getElementById('create-rule-preview').value = '';
                document.getElementById('create-rule-suggestions').innerHTML = '<p class="text-muted">AI suggestions will appear here.</p>';
                showToast(`Group "${name}" created!`, 'success');
                await loadGroups();
                selectGroup(data.group_id);
            } else {
                setError('create-group-error', data.message || 'Failed.');
            }
        } catch (err) {
            setError('create-group-error', 'Connection error.');
        }
    });

    // Join group form
    document.getElementById('form-join-group').addEventListener('submit', async (e) => {
        e.preventDefault();
        clearErrors('join-group-error', 'join-group-success');
        const id = document.getElementById('join-id').value.trim();
        const password = document.getElementById('join-password').value.trim();

        if (!id) { setError('join-group-error', 'Group ID is required.'); return; }

        try {
            const data = await API.joinGroup(id, password, State.user.username);
            if (data.success) {
                closeModal('modal-group');
                document.getElementById('form-join-group').reset();
                showToast('Joined group!', 'success');
                await loadGroups();
                selectGroup(id);
            } else {
                setError('join-group-error', data.message || 'Failed.');
            }
        } catch (err) {
            setError('join-group-error', 'Connection error.');
        }
    });
}

// ═══════════════════════════════════════════════════════════════════════════════
// ADMIN PANEL
// ═══════════════════════════════════════════════════════════════════════════════
async function openAdminPanel() {
    if (!State.activeGroup || !State.user) return;

    const isAdmin = State.activeGroup.admin_username === State.user.username;

    // Set panel title based on role
    const titleEl = document.getElementById('admin-panel-title');
    if (titleEl) titleEl.textContent = isAdmin ? 'Admin Panel' : 'Group Info';

    // Show/hide admin-only tabs
    document.querySelectorAll('[data-admin-only="true"]').forEach(tab => {
        tab.style.display = isAdmin ? '' : 'none';
    });

    // Reset to Rules tab
    document.querySelectorAll('[data-admin-tab]').forEach(t => t.classList.remove('active'));
    const firstTab = document.querySelector('[data-admin-tab="rules"]');
    if (firstTab) firstTab.classList.add('active');
    document.querySelectorAll('.admin-tab-content').forEach(c => c.style.display = 'none');
    const rulesTab = document.getElementById('admin-tab-rules');
    if (rulesTab) rulesTab.style.display = 'block';

    document.getElementById('admin-group-id').textContent = State.activeGroup.group_id;

    // Members
    try {
        const membersData = await API.getGroupMembers(State.activeGroup.group_id);
        if (membersData.success) {
            document.getElementById('admin-members').innerHTML = membersData.members.map(member => `
                <span class="member-chip">
                    ${escapeHtml(member)}
                    ${renderRiskBadge(member)}
                </span>`).join('');
        }
    } catch (err) {
        document.getElementById('admin-members').textContent = 'Error loading';
    }

    // Rules — editable for admin, read-only for members
    const rulesTextarea = document.getElementById('admin-rules');
    rulesTextarea.value = State.activeGroup.rules || '';
    document.getElementById('admin-sensitivity').value = State.activeGroup.moderation_sensitivity || 'Moderate';
    document.getElementById('admin-rule-preview').value = '';
    document.getElementById('admin-rule-suggestions').innerHTML = '<p class="text-muted">AI suggestions will appear here.</p>';
    rulesTextarea.readOnly = !isAdmin;
    rulesTextarea.style.opacity = isAdmin ? '' : '0.7';
    const saveRulesBtn = document.getElementById('btn-save-rules');
    if (saveRulesBtn) saveRulesBtn.style.display = isAdmin ? '' : 'none';
    const suggestRulesBtn = document.getElementById('btn-suggest-admin-rules');
    if (suggestRulesBtn) suggestRulesBtn.style.display = isAdmin ? '' : 'none';
    const previewRulesEl = document.getElementById('admin-rule-preview');
    if (previewRulesEl) previewRulesEl.style.display = isAdmin ? '' : 'none';
    const suggestionsPanelEl = document.getElementById('admin-rule-suggestions');
    if (suggestionsPanelEl) suggestionsPanelEl.style.display = isAdmin ? '' : 'none';
    const sensitivityEl = document.getElementById('admin-sensitivity');
    if (sensitivityEl) {
        sensitivityEl.disabled = !isAdmin;
        sensitivityEl.style.opacity = isAdmin ? '' : '0.7';
    }

    // Flagged messages (admin only)
    if (isAdmin) {
        try {
            const flaggedData = await API.getFlagged(State.activeGroup.group_id);
            const container = document.getElementById('flagged-list');
            if (flaggedData.success && flaggedData.flagged.length > 0) {
                container.innerHTML = flaggedData.flagged.map(f => {
                    const isImg = f.message === '[IMAGE]';
                    const isAud = f.message === '[AUDIO]';
                    const typeBadge = isImg ? '📷 Image' : isAud ? '🎤 Audio' : '💬 Text';
                    const displayMsg = isImg
                        ? (f.summary || 'Image content')
                        : isAud
                            ? (f.summary || 'Audio content')
                            : f.message;
                    return `
                    <div class="flagged-item">
                        <div class="flagged-item-header">
                            <span class="badge">${typeBadge}</span>
                            <span>${escapeHtml(f.username)}</span>
                            <span>${formatTime(f.timestamp)}</span>
                        </div>
                        <div class="flagged-item-message">${escapeHtml(displayMsg)}</div>
                        <div class="flagged-item-reason">${escapeHtml(f.reason)}</div>
                    </div>`;
                }).join('');
            } else {
                container.innerHTML = '<p class="text-muted" style="padding:12px 0; font-size:13px;">Great! No flagged messages.</p>';
            }
            renderFlaggedList(flaggedData.success ? flaggedData.flagged : [], true);
        } catch (err) {
            console.error('Failed to load flagged:', err);
        }
    }

    openModal('modal-admin');
}

// ── Moderation Report ────────────────────────────────────────────────────────

async function loadModerationReport(group_id) {
    // Reset to loading state
    ['report-total', 'report-passed', 'report-flagged', 'report-images',
        'report-pass-rate', 'report-flagged-rate'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = '...';
        });
    document.getElementById('report-bar-pass').style.width = '0%';
    document.getElementById('report-bar-flag').style.width = '0%';
    document.getElementById('report-member-table').innerHTML = '<p class="text-muted" style="font-size:13px;">Loading...</p>';
    document.getElementById('report-reasons').innerHTML = '<p class="text-muted" style="font-size:13px;">Loading...</p>';
    const passedLogEl = document.getElementById('report-passed-log');
    const flaggedLogEl = document.getElementById('report-flagged-log');
    if (passedLogEl) passedLogEl.innerHTML = '<p class="text-muted" style="font-size:13px;">Loading...</p>';
    if (flaggedLogEl) flaggedLogEl.innerHTML = '<p class="text-muted" style="font-size:13px;">Loading...</p>';

    try {
        const data = await API.getModerationReport(group_id);
        if (!data.success) { showToast('Failed to load report.', 'error'); return; }
        const r = data.report;

        // Stat cards
        document.getElementById('report-total').textContent = r.total_messages;
        document.getElementById('report-passed').textContent = r.pass_count;
        document.getElementById('report-flagged').textContent = r.flagged_count;
        document.getElementById('report-images').textContent = r.image_count;
        const audioEl = document.getElementById('report-audios');
        if (audioEl) audioEl.textContent = r.audio_count ?? 0;
        document.getElementById('report-pass-rate').textContent = `${r.pass_rate}%`;
        document.getElementById('report-flagged-rate').textContent = `${r.flagged_rate}%`;

        setTimeout(() => {
            document.getElementById('report-bar-pass').style.width = `${r.pass_rate}%`;
            document.getElementById('report-bar-flag').style.width = `${r.flagged_rate}%`;
        }, 80);

        // Member activity table
        const memberTable = document.getElementById('report-member-table');
        if (r.member_activity && r.member_activity.length > 0) {
            memberTable.innerHTML = `
                <table class="report-table">
                    <thead><tr><th>Member</th><th>Sent</th><th>Flagged</th><th>Total</th></tr></thead>
                    <tbody>${r.member_activity.map(m => `
                        <tr>
                            <td>${escapeHtml(m.username)}</td>
                            <td class="text-pass">${m.sent}</td>
                            <td class="text-danger">${m.flagged}</td>
                            <td>${m.total_attempts}</td>
                        </tr>`).join('')}
                    </tbody>
                </table>`;
        } else {
            memberTable.innerHTML = '<p class="text-muted" style="font-size:13px;">No activity yet.</p>';
        }

        // Flagged reasons
        const reasonsEl = document.getElementById('report-reasons');
        if (r.flagged_reasons && r.flagged_reasons.length > 0) {
            reasonsEl.innerHTML = r.flagged_reasons.map(reason => `
                <div class="reason-item">
                    <span class="reason-label">${escapeHtml(reason.reason)}</span>
                    <span class="reason-count">${reason.count}×</span>
                </div>`).join('');
        } else {
            reasonsEl.innerHTML = '<p class="text-muted" style="font-size:13px;">No violations recorded.</p>';
        }

        // ── Helper to build a message log item ──────────────────────────────
        function buildMsgItem(m, style) {
            const isAudio = m.type === 'audio';
            const badgeCls = m.type === 'image' ? 'badge-image' : isAudio ? 'badge-audio' : 'badge-text';
            const badgeTxt = m.type === 'image' ? '📷 Image' : isAudio ? '🎤 Audio' : '💬 Text';
            return `
                <div class="report-msg-item ${style}">
                    <div class="report-msg-header">
                        <span class="report-msg-user">${escapeHtml(m.username)}</span>
                        <span class="report-msg-badge ${badgeCls}">${badgeTxt}</span>
                        <span class="report-msg-time">${formatTime(m.timestamp)}</span>
                    </div>
                    <div class="report-msg-content">${escapeHtml(m.display)}</div>
                    <div class="report-msg-reason ${style}">${escapeHtml(m.reason)}</div>
                </div>`;
        }

        // ── Passed messages log ──────────────────────────────────────────────
        if (passedLogEl) {
            if (r.passed_messages && r.passed_messages.length > 0) {
                passedLogEl.innerHTML = r.passed_messages.map(m => buildMsgItem(m, 'pass')).join('');
            } else {
                passedLogEl.innerHTML = '<p class="text-muted" style="font-size:13px;">No passed messages yet.</p>';
            }
        }

        // ── Flagged messages log ─────────────────────────────────────────────
        if (flaggedLogEl) {
            if (r.flagged_messages && r.flagged_messages.length > 0) {
                flaggedLogEl.innerHTML = r.flagged_messages.map(m => buildMsgItem(m, 'flagged')).join('');
            } else {
                flaggedLogEl.innerHTML = '<p class="text-muted" style="font-size:13px;">No flagged messages. 🎉</p>';
            }
        }

    } catch (err) {
        console.error('Failed to load report:', err);
        showToast('Error loading report.', 'error');
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// EVENT BINDINGS
// ═══════════════════════════════════════════════════════════════════════════════
function initEventBindings() {
    document.getElementById('btn-new-chat').addEventListener('click', () => openModal('modal-group'));
    document.getElementById('btn-catchup').addEventListener('click', openCatchUpModal);

    document.getElementById('btn-settings-nav').addEventListener('click', () => {
        stopPolling();
        navigateTo('settings');
    });

    document.getElementById('btn-settings-back').addEventListener('click', () => {
        navigateTo('chat');
        if (State.activeGroupId) startPolling();
    });

    document.getElementById('btn-logout').addEventListener('click', logout);

    // Text message send
    document.getElementById('btn-send').addEventListener('click', sendMessage);
    document.getElementById('message-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Image attach button → trigger file picker
    document.getElementById('btn-attach-image').addEventListener('click', () => {
        document.getElementById('image-file-input').click();
    });

    // File chosen → send image
    document.getElementById('image-file-input').addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (file) {
            await sendImage(file);
            e.target.value = '';
        }
    });

    // Audio attach button → trigger file picker
    document.getElementById('btn-attach-audio').addEventListener('click', () => {
        document.getElementById('audio-file-input').click();
    });

    // File chosen → send audio
    document.getElementById('audio-file-input').addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (file) {
            await sendAudio(file);
            e.target.value = '';
        }
    });

    document.getElementById('btn-admin-panel').addEventListener('click', openAdminPanel);
    document.getElementById('btn-submit-appeal').addEventListener('click', submitAppeal);

    document.getElementById('btn-save-rules').addEventListener('click', async () => {
        if (!State.activeGroup) return;
        const previewRules = document.getElementById('admin-rule-preview').value.trim();
        const newRules = previewRules || document.getElementById('admin-rules').value.trim();
        const sensitivity = document.getElementById('admin-sensitivity').value;
        try {
            const data = await API.updateRules(State.activeGroup.group_id, newRules, State.user.username, sensitivity);
            if (data.success) {
                State.activeGroup.rules = newRules;
                State.activeGroup.moderation_sensitivity = sensitivity;
                document.getElementById('admin-rules').value = newRules;
                showToast('Rules updated!', 'success');
            } else {
                showToast(data.message || 'Failed.', 'error');
            }
        } catch (err) {
            showToast('Connection error.', 'error');
        }
    });

    document.getElementById('btn-suggest-create-rules').addEventListener('click', () => requestRuleSuggestions('create'));
    document.getElementById('btn-suggest-admin-rules').addEventListener('click', () => requestRuleSuggestions('admin'));

    const createRulesDebounced = debounce(() => requestRuleSuggestions('create'), 900);
    const adminRulesDebounced = debounce(() => requestRuleSuggestions('admin'), 900);
    document.getElementById('create-rules').addEventListener('input', createRulesDebounced);
    document.getElementById('admin-rules').addEventListener('input', adminRulesDebounced);

    document.getElementById('search-groups').addEventListener('input', (e) => {
        renderGroupList(e.target.value);
    });
}

// ═══════════════════════════════════════════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
    initAuth();
    initModals();
    initEventBindings();
    ThemeManager.bindControls();
    navigateTo('auth');
});

async function _legacyLoadModerationReport(group_id) {
    ['report-total', 'report-passed', 'report-flagged', 'report-images', 'report-pass-rate', 'report-flagged-rate']
        .forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = '...';
        });

    document.getElementById('report-bar-pass').style.width = '0%';
    document.getElementById('report-bar-flag').style.width = '0%';
    document.getElementById('report-member-table').innerHTML = '<p class="text-muted" style="font-size:13px;">Loading...</p>';
    document.getElementById('report-reasons').innerHTML = '<p class="text-muted" style="font-size:13px;">Loading...</p>';
    document.getElementById('report-categories').innerHTML = '<p class="text-muted" style="font-size:13px;">Loading...</p>';
    document.getElementById('report-trends').innerHTML = '<p class="text-muted" style="font-size:13px;">Loading...</p>';
    document.getElementById('report-heatmap').innerHTML = '<p class="text-muted" style="font-size:13px;">Loading...</p>';

    const passedLogEl = document.getElementById('report-passed-log');
    const flaggedLogEl = document.getElementById('report-flagged-log');
    if (passedLogEl) passedLogEl.innerHTML = '<p class="text-muted" style="font-size:13px;">Loading...</p>';
    if (flaggedLogEl) flaggedLogEl.innerHTML = '<p class="text-muted" style="font-size:13px;">Loading...</p>';

    try {
        const data = await API.getModerationReport(group_id);
        if (!data.success) {
            showToast('Failed to load report.', 'error');
            return;
        }

        const r = data.report;
        State.memberRiskMap = Object.fromEntries((r.member_activity || []).map(member => [member.username, member]));

        document.getElementById('report-total').textContent = r.total_messages;
        document.getElementById('report-passed').textContent = r.pass_count;
        document.getElementById('report-flagged').textContent = r.flagged_count;
        document.getElementById('report-images').textContent = r.image_count;
        const audioEl = document.getElementById('report-audios');
        if (audioEl) audioEl.textContent = r.audio_count ?? 0;
        document.getElementById('report-pass-rate').textContent = `${r.pass_rate}%`;
        document.getElementById('report-flagged-rate').textContent = `${r.flagged_rate}%`;

        setTimeout(() => {
            document.getElementById('report-bar-pass').style.width = `${r.pass_rate}%`;
            document.getElementById('report-bar-flag').style.width = `${r.flagged_rate}%`;
        }, 80);

        const memberTable = document.getElementById('report-member-table');
        if (r.member_activity?.length) {
            memberTable.innerHTML = `
                <table class="report-table">
                    <thead><tr><th>Member</th><th>Trust</th><th>Sent</th><th>Flagged</th><th>Total</th></tr></thead>
                    <tbody>${r.member_activity.map(m => `
                        <tr>
                            <td>${escapeHtml(m.username)} ${renderRiskBadge(m.username)}</td>
                            <td><span class="trust-pill ${m.badge}">${m.trust_score}</span></td>
                            <td class="text-pass">${m.sent}</td>
                            <td class="text-danger">${m.flagged}</td>
                            <td>${m.total_attempts}</td>
                        </tr>`).join('')}
                    </tbody>
                </table>`;
        } else {
            memberTable.innerHTML = '<p class="text-muted" style="font-size:13px;">No activity yet.</p>';
        }

        const renderReasonList = items => items.map(item => `
            <div class="reason-item">
                <span class="reason-label">${escapeHtml(item.reason || item.category)}</span>
                <span class="reason-count">${item.count}x</span>
            </div>`).join('');

        document.getElementById('report-reasons').innerHTML = r.flagged_reasons?.length
            ? renderReasonList(r.flagged_reasons)
            : '<p class="text-muted" style="font-size:13px;">No violations recorded.</p>';

        document.getElementById('report-categories').innerHTML = r.flag_categories?.length
            ? renderReasonList(r.flag_categories)
            : '<p class="text-muted" style="font-size:13px;">No category trends yet.</p>';

        document.getElementById('report-trends').innerHTML = r.trend_points?.length
            ? r.trend_points.map(point => `
                <div class="trend-card">
                    <div class="trend-date">${escapeHtml(point.date)}</div>
                    <div class="trend-bars">
                        <div class="trend-bar pass" style="width:${Math.min(100, point.passed * 20)}%"></div>
                        <div class="trend-bar danger" style="width:${Math.min(100, point.flagged * 20)}%"></div>
                    </div>
                    <div class="trend-meta">
                        <span>Pass ${point.passed}</span>
                        <span>Flag ${point.flagged}</span>
                    </div>
                </div>`).join('')
            : '<p class="text-muted" style="font-size:13px;">No trend data yet.</p>';

        document.getElementById('report-heatmap').innerHTML = r.member_heatmap?.length
            ? r.member_heatmap.map(member => `
                <div class="heatmap-card ${member.risk_level}">
                    <div class="heatmap-user">${escapeHtml(member.username)}</div>
                    <div class="heatmap-score">${member.trust_score}</div>
                    <div class="heatmap-meta">Compliance ${member.compliance_rate}%</div>
                </div>`).join('')
            : '<p class="text-muted" style="font-size:13px;">No member heatmap data yet.</p>';

        const buildMsgItem = (m, style) => {
            const badgeCls = m.type === 'image' ? 'badge-image' : m.type === 'audio' ? 'badge-audio' : 'badge-text';
            const badgeTxt = m.type === 'image' ? 'Image' : m.type === 'audio' ? 'Audio' : 'Text';
            const categoryTag = m.category ? `<span class="report-msg-badge category">${escapeHtml(m.category)}</span>` : '';
            return `
                <div class="report-msg-item ${style}">
                    <div class="report-msg-header">
                        <span class="report-msg-user">${escapeHtml(m.username)}</span>
                        <span class="report-msg-badge ${badgeCls}">${badgeTxt}</span>
                        ${categoryTag}
                        <span class="report-msg-time">${formatTime(m.timestamp)}</span>
                    </div>
                    <div class="report-msg-content">${escapeHtml(m.display)}</div>
                    <div class="report-msg-reason ${style}">${escapeHtml(m.reason)}</div>
                </div>`;
        };

        if (passedLogEl) {
            passedLogEl.innerHTML = r.passed_messages?.length
                ? r.passed_messages.map(m => buildMsgItem(m, 'pass')).join('')
                : '<p class="text-muted" style="font-size:13px;">No passed messages yet.</p>';
        }

        if (flaggedLogEl) {
            flaggedLogEl.innerHTML = r.flagged_messages?.length
                ? r.flagged_messages.map(m => buildMsgItem(m, 'flagged')).join('')
                : '<p class="text-muted" style="font-size:13px;">No flagged messages.</p>';
        }
    } catch (err) {
        console.error('Failed to load report:', err);
        showToast('Error loading report.', 'error');
    }
}
