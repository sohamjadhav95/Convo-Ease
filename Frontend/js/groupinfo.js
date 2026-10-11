// Group details side sheet: invite, moderation settings, rules, members.
import { h, iconButton, button, avatar, clear, copyText, plural } from './dom.js';
import { api } from './api.js';
import { store, navigate, refreshGroups } from './store.js';
import { openSheet, snackbar, confirmDialog, segmented, textField, spinnerLine } from './ui.js';
import { rulesEditor, SENSITIVITY, sensitivityHelp } from './groupdialogs.js';

export function openGroupInfo(groupId, { onChanged } = {}) {
  const sheet = openSheet({ title: 'Group details', body: spinnerLine('Loading…') });
  load();

  async function load() {
    const [groupRes, membersRes, reportRes] = await Promise.all([
      api.group(groupId),
      api.members(groupId),
      store.groups.find((g) => g.group_id === groupId)?.is_admin ? api.report(groupId) : Promise.resolve(null),
    ]);
    if (!groupRes.success) {
      clear(sheet.content).append(h('p', {}, groupRes.message || 'Could not load this group.'));
      return;
    }
    const risk = {};
    if (reportRes?.success) {
      for (const row of reportRes.report.member_activity) risk[row.username] = row;
    }
    render(groupRes.group, membersRes.success ? membersRes.profiles : [], risk);
  }

  function render(group, members, risk) {
    const admin = group.is_admin;
    const body = sheet.content;
    clear(body);

    // Hero + name
    const nameLine = h('div.title-large', {}, group.group_name);
    const hero = h('div.info-hero', {}, avatar(group, 'xl'), nameLine,
      h('div.body-medium.muted', {}, `Group · ${plural(members.length, 'member')}`));
    if (admin) {
      hero.append(button('Rename', { variant: 'text', iconName: 'edit', onClick: () => rename(group, hero) }));
    }
    body.append(hero);

    // Invite
    body.append(h('div.section', {},
      h('h3.title-small', {}, 'Invite people'),
      h('div.id-box', {}, h('span.mono', { 'aria-label': 'Group ID' }, group.group_id),
        iconButton('content_copy', 'Copy group ID', async () => { await copyText(group.group_id); snackbar('Group ID copied'); })),
      h('p.help', {}, group.has_password
        ? 'People need this ID and the group password to join.'
        : 'Anyone with this ID can join.')));

    // Moderation strictness
    const sensSection = h('div.section', {}, h('h3.title-small', {}, 'Moderation strictness'));
    if (admin) {
      const help = h('p.help', {}, sensitivityHelp(group.moderation_sensitivity));
      const seg = segmented(SENSITIVITY, group.moderation_sensitivity, async (value) => {
        help.textContent = sensitivityHelp(value);
        const res = await api.updateRules(groupId, group.rules, value);
        if (!res.success) {
          seg.set(group.moderation_sensitivity);
          return snackbar(res.message || 'Could not save.');
        }
        group.moderation_sensitivity = value;
        snackbar(`Moderation set to ${value}`);
        onChanged?.();
      }, { label: 'Moderation strictness' });
      sensSection.append(seg.el, help);
    } else {
      sensSection.append(h('p.body-medium', { style: { color: 'var(--md-on-surface)' } }, group.moderation_sensitivity),
        h('p.help', {}, sensitivityHelp(group.moderation_sensitivity)));
    }
    body.append(sensSection);

    // Rules
    const rulesSection = h('div.section', {});
    const rulesView = () => {
      clear(rulesSection).append(
        h('div.row-between', { style: { marginBottom: '12px' } }, h('h3.title-small', { style: { margin: 0 } }, 'Rules'),
          admin ? button('Edit', { variant: 'text', iconName: 'edit', onClick: rulesEdit }) : null),
        h('div.rules-text.body-medium', {}, group.rules || 'No rules yet — everything is allowed.'));
    };
    const rulesEdit = () => {
      const editor = rulesEditor({ value: group.rules, groupName: () => group.group_name });
      clear(rulesSection).append(h('h3.title-small', {}, 'Edit rules'), editor.el,
        h('div.row-wrap', { style: { justifyContent: 'flex-end', marginTop: '12px' } },
          button('Cancel', { onClick: rulesView }),
          button('Save rules', {
            variant: 'filled',
            onClick: async (event) => {
              const saveBtn = event.currentTarget;
              saveBtn.disabled = true;
              const res = await api.updateRules(groupId, editor.value, group.moderation_sensitivity);
              if (!res.success) {
                saveBtn.disabled = false;
                return snackbar(res.message || 'Could not save the rules.');
              }
              group.rules = editor.value;
              snackbar('Rules saved. New messages follow them right away.');
              rulesView();
              onChanged?.();
            },
          })));
      editor.field.input.focus();
    };
    rulesView();
    body.append(rulesSection);

    // Members
    const membersSection = h('div.section', {}, h('h3.title-small', {}, `Members (${members.length})`));
    for (const member of members) {
      const stats = risk[member.username];
      let tag = null;
      if (member.is_admin) tag = h('span.tag.primary', {}, 'Admin');
      else if (stats?.risk_level === 'high') tag = h('span.tag.error', {}, `Trust ${stats.trust_score}`);
      else if (stats?.risk_level === 'moderate') tag = h('span.tag', {}, `Trust ${stats.trust_score}`);
      membersSection.append(h('div.member-row', {}, avatar(member),
        h('div.text', {}, h('b', {}, member.username === store.user.username ? `${member.full_name} (you)` : member.full_name),
          h('span', {}, `@${member.username}`)),
        tag));
    }
    body.append(membersSection);

    // Leave / delete
    body.append(h('div.section', {}, admin
      ? button('Delete group', { variant: 'outlined', iconName: 'delete', extra: 'danger', onClick: () => remove(group) })
      : button('Leave group', { variant: 'outlined', iconName: 'logout', extra: 'danger', onClick: () => leave(group) })));
  }

  function rename(group, hero) {
    const field = textField({ label: 'Group name', value: group.group_name, maxlength: 120 });
    const form = h('form.stack-8', { style: { width: '100%' } }, field.el,
      h('div.row-wrap', { style: { justifyContent: 'flex-end' } },
        button('Cancel', { onClick: () => load() }),
        button('Save', { variant: 'filled', type: 'submit' })));
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const name = field.value.trim();
      if (!name) return field.setError('Enter a name.');
      const res = await api.renameGroup(groupId, name);
      if (!res.success) return snackbar(res.message || 'Could not rename.');
      snackbar('Group renamed');
      onChanged?.();
      load();
    });
    clear(hero).append(avatar(group, 'xl'), form);
    field.input.focus();
    field.input.select();
  }

  async function leave(group) {
    const ok = await confirmDialog({ title: `Leave ${group.group_name}?`, message: "You'll stop seeing its messages. You can rejoin with the group ID.", confirmLabel: 'Leave', danger: true });
    if (!ok) return;
    const res = await api.leaveGroup(groupId);
    if (!res.success) return snackbar(res.message || 'Could not leave the group.');
    sheet.close();
    await refreshGroups();
    navigate('chats');
    snackbar('You left the group');
  }

  async function remove(group) {
    const ok = await confirmDialog({
      title: `Delete ${group.group_name}?`,
      message: 'All messages, images and voice notes in this group are deleted for everyone. This cannot be undone.',
      confirmLabel: 'Delete group',
      danger: true,
      iconName: 'delete_forever',
    });
    if (!ok) return;
    const res = await api.deleteGroup(groupId);
    if (!res.success) return snackbar(res.message || 'Could not delete the group.');
    sheet.close();
    await refreshGroups();
    navigate('chats');
    snackbar('Group deleted');
  }

  return sheet;
}

