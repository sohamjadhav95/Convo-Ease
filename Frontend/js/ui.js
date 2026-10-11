// Reusable Material 3 pieces: snackbar, dialogs, fields, segmented buttons, menus.
import { h, icon, iconButton, button, clear } from './dom.js';

// ── Snackbar ────────────────────────────────────────────────────────────
let snackTimer = null;

export function snackbar(message, { action, onAction, duration = 4000 } = {}) {
  const host = document.getElementById('snackbars');
  if (!host) return;
  clear(host);
  clearTimeout(snackTimer);
  const bar = h('div.snackbar', { role: 'status' },
    h('span.msg', {}, message),
    action ? button(action, { onClick: () => { dismiss(); onAction?.(); } }) : null,
    iconButton('close', 'Dismiss', () => dismiss(), 'sm'),
  );
  bar.querySelector('.icon-btn').style.color = 'inherit';
  host.append(bar);
  function dismiss() {
    bar.classList.add('leaving');
    setTimeout(() => bar.remove(), 160);
  }
  snackTimer = setTimeout(dismiss, duration);
}

// ── Dialogs ─────────────────────────────────────────────────────────────
// actions: [{ label, variant, iconName, onClick(ctrl) -> value|Promise, close: true }]
export function openDialog({ title, iconName, body, actions = [], size = '', centered = false, onClose, dismissible = true }) {
  const footer = h('footer');
  const dialog = h(`dialog.dialog${size ? '.' + size : ''}`, { 'aria-label': typeof title === 'string' ? title : undefined },
    h(`header${centered || iconName ? '.centered' : ''}`, {},
      iconName ? icon(iconName, 'icon-head') : null,
      title ? h('h2.headline-small', {}, title) : null,
    ),
    h('div.body', {}, body),
    footer,
  );
  let result;
  const ctrl = {
    dialog,
    footer,
    close(value) {
      result = value;
      if (dialog.open) dialog.close();
    },
    setBusy(busy) {
      footer.querySelectorAll('button').forEach((b) => { b.disabled = busy; });
    },
  };
  for (const action of actions) {
    const btn = button(action.label, { variant: action.variant || 'text', iconName: action.iconName, extra: action.danger ? 'danger' : '' });
    btn.addEventListener('click', async () => {
      if (!action.onClick) return ctrl.close(action.value);
      const value = await action.onClick(ctrl);
      if (value !== false && action.close !== false) ctrl.close(value === undefined ? action.value : value);
    });
    footer.append(btn);
  }
  if (!actions.length) footer.remove();
  dialog.addEventListener('cancel', (event) => { if (!dismissible) event.preventDefault(); });
  dialog.addEventListener('click', (event) => {
    if (event.target === dialog && dismissible) ctrl.close();
  });
  const done = new Promise((resolve) => {
    dialog.addEventListener('close', () => {
      dialog.remove();
      onClose?.(result);
      resolve(result);
    });
  });
  ctrl.done = done;
  document.body.append(dialog);
  dialog.showModal();
  return ctrl;
}

export function confirmDialog({ title, message, confirmLabel = 'Confirm', danger = false, iconName }) {
  const ctrl = openDialog({
    title,
    iconName,
    size: 'sm',
    body: h('p.body-medium', {}, message),
    actions: [
      { label: 'Cancel', value: false },
      { label: confirmLabel, value: true, variant: danger ? 'text' : 'text', danger },
    ],
  });
  return ctrl.done.then((value) => value === true);
}

// ── Side sheet ──────────────────────────────────────────────────────────
export function openSheet({ title, body, onClose }) {
  const content = h('div.sheet-body', {}, body);
  const dialog = h('dialog.sheet', { 'aria-label': title },
    h('header', {}, h('h2.title-large', {}, title), iconButton('close', 'Close', () => dialog.close())),
    content,
  );
  dialog.addEventListener('click', (event) => { if (event.target === dialog) dialog.close(); });
  dialog.addEventListener('close', () => { dialog.remove(); onClose?.(); });
  document.body.append(dialog);
  dialog.showModal();
  return { dialog, content, close: () => dialog.close() };
}

// ── Text field ──────────────────────────────────────────────────────────
let fieldCount = 0;

export function textField({ label, value = '', type = 'text', name, autocomplete, multiline = false, rows = 5, supporting, maxlength, required, autofocus, trailing, inputmode, spellcheck }) {
  const id = `f${++fieldCount}`;
  const common = { id, name, maxlength, required, placeholder: ' ', spellcheck, 'aria-describedby': `${id}-help` };
  const input = multiline
    ? h('textarea', { ...common, rows })
    : h('input', { ...common, type, autocomplete, inputmode });
  input.value = value;
  if (autofocus) input.setAttribute('autofocus', '');
  const support = h('span.supporting', { id: `${id}-help`, hidden: !supporting }, supporting || '');
  // The visible floating label sits over the input; the <label for> keeps
  // the accessible name to just the label text.
  const el = h(`div.field${trailing ? '.has-trailing' : ''}`, {}, input, h('label.label', { for: id }, label), trailing || null, support);
  return {
    el,
    input,
    get value() { return input.value; },
    set value(v) { input.value = v; },
    setError(message) {
      el.classList.toggle('invalid', Boolean(message));
      support.textContent = message || supporting || '';
      support.hidden = !message && !supporting;
    },
  };
}

