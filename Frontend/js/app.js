/**
 * ConvoEase - Frontend Application v3.5
 * SPA routing, API client, state management, DOM rendering, and theme system.
 * Pure vanilla JavaScript - no frameworks.
 */

// STATE

const State = {
    user: null,           // { username, full_name, profile_pic_color, ... }
    groups: [],           // [{ group_id, group_name, admin_username }, ...]
    activeGroupId: null,
    activeGroup: null,    // { group_id, group_name, admin_username, rules, ... }
    messages: [],         // [{ message_id, username, message, timestamp }, ...]
    pendingAppeal: null,  // { message_id, message, reason }
    memberRiskMap: {},    // { username: { trust_score, badge, risk_level } }
    pollTimer: null,
    imageCache: {},       // { message_id: "/media/image/..." } - session-only cache
    audioCache: {},       // { message_id: "/media/audio/..." } - session-only cache
    modalOpenCount: 0,
    unreadCounts: {},
    groupMessageCounts: {},
};

// =========================================================================
// API CLIENT
// =========================================================================
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

    leaveGroup: (group_id, username) =>
        API.request('POST', `/api/groups/${group_id}/leave`, { username }),

    deleteGroup: (group_id, username) =>
        API.request('DELETE', `/api/groups/${group_id}`, { username }),

    updateRules: (group_id, rules, username, moderation_sensitivity) =>
        API.request('PUT', `/api/groups/${group_id}/rules`, { rules, username, moderation_sensitivity }),

    updateGroupName: (group_id, group_name, username) =>
        API.request('PUT', `/api/groups/${group_id}/name`, { group_name, username }),

    // Messages
    getMessages: (group_id) =>
        API.request('GET', `/api/groups/${group_id}/messages`),

    sendMessage: (group_id, username, message) =>
        API.request('POST', `/api/groups/${group_id}/messages`, { username, message }),

    deleteMessage: (group_id, message_id, username) =>
        API.request('DELETE', `/api/groups/${group_id}/messages/${message_id}`, { username }),

    // Images - sends base64, returns message_id + summary + moderation result
    sendImage: (group_id, username, image_data, mime_type) =>
        API.request('POST', `/api/groups/${group_id}/images`, { username, image_data, mime_type }),

    // Audio - sends base64, returns message_id + transcript + moderation result
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

    updateProfile: (username, full_name, bio, avatar) =>
        API.request('PUT', '/api/user/profile', { username, full_name, bio, avatar }),
};

// =========================================================================
// UTILITIES
// =========================================================================
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

const AVATAR_EMOJIS = {
    bear: '🐻', fox: '🦊', owl: '🦉', wolf: '🐺', cat: '🐱',
    eagle: '🦅', panda: '🐼', lion: '🦁', rocket: '🚀', diamond: '💎', ghost: '👻',
};

function renderAvatarContent(user) {
    const avatar = user?.avatar || '';
    if (avatar && AVATAR_EMOJIS[avatar]) {
        return { text: AVATAR_EMOJIS[avatar], isEmoji: true };
    }
    return { text: getInitials(user?.full_name || ''), isEmoji: false };
}

function applyAvatarToElement(element, user) {
    if (!element) return;
    const content = renderAvatarContent(user);
    element.textContent = content.text;
    element.style.fontSize = content.isEmoji ? '20px' : '';
    element.style.backgroundColor = content.isEmoji ? 'transparent' : (user?.profile_pic_color || getAvatarColor(user?.full_name || ''));
    element.style.color = content.isEmoji ? '' : '#fff';
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

function setRuleSuggestionVisibility(source, visible) {
    const isCreate = source === 'create';
    const suggestionsEl = document.getElementById(isCreate ? 'create-rule-suggestions' : 'admin-rule-suggestions');
    const previewEl = document.getElementById(isCreate ? 'create-rule-preview' : 'admin-rule-preview');
    if (suggestionsEl) suggestionsEl.classList.toggle('hidden', !visible);
    if (previewEl) previewEl.classList.toggle('hidden', !visible || isCreate);
}

function autoResizeComposer() {
    const input = document.getElementById('message-input');
    if (!input) return;
    input.style.height = 'auto';
    input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
}

function setIconButtonBusy(btnId, busy) {
    const btn = document.getElementById(btnId);
    if (!btn) return;
    btn.disabled = busy;
    btn.classList.toggle('is-busy', busy);
}

function primeAttachButton(btnId, inputId) {
    const input = document.getElementById(inputId);
    setIconButtonBusy(btnId, true);
    setTimeout(() => {
        if (!input?.files?.length) {
            setIconButtonBusy(btnId, false);
        }
    }, 1200);
}

function getReportRiskTone(member) {
    if ((member.trust_score ?? 100) < 60 || member.badge === 'warning') return 'high';
    if ((member.trust_score ?? 100) < 85 || member.badge === 'watch') return 'medium';
    return 'low';
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
            // reader.result is "data:<mime>;base64,<data>" - strip the prefix
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

/**
 * Lightweight fingerprint for message-list change detection.
 * Avoids expensive JSON.stringify on every poll cycle.
 */
function _messageFingerprint(messages) {
    if (!messages || !messages.length) return '0::';
    const last = messages[messages.length - 1];
    return `${messages.length}:${last.message_id}:${last.status}:${last.message}`;
}

async function extractRulesFromFile(file, targetTextareaId, fileNameDisplayId) {
    if (!file) return;
    const maxSize = 2 * 1024 * 1024;
    if (file.size > maxSize) {
        showToast('File too large. Max 2 MB.', 'error');
        return;
    }

    const display = fileNameDisplayId ? document.getElementById(fileNameDisplayId) : null;
    if (display) display.textContent = `Extracting: ${file.name}...`;

    const formData = new FormData();
    formData.append('file', file);

    try {
        const resp = await fetch('/api/rules/extract', { method: 'POST', body: formData });
        const data = await resp.json();
        if (data.success) {
            const target = document.getElementById(targetTextareaId);
            if (target) target.value = data.extracted_text;
            if (display) display.textContent = `Loaded: ${file.name}`;
            showToast('Rules extracted from file!', 'success');
        } else {
            showToast(data.message || 'Failed to extract.', 'error');
            if (display) display.textContent = '';
        }
    } catch (err) {
        showToast('Connection error.', 'error');
        if (display) display.textContent = '';
    }
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

// =========================================================================
// THEME MANAGER  - v3.5
// Persists dark/light + accent to localStorage. Applies data-theme / data-accent
// on <html> so CSS variable overrides trigger automatically.
// =========================================================================
const ThemeManager = {
    LS_THEME: 'ce_theme',   // 'dark' | 'light'
    LS_ACCENT: 'ce_accent',  // 'teal' | 'slate' | 'graphite' | 'copper' | 'sage'
    TRANSITION_CLASS: 'theme-transitioning',
    _transitionTimer: null,

    /** Apply persisted settings immediately on load (called before DOMContentLoaded UI init) */
    applyPersisted() {
        const theme = localStorage.getItem(this.LS_THEME) || 'dark';
        let accent = localStorage.getItem(this.LS_ACCENT) || 'teal';
        const migration = { violet: 'teal', blue: 'slate', emerald: 'sage', rose: 'copper', amber: 'copper' };
        if (migration[accent]) {
            accent = migration[accent];
            localStorage.setItem(this.LS_ACCENT, accent);
        }
        this._apply(theme, accent);
    },

    setTheme(theme) {
        localStorage.setItem(this.LS_THEME, theme);
        this._applyWithTransition(theme, localStorage.getItem(this.LS_ACCENT) || 'teal');
    },

    setAccent(accent) {
        localStorage.setItem(this.LS_ACCENT, accent);
        this._applyWithTransition(localStorage.getItem(this.LS_THEME) || 'dark', accent);
    },

    _apply(theme, accent) {
        const html = document.documentElement;
        if (theme === 'light') html.setAttribute('data-theme', 'light');
        else html.removeAttribute('data-theme');
        html.setAttribute('data-accent', accent);
    },

    _applyWithTransition(theme, accent) {
        const html = document.documentElement;
        clearTimeout(this._transitionTimer);
        html.classList.add(this.TRANSITION_CLASS);
        this._apply(theme, accent);
        this._transitionTimer = setTimeout(() => {
            html.classList.remove(this.TRANSITION_CLASS);
        }, 250);
    },

    /** Sync the Settings UI controls to current persisted values */
    syncUI() {
        const theme = localStorage.getItem(this.LS_THEME) || 'dark';
        const accent = localStorage.getItem(this.LS_ACCENT) || 'teal';

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

// =========================================================================
// AUDIO RECORDER
// =========================================================================
const AudioRecorder = {
    mediaRecorder: null,
    chunks: [],
    stream: null,
    timerInterval: null,
    startTime: null,
    isRecording: false,

    async start() {
        if (this.isRecording) return;
        if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
            showToast('Audio recording is not supported in this browser. Please upload an audio file instead.', 'error');
            return;
        }
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        } catch (err) {
            showToast('Microphone access denied. Please allow mic access or upload an audio file.', 'error');
            return;
        }

        this.chunks = [];
        const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
            ? 'audio/webm;codecs=opus'
            : MediaRecorder.isTypeSupported('audio/webm')
                ? 'audio/webm'
                : '';
        const options = mimeType ? { mimeType } : {};

        this.mediaRecorder = new MediaRecorder(this.stream, options);
        this.mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) this.chunks.push(e.data);
        };
        this.mediaRecorder.onstop = () => {
            if (this.stream) {
                this.stream.getTracks().forEach(t => t.stop());
                this.stream = null;
            }
        };

        this.mediaRecorder.start();
        this.isRecording = true;
        this.startTime = Date.now();
        this._startTimer();
        this._showRecordingUI(true);
    },

    stop() {
        return new Promise((resolve) => {
            if (!this.isRecording || !this.mediaRecorder) {
                resolve(null);
                return;
            }
            this.mediaRecorder.onstop = () => {
                if (this.stream) {
                    this.stream.getTracks().forEach(t => t.stop());
                    this.stream = null;
                }
                const actualMime = this.mediaRecorder.mimeType || 'audio/webm';
                const blob = new Blob(this.chunks, { type: actualMime });
                this.mediaRecorder = null;
                this.chunks = [];
                this.isRecording = false;
                this.startTime = null;
                this._stopTimer();
                this._showRecordingUI(false);
                resolve(blob);
            };
            this.mediaRecorder.stop();
        });
    },

    cancel() {
        if (!this.isRecording) return;
        if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
            this.mediaRecorder.onstop = () => {
                if (this.stream) {
                    this.stream.getTracks().forEach(t => t.stop());
                    this.stream = null;
                }
                this.mediaRecorder = null;
            };
            this.mediaRecorder.stop();
        }
        this.chunks = [];
        this.isRecording = false;
        this.startTime = null;
        this._stopTimer();
        this._showRecordingUI(false);
    },

    _startTimer() {
        const timerEl = document.getElementById('recording-timer');
        if (timerEl) timerEl.textContent = '0:00';
        this.timerInterval = setInterval(() => {
            if (!this.startTime) return;
            const elapsed = Math.floor((Date.now() - this.startTime) / 1000);
            const mins = Math.floor(elapsed / 60);
            const secs = elapsed % 60;
            if (timerEl) timerEl.textContent = `${mins}:${secs.toString().padStart(2, '0')}`;
        }, 500);
    },

    _stopTimer() {
        clearInterval(this.timerInterval);
        this.timerInterval = null;
        const timerEl = document.getElementById('recording-timer');
        if (timerEl) timerEl.textContent = '0:00';
    },

    _showRecordingUI(recording) {
        const micBtn = document.getElementById('btn-attach-audio');
        const controls = document.getElementById('audio-recording-controls');
        if (micBtn) micBtn.classList.toggle('is-recording', recording);
        if (micBtn) micBtn.classList.toggle('hidden', recording);
        if (controls) controls.classList.toggle('hidden', !recording);
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
    } else if (page === 'moderation') {
        stopPolling();
        showPage('page-moderation');
        loadModerationPage();
    } else {
        showPage('page-auth');
    }
}

