// App shell: navigation rail / bottom bar, list pane and content pane.
import { h, icon, avatar, clear, logo, formatListTime, button } from './dom.js';
import { store, on, refreshGroups, parseRoute } from './store.js';
import { openNewGroupDialog } from './groupdialogs.js';
import { mountChat } from './chat.js';
import { mountDashboard } from './dashboard.js';
import { mountSettings } from './settings.js';

let els = null;
let unmountContent = null;
let currentKey = '';
let groupsTimer = null;

export function mountShell(root) {
  clear(root);
  const listPane = h('section.list-pane', { 'aria-label': 'Groups' });
  const contentPane = h('main.content-pane');
  const rail = h('nav.rail', { 'aria-label': 'Main' });
  const bottomNav = h('nav.bottom-nav', { 'aria-label': 'Main' });
  const shell = h('div.shell', {}, rail, listPane, contentPane, bottomNav);
  root.append(shell);
  els = { shell, rail, listPane, contentPane, bottomNav };

  on('groups', () => { renderNav(); renderList(); updateTitle(); });
  on('route', () => route());
  on('user', () => renderNav());

  route();
  refreshGroups();
  clearInterval(groupsTimer);
  groupsTimer = setInterval(() => {
    if (!document.hidden) refreshGroups();
  }, 8000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refreshGroups(); });
}

export function unmountShell() {
  clearInterval(groupsTimer);
  unmountContent?.();
  unmountContent = null;
  currentKey = '';
  els = null;
}

function totals() {
  let unread = 0;
  let appeals = 0;
  for (const group of store.groups) {
    unread += group.unread_count || 0;
    appeals += group.pending_appeals || 0;
  }
  return { unread, appeals };
}

function updateTitle() {
  const { unread } = totals();
  document.title = unread ? `(${unread}) ConvoEase` : 'ConvoEase';
}

function navItem(section, label, iconName, badge) {
  const { section: active } = parseRoute();
  const isActive = active === section;
  return h(`a.rail-item${isActive ? '.active' : ''}`, {
    href: `#/${section}`,
    'aria-current': isActive ? 'page' : undefined,
  },
  h('span.pill.state', {}, icon(iconName), badge ? h('span.badge', {}, badge > 99 ? '99+' : String(badge)) : null),
  label);
}

function renderNav() {
  if (!els) return;
  const { unread, appeals } = totals();
  const admin = store.groups.some((group) => group.is_admin);
  const items = () => [
    navItem('chats', 'Chats', 'forum', unread),
    admin ? navItem('moderation', 'Moderation', 'shield_person', appeals) : null,
    navItem('settings', 'Settings', 'settings'),
  ];
  clear(els.rail).append(
    h('a.brand', { href: '#/chats', title: 'ConvoEase', 'aria-label': 'ConvoEase home' }, logo()),
    h('button.fab.state', { type: 'button', title: 'New group', 'aria-label': 'Create or join a group', onclick: () => openNewGroupDialog() }, icon('edit_square')),
    ...items().filter(Boolean),
    h('div.spacer'),
    h('a.me', { href: '#/settings', title: 'Your profile', 'aria-label': 'Your profile' }, avatar(store.user)),
  );
  clear(els.bottomNav).append(...items().filter(Boolean));
}

// ── List pane ───────────────────────────────────────────────────────────
function renderList() {
  if (!els) return;
  const { section, id } = parseRoute();
  if (section === 'settings') return;
  const pane = els.listPane;
  const moderation = section === 'moderation';
  const searchInput = pane.querySelector('.search-bar input');
  const hadFocus = document.activeElement === searchInput;

  clear(pane);
  pane.append(h('div.pane-header', {}, h('h1.headline-small', {}, moderation ? 'Moderation' : 'Chats')));

  if (!moderation) {
    const input = h('input', {
      type: 'search', placeholder: 'Search groups', 'aria-label': 'Search groups', value: store.filter.q,
      oninput: (event) => { store.filter.q = event.target.value; renderItems(); },
    });
    pane.append(h('label.search-bar', {}, icon('search'), input));
    const chips = [['all', 'All'], ['unread', 'Unread'], ['admin', "I'm admin"]];
    pane.append(h('div.chip-row', { role: 'group', 'aria-label': 'Filter' }, chips.map(([value, label]) => {
      const selected = store.filter.chip === value;
      return h(`button.chip.state${selected ? '.selected' : ''}`, {
        type: 'button', 'aria-pressed': String(selected),
        onclick: () => { store.filter.chip = value; renderList(); },
      }, selected ? icon('check') : null, label);
    })));
    if (hadFocus) requestAnimationFrame(() => { input.focus(); input.setSelectionRange(input.value.length, input.value.length); });
  } else {
    pane.append(h('p.body-medium.muted', { style: { padding: '0 24px 12px' } }, 'Groups you manage. Review held messages and appeals.'));
  }

  const list = h('nav.list-scroll', { 'aria-label': moderation ? 'Groups you manage' : 'Your groups' });
  pane.append(list, h('button.fab.extended.list-fab.state', { type: 'button', onclick: () => openNewGroupDialog() }, icon('edit_square'), 'New group'));

  function renderItems() {
    clear(list);
    let groups = store.groups;
    if (moderation) groups = groups.filter((group) => group.is_admin);
    const q = store.filter.q.trim().toLowerCase();
    if (!moderation && q) groups = groups.filter((group) => group.group_name.toLowerCase().includes(q) || group.group_id.toLowerCase().includes(q));
    if (!moderation && store.filter.chip === 'unread') groups = groups.filter((group) => group.unread_count > 0);
    if (!moderation && store.filter.chip === 'admin') groups = groups.filter((group) => group.is_admin);

    if (!store.groupsLoaded) {
      list.append(...[0, 1, 2].map(() => h('div.list-item', {}, h('div.avatar.lg.skeleton'), h('div.text.stack-8', {}, h('div.skeleton', { style: { width: '60%' } }), h('div.skeleton', { style: { width: '85%' } })))));
      return;
    }
    if (!groups.length) {
      list.append(emptyList(moderation, Boolean(q) || store.filter.chip !== 'all'));
      return;
    }
    for (const group of groups) list.append(moderation ? moderationItem(group, id) : groupItem(group, id));
  }
  renderItems();
}

