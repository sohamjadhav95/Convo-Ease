// Small DOM and formatting helpers. User content is only ever set as text,
// never as HTML.

const PROPS = new Set(['value', 'checked', 'disabled', 'hidden', 'textContent', 'selected', 'muted', 'readOnly', 'required', 'indeterminate']);

export function h(tag, props, ...children) {
  const [name, ...classes] = tag.split('.');
  const el = document.createElement(name || 'div');
  if (classes.length) el.className = classes.join(' ');
  for (const [key, value] of Object.entries(props || {})) {
    if (value == null || value === false) continue;
    if (key === 'class') el.className = [el.className, value].filter(Boolean).join(' ');
    else if (key === 'dataset') Object.assign(el.dataset, value);
    else if (key === 'style' && typeof value === 'object') Object.assign(el.style, value);
    else if (key.startsWith('on') && typeof value === 'function') el.addEventListener(key.slice(2).toLowerCase(), value);
    else if (key === 'ref' && typeof value === 'function') value(el);
    else if (PROPS.has(key)) el[key] = value;
    else el.setAttribute(key, value === true ? '' : value);
  }
  append(el, children);
  return el;
}

export function append(el, children) {
  for (const child of children.flat(Infinity)) {
    if (child == null || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

export function icon(name, extra = '') {
  return h(`span.ms${extra ? '.' + extra.split(' ').join('.') : ''}`, { 'aria-hidden': 'true' }, name);
}

export function clear(el) {
  while (el.firstChild) el.firstChild.remove();
  return el;
}

export function iconButton(name, label, onClick, extra = '') {
  return h(`button.icon-btn.state${extra ? '.' + extra.split(' ').join('.') : ''}`, {
    type: 'button', 'aria-label': label, title: label, onclick: onClick,
  }, icon(name));
}

export function button(label, { variant = 'text', iconName, onClick, type = 'button', disabled, extra = '' } = {}) {
  const cls = ['btn', 'state', variant, iconName ? 'has-icon' : '', extra].filter(Boolean).join('.');
  return h(`button.${cls}`, { type, onclick: onClick, disabled }, iconName ? icon(iconName) : null, label);
}

// ── Avatars ─────────────────────────────────────────────────────────────
export const AVATAR_EMOJIS = {
  bear: '🐻', fox: '🦊', owl: '🦉', wolf: '🐺', cat: '🐱', eagle: '🦅',
  panda: '🐼', lion: '🦁', rocket: '🚀', diamond: '💎', ghost: '👻',
};

export function initials(name) {
  const parts = String(name || '?').trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return String(parts[0] || '?').slice(0, 2).toUpperCase();
}

function hashIndex(text, buckets) {
  let hash = 0;
  for (const ch of String(text || '')) hash = (hash * 31 + ch.codePointAt(0)) >>> 0;
  return hash % buckets;
}

export function avatar(person, size = '') {
  const name = person?.full_name || person?.group_name || person?.username || '?';
  const emoji = AVATAR_EMOJIS[person?.avatar];
  const key = person?.username || person?.group_id || name;
  const cls = ['avatar', size, emoji ? 'emoji' : '', `c${hashIndex(key, 7)}`].filter(Boolean).join('.');
  return h(`span.${cls}`, { 'aria-hidden': 'true' }, emoji || initials(name));
}

// ── Time ────────────────────────────────────────────────────────────────
// The server stores UTC as "YYYY-MM-DD HH:MM:SS".
export function parseTime(ts) {
  if (!ts) return null;
  const date = new Date(String(ts).replace(' ', 'T') + 'Z');
  return Number.isNaN(date.getTime()) ? null : date;
}

const timeFmt = new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' });
const weekdayFmt = new Intl.DateTimeFormat(undefined, { weekday: 'short' });
const longWeekdayFmt = new Intl.DateTimeFormat(undefined, { weekday: 'long' });
const shortDateFmt = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' });
const fullDateFmt = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
const longDateFmt = new Intl.DateTimeFormat(undefined, { weekday: 'long', month: 'long', day: 'numeric' });

function startOfDay(date) {
  const copy = new Date(date);
  copy.setHours(0, 0, 0, 0);
  return copy;
}

function daysAgo(date) {
  return Math.round((startOfDay(new Date()) - startOfDay(date)) / 86400000);
}

export function formatClock(ts) {
  const date = parseTime(ts);
  return date ? timeFmt.format(date) : '';
}

export function formatListTime(ts) {
  const date = parseTime(ts);
  if (!date) return '';
  const ago = daysAgo(date);
  if (ago <= 0) return timeFmt.format(date);
  if (ago === 1) return 'Yesterday';
  if (ago < 7) return weekdayFmt.format(date);
  if (date.getFullYear() === new Date().getFullYear()) return shortDateFmt.format(date);
  return fullDateFmt.format(date);
}

export function dayKey(ts) {
  const date = parseTime(ts);
  return date ? startOfDay(date).toDateString() : '';
}

export function formatDay(ts) {
  const date = parseTime(ts);
  if (!date) return '';
  const ago = daysAgo(date);
  if (ago <= 0) return 'Today';
  if (ago === 1) return 'Yesterday';
  if (ago < 7) return longWeekdayFmt.format(date);
  if (date.getFullYear() === new Date().getFullYear()) return longDateFmt.format(date);
  return fullDateFmt.format(date);
}

export function formatDuration(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00';
  const s = Math.round(seconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

// ── Misc ────────────────────────────────────────────────────────────────
export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const area = h('textarea', { style: { position: 'fixed', opacity: '0' } }, text);
    document.body.append(area);
    area.select();
    const ok = document.execCommand('copy');
    area.remove();
    return ok;
  }
}

export function storageGet(key, fallback = null) {
  try {
    const value = localStorage.getItem(key);
    return value == null ? fallback : JSON.parse(value);
  } catch {
    return fallback;
  }
}

export function storageSet(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode */ }
}

export function plural(count, word, many = `${word}s`) {
  return `${count} ${count === 1 ? word : many}`;
}

export function autoGrow(textarea, max = 160) {
  textarea.style.height = 'auto';
  textarea.style.height = `${Math.min(textarea.scrollHeight, max)}px`;
}

// ── Brand mark ──────────────────────────────────────────────────────────
const LOGO_SVG = '<svg viewBox="0 0 32 32" aria-hidden="true"><path fill="currentColor" d="M7 4h18a5 5 0 0 1 5 5v11a5 5 0 0 1-5 5h-9.5L9 29.5a.8.8 0 0 1-1.3-.6V25H7a5 5 0 0 1-5-5V9a5 5 0 0 1 5-5z"/><path d="M10.5 14.8l3.8 3.8 7.4-7.6" fill="none" stroke="var(--md-surface, #fff)" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';

export function logo() {
  const template = document.createElement('template');
  template.innerHTML = LOGO_SVG;
  return template.content.firstChild;
}
