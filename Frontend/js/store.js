// Shared app state, a tiny event bus, and hash-based routing.
import { api } from './api.js';

export const store = {
  user: null,
  settings: null,
  groups: [],
  groupsLoaded: false,
  filter: { q: '', chip: 'all' },
};

const listeners = new Map();

export function on(topic, fn) {
  if (!listeners.has(topic)) listeners.set(topic, new Set());
  listeners.get(topic).add(fn);
  return () => listeners.get(topic)?.delete(fn);
}

export function emit(topic, payload) {
  listeners.get(topic)?.forEach((fn) => fn(payload));
}

export async function refreshGroups() {
  const res = await api.groups();
  if (res.success) {
    store.groups = res.groups;
    store.groupsLoaded = true;
    emit('groups', store.groups);
  }
  return res;
}

export function findGroup(groupId) {
  return store.groups.find((group) => group.group_id === groupId) || null;
}

export function isAdminAnywhere() {
  return store.groups.some((group) => group.is_admin);
}

// Routes: #/chats, #/chats/<id>, #/moderation, #/moderation/<id>, #/settings
export function parseRoute() {
  const [section = 'chats', id = ''] = location.hash.replace(/^#\/?/, '').split('/');
  const known = ['chats', 'moderation', 'settings'];
  return { section: known.includes(section) ? section : 'chats', id: decodeURIComponent(id || '') };
}

export function navigate(path, { replace = false } = {}) {
  const hash = `#/${path}`;
  if (location.hash === hash) {
    emit('route', parseRoute());
    return;
  }
  if (replace) {
    history.replaceState(null, '', hash);
    emit('route', parseRoute());
  } else {
    location.hash = hash;
  }
}

window.addEventListener('hashchange', () => emit('route', parseRoute()));
