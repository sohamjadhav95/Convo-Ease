// Dialogs: create / join a group, appeal a held message, AI catch-up.
import { h, icon, button, copyText, clear } from './dom.js';
import { api } from './api.js';
import { openDialog, textField, passwordField, segmented, snackbar, errorBox, spinnerLine } from './ui.js';
import { refreshGroups, navigate } from './store.js';

export const SENSITIVITY = [
  { value: 'Relaxed', label: 'Relaxed', help: 'Only clear, serious rule breaks are held.' },
  { value: 'Moderate', label: 'Moderate', help: 'Balanced: clear violations and clearly off-topic messages are held.' },
  { value: 'Strict', label: 'Strict', help: 'Borderline and slightly off-topic messages are held too.' },
];

export function sensitivityHelp(value) {
  return SENSITIVITY.find((s) => s.value === value)?.help || '';
}

/** Rules text area with "Improve with AI" and "Upload file" helpers. */
export function rulesEditor({ value = '', groupName = () => '' } = {}) {
  const field = textField({ label: 'Group rules', value, multiline: true, rows: 6, maxlength: 4000,
    supporting: 'Write them like you would explain them to a person. The AI moderator follows these.' });
  const fileInput = h('input', { type: 'file', accept: '.txt,.pdf,text/plain,application/pdf', hidden: true });
  const suggestions = h('div', { hidden: true });
  const status = h('div', { hidden: true });

  const suggestBtn = button('Improve with AI', { variant: 'tonal', iconName: 'auto_awesome', onClick: suggest });
  const uploadBtn = button('Upload .txt / .pdf', { variant: 'text', iconName: 'upload_file', onClick: () => fileInput.click() });

  fileInput.addEventListener('change', async () => {
    const file = fileInput.files[0];
    fileInput.value = '';
    if (!file) return;
    setStatus(spinnerLine('Reading file…'));
    const res = await api.extractRules(file);
    setStatus(null);
    if (!res.success) return snackbar(res.message || 'Could not read that file.');
    field.value = res.extracted_text;
    snackbar('Rules loaded from file. Review them before saving.');
  });

  async function suggest() {
    suggestBtn.disabled = true;
    setStatus(spinnerLine('Asking the AI for improvements…'));
    const res = await api.suggestRules(field.value, groupName());
    setStatus(null);
    suggestBtn.disabled = false;
    if (!res.success) return snackbar(res.message || 'Suggestions are unavailable right now.');
    clear(suggestions).append(h('div.suggest-box', {},
      h('div.title-small', { style: { display: 'flex', gap: '8px', alignItems: 'center' } }, icon('auto_awesome', 'sm'), 'Suggestions'),
      h('ul.body-medium', {}, res.suggestions.map((item) => h('li', {}, item))),
      h('div.label-medium', {}, 'Improved rules'),
      h('pre.body-medium', {}, res.revised_rules),
      h('div.row-wrap', { style: { justifyContent: 'flex-end' } },
        button('Dismiss', { onClick: () => { suggestions.hidden = true; } }),
        button('Use these rules', { variant: 'filled', onClick: () => { field.value = res.revised_rules; suggestions.hidden = true; } })),
    ));
    suggestions.hidden = false;
  }

  function setStatus(node) {
    clear(status);
    status.hidden = !node;
    if (node) status.append(node);
  }

  const el = h('div.stack-12', {}, field.el, h('div.row-wrap', {}, suggestBtn, uploadBtn), status, suggestions, fileInput);
  return { el, field, get value() { return field.value.trim(); } };
}

// ── Create / join ───────────────────────────────────────────────────────
export function openNewGroupDialog(startTab = 'create') {
  let tab = startTab;
  const body = h('div.stack-16', { style: { paddingTop: '4px' } });
  const tabs = segmented([
    { value: 'create', label: 'Create', icon: 'group_add' },
    { value: 'join', label: 'Join', icon: 'login' },
  ], tab, (value) => { tab = value; render(); }, { label: 'Create or join' });

  const name = textField({ label: 'Group name', maxlength: 120, autofocus: true });
  const rules = rulesEditor({ value: 'Be respectful. No insults, harassment or spam.', groupName: () => name.value });
  let sensitivity = 'Moderate';
  const sensHelp = h('p.help', {}, sensitivityHelp(sensitivity));
  const sens = segmented(SENSITIVITY, sensitivity, (value) => { sensitivity = value; sensHelp.textContent = sensitivityHelp(value); }, { label: 'Moderation strictness' });
  const createPassword = passwordField({ label: 'Password (optional)', autocomplete: 'new-password',
    supporting: 'Leave empty so anyone with the group ID can join.' });

  const joinId = textField({ label: 'Group ID', maxlength: 16, autocomplete: 'off', spellcheck: 'false',
    supporting: 'The 6-character code the admin shared, e.g. K7Q2MX' });
  joinId.input.style.textTransform = 'uppercase';
  joinId.input.style.letterSpacing = '2px';
  const joinPassword = passwordField({ label: 'Password (if the group has one)', autocomplete: 'off' });
  const errorSlot = h('div');

  const createPanel = h('div.stack-16', {}, name.el,
    h('div.stack-8', {}, h('div.title-small', {}, 'Moderation strictness'), sens.el, sensHelp),
    rules.el, createPassword.el);
  const joinPanel = h('div.stack-16', {}, joinId.el, joinPassword.el);

  function render() {
    clear(body).append(tabs.el, errorSlot, tab === 'create' ? createPanel : joinPanel);
    submitBtn.textContent = tab === 'create' ? 'Create group' : 'Join group';
    clear(errorSlot);
    requestAnimationFrame(() => (tab === 'create' ? name.input : joinId.input).focus());
  }

  async function submit(ctrl) {
    clear(errorSlot);
    ctrl.setBusy(true);
    try {
      if (tab === 'create') {
        if (!name.value.trim()) {
          name.setError('Give the group a name.');
          return false;
        }
        const res = await api.createGroup({
          group_name: name.value.trim(),
          rules: rules.value,
          moderation_sensitivity: sensitivity,
          password: createPassword.value,
        });
        if (!res.success) {
          errorSlot.append(errorBox(res.message || 'Could not create the group.'));
          return false;
        }
        await refreshGroups();
        ctrl.close();
        navigate(`chats/${encodeURIComponent(res.group_id)}`);
        showInvite(res.group_id, name.value.trim(), Boolean(createPassword.value));
        return false;
      }
      const id = joinId.value.trim().toUpperCase();
      if (!id) {
        joinId.setError('Enter the group ID.');
        return false;
      }
      const res = await api.joinGroup(id, joinPassword.value);
      if (!res.success) {
        errorSlot.append(errorBox(res.message || 'Could not join the group.'));
        return false;
      }
      await refreshGroups();
      ctrl.close();
      navigate(`chats/${encodeURIComponent(res.group_id || id)}`);
      snackbar(res.message === 'Already a member.' ? "You're already in this group." : 'Joined the group.');
      return false;
    } finally {
      ctrl.setBusy(false);
    }
  }

  const ctrl = openDialog({
    title: 'New group',
    body,
    actions: [
      { label: 'Cancel' },
      { label: 'Create group', variant: 'filled', onClick: submit },
    ],
  });
  const submitBtn = ctrl.footer.lastElementChild;
  render();
  return ctrl;
}