function groupItem(group, activeId) {
  const unread = group.unread_count > 0;
  const sender = group.last_message_user === store.user.username
    ? 'You'
    : (group.last_message_name || group.last_message_user || '').split(' ')[0];
  const preview = group.last_message ? `${sender ? `${sender}: ` : ''}${group.last_message}` : 'No messages yet';
  return h(`a.list-item.group-item.state${group.group_id === activeId ? '.selected' : ''}${unread ? '.unread' : ''}`, {
    href: `#/chats/${encodeURIComponent(group.group_id)}`,
    'aria-current': group.group_id === activeId ? 'true' : undefined,
  },
  avatar(group, 'lg'),
  h('div.text', {},
    h('div.headline', {}, h('span', {}, group.group_name), group.is_admin ? h('span.admin-mark', {}, 'Admin') : null),
    h('div.supporting', {}, preview)),
  h('div.meta', {}, h('span', {}, formatListTime(group.last_message_at)), unread ? h('span.count', { 'aria-label': `${group.unread_count} unread` }, String(group.unread_count)) : null));
}

function moderationItem(group, activeId) {
  const parts = [];
  if (group.pending_appeals) parts.push(`${group.pending_appeals} appeal${group.pending_appeals > 1 ? 's' : ''} to review`);
  parts.push(`${group.held_count || 0} held`);
  return h(`a.list-item.group-item.state${group.group_id === activeId ? '.selected' : ''}`, {
    href: `#/moderation/${encodeURIComponent(group.group_id)}`,
  },
  avatar(group, 'lg'),
  h('div.text', {}, h('div.headline', {}, h('span', {}, group.group_name)), h('div.supporting', {}, parts.join(' · '))),
  group.pending_appeals ? h('span.count', {}, String(group.pending_appeals)) : icon('chevron_right'));
}

function emptyList(moderation, filtered) {
  if (filtered) return h('div.empty', {}, h('p', {}, 'No groups match.'));
  if (moderation) return h('div.empty', {}, h('p', {}, "You don't manage any groups yet."));
  return h('div.empty', {},
    h('div.art', {}, icon('forum')),
    h('h2.title-medium', {}, 'No groups yet'),
    h('p.body-medium', {}, 'Create a group with your own rules, or join one with its ID.'),
    h('div.actions', {},
      button('Create group', { variant: 'filled', iconName: 'add', onClick: () => openNewGroupDialog('create') }),
      button('Join with ID', { variant: 'outlined', onClick: () => openNewGroupDialog('join') })));
}

// ── Content pane ────────────────────────────────────────────────────────
function route() {
  if (!els) return;
  const { section, id } = parseRoute();
  els.shell.classList.toggle('wide-content', section === 'settings');
  els.shell.classList.toggle('show-content', Boolean(id) || section === 'settings');
  renderNav();
  renderList();

  const key = `${section}/${id}`;
  if (key === currentKey) return;
  currentKey = key;
  unmountContent?.();
  unmountContent = null;
  clear(els.contentPane);

  if (section === 'settings') {
    unmountContent = mountSettings(els.contentPane);
  } else if (section === 'moderation' && id) {
    unmountContent = mountDashboard(els.contentPane, id);
  } else if (section === 'chats' && id) {
    unmountContent = mountChat(els.contentPane, id);
  } else {
    els.contentPane.append(contentEmpty(section));
  }
}

function contentEmpty(section) {
  const moderation = section === 'moderation';
  return h('div.empty', { style: { flex: '1' } },
    h('div.art', {}, icon(moderation ? 'shield_person' : 'forum')),
    h('h2.title-large', {}, moderation ? 'Pick a group to review' : 'Pick a chat'),
    h('p.body-medium', { style: { maxWidth: '360px' } }, moderation
      ? 'See what the AI moderator held back, why, and decide on appeals.'
      : 'Every message is checked against the group rules before anyone sees it.'),
    moderation ? null : h('div.actions', {},
      button('New group', { variant: 'tonal', iconName: 'add', onClick: () => openNewGroupDialog('create') }),
      button('Join with ID', { variant: 'text', onClick: () => openNewGroupDialog('join') })));
}