// =========================================================================
// AUTH
// =========================================================================
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
                sessionStorage.setItem('ce_session', JSON.stringify(data.user));
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
        if (username.toLowerCase() === password.toLowerCase()) {
            setError('register-error', 'Username and password cannot be the same.');
            setLoading('btn-register', false);
            return;
        }
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
    sessionStorage.removeItem('ce_session');
    AudioRecorder.cancel();
    State.user = null;
    State.groups = [];
    State.activeGroupId = null;
    State.activeGroup = null;
    State.messages = [];
    State.pendingAppeal = null;
    State.memberRiskMap = {};
    State.imageCache = {};
    State.audioCache = {};
    State.modalOpenCount = 0;
    State.unreadCounts = {};
    State.groupMessageCounts = {};
    document.querySelectorAll('.flag-banner').forEach(el => el.remove());
    document.querySelectorAll('.modal-overlay').forEach(el => el.classList.add('hidden'));
    stopPolling();
    navigateTo('auth');
    document.getElementById('form-login').reset();
    document.getElementById('form-register').reset();
}

// =========================================================================
// SIDEBAR
// =========================================================================
function updateSidebar() {
    if (!State.user) return;
    const avatar = document.getElementById('sidebar-avatar');
    const name = document.getElementById('sidebar-name');
    applyAvatarToElement(avatar, State.user);
    name.textContent = State.user.full_name;
}

async function loadGroups() {
    if (!State.user) return;
    try {
        const data = await API.getGroups(State.user.username);
        if (data.success) {
            State.groups = data.groups;
            data.groups.forEach(group => {
                if (typeof State.groupMessageCounts[group.group_id] !== 'number') {
                    State.groupMessageCounts[group.group_id] = null;
                }
                if (typeof State.unreadCounts[group.group_id] !== 'number') {
                    State.unreadCounts[group.group_id] = 0;
                }
            });
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
        const preview = (g.last_message || '').trim() || 'No messages yet';
        const unreadCount = State.unreadCounts[g.group_id] || 0;
        const unreadBadge = !isActive && unreadCount > 0
            ? `<span class="group-item-unread" title="${unreadCount} unread message${unreadCount === 1 ? '' : 's'}">${unreadCount > 99 ? '99+' : unreadCount}</span>`
            : '';
        const roleBadge = State.user && g.admin_username === State.user.username
            ? `<span class="group-item-role" title="You manage this group">
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                        <path d="M5 16 3 7l5 3 4-6 4 6 5-3-2 9H5zm1 2h12v2H6z"></path>
                    </svg>
                    Admin
               </span>`
            : '';
        return `
            <div class="group-item ${isActive ? 'active' : ''}" data-gid="${escapeHtml(g.group_id)}">
                <div class="avatar-circle" style="background:${color}">${initials}</div>
                <div class="group-item-info">
                    <div class="group-item-topline">
                        <div class="group-item-name">${escapeHtml(g.group_name)}</div>
                        ${roleBadge}
                    </div>
                    <div class="group-item-preview">${escapeHtml(preview)}</div>
                </div>
                ${unreadBadge}
            </div>`;
    }).join('');

    container.querySelectorAll('.group-item').forEach(el => {
        el.addEventListener('click', () => selectGroup(el.dataset.gid));
    });
}