function showInvite(groupId, groupName, hasPassword) {
  openDialog({
    title: 'Group created',
    iconName: 'celebration',
    size: 'sm',
    body: h('div.stack-16', {},
      h('p.body-medium', {}, `Invite people to ${groupName} by sharing this ID${hasPassword ? ' and the password' : ''}.`),
      h('div.id-box', {}, h('span.mono', {}, groupId),
        button('Copy', { variant: 'text', iconName: 'content_copy', onClick: async () => { await copyText(groupId); snackbar('Group ID copied'); } }))),
    actions: [{ label: 'Done', variant: 'filled' }],
  });
}

// ── Appeal ──────────────────────────────────────────────────────────────
export function openAppealDialog(groupId, message, onDone) {
  const explanation = textField({ label: 'Why should this be allowed?', multiline: true, rows: 4, maxlength: 2000, autofocus: true,
    supporting: 'Give context: a quote, a joke between friends, a misunderstanding…' });
  const result = h('div');
  const preview = message.message?.startsWith('[') ? (message.summary || 'Media message') : message.message;
  const ctrl = openDialog({
    title: 'Appeal this decision',
    body: h('div.stack-16', {},
      h('div.card.filled.stack-8', {},
        h('div.label-medium.muted', {}, 'Your message'),
        h('div.body-medium', { style: { whiteSpace: 'pre-wrap', color: 'var(--md-on-surface)' } }, preview),
        h('div.body-small', { style: { color: 'var(--md-error)' } }, `Held because: ${message.reason || 'it broke a group rule.'}`)),
      explanation.el,
      h('p.help', {}, 'The AI takes a second look with your explanation, then the group admin makes the final call.'),
      result),
    actions: [
      { label: 'Cancel' },
      {
        label: 'Send appeal',
        variant: 'filled',
        onClick: async (c) => {
          if (explanation.value.trim().length < 3) {
            explanation.setError('Please add a short explanation.');
            return false;
          }
          c.setBusy(true);
          clear(result).append(spinnerLine('Sending…'));
          const res = await api.appeal(groupId, message.message_id, explanation.value.trim());
          c.setBusy(false);
          clear(result);
          if (!res.success) {
            result.append(errorBox(res.message || 'Could not send the appeal.'));
            return false;
          }
          snackbar(res.ai_status === 'PASS'
            ? 'Appeal sent. The AI agrees it looks fine — the admin will confirm.'
            : 'Appeal sent to the group admin.');
          onDone?.();
          return true;
        },
      },
    ],
  });
  return ctrl;
}

// ── Catch-up ────────────────────────────────────────────────────────────
export function openCatchUp(groupId, groupName) {
  const body = h('div.stack-12', { 'aria-live': 'polite' },
    h('div.skeleton', { style: { width: '70%' } }),
    h('div.skeleton', { style: { width: '92%' } }),
    h('div.skeleton', { style: { width: '84%' } }),
    h('div.skeleton', { style: { width: '60%' } }));
  openDialog({
    title: 'Catch up',
    iconName: 'auto_awesome',
    body,
    actions: [{ label: 'Close', variant: 'text' }],
  });
  api.summary(groupId, 30).then((res) => {
    clear(body);
    if (!res.success) {
      body.append(errorBox(res.message || 'The summary is unavailable right now.'));
      return;
    }
    body.append(
      h('p.title-small', { style: { color: 'var(--md-on-surface)' } }, res.summary.headline || `Recent activity in ${groupName}`),
      h('ul.body-medium', { style: { margin: '0', paddingLeft: '20px', display: 'grid', gap: '8px', color: 'var(--md-on-surface)' } },
        res.summary.bullets.map((item) => h('li', {}, item))),
      h('p.help', {}, 'Summary written by AI from recent messages. It can miss details.'));
  });
}