export function passwordField(options) {
  const toggle = iconButton('visibility', 'Show password', () => {
    const showing = field.input.type === 'text';
    field.input.type = showing ? 'password' : 'text';
    toggle.querySelector('.ms').textContent = showing ? 'visibility' : 'visibility_off';
    toggle.setAttribute('aria-label', showing ? 'Show password' : 'Hide password');
  });
  toggle.classList.add('trailing');
  const field = textField({ ...options, type: 'password', trailing: toggle });
  return field;
}

// ── Segmented buttons ───────────────────────────────────────────────────
export function segmented(options, value, onChange, { label } = {}) {
  let current = value;
  const el = h('div.segmented', { role: 'group', 'aria-label': label });
  const buttons = options.map((option) => {
    const btn = h('button.state', { type: 'button', 'aria-pressed': String(option.value === current) },
      icon('check', 'check'), option.icon ? icon(option.icon) : null, option.label);
    btn.addEventListener('click', () => {
      if (current === option.value) return;
      set(option.value);
      onChange?.(option.value);
    });
    el.append(btn);
    return btn;
  });
  function set(next) {
    current = next;
    options.forEach((option, index) => buttons[index].setAttribute('aria-pressed', String(option.value === next)));
  }
  return { el, set, get value() { return current; } };
}

// ── Menu ────────────────────────────────────────────────────────────────
let openMenuEl = null;

export function openMenu(anchor, items) {
  closeMenu();
  const menu = h('div', { role: 'menu', class: 'menu' });
  Object.assign(menu.style, {
    position: 'fixed', zIndex: '900', minWidth: '180px', padding: '8px 0',
    borderRadius: '4px', background: 'var(--md-surface-container)', boxShadow: 'var(--elev-2)',
  });
  for (const item of items) {
    const row = h('button.list-item.state', { type: 'button', role: 'menuitem', style: { minHeight: '48px', padding: '0 16px', gap: '12px' } },
      item.iconName ? icon(item.iconName) : null,
      h('span.label-large', { style: { fontWeight: '400', fontSize: '14px' } }, item.label));
    if (item.iconName) row.firstChild.style.color = 'var(--md-on-surface-variant)';
    row.addEventListener('click', () => { closeMenu(); item.onClick?.(); });
    menu.append(row);
  }
  document.body.append(menu);
  const rect = anchor.getBoundingClientRect();
  const menuRect = menu.getBoundingClientRect();
  const top = rect.top - menuRect.height - 4 > 8 ? rect.top - menuRect.height - 4 : rect.bottom + 4;
  menu.style.top = `${Math.min(top, window.innerHeight - menuRect.height - 8)}px`;
  menu.style.left = `${Math.max(8, Math.min(rect.left, window.innerWidth - menuRect.width - 8))}px`;
  openMenuEl = menu;
  menu.querySelector('button')?.focus();
  setTimeout(() => {
    document.addEventListener('pointerdown', outside, true);
    document.addEventListener('keydown', onKey, true);
  });
  function outside(event) { if (!menu.contains(event.target)) closeMenu(); }
  function onKey(event) { if (event.key === 'Escape') { event.stopPropagation(); closeMenu(); anchor.focus(); } }
  menu._cleanup = () => {
    document.removeEventListener('pointerdown', outside, true);
    document.removeEventListener('keydown', onKey, true);
  };
}

export function closeMenu() {
  if (!openMenuEl) return;
  openMenuEl._cleanup?.();
  openMenuEl.remove();
  openMenuEl = null;
}

// ── Image viewer ────────────────────────────────────────────────────────
export function openImageViewer(src, caption) {
  const dialog = h('dialog.viewer', { 'aria-label': 'Image' },
    h('div.viewer-inner', {},
      h('header', {}, iconButton('close', 'Close', () => dialog.close())),
      h('img', { src, alt: caption || 'Shared image' }),
      caption ? h('div.caption', {}, icon('auto_awesome', 'sm'), h('span', {}, caption)) : h('div'),
    ),
  );
  dialog.addEventListener('click', (event) => {
    if (event.target === dialog || event.target.classList.contains('viewer-inner')) dialog.close();
  });
  dialog.addEventListener('close', () => dialog.remove());
  document.body.append(dialog);
  dialog.showModal();
}

export function errorBox(message) {
  return h('div.form-error', { role: 'alert' }, icon('error'), h('span', {}, message));
}

export function spinnerLine(text) {
  return h('div', { style: { display: 'flex', alignItems: 'center', gap: '12px', color: 'var(--md-on-surface-variant)' } },
    h('div.spinner'), h('span', {}, text));
}