// =========================================================================
// CHAT
// =========================================================================
async function selectGroup(groupId) {
    State.activeGroupId = groupId;
    State.messages = [];
    State.unreadCounts[groupId] = 0;
    renderGroupList();

    let memberCount = 0;
    try {
        const detailData = await API.getGroupDetails(groupId);
        if (detailData.success) {
            State.activeGroup = detailData.group;
        }
    } catch (err) {
        console.error('Failed to load group details:', err);
    }

    try {
        const membersData = await API.getGroupMembers(groupId);
        if (membersData.success && Array.isArray(membersData.members)) {
            memberCount = membersData.members.length;
        }
    } catch (err) {
        console.error('Failed to load member count:', err);
    }

    document.getElementById('chat-empty').classList.add('hidden');
    document.getElementById('chat-active').classList.remove('hidden');

    const group = State.activeGroup || { group_name: 'Unknown', admin_username: '', group_id: groupId };
    document.getElementById('chat-header-name').textContent = group.group_name;
    const memberLabel = memberCount === 1 ? '1 member' : `${memberCount || 0} members`;
    document.getElementById('chat-header-meta').textContent = `${memberLabel} \u2022 ${group.admin_username || 'Unknown'} (admin)`;
    const headerAvatar = document.getElementById('chat-header-avatar');
    headerAvatar.textContent = getInitials(group.group_name);
    headerAvatar.style.backgroundColor = getAvatarColor(group.group_name);

    const adminBtn = document.getElementById('btn-admin-panel');
    // Show the panel button for ALL members (admin sees full panel, others see read-only Rules)
    adminBtn.classList.remove('hidden');
    // Update tooltip based on role
    adminBtn.title = (State.user && group.admin_username === State.user.username)
        ? 'Admin Panel' : 'Group Info';
    const moderationBtn = document.getElementById('btn-moderation-page-nav');
    if (moderationBtn) {
        moderationBtn.classList.remove('hidden');
        moderationBtn.title = (State.user && group.admin_username === State.user.username)
            ? 'Moderation Dashboard'
            : 'My Moderation';
    }

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
    const groupId = State.activeGroupId;
    if (!groupId) return;
    try {
        const data = await API.getMessages(groupId);
        if (!data.success || groupId !== State.activeGroupId) return;

        const oldFingerprint = _messageFingerprint(State.messages);
        const newFingerprint = _messageFingerprint(data.messages);

        if (oldFingerprint === newFingerprint) return;

        const oldCount = State.messages.length;
        const newCount = data.messages.length;
        State.messages = data.messages;
        State.groupMessageCounts[groupId] = newCount;

        if (oldCount === 0 || newCount < oldCount) {
            renderMessages(false);
            if (newCount > 0) scrollToBottom();
        } else if (newCount > oldCount) {
            appendNewMessages(data.messages.slice(oldCount));
        } else {
            renderMessages(false);
        }
    } catch (err) {
        console.error('Failed to load messages:', err);
    }
}

function _bindMessageDeleteButtons(nodes) {
    nodes.forEach(node => {
        node.querySelectorAll('.msg-delete-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                const messageId = btn.dataset.mid;
                if (!messageId || !State.activeGroupId || !State.user) return;
                if (!confirm('Delete this message? This cannot be undone.')) return;

                try {
                    const data = await API.deleteMessage(State.activeGroupId, messageId, State.user.username);
                    if (data.success) await loadMessages();
                    else showToast(data.message || 'Could not delete.', 'error');
                } catch (err) {
                    showToast('Connection error.', 'error');
                }
            });
        });
    });
}

function _buildMessageHTML(m) {
    const isMe = State.user && m.username === State.user.username;
    const senderHtml = isMe ? '' : `
        <div class="msg-sender-row">
            <div class="msg-sender">${escapeHtml(m.username)}</div>
            ${renderRiskBadge(m.username)}
        </div>`;

    const isDeleted = m.message === '[deleted]' || m.status === 'DELETED';
    const isImage = m.message && (m.message === '[IMAGE]' || m.message.startsWith('[IMAGE]'));
    const isAudio = m.message && (m.message === '[AUDIO]' || m.message.startsWith('[AUDIO]'));

    let bubbleContent;
    if (isDeleted) {
        bubbleContent = `<span class="msg-deleted">This message was deleted.</span>`;
    } else if (isImage) {
        const inlineSummary = m.summary || m.message.replace(/^\[IMAGE\]\s*/, '');
        const imgSrc = (m.media_url && m.media_url.trim())
            ? m.media_url
            : (State.imageCache[m.message_id] || null);
        if (imgSrc) {
            bubbleContent = `
                <div class="msg-image-wrapper">
                    <img class="msg-image" src="${imgSrc}" alt="Shared image" loading="lazy">
                </div>
                ${inlineSummary ? `<div class="msg-image-caption">${escapeHtml(inlineSummary)}</div>` : ''}`;
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
                ${transcript ? `<div class="msg-audio-transcript">\u{1F3A4} ${escapeHtml(transcript)}</div>` : ''}`;
        } else {
            bubbleContent = `
                <div class="msg-audio-indicator">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
                        <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                    </svg>
                    <span>Audio</span>
                </div>
                ${transcript ? `<div class="msg-audio-transcript">\u{1F3A4} ${escapeHtml(transcript)}</div>` : ''}`;
        }
    } else {
        bubbleContent = escapeHtml(m.message);
    }

    return `
        <div class="message-row ${isMe ? 'me' : 'other'}${isImage ? ' image-msg' : ''}${isAudio ? ' audio-msg' : ''}">
            ${senderHtml}
            <div class="msg-bubble">
                ${bubbleContent}
                <div class="msg-meta-row">
                    <span class="msg-time">${formatTime(m.timestamp)}</span>
                    ${isMe && !isDeleted ? `<button class="msg-delete-btn" data-mid="${m.message_id}" title="Delete message">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="3 6 5 6 21 6"></polyline>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                        </svg>
                    </button>` : ''}
                </div>
            </div>
        </div>`;
}

function renderMessages(autoScroll = false) {
    const container = document.getElementById('chat-messages');
    if (!container) return;
    if (State.messages.length === 0) {
        container.innerHTML = `
            <div style="text-align:center; padding:60px 20px; color:var(--text-muted);">
                <p>No messages yet. Say hello! \u{1F44B}</p>
            </div>`;
        return;
    }

    container.innerHTML = State.messages.map(m => _buildMessageHTML(m)).join('');

    if (autoScroll) scrollToBottom();

    _bindMessageDeleteButtons(Array.from(container.children));
}

/**
 * Append only new messages to the DOM without destroying existing nodes.
 * This is the key anti-flicker optimization for the common case of
 * new messages arriving during polling.
 */
function appendNewMessages(newMessages) {
    const container = document.getElementById('chat-messages');
    if (!container || !newMessages.length) return;

    if (container.querySelector('.message-row') === null) {
        renderMessages(true);
        return;
    }

    const fragment = document.createDocumentFragment();
    const newNodes = [];
    newMessages.forEach(m => {
        const wrapper = document.createElement('div');
        wrapper.innerHTML = _buildMessageHTML(m);
        const node = wrapper.firstElementChild;
        if (node) {
            newNodes.push(node);
            fragment.appendChild(node);
        }
    });

    container.appendChild(fragment);
    _bindMessageDeleteButtons(newNodes);
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
    autoResizeComposer();
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

// =========================================================================

async function sendAudio(file) {
    if (!file || !State.activeGroupId || !State.user) return;

    const maxSize = 10 * 1024 * 1024; // 10 MB limit
    if (file.size > maxSize) {
        showToast('Audio too large. Max 10 MB.', 'error');
        return;
    }

    showTypingIndicator();
    showToast('Analyzing audio...', '');
    setIconButtonBusy('btn-attach-audio', true);

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
    } finally {
        setIconButtonBusy('btn-attach-audio', false);
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
    setIconButtonBusy('btn-attach-image', true);

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
    } finally {
        setIconButtonBusy('btn-attach-image', false);
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
        ${appealButton}
        <button class="flag-banner-dismiss" type="button" aria-label="Dismiss banner" title="Dismiss">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
        </button>`;

    const bannerSlot = document.getElementById('flag-banner-slot');
    if (!bannerSlot) return;

    bannerSlot.appendChild(banner);
    if (appealData?.message_id) {
        banner.querySelector('#btn-open-appeal').addEventListener('click', () => openAppealModal(appealData));
    }
    banner.querySelector('.flag-banner-dismiss').addEventListener('click', () => banner.remove());

    // Auto-dismiss after 5 seconds, paused on hover
    let autoDismissTimer = setTimeout(() => banner.remove(), 5000);

    banner.addEventListener('mouseenter', () => {
        clearTimeout(autoDismissTimer);
    });

    banner.addEventListener('mouseleave', () => {
        autoDismissTimer = setTimeout(() => banner.remove(), 3000);
    });
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
    body.innerHTML = `
        <div class="catchup-loading">
            <div class="typing-indicator catchup-loading-indicator">
                <div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>
            </div>
            <p class="text-muted">Preparing your AI catch-up...</p>
        </div>`;

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
        if (previewEl) previewEl.textContent = '';
        setRuleSuggestionVisibility(source, false);
        return;
    }

    setRuleSuggestionVisibility(source, true);
    suggestionsEl.innerHTML = '<p class="text-muted">Reviewing rules...</p>';
    if (previewEl) previewEl.textContent = '';

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
        if (previewEl) previewEl.textContent = data.revised_rules || '';
    } catch (err) {
        suggestionsEl.innerHTML = '<p class="text-muted">Connection error while suggesting rules.</p>';
    }
}

