/**
 * ConvoEase — Frontend Application
 * SPA routing, API client, state management, and DOM rendering.
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
    pollTimer: null,
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

    createGroup: (group_name, password, admin_username, rules) =>
        API.request('POST', '/api/groups', { group_name, password, admin_username, rules }),

    joinGroup: (group_id, password, username) =>
        API.request('POST', '/api/groups/join', { group_id, password, username }),

    getGroupDetails: (group_id) =>
        API.request('GET', `/api/groups/${group_id}`),

    getGroupMembers: (group_id) =>
        API.request('GET', `/api/groups/${group_id}/members`),

    updateRules: (group_id, rules, username) =>
        API.request('PUT', `/api/groups/${group_id}/rules`, { rules, username }),

    // Messages
    getMessages: (group_id) =>
        API.request('GET', `/api/groups/${group_id}/messages`),

    sendMessage: (group_id, username, message) =>
        API.request('POST', `/api/groups/${group_id}/messages`, { username, message }),

    getFlagged: (group_id) =>
        API.request('GET', `/api/groups/${group_id}/messages/flagged`),

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

// ═══════════════════════════════════════════════════════════════════════════════
// PAGE NAVIGATION
// ═══════════════════════════════════════════════════════════════════════════════
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
    stopPolling();
    navigateTo('auth');
    // Reset forms
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

    // Click handlers
    container.querySelectorAll('.group-item').forEach(el => {
        el.addEventListener('click', () => selectGroup(el.dataset.gid));
    });
}

// ═══════════════════════════════════════════════════════════════════════════════
// CHAT
// ═══════════════════════════════════════════════════════════════════════════════
async function selectGroup(groupId) {
    State.activeGroupId = groupId;
    renderGroupList(); // Update active state in sidebar

    // Load group details
    try {
        const detailData = await API.getGroupDetails(groupId);
        if (detailData.success) {
            State.activeGroup = detailData.group;
        }
    } catch (err) {
        console.error('Failed to load group details:', err);
    }

    // Show chat view
    document.getElementById('chat-empty').classList.add('hidden');
    document.getElementById('chat-active').classList.remove('hidden');

    // Update header
    const group = State.activeGroup || { group_name: 'Unknown', admin_username: '', group_id: groupId };
    document.getElementById('chat-header-name').textContent = group.group_name;
    document.getElementById('chat-header-meta').textContent = `ID: ${group.group_id} • Admin: ${group.admin_username}`;
    const headerAvatar = document.getElementById('chat-header-avatar');
    headerAvatar.textContent = getInitials(group.group_name);
    headerAvatar.style.backgroundColor = getAvatarColor(group.group_name);

    // Show/hide admin button
    const adminBtn = document.getElementById('btn-admin-panel');
    if (State.user && group.admin_username === State.user.username) {
        adminBtn.classList.remove('hidden');
    } else {
        adminBtn.classList.add('hidden');
    }

    // Load messages
    await loadMessages();
    startPolling();
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
                if (data.messages.length > oldCount) {
                    scrollToBottom();
                }
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
        const senderHtml = isMe ? '' : `<div class="msg-sender">${escapeHtml(m.username)}</div>`;
        return `
            <div class="message-row ${isMe ? 'me' : 'other'}">
                ${senderHtml}
                <div class="msg-bubble">
                    ${escapeHtml(m.message)}
                    <div class="msg-time">${formatTime(m.timestamp)}</div>
                </div>
            </div>`;
    }).join('');

    scrollToBottom();
}

function scrollToBottom() {
    const container = document.getElementById('chat-messages');
    requestAnimationFrame(() => {
        container.scrollTop = container.scrollHeight;
    });
}

async function sendMessage() {
    const input = document.getElementById('message-input');
    const text = input.value.trim();
    if (!text || !State.activeGroupId || !State.user) return;

    input.value = '';
    input.focus();

    // Show typing indicator
    showTypingIndicator();

    try {
        const data = await API.sendMessage(State.activeGroupId, State.user.username, text);
        removeTypingIndicator();

        if (data.success && data.status === 'PASS') {
            await loadMessages();
        } else if (data.status === 'FLAGGED') {
            showFlagBanner(data.reason || 'Message was flagged by AI moderation.');
            // Still reload to update
            await loadMessages();
        } else {
            showToast(data.message || 'Failed to send.', 'error');
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

function showFlagBanner(reason) {
    // Remove existing
    document.querySelectorAll('.flag-banner').forEach(el => el.remove());

    const banner = document.createElement('div');
    banner.className = 'flag-banner';
    banner.innerHTML = `
        <div class="flag-banner-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                <line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line>
            </svg>
        </div>
        <div class="flag-banner-text"><strong>Blocked:</strong> ${escapeHtml(reason)}</div>`;

    const messagesArea = document.getElementById('chat-messages');
    messagesArea.parentNode.insertBefore(banner, messagesArea.nextSibling.nextSibling);

    // Auto-remove after 5s
    setTimeout(() => banner.remove(), 5000);
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

    // Profile
    const avatar = document.getElementById('settings-avatar');
    avatar.textContent = getInitials(State.user.full_name);
    avatar.style.backgroundColor = State.user.profile_pic_color || getAvatarColor(State.user.full_name);
    document.getElementById('settings-fullname').textContent = State.user.full_name;
    document.getElementById('settings-username').textContent = `@${State.user.username}`;

    // Engine settings
    try {
        const data = await API.getSettings();
        if (data.success) {
            const s = data.settings;
            document.getElementById('setting-mode').textContent = s.mode.toUpperCase();
            document.getElementById('setting-model').textContent = s.model || 'N/A';
            document.getElementById('setting-url').textContent = s.base_url || 'N/A';
            document.getElementById('setting-plugins').textContent = s.plugins.join(', ') || 'None';
        }
    } catch (err) {
        console.error('Failed to load settings:', err);
    }
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

    // Modal tabs (Create/Join)
    document.querySelectorAll('.modal-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const target = tab.dataset.modalTab;
            const parent = tab.closest('.modal');
            parent.querySelectorAll('.modal-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            parent.querySelectorAll('.modal-form').forEach(f => f.classList.remove('active'));
            document.getElementById(`form-${target}-group`).classList.add('active');
        });
    });

    // Create group
    document.getElementById('form-create-group').addEventListener('submit', async (e) => {
        e.preventDefault();
        clearErrors('create-group-error');
        const name = document.getElementById('create-name').value.trim();
        const password = document.getElementById('create-password').value.trim();
        const rules = document.getElementById('create-rules').value.trim();

        if (!name) { setError('create-group-error', 'Group name is required.'); return; }

        try {
            const data = await API.createGroup(name, password, State.user.username, rules);
            if (data.success) {
                closeModal('modal-group');
                document.getElementById('form-create-group').reset();
                document.getElementById('create-rules').value = 'Be respectful.';
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

    // Join group
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

    document.getElementById('admin-group-id').textContent = State.activeGroup.group_id;

    // Load members
    try {
        const membersData = await API.getGroupMembers(State.activeGroup.group_id);
        if (membersData.success) {
            document.getElementById('admin-members').textContent = membersData.members.join(', ');
        }
    } catch (err) {
        document.getElementById('admin-members').textContent = 'Error loading';
    }

    // Rules
    document.getElementById('admin-rules').value = State.activeGroup.rules || '';

    // Flagged messages
    try {
        const flaggedData = await API.getFlagged(State.activeGroup.group_id);
        const container = document.getElementById('flagged-list');
        if (flaggedData.success && flaggedData.flagged.length > 0) {
            container.innerHTML = flaggedData.flagged.map(f => `
                <div class="flagged-item">
                    <div class="flagged-item-header">
                        <span>${escapeHtml(f.username)}</span>
                        <span>${formatTime(f.timestamp)}</span>
                    </div>
                    <div class="flagged-item-message">${escapeHtml(f.message)}</div>
                    <div class="flagged-item-reason">${escapeHtml(f.reason)}</div>
                </div>`).join('');
        } else {
            container.innerHTML = '<p class="text-muted" style="padding:12px 0; font-size:13px;">Great! No flagged messages.</p>';
        }
    } catch (err) {
        console.error('Failed to load flagged:', err);
    }

    openModal('modal-admin');
}

// ═══════════════════════════════════════════════════════════════════════════════
// EVENT BINDINGS
// ═══════════════════════════════════════════════════════════════════════════════
function initEventBindings() {
    // New chat button
    document.getElementById('btn-new-chat').addEventListener('click', () => {
        openModal('modal-group');
    });

    // Settings nav
    document.getElementById('btn-settings-nav').addEventListener('click', () => {
        stopPolling();
        navigateTo('settings');
    });

    // Settings back
    document.getElementById('btn-settings-back').addEventListener('click', () => {
        navigateTo('chat');
        if (State.activeGroupId) startPolling();
    });

    // Logout
    document.getElementById('btn-logout').addEventListener('click', logout);

    // Send message
    document.getElementById('btn-send').addEventListener('click', sendMessage);
    document.getElementById('message-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Admin panel
    document.getElementById('btn-admin-panel').addEventListener('click', openAdminPanel);

    // Save rules
    document.getElementById('btn-save-rules').addEventListener('click', async () => {
        if (!State.activeGroup) return;
        const newRules = document.getElementById('admin-rules').value.trim();
        try {
            const data = await API.updateRules(State.activeGroup.group_id, newRules, State.user.username);
            if (data.success) {
                State.activeGroup.rules = newRules;
                showToast('Rules updated!', 'success');
            } else {
                showToast(data.message || 'Failed.', 'error');
            }
        } catch (err) {
            showToast('Connection error.', 'error');
        }
    });

    // Search groups
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
    navigateTo('auth');
});
