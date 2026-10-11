// Chat view: message list, held-message cards, composer, media and polling.
import {
  h, icon, iconButton, button, avatar, clear, formatClock, formatDay, dayKey, parseTime,
  formatDuration, copyText, plural, autoGrow, storageGet, storageSet,
} from './dom.js';
import { api } from './api.js';
import { store, refreshGroups, navigate, findGroup } from './store.js';
import { snackbar, confirmDialog, openMenu, openImageViewer } from './ui.js';
import { prepareImage, prepareAudioFile, blobToBase64, VoiceRecorder, canRecord, toWav, MAX_RECORDING_SECONDS } from './media.js';
import { openAppealDialog, openCatchUp } from './groupdialogs.js';
import { openGroupInfo } from './groupinfo.js';

const PAGE = 100;
const POLL_MS = 3000;
const FULL_REFRESH_MS = 20000;
const RUN_GAP_MS = 5 * 60 * 1000;
const drafts = new Map();
let activeAudio = null;

export function mountChat(container, groupId) {
  const me = store.user.username;
  const caps = store.settings?.capabilities || { text: true, image: true, audio: true };
  const audioFormats = store.settings?.audio_formats?.length ? store.settings.audio_formats : ['wav', 'mp3', 'webm', 'ogg', 'm4a'];
  const state = {
    group: findGroup(groupId),
    profiles: new Map(),
    risk: {},
    messages: new Map(),
    nodes: new Map(),
    pending: [],
    oldestSeq: 0,
    newestSeq: 0,
    hasMore: false,
    loaded: false,
    dismissed: new Set(storageGet(`ce.dismissed.${groupId}`, [])),
    missing: new Set(),
    destroyed: false,
  };
  let pollTimer = null;
  let fullTimer = null;
  let polling = false;
  let recorder = null;
  let recordTick = null;

  // ── Layout ────────────────────────────────────────────────────────────
  const titleName = h('b', {}, state.group?.group_name || 'Loading…');
  const titleSub = h('span', {}, '');
  const headerAvatar = h('span');
  const shieldBtn = iconButton('shield_person', 'Moderation dashboard', () => navigate(`moderation/${encodeURIComponent(groupId)}`));
  shieldBtn.hidden = true;
  const header = h('header.top-bar', {},
    iconButton('arrow_back', 'Back to chats', () => navigate('chats'), 'only-compact'),
    h('button.title-btn.state', { type: 'button', onclick: () => showInfo(), 'aria-label': 'Group details' },
      headerAvatar, h('div.title', {}, titleName, titleSub)),
    h('div.actions', {},
      h('button.btn.tonal.has-icon.state.hide-compact', { type: 'button', onclick: () => openCatchUp(groupId, state.group?.group_name) },
        icon('auto_awesome'), 'Catch up'),
      iconButton('auto_awesome', 'Catch up', () => openCatchUp(groupId, state.group?.group_name), 'only-compact'),
      shieldBtn,
      iconButton('info', 'Group details', () => showInfo())));

  const inner = h('div.messages-inner', { role: 'log', 'aria-live': 'polite', 'aria-relevant': 'additions' });
  const loadEarlierBtn = button('Load earlier messages', { variant: 'text', iconName: 'history', onClick: loadEarlier, extra: 'load-earlier' });
  loadEarlierBtn.hidden = true;
  const scroller = h('div.messages', {}, h('div.messages-inner', { style: { marginTop: '0' } }, loadEarlierBtn), inner);
  const jumpBtn = h('button.fab.lowered.jump-latest.state', { type: 'button', 'aria-label': 'Jump to latest', hidden: true, onclick: () => scrollToBottom(true) }, icon('arrow_downward'));

  const textarea = h('textarea', { rows: 1, placeholder: 'Message', 'aria-label': 'Message', maxlength: store.settings?.limits?.message_chars || 4000 });
  const imageInput = h('input', { type: 'file', accept: 'image/*', hidden: true });
  const audioInput = h('input', { type: 'file', accept: 'audio/*', hidden: true });
  const addBtn = iconButton('add_circle', 'Attach', (event) => openAttachMenu(event.currentTarget));
  addBtn.hidden = !caps.image && !caps.audio;
  const micBtn = iconButton('mic', 'Record a voice note', () => startRecording());
  micBtn.hidden = !caps.audio || !canRecord();
  const sendBtn = h('button.send.state', { type: 'button', 'aria-label': 'Send', title: 'Send', disabled: true, onclick: () => sendText() }, icon('send', 'fill'));
  const fieldShell = h('div.field-shell', {}, addBtn, textarea, micBtn);
  const composer = h('div.composer', {}, fieldShell, sendBtn, imageInput, audioInput);
  const note = h('div.composer-note', {}, icon('verified_user'), 'Messages are checked against the group rules before others see them.');

  const chat = h('div.chat', {}, header, scroller, jumpBtn, composer, note);
  container.append(chat);
  renderHeader();

  // ── Header & info ────────────────────────────────────────────────────
  function renderHeader() {
    const group = state.group;
    if (!group) return;
    titleName.textContent = group.group_name;
    const count = group.member_count ?? state.profiles.size;
    titleSub.textContent = [count ? plural(count, 'member') : null, `${group.moderation_sensitivity || 'Moderate'} moderation`].filter(Boolean).join(' · ');
    clear(headerAvatar).append(avatar(group));
    shieldBtn.hidden = !group.is_admin;
    textarea.placeholder = window.matchMedia('(max-width: 840px)').matches ? 'Message' : `Message ${group.group_name}`;
  }

  function showInfo() {
    if (!state.group) return;
    openGroupInfo(groupId, {
      onChanged: async () => {
        await loadGroup();
        refreshGroups();
      },
    });
  }

  async function loadGroup() {
    const [groupRes, membersRes] = await Promise.all([api.group(groupId), api.members(groupId)]);
    if (state.destroyed) return false;
    if (!groupRes.success) {
      clear(container).append(h('div.empty', { style: { flex: '1' } },
        h('div.art', {}, icon('lock')),
        h('h2.title-large', {}, groupRes.httpStatus === 404 ? 'Group not found' : "You're not in this group"),
        h('p.body-medium', {}, 'It may have been deleted, or you left it.'),
        h('div.actions', {}, button('Back to chats', { variant: 'tonal', onClick: () => navigate('chats') }))));
      state.destroyed = true;
      refreshGroups();
      return false;
    }
    state.group = groupRes.group;
    if (membersRes.success) {
      state.profiles = new Map(membersRes.profiles.map((profile) => [profile.username, profile]));
    }
    renderHeader();
    if (state.group.is_admin) {
      api.report(groupId).then((res) => {
        if (!res.success || state.destroyed) return;
        state.risk = Object.fromEntries(res.report.member_activity.map((row) => [row.username, row.risk_level]));
        render({ refreshSenders: true });
      });
    }
    return true;
  }

  // ── Data ──────────────────────────────────────────────────────────────
  function ingest(rows) {
    let unknownSender = false;
    for (const row of rows) {
      state.messages.set(row.seq, row);
      state.newestSeq = Math.max(state.newestSeq, row.seq);
      state.oldestSeq = state.oldestSeq ? Math.min(state.oldestSeq, row.seq) : row.seq;
      if (row.username !== me && !state.profiles.has(row.username) && !state.missing.has(row.username)) {
        state.missing.add(row.username);
        unknownSender = true;
      }
    }
    if (unknownSender) reloadMembers();
  }

  // Someone new joined (or changed their name) since the chat opened.
  async function reloadMembers() {
    const res = await api.members(groupId);
    if (state.destroyed || !res.success) return;
    state.profiles = new Map(res.profiles.map((profile) => [profile.username, profile]));
    if (state.group) state.group.member_count = res.members.length;
    renderHeader();
    render();
  }

  async function initialLoad() {
    const ok = await loadGroup();
    if (!ok) return;
    const res = await api.messages(groupId, { limit: PAGE });
    if (state.destroyed) return;
    if (res.success) {
      ingest(res.messages);
      state.hasMore = res.messages.length >= PAGE;
    }
    state.loaded = true;
    render();
    scrollToBottom(true);
    refreshGroups();
    pollTimer = setInterval(() => { if (!document.hidden && !polling) poll(); }, POLL_MS);
    fullTimer = setInterval(() => { if (!document.hidden) fullRefresh(); }, FULL_REFRESH_MS);
  }

  // Polls run one after another, so a caller can await a fetch that is
  // guaranteed to start after its own request finished.
  let pollChain = Promise.resolve();
  function poll() {
    pollChain = pollChain.then(fetchNew, fetchNew);
    return pollChain;
  }

  async function fetchNew() {
    if (state.destroyed || !state.loaded) return;
    polling = true;
    try {
      const res = await api.messages(groupId, { after: state.newestSeq, limit: 200 });
      if (state.destroyed || !res.success || !res.messages.length) return;
      const nearBottom = isNearBottom();
      ingest(res.messages);
      render();
      if (nearBottom || res.messages.some((m) => m.username === me)) scrollToBottom();
      else jumpBtn.hidden = false;
    } finally {
      polling = false;
    }
  }

  async function fullRefresh() {
    if (state.destroyed || !state.loaded) return;
    const count = Math.min(500, Math.max(PAGE, state.messages.size));
    const res = await api.messages(groupId, { limit: count });
    if (state.destroyed || !res.success) return;
    const fresh = new Map(res.messages.map((m) => [m.seq, m]));
    const oldestFresh = res.messages[0]?.seq ?? Infinity;
    // Within the refreshed window, drop anything that is no longer visible.
    for (const seq of [...state.messages.keys()]) {
      if (seq >= oldestFresh && !fresh.has(seq)) state.messages.delete(seq);
    }
    const nearBottom = isNearBottom();
    ingest(res.messages);
    render();
    if (nearBottom) scrollToBottom();
  }

  async function loadEarlier() {
    loadEarlierBtn.disabled = true;
    const res = await api.messages(groupId, { before: state.oldestSeq, limit: PAGE });
    loadEarlierBtn.disabled = false;
    if (!res.success) return snackbar(res.message || 'Could not load earlier messages.');
    const before = scroller.scrollHeight;
    ingest(res.messages);
    state.hasMore = res.messages.length >= PAGE;
    render();
    scroller.scrollTop += scroller.scrollHeight - before;
  }

  // ── Rendering ─────────────────────────────────────────────────────────
  function signature(m) {
    const sender = state.profiles.get(m.username);
    return [m.status, m.message, m.summary, m.media_url, m.appeal_status, m.appeal_admin_note, m.reason,
      sender?.full_name, sender?.avatar, state.risk[m.username]].join('\u0001');
  }

  function render({ refreshSenders = false } = {}) {
    if (refreshSenders) state.nodes.clear();
    loadEarlierBtn.hidden = !state.hasMore;
    const ordered = [...state.messages.values()].sort((a, b) => a.seq - b.seq);
    const desired = [];
    let lastDay = '';
    let prev = null;
    const keep = new Set();

    const visibleRows = [];
    for (const m of ordered) {
      if (m.status === 'FLAGGED') {
        if (m.username !== me || state.dismissed.has(m.message_id)) continue;
      }
      visibleRows.push(m);
    }

    visibleRows.forEach((m, index) => {
      const day = dayKey(m.timestamp);
      if (day !== lastDay) {
        const key = `day:${day}`;
        desired.push(cached(key, day, () => h('div.day-divider', { role: 'separator' }, formatDay(m.timestamp))));
        keep.add(key);
        lastDay = day;
        prev = null;
      }
      const key = `m:${m.message_id}`;
      keep.add(key);
      if (m.status === 'FLAGGED') {
        desired.push(cached(key, signature(m), () => heldCard(m)));
        prev = null;
        return;
      }
      const node = cached(key, signature(m), () => messageRow(m));
      const next = visibleRows[index + 1];
      const cont = Boolean(prev && sameRun(prev, m));
      const nextSame = Boolean(next && next.status !== 'FLAGGED' && sameRun(m, next));
      node.classList.toggle('cont', cont);
      node.classList.toggle('next-same', nextSame);
      node.classList.toggle('last-of-run', !nextSame);
      desired.push(node);
      prev = m;
    });

    for (const item of state.pending) {
      keep.add(`p:${item.id}`);
      desired.push(item.node);
    }

    if (state.loaded && !visibleRows.length && !state.pending.length) {
      desired.push(cached('empty', '1', () => h('div.empty', {},
        h('div.art', {}, icon('waving_hand')),
        h('h2.title-medium', {}, 'Say hello'),
        h('p.body-medium', {}, 'No messages yet. Everything you send is checked against the group rules first.'))));
      keep.add('empty');
    }

    for (const [key, entry] of state.nodes) {
      if (!keep.has(key)) {
        entry.el.remove();
        state.nodes.delete(key);
      }
    }
    // Reorder with as few DOM moves as possible.
    let cursor = inner.firstChild;
    for (const node of desired) {
      if (node === cursor) {
        cursor = cursor.nextSibling;
      } else {
        inner.insertBefore(node, cursor);
      }
    }
    while (cursor) {
      const next = cursor.nextSibling;
      cursor.remove();
      cursor = next;
    }
  }

  function cached(key, sig, build) {
    const entry = state.nodes.get(key);
    if (entry && entry.sig === sig) return entry.el;
    const el = build();
    if (entry) entry.el.replaceWith(el);
    state.nodes.set(key, { el, sig });
    return el;
  }

  function sameRun(a, b) {
    if (a.username !== b.username) return false;
    const ta = parseTime(a.timestamp);
    const tb = parseTime(b.timestamp);
    return ta && tb && tb - ta < RUN_GAP_MS && dayKey(a.timestamp) === dayKey(b.timestamp);
  }

  function senderName(username) {
    if (username === me) return 'You';
    return state.profiles.get(username)?.full_name || username;
  }

  function messageRow(m) {
    const mine = m.username === me;
    const deleted = m.status === 'DELETED';
    const type = m.message?.startsWith('[IMAGE]') ? 'image' : m.message?.startsWith('[AUDIO]') ? 'audio' : 'text';
    let content;
    if (deleted) {
      content = h('div.bubble', {}, mine ? 'You deleted this message' : 'This message was deleted');
    } else if (type === 'image') {
      content = h('div.media-card', {},
        h('img.thumb', { src: m.media_url, alt: m.summary || 'Shared image', loading: 'lazy',
          onclick: () => openImageViewer(m.media_url, m.summary), onload: () => { if (isNearBottom(240)) scrollToBottom(); } }),
        m.summary ? h('div.ai-note', {}, icon('auto_awesome'), h('span', {}, m.summary)) : null);
    } else if (type === 'audio') {
      content = h('div.media-card', {}, audioPlayer(m.media_url, m.message_id),
        m.summary ? h('div.ai-note', {}, icon('auto_awesome'), h('span', {}, m.summary)) : h('div', { style: { height: '8px' } }));
    } else {
      content = h('div.bubble', {}, m.message);
    }

    const actions = [];
    if (!deleted && type === 'text') {
      actions.push(iconButton('content_copy', 'Copy text', async () => { await copyText(m.message); snackbar('Copied'); }, 'sm'));
    }
    if (mine && !deleted) {
      actions.push(iconButton('delete', 'Delete message', () => deleteMessage(m), 'sm'));
    }
    const risk = state.group?.is_admin ? state.risk[m.username] : null;
    const profile = mine ? store.user : state.profiles.get(m.username) || { username: m.username, full_name: m.username };
    return h(`div.msg${mine ? '.mine' : ''}${deleted ? '.deleted' : ''}`, { dataset: { seq: String(m.seq) } },
      mine ? null : avatar(profile, 'sm'),
      h('div.stack', {},
        mine ? null : h('div.sender', {}, senderName(m.username),
          risk === 'high' ? h('span.tag.error', {}, 'High risk') : risk === 'moderate' ? h('span.tag', {}, 'Watch') : null),
        h('div.row', {}, content, actions.length ? h('div.msg-actions', {}, actions) : null),
        h('time.time', { datetime: m.timestamp }, formatClock(m.timestamp))));
  }

  function heldCard(m) {
    const type = m.message?.startsWith('[IMAGE]') ? 'image' : m.message?.startsWith('[AUDIO]') ? 'audio' : 'text';
    const status = String(m.appeal_status || '').toUpperCase();
    const original = type === 'text'
      ? h('div.original', {}, m.message)
      : h('div.original.media', {}, `${type === 'image' ? 'Image' : 'Voice note'}${m.summary ? `: ${m.summary}` : ''}`);
    const tags = [];
    if (status === 'PENDING_ADMIN') tags.push(h('span.tag', {}, icon('hourglass_top'), 'Appeal sent — waiting for the admin'));
    if (status === 'REJECTED') {
      tags.push(h('span.tag', {}, icon('gavel'), 'Appeal declined'));
      if (m.appeal_admin_note) tags.push(h('span.body-small', {}, `Admin: ${m.appeal_admin_note}`));
    }
    const acts = [button('Dismiss', { onClick: () => dismissHeld(m) })];
    if (type === 'text') acts.push(button('Edit', { onClick: () => { textarea.value = m.message; autoGrow(textarea); updateSend(); textarea.focus(); } }));
    if (!status) acts.push(button('Appeal', { onClick: () => openAppealDialog(groupId, m, () => fullRefresh()) }));
    return h('div.held-card', { role: 'note' },
      h('div.head', {}, icon('block'), h('div', {}, h('b', {}, 'Not sent — held by moderation'), h('span', {}, m.reason || 'It breaks a group rule.'))),
      original,
      tags.length ? h('div.status', {}, tags) : null,
      h('div.acts', {}, acts),
      h('time.time.body-small', { datetime: m.timestamp, style: { display: 'block', textAlign: 'right', opacity: '.7', marginTop: '2px' } }, formatClock(m.timestamp)));
  }

  function dismissHeld(m) {
    state.dismissed.add(m.message_id);
    storageSet(`ce.dismissed.${groupId}`, [...state.dismissed].slice(-200));
    render();
  }

  async function deleteMessage(m) {
    const ok = await confirmDialog({ title: 'Delete message?', message: 'It will show as deleted for everyone in the group.', confirmLabel: 'Delete', danger: true });
    if (!ok) return;
    const res = await api.deleteMessage(groupId, m.message_id);
    if (!res.success) return snackbar(res.message || 'Could not delete the message.');
    await fullRefresh();
  }

  // ── Audio player ──────────────────────────────────────────────────────
  function audioPlayer(src, seed) {
    const audio = new Audio();
    audio.preload = 'metadata';
    audio.src = src;
    const bars = [];
    let hash = 0;
    for (const ch of String(seed)) hash = (hash * 33 + ch.charCodeAt(0)) >>> 0;
    for (let i = 0; i < 36; i++) {
      hash = (hash * 1103515245 + 12345) >>> 0;
      const height = 6 + (hash % 22) * Math.sin((i / 36) * Math.PI) + 4;
      bars.push(h('i', { style: { height: `${Math.round(height)}px` } }));
    }
    const playIcon = icon('play_arrow', 'fill');
    const dur = h('span.dur', {}, '0:00');
    const playBtn = h('button.play.state', { type: 'button', 'aria-label': 'Play voice note' }, playIcon);
    const track = h('div.track', { role: 'slider', 'aria-label': 'Seek', tabindex: '0', 'aria-valuemin': '0', 'aria-valuemax': '100', 'aria-valuenow': '0' }, h('div.bars', {}, bars));
    playBtn.addEventListener('click', () => {
      if (audio.paused) {
        if (activeAudio && activeAudio !== audio) activeAudio.pause();
        activeAudio = audio;
        audio.play().catch(() => snackbar("Couldn't play this voice note."));
      } else {
        audio.pause();
      }
    });
    const update = () => {
      const total = Number.isFinite(audio.duration) ? audio.duration : 0;
      const fraction = total ? audio.currentTime / total : 0;
      bars.forEach((bar, index) => bar.classList.toggle('played', index / bars.length < fraction));
      dur.textContent = formatDuration(audio.paused && !audio.currentTime ? total : audio.currentTime);
      track.setAttribute('aria-valuenow', String(Math.round(fraction * 100)));
    };
    audio.addEventListener('loadedmetadata', update);
    audio.addEventListener('timeupdate', update);
    audio.addEventListener('play', () => { playIcon.textContent = 'pause'; playBtn.setAttribute('aria-label', 'Pause'); });
    audio.addEventListener('pause', () => { playIcon.textContent = 'play_arrow'; playBtn.setAttribute('aria-label', 'Play voice note'); });
    audio.addEventListener('ended', () => { audio.currentTime = 0; update(); });
    const seek = (fraction) => {
      if (Number.isFinite(audio.duration)) audio.currentTime = Math.max(0, Math.min(1, fraction)) * audio.duration;
    };
    track.addEventListener('click', (event) => {
      const rect = track.getBoundingClientRect();
      seek((event.clientX - rect.left) / rect.width);
    });
    track.addEventListener('keydown', (event) => {
      if (!Number.isFinite(audio.duration)) return;
      if (event.key === 'ArrowRight') seek((audio.currentTime + 5) / audio.duration);
      if (event.key === 'ArrowLeft') seek((audio.currentTime - 5) / audio.duration);
    });
    return h('div.audio-player', {}, playBtn, track, dur);
  }

  // ── Sending ───────────────────────────────────────────────────────────
  function addPending(item) {
    item.id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    item.node = h('div.pending-wrap');
    state.pending.push(item);
    paintPending(item);
    render();
    scrollToBottom(true);
    return item;
  }

  function paintPending(item) {
    clear(item.node);
    item.node.classList.toggle('failed', Boolean(item.error));
    let body;
    if (item.kind === 'image') {
      body = h('div.media-card', { style: { opacity: item.error ? '.6' : '.75' } }, h('img.thumb', { src: item.previewUrl, alt: 'Image being checked' }));
    } else if (item.kind === 'audio') {
      body = h('div.bubble', {}, icon('mic', 'sm'), ' Voice note');
    } else {
      body = h('div.bubble', {}, item.text);
    }
    const line = item.error
      ? h('div.state-line', {}, icon('error', 'sm'), h('span', {}, item.error),
        item.retry ? button('Retry', { onClick: () => { item.error = null; paintPending(item); item.retry(); } }) : null,
        button('Discard', { onClick: () => removePending(item) }))
      : h('div.state-line', {}, h('div.spinner', { style: { width: '14px', height: '14px', borderWidth: '2px' } }),
        item.kind === 'image' ? 'Checking the image…' : item.kind === 'audio' ? 'Listening and checking…' : 'Checking with the moderator…');
    item.node.append(body, line);
  }

  function removePending(item) {
    state.pending = state.pending.filter((p) => p !== item);
    if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
    state.nodes.delete(`p:${item.id}`);
    item.node.remove();
    render();
  }

  async function handleResult(item, res) {
    if (res.ok && (res.status === 'PASS' || res.status === 'FLAGGED')) {
      await poll();
      removePending(item);
      scrollToBottom(true);
      if (res.status === 'FLAGGED') snackbar('Held by moderation. You can edit it or appeal.');
      refreshGroups();
      return;
    }
    if (res.httpStatus === 429) item.error = 'Sending too fast. Wait a moment.';
    else if (res.httpStatus === 503) item.error = 'Moderation is busy right now.';
    else item.error = res.message || 'Not sent.';
    paintPending(item);
  }

  async function sendText() {
    const text = textarea.value.trim();
    if (!text) return;
    textarea.value = '';
    drafts.delete(groupId);
    autoGrow(textarea);
    updateSend();
    const item = addPending({ kind: 'text', text });
    item.retry = async () => handleResult(item, await api.sendMessage(groupId, text));
    await item.retry();
  }

  async function sendImageFile(file) {
    if (!file) return;
    let prepared;
    try {
      prepared = await prepareImage(file, { maxBytes: (store.settings?.limits?.image_mb || 8) * 1024 * 1024 });
    } catch (error) {
      return snackbar(error.message);
    }
    const data = await blobToBase64(prepared.blob);
    const item = addPending({ kind: 'image', previewUrl: URL.createObjectURL(prepared.blob) });
    item.retry = async () => handleResult(item, await api.sendImage(groupId, data, prepared.mime));
    await item.retry();
  }

  async function sendAudioBlob(blob, mime) {
    const limit = (store.settings?.limits?.audio_mb || 10) * 1024 * 1024;
    if (blob.size > limit) return snackbar(`Voice note is too long (max ${store.settings?.limits?.audio_mb || 10} MB).`);
    const data = await blobToBase64(blob);
    const item = addPending({ kind: 'audio' });
    item.retry = async () => handleResult(item, await api.sendAudio(groupId, data, mime));
    await item.retry();
  }

  async function sendAudioFile(file) {
    if (!file) return;
    try {
      const prepared = await prepareAudioFile(file, audioFormats);
      await sendAudioBlob(prepared.blob, prepared.mime);
    } catch (error) {
      snackbar(error.message || 'Could not read that audio file.');
    }
  }

  function openAttachMenu(anchor) {
    const items = [];
    if (caps.image) items.push({ label: 'Photo or image', iconName: 'image', onClick: () => imageInput.click() });
    if (caps.audio) items.push({ label: 'Audio file', iconName: 'audio_file', onClick: () => audioInput.click() });
    openMenu(anchor, items);
  }

  imageInput.addEventListener('change', () => { const file = imageInput.files[0]; imageInput.value = ''; sendImageFile(file); });
  audioInput.addEventListener('change', () => { const file = audioInput.files[0]; audioInput.value = ''; sendAudioFile(file); });

  // ── Recording ─────────────────────────────────────────────────────────
  async function startRecording() {
    recorder = new VoiceRecorder();
    try {
      await recorder.start();
    } catch {
      recorder = null;
      snackbar('Microphone access is needed to record. Check your browser permissions.');
      return;
    }
    const timer = h('span.timer', {}, `0:00 / ${formatDuration(MAX_RECORDING_SECONDS)}`);
    const bar = h('div.recording', {},
      h('span.dot'), timer,
      iconButton('delete', 'Discard recording', () => stopRecording(false)));
    bar.querySelector('.icon-btn').style.color = 'inherit';
    fieldShell.hidden = true;
    composer.insertBefore(bar, sendBtn);
    sendBtn.disabled = false;
    sendBtn.onclick = () => stopRecording(true);
    sendBtn.setAttribute('aria-label', 'Send voice note');
    recordTick = setInterval(() => {
      const seconds = recorder?.seconds || 0;
      timer.textContent = `${formatDuration(seconds)} / ${formatDuration(MAX_RECORDING_SECONDS)}`;
      if (seconds >= MAX_RECORDING_SECONDS) stopRecording(true);
    }, 250);
  }

  async function stopRecording(send) {
    clearInterval(recordTick);
    const active = recorder;
    recorder = null;
    composer.querySelector('.recording')?.remove();
    fieldShell.hidden = false;
    sendBtn.onclick = () => sendText();
    sendBtn.setAttribute('aria-label', 'Send');
    updateSend();
    if (!active) return;
    if (!send) {
      active.cancel();
      return;
    }
    const seconds = active.seconds;
    const blob = await active.stop();
    if (!blob || seconds < 0.8) return snackbar('Recording was too short.');
    try {
      const { blob: wav } = await toWav(blob);
      await sendAudioBlob(wav, 'audio/wav');
    } catch (error) {
      snackbar(error.message || 'Could not process the recording.');
    }
  }

  // ── Composer behaviour ────────────────────────────────────────────────
  function updateSend() {
    if (!recorder) sendBtn.disabled = !textarea.value.trim();
  }
  textarea.value = drafts.get(groupId) || '';
  updateSend();
  textarea.addEventListener('input', () => {
    autoGrow(textarea);
    updateSend();
    drafts.set(groupId, textarea.value);
  });
  textarea.addEventListener('keydown', (event) => {
    const touch = window.matchMedia('(pointer: coarse)').matches;
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && !touch) {
      event.preventDefault();
      sendText();
    }
  });
  textarea.addEventListener('paste', (event) => {
    const file = [...(event.clipboardData?.files || [])].find((f) => f.type.startsWith('image/'));
    if (file && caps.image) {
      event.preventDefault();
      sendImageFile(file);
    }
  });
  composer.addEventListener('dragover', (event) => { if (caps.image) event.preventDefault(); });
  composer.addEventListener('drop', (event) => {
    const file = [...(event.dataTransfer?.files || [])].find((f) => f.type.startsWith('image/'));
    if (file && caps.image) { event.preventDefault(); sendImageFile(file); }
  });

  // ── Scrolling ─────────────────────────────────────────────────────────
  function isNearBottom(threshold = 120) {
    return scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < threshold;
  }
  function scrollToBottom(force = false) {
    if (force || isNearBottom(400)) {
      scroller.scrollTop = scroller.scrollHeight;
      jumpBtn.hidden = true;
    }
  }
  scroller.addEventListener('scroll', () => { if (isNearBottom()) jumpBtn.hidden = true; });

  render();
  initialLoad();
  if (!window.matchMedia('(pointer: coarse)').matches) textarea.focus();

  return function unmount() {
    state.destroyed = true;
    clearInterval(pollTimer);
    clearInterval(fullTimer);
    clearInterval(recordTick);
    recorder?.cancel();
    if (activeAudio) activeAudio.pause();
    for (const item of state.pending) if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
  };
}