// Polling
let _pollTick = 0;

function startPolling() {
    if (!State.activeGroupId || State.modalOpenCount > 0) return;
    stopPolling();
    State.pollTimer = setInterval(() => {
        if (State.activeGroupId && State.modalOpenCount === 0) {
            loadMessages();
            pollGroupUnreadCounts();
            _pollTick++;
            if (_pollTick % 5 === 0) pollGroupDetails();
        }
    }, 3000);
}

function stopPolling() {
    if (State.pollTimer) {
        clearInterval(State.pollTimer);
        State.pollTimer = null;
    }
    _pollTick = 0;
}

async function pollGroupUnreadCounts() {
    if (!State.user || !State.groups?.length) return;

    const inactiveGroups = State.groups.filter(g => g.group_id !== State.activeGroupId);
    if (!inactiveGroups.length) return;

    try {
        const results = await Promise.all(inactiveGroups.map(async group => {
            const data = await API.getMessages(group.group_id);
            return { groupId: group.group_id, messages: data.success ? data.messages : [] };
        }));

        let hasUnreadUpdate = false;
        results.forEach(result => {
            const previousCount = State.groupMessageCounts[result.groupId];
            const nextCount = result.messages.length;
            if (typeof previousCount === 'number' && nextCount > previousCount) {
                State.unreadCounts[result.groupId] = (State.unreadCounts[result.groupId] || 0) + (nextCount - previousCount);
                hasUnreadUpdate = true;
            }
            State.groupMessageCounts[result.groupId] = nextCount;
        });

        if (hasUnreadUpdate) {
            _updateUnreadBadgesInPlace();
        }
    } catch (err) {
        console.error('Failed to poll unread counts:', err);
    }
}

/**
 * Update unread badges in the sidebar without re-rendering the entire group list.
 * This prevents the flicker caused by innerHTML replacement on every poll cycle.
 */
function _updateUnreadBadgesInPlace() {
    const container = document.getElementById('group-list');
    if (!container) return;
    container.querySelectorAll('.group-item').forEach(el => {
        const gid = el.dataset.gid;
        const count = State.unreadCounts[gid] || 0;
        const isActive = gid === State.activeGroupId;
        const existingBadge = el.querySelector('.group-item-unread');
        if (existingBadge) existingBadge.remove();
        if (!isActive && count > 0) {
            const badge = document.createElement('span');
            badge.className = 'group-item-unread';
            badge.textContent = count > 99 ? '99+' : count;
            badge.title = `${count} unread message${count === 1 ? '' : 's'}`;
            el.appendChild(badge);
        }
    });
}

async function pollGroupDetails() {
    if (!State.activeGroupId || !State.activeGroup) return;
    try {
        const data = await API.getGroupDetails(State.activeGroupId);
        if (!data.success || !data.group) return;

        const updated = data.group;
        const current = State.activeGroup;

        const rulesChanged = updated.rules !== current.rules;
        const sensitivityChanged = updated.moderation_sensitivity !== current.moderation_sensitivity;
        const nameChanged = updated.group_name !== current.group_name;

        if (!rulesChanged && !sensitivityChanged && !nameChanged) return;

        State.activeGroup = { ...current, ...updated };

        if (nameChanged) {
            const headerName = document.getElementById('chat-header-name');
            if (headerName) headerName.textContent = updated.group_name;
            const headerAvatar = document.getElementById('chat-header-avatar');
            if (headerAvatar) {
                headerAvatar.textContent = getInitials(updated.group_name);
                headerAvatar.style.backgroundColor = getAvatarColor(updated.group_name);
            }
            State.groups = State.groups.map(group =>
                group.group_id === updated.group_id ? { ...group, group_name: updated.group_name } : group
            );
            renderGroupList(document.getElementById('search-groups')?.value || '');
        }

        const moderationGroupName = document.getElementById('mod-page-group-name');
        if (moderationGroupName && nameChanged) {
            moderationGroupName.textContent = updated.group_name || '';
        }

        const adminModal = document.getElementById('modal-admin');
        if (adminModal && !adminModal.classList.contains('hidden')) {
            const rulesTextarea = document.getElementById('admin-rules');
            if (State.user && updated.admin_username !== State.user.username) {
                if (rulesTextarea && rulesChanged) {
                    rulesTextarea.value = updated.rules || '';
                }
            }
            const sensitivitySelect = document.getElementById('admin-sensitivity');
            if (sensitivitySelect && sensitivityChanged) {
                sensitivitySelect.value = updated.moderation_sensitivity || 'Moderate';
            }
        }

        const sensitivityEl = document.getElementById('mod-grp-sensitivity');
        if (sensitivityEl && sensitivityChanged) {
            sensitivityEl.textContent = updated.moderation_sensitivity || 'Moderate';
        }

        if (rulesChanged) {
            showToast('Group rules were updated by the admin.', '');
        } else if (sensitivityChanged) {
            showToast('Moderation sensitivity was changed by the admin.', '');
        }
    } catch (err) {
        console.error('Failed to poll group details:', err);
    }
}

// =========================================================================
// SETTINGS
// =========================================================================
async function loadSettings() {
    if (!State.user) return;

    const avatar = document.getElementById('settings-avatar');
    applyAvatarToElement(avatar, State.user);
    document.getElementById('settings-fullname').textContent = State.user.full_name;
    document.getElementById('settings-username').textContent = `@${State.user.username}`;
    const editFullname = document.getElementById('edit-fullname');
    const editBio = document.getElementById('edit-bio');
    if (editFullname) editFullname.value = State.user.full_name || '';
    if (editBio) editBio.value = State.user.bio || '';
    document.querySelectorAll('.avatar-option').forEach(btn => {
        btn.classList.toggle('active', (btn.dataset.avatar || '') === (State.user.avatar || ''));
    });
    const defaultBtn = document.getElementById('avatar-option-default');
    if (defaultBtn) defaultBtn.textContent = getInitials(State.user.full_name || '');

    try {
        const data = await API.getSettings();
        if (data.success) {
            const s = data.settings;
            document.getElementById('setting-mode').textContent = (s.moderation_status || 'Active').toUpperCase();
            document.getElementById('setting-model').textContent = s.workspace_mode || 'Protected';
            document.getElementById('setting-url').textContent = (s.content_types || []).join(', ') || 'Standard chat';
            document.getElementById('setting-plugins').textContent = (s.features || []).join(', ') || 'Enabled';
            const versionEl = document.getElementById('setting-version');
            if (versionEl) versionEl.textContent = s.app_version || '4.1';
            const vmEl = document.getElementById('setting-vision-model');
            if (vmEl) vmEl.textContent = `${s.plugin_count || 0} active`;
        }
    } catch (err) {
        console.error('Failed to load settings:', err);
    }

    // Sync theme controls to stored preferences
    ThemeManager.syncUI();
}

