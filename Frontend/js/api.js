// Thin client for the ConvoEase REST API. Every call resolves to the parsed
// JSON body plus `ok` and `httpStatus`; it never throws for HTTP errors.

const listeners = new Set();

export function onUnauthenticated(fn) {
  listeners.add(fn);
}

async function request(method, path, body, { isForm = false } = {}) {
  const options = { method, headers: {}, credentials: 'same-origin' };
  if (body !== undefined) {
    if (isForm) {
      options.body = body;
    } else {
      options.headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(body);
    }
  }
  let response;
  try {
    response = await fetch(path, options);
  } catch {
    return { ok: false, httpStatus: 0, success: false, message: "Can't reach the server. Check your connection." };
  }
  let data = {};
  try {
    data = await response.json();
  } catch {
    data = { success: false, message: `Server error (${response.status}). Please try again.` };
  }
  if (response.status === 401 && !path.startsWith('/api/auth/')) {
    listeners.forEach((fn) => fn());
  }
  return { ...data, ok: response.ok, httpStatus: response.status };
}

const get = (path) => request('GET', path);
const post = (path, body = {}) => request('POST', path, body);
const put = (path, body = {}) => request('PUT', path, body);
const del = (path, body = {}) => request('DELETE', path, body);
const enc = encodeURIComponent;

export const api = {
  // Auth
  me: () => get('/api/auth/me'),
  login: (username, password) => post('/api/auth/login', { username, password }),
  register: (full_name, username, password) => post('/api/auth/register', { full_name, username, password }),
  logout: () => post('/api/auth/logout'),
  settings: () => get('/api/settings'),

  // Profile
  updateProfile: (fields) => put('/api/user/profile', fields),
  changePassword: (current_password, new_password) => put('/api/user/password', { current_password, new_password }),

  // Groups
  groups: () => get('/api/groups'),
  createGroup: (fields) => post('/api/groups', fields),
  joinGroup: (group_id, password) => post('/api/groups/join', { group_id, password }),
  group: (id) => get(`/api/groups/${enc(id)}`),
  members: (id) => get(`/api/groups/${enc(id)}/members`),
  renameGroup: (id, group_name) => put(`/api/groups/${enc(id)}/name`, { group_name }),
  updateRules: (id, rules, moderation_sensitivity) => put(`/api/groups/${enc(id)}/rules`, { rules, moderation_sensitivity }),
  leaveGroup: (id) => post(`/api/groups/${enc(id)}/leave`),
  deleteGroup: (id) => del(`/api/groups/${enc(id)}`),

  // Messages
  messages: (id, { after = 0, before = 0, limit = 100 } = {}) => {
    const params = new URLSearchParams({ include_own_flagged: '1', limit: String(limit) });
    if (after) params.set('after', String(after));
    if (before) params.set('before', String(before));
    return get(`/api/groups/${enc(id)}/messages?${params}`);
  },
  sendMessage: (id, message) => post(`/api/groups/${enc(id)}/messages`, { message }),
  sendImage: (id, image_data, mime_type) => post(`/api/groups/${enc(id)}/images`, { image_data, mime_type }),
  sendAudio: (id, audio_data, mime_type) => post(`/api/groups/${enc(id)}/audio`, { audio_data, mime_type }),
  deleteMessage: (id, messageId) => del(`/api/groups/${enc(id)}/messages/${enc(messageId)}`),
  appeal: (id, messageId, appeal_text) => post(`/api/groups/${enc(id)}/messages/${enc(messageId)}/appeal`, { appeal_text }),
  reviewAppeal: (id, messageId, decision, admin_note) =>
    post(`/api/groups/${enc(id)}/messages/${enc(messageId)}/appeal/review`, { decision, admin_note }),
  flagged: (id) => get(`/api/groups/${enc(id)}/messages/flagged`),
  report: (id) => get(`/api/groups/${enc(id)}/report`),
  summary: (id, limit = 30) => get(`/api/groups/${enc(id)}/summary?limit=${limit}`),

  // Rules helpers
  suggestRules: (rules, group_name) => post('/api/rules/suggest', { rules, group_name }),
  extractRules: (file) => {
    const form = new FormData();
    form.append('file', file);
    return request('POST', '/api/rules/extract', form, { isForm: true });
  },
};
