// Settings: profile, appearance, password, about.
import { h, icon, button, avatar, clear, AVATAR_EMOJIS } from './dom.js';
import { api } from './api.js';
import { store, emit } from './store.js';
import { textField, passwordField, segmented, snackbar, confirmDialog } from './ui.js';

const ACCENTS = [
  { value: 'teal', label: 'Teal', color: '#006B5E' },
  { value: 'indigo', label: 'Indigo', color: '#4355B9' },
  { value: 'rose', label: 'Rose', color: '#984061' },
  { value: 'amber', label: 'Amber', color: '#7F5700' },
];

function readPref(key, fallback) {
  try { return localStorage.getItem(key) || fallback; } catch { return fallback; }
}
function writePref(key, value) {
  try { localStorage.setItem(key, value); } catch { /* ignore */ }
  window.__applyTheme?.();
}

export function mountSettings(container) {
  const scroller = h('div.settings');
  const inner = h('div.settings-inner');
  scroller.append(inner);
  container.append(h('div.chat', {},
    h('header.top-bar', {}, h('div.title', { style: { paddingLeft: '8px' } }, h('b', {}, 'Settings'))),
    scroller));

  inner.append(profileCard(), appearanceCard(), passwordCard(), aboutCard());
  return () => {};
}

function profileCard() {
  const user = store.user;
  let chosen = user.avatar || '';
  const preview = h('span');
  const paintPreview = () => clear(preview).append(avatar({ ...user, avatar: chosen }, 'xl'));
  paintPreview();

  const name = textField({ label: 'Full name', value: user.full_name, maxlength: 120, autocomplete: 'name' });
  const bio = textField({ label: 'About you (optional)', value: user.bio || '', multiline: true, rows: 3, maxlength: 500 });

  const picker = h('div.avatar-picker', { role: 'group', 'aria-label': 'Profile picture' });
  const options = [['', null], ...Object.keys(AVATAR_EMOJIS).map((key) => [key, key])];
  const pickerButtons = options.map(([value]) => {
    const btn = h('button', { type: 'button', 'aria-pressed': String(value === chosen), 'aria-label': value ? `Use ${value}` : 'Use initials',
      onclick: () => { chosen = value; pickerButtons.forEach((b, i) => b.setAttribute('aria-pressed', String(options[i][0] === chosen))); paintPreview(); } },
    avatar({ ...user, avatar: value }, 'lg'));
    picker.append(btn);
    return btn;
  });

  const form = h('form.stack-16', {}, name.el, bio.el,
    h('div.stack-8', {}, h('div.title-small', {}, 'Profile picture'), picker),
    h('div.row-wrap', { style: { justifyContent: 'flex-end' } }, button('Save profile', { variant: 'filled', type: 'submit' })));
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!name.value.trim()) return name.setError('Enter your name.');
    name.setError('');
    const res = await api.updateProfile({ full_name: name.value.trim(), bio: bio.value.trim(), avatar: chosen });
    if (!res.success) return snackbar(res.message || 'Could not save your profile.');
    store.user = res.user;
    emit('user', res.user);
    snackbar('Profile saved');
  });

  return h('section.card', {},
    h('h2.title-large', {}, 'Profile'),
    h('div.profile-head', {}, preview,
      h('div', {}, h('div.title-medium', {}, user.full_name), h('div.body-medium.muted', {}, `@${user.username}`))),
    form);
}

function appearanceCard() {
  const theme = segmented([
    { value: 'system', label: 'System', icon: 'brightness_auto' },
    { value: 'light', label: 'Light', icon: 'light_mode' },
    { value: 'dark', label: 'Dark', icon: 'dark_mode' },
  ], readPref('ce.theme', 'system'), (value) => writePref('ce.theme', value), { label: 'Theme' });

  const current = readPref('ce.accent', 'teal');
  const swatches = h('div.swatches', { role: 'group', 'aria-label': 'Accent color' });
  const swatchButtons = ACCENTS.map((accent) => {
    const btn = h('button.swatch', {
      type: 'button', title: accent.label, 'aria-label': accent.label, 'aria-pressed': String(accent.value === current),
      style: { background: accent.color },
      onclick: () => {
        writePref('ce.accent', accent.value);
        swatchButtons.forEach((b, i) => {
          b.setAttribute('aria-pressed', String(ACCENTS[i].value === accent.value));
          clear(b);
          if (ACCENTS[i].value === accent.value) b.append(icon('check'));
        });
      },
    }, accent.value === current ? icon('check') : null);
    swatches.append(btn);
    return btn;
  });

  return h('section.card', {},
    h('h2.title-large', {}, 'Appearance'),
    h('div.stack-16', {},
      h('div.stack-8', {}, h('div.title-small', {}, 'Theme'), theme.el),
      h('div.stack-8', {}, h('div.title-small', {}, 'Accent color'), swatches)));
}

function passwordCard() {
  const current = passwordField({ label: 'Current password', autocomplete: 'current-password' });
  const next = passwordField({ label: 'New password', autocomplete: 'new-password', supporting: 'At least 6 characters.' });
  const form = h('form.stack-16', {}, current.el, next.el,
    h('div.row-wrap', { style: { justifyContent: 'flex-end' } }, button('Change password', { variant: 'tonal', type: 'submit' })));
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    current.setError('');
    next.setError('');
    if (next.value.length < 6) return next.setError('At least 6 characters.');
    const res = await api.changePassword(current.value, next.value);
    if (!res.success) {
      if (/current/i.test(res.message || '')) current.setError(res.message);
      else next.setError(res.message || 'Could not change the password.');
      return;
    }
    current.value = '';
    next.value = '';
    snackbar('Password changed');
  });
  return h('section.card', {}, h('h2.title-large', {}, 'Password'), form);
}

function aboutCard() {
  const settings = store.settings || {};
  const caps = settings.capabilities || {};
  const yes = (on) => h('span', { style: { display: 'inline-flex', gap: '6px', alignItems: 'center' } },
    icon(on ? 'check_circle' : 'cancel', 'sm'), on ? 'On' : 'Unavailable');
  return h('section.card', {},
    h('h2.title-large', {}, 'About'),
    h('dl.kv.body-medium', { style: { margin: '0 0 20px' } },
      h('dt', {}, 'Version'), h('dd', {}, settings.app_version || '—'),
      h('dt', {}, 'AI moderator'), h('dd', {}, settings.ai_provider || '—'),
      h('dt', {}, 'Text checks'), h('dd', {}, yes(caps.text)),
      h('dt', {}, 'Image checks'), h('dd', {}, yes(caps.image)),
      h('dt', {}, 'Voice checks'), h('dd', {}, yes(caps.audio))),
    h('div.row-wrap', {}, button('Sign out', {
      variant: 'outlined', iconName: 'logout', onClick: async () => {
        const ok = await confirmDialog({ title: 'Sign out?', message: 'You can sign back in any time.', confirmLabel: 'Sign out' });
        if (!ok) return;
        await api.logout();
        emit('signed-out');
      },
    })));
}

