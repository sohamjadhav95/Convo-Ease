// Sign in / create account screen.
import { h, icon, clear, logo } from './dom.js';
import { api } from './api.js';
import { textField, passwordField, segmented, errorBox } from './ui.js';

export function mountAuth(root, onSignedIn) {
  clear(root);
  let mode = 'signin';
  const errorSlot = h('div');
  const formSlot = h('div');

  const tabs = segmented([
    { value: 'signin', label: 'Sign in' },
    { value: 'register', label: 'Create account' },
  ], mode, (value) => { mode = value; renderForm(); }, { label: 'Sign in or create account' });

  const card = h('div.auth-card', {},
    h('div.mobile-brand', {}, logo(), h('span.title-large', {}, 'ConvoEase')),
    h('div.stack-8', {},
      h('h2.headline-medium', { id: 'auth-title' }, 'Welcome back'),
      h('p.body-medium.muted', { id: 'auth-sub' }, 'Sign in to continue to your groups.')),
    tabs.el, errorSlot, formSlot);

  root.append(h('div.auth', {},
    h('aside.auth-side', {},
      h('div', {},
        h('div.brandline', {}, logo(), h('span.title-large', {}, 'ConvoEase')),
        h('h1.display-small', {}, 'Group chat that keeps itself friendly.'),
        h('p.body-large', {}, 'An AI moderator checks every message, photo and voice note against the rules your group sets.'),
        h('div.auth-points', {},
          point('rule', 'Your rules, in plain words', 'Write what the group is for. The AI follows it.'),
          point('gavel', 'Fair by design', 'Held messages can be appealed, and the admin has the final say.'),
          point('auto_awesome', 'Catch up in seconds', 'Get a short AI summary of what you missed.'))),
      h('p.body-small', {}, 'Messages are checked by AI and may occasionally be held by mistake.')),
    h('main.auth-main', {}, card)));

  function point(iconName, title, text) {
    return h('div', {}, icon(iconName), h('div', {}, h('b', {}, title), h('span.body-medium', {}, text)));
  }

  function renderForm() {
    clear(errorSlot);
    const register = mode === 'register';
    card.querySelector('#auth-title').textContent = register ? 'Create your account' : 'Welcome back';
    card.querySelector('#auth-sub').textContent = register ? 'It takes less than a minute.' : 'Sign in to continue to your groups.';

    const fullName = textField({ label: 'Full name', autocomplete: 'name', maxlength: 120 });
    const username = textField({ label: 'Username', autocomplete: 'username', maxlength: 32, spellcheck: 'false',
      supporting: register ? '3–32 letters, numbers, dots, dashes or underscores.' : undefined });
    const password = passwordField({ label: 'Password', autocomplete: register ? 'new-password' : 'current-password',
      supporting: register ? 'At least 6 characters.' : undefined });
    const submit = h('button.btn.filled.block.state', { type: 'submit' }, register ? 'Create account' : 'Sign in');
    const form = h('form.fields', { novalidate: true },
      register ? fullName.el : null, username.el, password.el, submit);

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      clear(errorSlot);
      [fullName, username, password].forEach((f) => f.setError(''));
      if (register && !fullName.value.trim()) return fullName.setError('Enter your name.');
      if (!username.value.trim()) return username.setError('Enter your username.');
      if (!password.value) return password.setError('Enter your password.');
      submit.disabled = true;
      submit.textContent = register ? 'Creating account…' : 'Signing in…';
      const res = register
        ? await api.register(fullName.value.trim(), username.value.trim(), password.value)
        : await api.login(username.value.trim(), password.value);
      submit.disabled = false;
      submit.textContent = register ? 'Create account' : 'Sign in';
      if (!res.success) {
        errorSlot.append(errorBox(res.message || 'Something went wrong. Please try again.'));
        return;
      }
      onSignedIn(res.user);
    });

    clear(formSlot).append(form);
    requestAnimationFrame(() => (register ? fullName.input : username.input).focus());
  }

  renderForm();
}