// =========================================================================
// MODALS
// =========================================================================
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal || !modal.classList.contains('hidden')) return;
    modal.classList.remove('hidden');
    State.modalOpenCount += 1;
    stopPolling();
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal || modal.classList.contains('hidden')) return;
    modal.classList.add('hidden');
    State.modalOpenCount = Math.max(0, State.modalOpenCount - 1);
    if (State.modalOpenCount === 0) {
        startPolling();
    }
}

async function reviewAppeal(messageId, decision, adminNote = '') {
    if (!State.activeGroup || !State.user) return;

    try {
        const data = await API.reviewAppeal(
            State.activeGroup.group_id,
            messageId,
            State.user.username,
            decision,
            adminNote
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
        btn.addEventListener('click', () => {
            const flaggedItem = btn.closest('.flagged-item');
            const adminNote = flaggedItem?.querySelector('[data-admin-note]')?.value.trim() || '';
            reviewAppeal(btn.dataset.messageId, btn.dataset.appealDecision, adminNote);
        });
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
        const appealLine = f.appeal_text
            ? `<div class="flagged-item-meta"><strong>Appeal:</strong> ${escapeHtml(f.appeal_text)}</div>
               <div class="flagged-item-meta"><strong>AI Re-check:</strong> ${escapeHtml(f.appeal_ai_status || 'Pending')} ${f.appeal_ai_reason ? `- ${escapeHtml(f.appeal_ai_reason)}` : ''}</div>`
            : '';
        const actions = isAdmin && f.appeal_status === 'PENDING_ADMIN'
            ? `
                <textarea class="flagged-item-admin-note" data-admin-note placeholder="Optional admin note for this decision..."></textarea>
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

    // Modal tabs (Create/Join group) - uses data-modal-tab
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

    // Admin panel tabs - uses data-admin-tab
    document.querySelectorAll('[data-admin-tab]').forEach(tab => {
        tab.addEventListener('click', () => {
            const target = tab.dataset.adminTab;
            document.querySelectorAll('[data-admin-tab]').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            document.querySelectorAll('.admin-tab-content').forEach(c => c.style.display = 'none');
            const tabEl = document.getElementById(`admin-tab-${target}`);
            if (tabEl) tabEl.style.display = 'block';
        });
    });

    // Create group form
    document.getElementById('form-create-group').addEventListener('submit', async (e) => {
        e.preventDefault();
        clearErrors('create-group-error');
        const name = document.getElementById('create-name').value.trim();
        const password = document.getElementById('create-password').value.trim();
        const rules = document.getElementById('create-rules').value.trim();
        const moderationSensitivity = document.getElementById('create-sensitivity').value;

        if (!name) { setError('create-group-error', 'Group name is required.'); return; }

        try {
            const data = await API.createGroup(name, password, State.user.username, rules, moderationSensitivity);
            if (data.success) {
                closeModal('modal-group');
                document.getElementById('form-create-group').reset();
                document.getElementById('create-rules').value = 'Be respectful.';
                document.getElementById('create-sensitivity').value = 'Moderate';
                document.getElementById('create-rule-suggestions').innerHTML = '<p class="text-muted">AI suggestions will appear here.</p>';
                setRuleSuggestionVisibility('create', false);
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

// =========================================================================
// ADMIN PANEL
// =========================================================================
async function openAdminPanel() {
    if (!State.activeGroup || !State.user) return;

    const isAdmin = State.activeGroup.admin_username === State.user.username;

    const titleEl = document.getElementById('admin-panel-title');
    if (titleEl) titleEl.textContent = isAdmin ? 'Admin Panel' : 'Group Info';

    const modPageBtn = document.getElementById('btn-open-mod-page');
    if (modPageBtn) modPageBtn.style.display = isAdmin ? '' : 'none';

    const flaggedTabBtn = document.getElementById('admin-tab-btn-flagged');
    if (flaggedTabBtn) flaggedTabBtn.style.display = isAdmin ? '' : 'none';

    document.querySelectorAll('[data-admin-tab]').forEach(t => t.classList.remove('active'));
    const infoTabBtn = document.querySelector('[data-admin-tab="info"]');
    if (infoTabBtn) infoTabBtn.classList.add('active');
    document.querySelectorAll('.admin-tab-content').forEach(c => c.style.display = 'none');
    const infoTab = document.getElementById('admin-tab-info');
    if (infoTab) infoTab.style.display = 'block';

    document.getElementById('admin-group-id').textContent = State.activeGroup.group_id;
    const groupNameRow = document.getElementById('admin-group-name-row');
    const groupNameInput = document.getElementById('admin-group-name-input');
    if (groupNameRow && groupNameInput) {
        groupNameRow.style.display = isAdmin ? '' : 'none';
        if (isAdmin) {
            groupNameInput.value = State.activeGroup.group_name || '';
        }
    }

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

    const myTrustRow = document.getElementById('admin-my-trust-row');
    if (!isAdmin && myTrustRow) {
        const myData = State.memberRiskMap[State.user.username];
        if (myData) {
            const pill = document.getElementById('admin-my-trust-pill');
            if (pill) {
                pill.textContent = myData.trust_score;
                pill.className = `trust-pill ${myData.badge}`;
            }
            myTrustRow.style.display = '';
        } else {
            myTrustRow.style.display = 'none';
        }
    } else if (myTrustRow) {
        myTrustRow.style.display = 'none';
    }

    const sensitivityBlock = document.getElementById('admin-sensitivity-block');
    if (sensitivityBlock) sensitivityBlock.style.display = isAdmin ? 'block' : 'none';
    if (isAdmin) {
        document.getElementById('admin-sensitivity').value =
            State.activeGroup.moderation_sensitivity || 'Moderate';
    }

    const leaveBlock = document.getElementById('leave-group-block');
    if (leaveBlock) {
        leaveBlock.style.display = isAdmin ? 'none' : 'block';
    }

    const deleteBlock = document.getElementById('delete-group-block');
    if (deleteBlock) {
        deleteBlock.style.display = isAdmin ? 'block' : 'none';
    }

    const rulesTextarea = document.getElementById('admin-rules');
    rulesTextarea.value = State.activeGroup.rules || '';
    document.getElementById('admin-rule-preview').value = '';
    document.getElementById('admin-rule-suggestions').innerHTML = '';
    setRuleSuggestionVisibility('admin', false);
    rulesTextarea.readOnly = !isAdmin;
    rulesTextarea.style.opacity = isAdmin ? '' : '0.7';
    const rulesActions = document.getElementById('admin-rules-actions');
    if (rulesActions) rulesActions.style.display = isAdmin ? 'block' : 'none';

    if (isAdmin) {
        try {
            const flaggedData = await API.getFlagged(State.activeGroup.group_id);
            const items = flaggedData.success ? flaggedData.flagged : [];
            const badge = document.getElementById('admin-flagged-badge');
            const pendingCount = items.filter(f => f.appeal_status === 'PENDING_ADMIN').length;
            if (badge) {
                if (pendingCount > 0) {
                    badge.textContent = pendingCount;
                    badge.classList.remove('hidden');
                } else {
                    badge.classList.add('hidden');
                }
            }

            renderFlaggedList(items, true);
        } catch (err) {
            console.error('Failed to load flagged:', err);
            renderFlaggedList([], true);
        }
    } else {
        const badge = document.getElementById('admin-flagged-badge');
        if (badge) {
            badge.textContent = '';
            badge.classList.add('hidden');
        }
    }

    openModal('modal-admin');
}

// =========================================================================

async function loadModerationReport(group_id) {
    return loadModerationPage(group_id);

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
                    <thead><tr><th>Member</th><th>Trust</th><th>Sent</th><th>Flagged</th><th>Total</th></tr></thead>
                    <tbody>${r.member_activity.map(m => `
                        <tr class="report-member-row ${getReportRiskTone(m)}">
                            <td><span class="report-member-name">${escapeHtml(m.username)} ${renderRiskBadge(m.username)}</span></td>
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

        // Flagged reasons
        const reasonsEl = document.getElementById('report-reasons');
        if (r.flagged_reasons && r.flagged_reasons.length > 0) {
            reasonsEl.innerHTML = r.flagged_reasons.map(reason => `
                <div class="reason-item">
                    <span class="reason-label">${escapeHtml(reason.reason)}</span>
                    <span class="reason-count">${reason.count}Ã—</span>
                </div>`).join('');
        } else {
            reasonsEl.innerHTML = '<p class="text-muted" style="font-size:13px;">No violations recorded.</p>';
        }

        // =========================================================================
        function buildMsgItem(m, style) {
            const isAudio = m.type === 'audio';
            const badgeCls = m.type === 'image' ? 'badge-image' : isAudio ? 'badge-audio' : 'badge-text';
            const badgeTxt = m.type === 'image' ? '\u{1F4F7} Image' : isAudio ? '\u{1F3A4} Audio' : '\u{1F4AC} Text';
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

        // =========================================================================
        if (passedLogEl) {
            if (r.passed_messages && r.passed_messages.length > 0) {
                passedLogEl.innerHTML = r.passed_messages.map(m => buildMsgItem(m, 'pass')).join('');
            } else {
                passedLogEl.innerHTML = '<p class="text-muted" style="font-size:13px;">No passed messages yet.</p>';
            }
        }

        // =========================================================================
        if (flaggedLogEl) {
            if (r.flagged_messages && r.flagged_messages.length > 0) {
                flaggedLogEl.innerHTML = r.flagged_messages.map(m => buildMsgItem(m, 'flagged')).join('');
            } else {
                flaggedLogEl.innerHTML = '<p class="text-muted" style="font-size:13px;">No flagged messages. \u{1F389}</p>';
            }
        }

    } catch (err) {
        console.error('Failed to load report:', err);
        showToast('Error loading report.', 'error');
    }
}

// =========================================================================
// EVENT BINDINGS
// =========================================================================
async function loadModerationPage() {
    if (!State.activeGroup || !State.user) return;

    const isAdmin = State.activeGroup.admin_username === State.user.username;
    const group = State.activeGroup;

    const titleEl = document.getElementById('mod-page-title');
    if (titleEl) titleEl.textContent = isAdmin ? 'Moderation Dashboard' : 'My Moderation';
    const groupNameEl = document.getElementById('mod-page-group-name');
    if (groupNameEl) groupNameEl.textContent = group.group_name || '';

    document.getElementById('mod-member-view').classList.toggle('hidden', isAdmin);
    document.getElementById('mod-admin-view').classList.toggle('hidden', !isAdmin);

    let report = null;
    try {
        const data = await API.getModerationReport(group.group_id);
        if (data.success) report = data.report;
    } catch (err) {
        console.error('Failed to load moderation report:', err);
        showToast('Failed to load moderation data.', 'error');
        return;
    }
    if (!report) return;

    State.memberRiskMap = Object.fromEntries((report.member_activity || []).map(member => [member.username, member]));

    if (isAdmin) {
        _populateAdminView(report);
    } else {
        _populateMemberView(report, group);
    }
}

function _populateMemberView(report, group) {
    const username = State.user.username;
    const myData = (report.member_activity || []).find(m => m.username === username);

    if (myData) {
        const scoreEl = document.getElementById('mod-my-score');
        scoreEl.textContent = myData.trust_score;
        scoreEl.className = `mod-trust-score-number ${myData.badge}`;

        const badgeLabels = { trusted: 'Trusted', watch: 'Under Watch', warning: 'High Risk' };
        const labelEl = document.getElementById('mod-my-badge-label');
        if (labelEl) labelEl.textContent = badgeLabels[myData.badge] || 'Trust Score';

        document.getElementById('mod-my-sent').textContent = myData.sent ?? '--';
        document.getElementById('mod-my-flagged-count').textContent = myData.flagged ?? '--';
        const compliance = myData.compliance_rate != null ? myData.compliance_rate + '%' : '--';
        document.getElementById('mod-my-compliance').textContent = compliance;
    }

    document.getElementById('mod-grp-pass-rate').textContent = report.pass_rate + '%';
    setTimeout(() => {
        document.getElementById('mod-grp-pass-bar').style.width = report.pass_rate + '%';
    }, 80);
    document.getElementById('mod-grp-sensitivity').textContent =
        group.moderation_sensitivity || 'Moderate';

    const myFlagged = (report.flagged_messages || []).filter(m => m.username === username);
    const listEl = document.getElementById('mod-my-flagged-list');
    if (myFlagged.length === 0) {
        listEl.innerHTML = '<p class="text-muted" style="font-size:13px;">No flagged messages - you\'re in good standing.</p>';
    } else {
        listEl.innerHTML = myFlagged.map(f => _buildFlaggedItem(f, false)).join('');
        _bindFlaggedItemEvents(listEl);
    }
}

function _populateAdminView(report) {
    document.getElementById('mds-total').textContent = report.total_messages ?? '--';
    document.getElementById('mds-passed').textContent = report.pass_count ?? '--';
    document.getElementById('mds-flagged').textContent = report.flagged_count ?? '--';
    document.getElementById('mds-text').textContent = report.text_count ?? '--';
    document.getElementById('mds-images').textContent = report.image_count ?? '--';
    document.getElementById('mds-audios').textContent = report.audio_count ?? '--';

    document.getElementById('mds-pass-rate').textContent = report.pass_rate + '%';
    document.getElementById('mds-flag-rate').textContent = report.flagged_rate + '%';
    setTimeout(() => {
        document.getElementById('mds-bar-pass').style.width = report.pass_rate + '%';
        document.getElementById('mds-bar-flag').style.width = report.flagged_rate + '%';
    }, 80);

    _renderTrendChart(report.trend_points || []);
    _renderReasons(report.flagged_reasons || []);
    _renderMemberTable(report.member_activity || []);

    const flaggedLogEl = document.getElementById('mds-flagged-log');
    const flaggedItems = report.flagged_messages || [];
    const pendingCount = flaggedItems.filter(f =>
        String(f.appeal_status || '').toUpperCase() === 'PENDING_ADMIN'
    ).length;
    const pendingBadge = document.getElementById('mds-pending-badge');
    if (pendingBadge) {
        pendingBadge.textContent = pendingCount;
        pendingBadge.classList.toggle('hidden', pendingCount === 0);
    }

    if (flaggedItems.length === 0) {
        flaggedLogEl.innerHTML = '<p class="text-muted" style="font-size:13px;">No flagged messages.</p>';
    } else {
        flaggedLogEl.innerHTML = flaggedItems.map(f => _buildFlaggedItem(f, true)).join('');
        _bindFlaggedItemEvents(flaggedLogEl);
    }
}

function _renderTrendChart(trendPoints) {
    const el = document.getElementById('mds-trend');
    if (!trendPoints.length) {
        el.innerHTML = '<p class="text-muted" style="font-size:13px;">No trend data yet.</p>';
        return;
    }

    const maxVal = Math.max(...trendPoints.map(p => (p.passed || 0) + (p.flagged || 0)), 1);

    el.innerHTML = trendPoints.map(p => {
        const passHeight = Math.round(((p.passed || 0) / maxVal) * 68);
        const flagHeight = Math.round(((p.flagged || 0) / maxVal) * 68);
        const dateLabel = (p.date || '').slice(5);

        return `<div class="mod-trend-bar-group" title="${p.date}: ${p.passed} passed, ${p.flagged} flagged">
            <div class="mod-trend-bars">
                <div class="mod-trend-bar pass" style="height:${passHeight}px"></div>
                <div class="mod-trend-bar flag" style="height:${flagHeight}px"></div>
            </div>
            <div class="mod-trend-date">${dateLabel}</div>
        </div>`;
    }).join('');
}

function _renderReasons(reasons) {
    const el = document.getElementById('mds-reasons');
    if (!reasons.length) {
        el.innerHTML = '<p class="text-muted" style="font-size:13px;">No violations recorded.</p>';
        return;
    }
    const maxCount = reasons[0].count || 1;
    el.innerHTML = reasons.map(r => {
        const pct = Math.round((r.count / maxCount) * 100);
        return `<div class="mod-reason-row">
            <span class="mod-reason-label" title="${escapeHtml(r.reason)}">${escapeHtml(r.reason)}</span>
            <div class="mod-reason-bar-wrap">
                <div class="mod-reason-bar" style="width:${pct}%"></div>
            </div>
            <span class="mod-reason-count">${r.count}</span>
        </div>`;
    }).join('');
}

function _renderMemberTable(members) {
    const el = document.getElementById('mds-members');
    if (!members.length) {
        el.innerHTML = '<p class="text-muted" style="font-size:13px;">No activity yet.</p>';
        return;
    }
    el.innerHTML = `<table class="mod-member-table">
        <thead>
            <tr>
                <th>Member</th>
                <th>Trust</th>
                <th>Sent</th>
                <th>Flagged</th>
                <th>Compliance</th>
            </tr>
        </thead>
        <tbody>
            ${members.map(m => `
            <tr class="mod-row-${m.badge}">
                <td>${escapeHtml(m.username)}</td>
                <td><span class="trust-pill ${m.badge}">${m.trust_score}</span></td>
                <td>${m.sent}</td>
                <td style="color:var(--danger)">${m.flagged}</td>
                <td>${m.compliance_rate != null ? m.compliance_rate + '%' : '--'}</td>
            </tr>`).join('')}
        </tbody>
    </table>`;
}

function _buildFlaggedItem(f, isAdmin) {
    const isImg = String(f.message || '').startsWith('[IMAGE]');
    const isAud = String(f.message || '').startsWith('[AUDIO]');
    const typeLabel = isImg ? 'Image' : isAud ? 'Audio' : 'Text';
    const display = isImg
        ? (f.display || f.summary || 'Image content')
        : isAud
            ? (f.display || f.summary || 'Audio content')
            : (f.display || f.message || '');

    const appealStatus = String(f.appeal_status || '').toUpperCase();
    const hasPendingAppeal = appealStatus === 'PENDING_ADMIN';
    const hasAppeal = !!f.appeal_text;

    let appealSection = '';
    if (hasAppeal) {
        appealSection = `<div class="mod-flagged-appeal-info">
            <strong>Appeal:</strong> ${escapeHtml(f.appeal_text)}<br>
            <strong>AI re-check:</strong> ${escapeHtml(f.appeal_ai_status || 'Pending')}
            ${f.appeal_ai_reason ? ' - ' + escapeHtml(f.appeal_ai_reason) : ''}
        </div>`;
    }

    let actionSection = '';
    if (isAdmin && hasPendingAppeal) {
        actionSection = `<div class="mod-appeal-actions">
            <button class="btn btn-primary btn-sm"
                data-appeal-decision="approve"
                data-message-id="${escapeHtml(f.message_id)}"
                type="button">Approve Appeal</button>
            <button class="btn btn-secondary btn-sm"
                data-appeal-decision="reject"
                data-message-id="${escapeHtml(f.message_id)}"
                type="button">Reject Appeal</button>
        </div>`;
    }

    const canAppeal = !isAdmin
        && f.username === State.user?.username
        && !hasAppeal;
    if (canAppeal) {
        actionSection = `<div class="mod-appeal-actions">
            <button class="btn btn-secondary btn-sm"
                data-open-appeal="true"
                data-message-id="${escapeHtml(f.message_id)}"
                data-message-text="${escapeHtml(display)}"
                data-reason="${escapeHtml(f.reason || '')}"
                type="button">Appeal this</button>
        </div>`;
    }

    return `<div class="mod-flagged-item">
        <div class="mod-flagged-header">
            <span class="mod-flagged-user">${escapeHtml(f.username)}</span>
            <span class="mod-flagged-type-badge">${typeLabel}</span>
            ${appealStatus === 'PENDING_ADMIN' ? '<span class="mod-flagged-type-badge" style="color:var(--warning);">Pending review</span>' : ''}
            ${appealStatus === 'APPROVED' ? '<span class="mod-flagged-type-badge" style="color:var(--success);">Approved</span>' : ''}
            ${appealStatus === 'REJECTED' ? '<span class="mod-flagged-type-badge" style="color:var(--danger);">Rejected</span>' : ''}
            <span class="mod-flagged-time">${formatTime(f.timestamp)}</span>
        </div>
        <div class="mod-flagged-message">${escapeHtml(display)}</div>
        <div class="mod-flagged-reason">${escapeHtml(f.reason || '')}</div>
        ${appealSection}
        ${actionSection}
    </div>`;
}

function _bindFlaggedItemEvents(container) {
    container.querySelectorAll('[data-appeal-decision]').forEach(btn => {
        btn.addEventListener('click', () =>
            reviewAppeal(btn.dataset.messageId, btn.dataset.appealDecision)
        );
    });
    container.querySelectorAll('[data-open-appeal]').forEach(btn => {
        btn.addEventListener('click', () => {
            openAppealModal({
                message_id: btn.dataset.messageId,
                message: btn.dataset.messageText,
                reason: btn.dataset.reason,
            });
        });
    });
}

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
    const messageInput = document.getElementById('message-input');
    const messageInputHint = document.getElementById('message-input-hint');
    autoResizeComposer();
    document.getElementById('btn-send').addEventListener('click', sendMessage);
    messageInput.addEventListener('input', () => {
        autoResizeComposer();
        if (!messageInput.value.trim()) {
            messageInputHint?.classList.add('hidden');
        }
    });
    messageInput.addEventListener('focus', () => messageInputHint?.classList.remove('hidden'));
    messageInput.addEventListener('blur', () => messageInputHint?.classList.add('hidden'));
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Image attach button â†’ trigger file picker
    document.getElementById('btn-attach-image').addEventListener('click', () => {
        primeAttachButton('btn-attach-image', 'image-file-input');
        document.getElementById('image-file-input').click();
    });

    // File chosen â†’ send image
    document.getElementById('image-file-input').addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (file) {
            await sendImage(file);
            e.target.value = '';
        }
    });

    // Audio button â†’ start mic recording
    document.getElementById('btn-attach-audio').addEventListener('click', () => {
        if (AudioRecorder.isRecording) return;
        AudioRecorder.start();
    });

    // Right-click on mic button â†’ file picker fallback
    document.getElementById('btn-attach-audio').addEventListener('contextmenu', (e) => {
        e.preventDefault();
        primeAttachButton('btn-attach-audio', 'audio-file-input');
        document.getElementById('audio-file-input').click();
    });

    // Stop recording â†’ send the captured audio
    document.getElementById('btn-stop-recording').addEventListener('click', async () => {
        const blob = await AudioRecorder.stop();
        if (blob && blob.size > 0) {
            const extension = blob.type.includes('webm') ? 'webm' : blob.type.includes('ogg') ? 'ogg' : 'wav';
            const file = new File([blob], `recording.${extension}`, { type: blob.type });
            await sendAudio(file);
        } else {
            showToast('No audio recorded.', 'error');
        }
    });

    // Cancel recording
    document.getElementById('btn-cancel-recording').addEventListener('click', () => {
        AudioRecorder.cancel();
        showToast('Recording cancelled.', '');
    });

    // File chosen â†’ send audio
    document.getElementById('audio-file-input').addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (file) {
            await sendAudio(file);
            e.target.value = '';
        }
    });

    document.getElementById('btn-admin-panel').addEventListener('click', openAdminPanel);
    document.getElementById('btn-moderation-page-nav').addEventListener('click', () => {
        if (!State.activeGroup) return;
        navigateTo('moderation');
    });
    document.getElementById('btn-copy-group-id').addEventListener('click', async () => {
        const groupId = document.getElementById('admin-group-id').textContent.trim();
        if (!groupId) return;
        try {
            await navigator.clipboard.writeText(groupId);
            showToast('Group ID copied!', 'success');
        } catch (err) {
            showToast('Could not copy Group ID.', 'error');
        }
    });
    document.getElementById('btn-save-group-name').addEventListener('click', async () => {
        if (!State.activeGroup || !State.user) return;
        const newName = document.getElementById('admin-group-name-input').value.trim();
        if (!newName) { showToast('Group name cannot be empty.', 'error'); return; }

        try {
            const data = await API.updateGroupName(State.activeGroup.group_id, newName, State.user.username);
            if (data.success) {
                State.activeGroup.group_name = newName;
                document.getElementById('chat-header-name').textContent = newName;
                const headerAvatar = document.getElementById('chat-header-avatar');
                if (headerAvatar) {
                    headerAvatar.textContent = getInitials(newName);
                    headerAvatar.style.backgroundColor = getAvatarColor(newName);
                }
                showToast('Group renamed!', 'success');
                await loadGroups();
            } else {
                showToast(data.message || 'Failed.', 'error');
            }
        } catch (err) {
            showToast('Connection error.', 'error');
        }
    });
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

    document.getElementById('btn-suggest-create-rules').addEventListener('click', () => {
        setRuleSuggestionVisibility('create', true);
        requestRuleSuggestions('create');
    });
    document.getElementById('btn-suggest-admin-rules').addEventListener('click', () => {
        setRuleSuggestionVisibility('admin', true);
        requestRuleSuggestions('admin');
    });
    document.getElementById('btn-upload-create-rules').addEventListener('click', () => {
        document.getElementById('create-rules-file').click();
    });
    document.getElementById('create-rules-file').addEventListener('change', (e) => {
        if (e.target.files[0]) extractRulesFromFile(e.target.files[0], 'create-rules', 'create-rules-file-name');
        e.target.value = '';
    });
    document.getElementById('btn-upload-admin-rules').addEventListener('click', () => {
        document.getElementById('admin-rules-file').click();
    });
    document.getElementById('admin-rules-file').addEventListener('change', (e) => {
        if (e.target.files[0]) extractRulesFromFile(e.target.files[0], 'admin-rules', null);
        e.target.value = '';
    });
    document.querySelectorAll('.avatar-option').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.avatar-option').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            if (State.user) State.user.avatar = btn.dataset.avatar || '';
        });
    });

    const createRulesDebounced = debounce(() => requestRuleSuggestions('create'), 900);
    const adminRulesDebounced = debounce(() => requestRuleSuggestions('admin'), 900);
    document.getElementById('create-rules').addEventListener('input', (e) => {
        if (!e.target.value.trim()) {
            setRuleSuggestionVisibility('create', false);
            document.getElementById('create-rule-suggestions').innerHTML = '<p class="text-muted">AI suggestions will appear here.</p>';
            return;
        }
        if (!document.getElementById('create-rule-suggestions').classList.contains('hidden')) {
            createRulesDebounced();
        }
    });
    document.getElementById('admin-rules').addEventListener('input', (e) => {
        if (!e.target.value.trim()) {
            setRuleSuggestionVisibility('admin', false);
            document.getElementById('admin-rule-preview').value = '';
            document.getElementById('admin-rule-suggestions').innerHTML = '<p class="text-muted">AI suggestions will appear here.</p>';
            return;
        }
        if (!document.getElementById('admin-rule-suggestions').classList.contains('hidden')) {
            adminRulesDebounced();
        }
    });

    document.getElementById('search-groups').addEventListener('input', (e) => {
        renderGroupList(e.target.value);
    });

    document.getElementById('btn-mod-back').addEventListener('click', () => {
        navigateTo('chat');
        if (State.activeGroupId) startPolling();
    });

    document.getElementById('btn-mod-refresh').addEventListener('click', () => {
        loadModerationPage();
    });

    document.getElementById('btn-open-mod-page').addEventListener('click', () => {
        closeModal('modal-admin');
        navigateTo('moderation');
    });

    document.getElementById('btn-save-sensitivity').addEventListener('click', async () => {
        if (!State.activeGroup || !State.user) return;
        const sensitivity = document.getElementById('admin-sensitivity').value;
        const currentRules = State.activeGroup.rules || '';
        try {
            const data = await API.updateRules(
                State.activeGroup.group_id,
                currentRules,
                State.user.username,
                sensitivity
            );
            if (data.success) {
                State.activeGroup.moderation_sensitivity = sensitivity;
                showToast('Sensitivity saved.', 'success');
            } else {
                showToast(data.message || 'Failed to save.', 'error');
            }
        } catch (err) {
            showToast('Connection error.', 'error');
        }
    });

    document.getElementById('btn-leave-group').addEventListener('click', async () => {
        if (!State.activeGroup || !State.user) return;
        if (!confirm('Are you sure you want to leave this group? You will need to rejoin with the group password.')) return;

        try {
            const data = await API.leaveGroup(State.activeGroup.group_id, State.user.username);
            if (data.success) {
                closeModal('modal-admin');
                stopPolling();
                State.activeGroupId = null;
                State.activeGroup = null;
                State.messages = [];
                document.getElementById('chat-active').classList.add('hidden');
                document.getElementById('chat-empty').classList.remove('hidden');
                showToast('Left the group.', 'success');
                await loadGroups();
            } else {
                showToast(data.message || 'Could not leave group.', 'error');
            }
        } catch (err) {
            showToast('Connection error.', 'error');
        }
    });

    document.getElementById('btn-delete-group').addEventListener('click', async () => {
        if (!State.activeGroup || !State.user) return;
        if (!confirm(`Are you sure you want to permanently delete "${State.activeGroup.group_name}"? All messages will be lost. This cannot be undone.`)) return;

        try {
            const data = await API.deleteGroup(State.activeGroup.group_id, State.user.username);
            if (data.success) {
                closeModal('modal-admin');
                stopPolling();
                State.activeGroupId = null;
                State.activeGroup = null;
                State.messages = [];
                document.getElementById('chat-active').classList.add('hidden');
                document.getElementById('chat-empty').classList.remove('hidden');
                showToast('Group deleted.', 'success');
                await loadGroups();
            } else {
                showToast(data.message || 'Could not delete group.', 'error');
            }
        } catch (err) {
            showToast('Connection error.', 'error');
        }
    });

    document.getElementById('btn-save-profile').addEventListener('click', async () => {
        if (!State.user) return;
        const fullName = document.getElementById('edit-fullname').value.trim();
        const bio = document.getElementById('edit-bio').value.trim();
        const avatar = State.user.avatar || '';
        if (!fullName) { showToast('Name cannot be empty.', 'error'); return; }

        try {
            const data = await API.updateProfile(State.user.username, fullName, bio, avatar);
            if (data.success) {
                State.user.full_name = fullName;
                State.user.bio = bio;
                State.user.avatar = avatar;
                sessionStorage.setItem('ce_session', JSON.stringify(State.user));
                document.getElementById('settings-fullname').textContent = fullName;
                const settingsAvatar = document.getElementById('settings-avatar');
                applyAvatarToElement(settingsAvatar, State.user);
                const defaultBtn = document.getElementById('avatar-option-default');
                if (defaultBtn) defaultBtn.textContent = getInitials(fullName);
                updateSidebar();
                showToast('Profile saved!', 'success');
            } else {
                showToast(data.message || 'Failed.', 'error');
            }
        } catch (err) {
            showToast('Connection error.', 'error');
        }
    });
}

// =========================================================================
// INIT
// =========================================================================
document.addEventListener('DOMContentLoaded', () => {
    initAuth();
    initModals();
    initEventBindings();
    ThemeManager.bindControls();

    // Restore session if available
    const savedSession = sessionStorage.getItem('ce_session');
    if (savedSession) {
        try {
            const userData = JSON.parse(savedSession);
            if (userData && userData.username) {
                State.user = userData;
                onLoginSuccess();
                return;
            }
        } catch (e) {
            sessionStorage.removeItem('ce_session');
        }
    }
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

