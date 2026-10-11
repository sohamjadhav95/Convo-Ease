// Moderation dashboard for group admins: KPIs, review queue, trends, members.
import { h, icon, iconButton, button, avatar, clear, formatListTime, formatClock, parseTime } from './dom.js';
import { api } from './api.js';
import { navigate, refreshGroups } from './store.js';
import { snackbar, openImageViewer, spinnerLine, errorBox } from './ui.js';

const CATEGORY_LABELS = {
  spam: 'Spam',
  hate: 'Harassment',
  sensitive: 'Sensitive',
  'off-topic': 'Off-topic',
  privacy: 'Privacy',
  policy: 'Other rule',
};

const SVG_NS = 'http://www.w3.org/2000/svg';
function s(tag, attrs = {}, ...children) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) if (value != null) el.setAttribute(key, value);
  for (const child of children) if (child != null) el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  return el;
}

export function mountDashboard(container, groupId) {
  let destroyed = false;
  let queueFilter = 'review';
  let people = new Map();
  const person = (username) => people.get(username) || { username, full_name: username };
  let resizeObserver = null;
  const title = h('b', {}, 'Moderation');
  const sub = h('span', {}, '');
  const header = h('header.top-bar', {},
    iconButton('arrow_back', 'Back', () => navigate('moderation'), 'only-compact'),
    h('div.title', { style: { paddingLeft: '4px' } }, title, sub),
    h('div.actions', {},
      iconButton('refresh', 'Refresh', () => load()),
      button('Open chat', { variant: 'text', iconName: 'forum', onClick: () => navigate(`chats/${encodeURIComponent(groupId)}`), extra: 'hide-compact' })));
  const body = h('div.dashboard', {}, spinnerLine('Loading moderation data…'));
  container.append(h('div.chat', {}, header, body));

  async function load() {
    const [groupRes, reportRes, membersRes] = await Promise.all([api.group(groupId), api.report(groupId), api.members(groupId)]);
    if (destroyed) return;
    clear(body);
    if (!groupRes.success || !reportRes.success) {
      body.append(errorBox((reportRes.httpStatus === 403 ? 'Only the group admin can see this dashboard.' : reportRes.message) || 'Could not load the dashboard.'));
      return;
    }
    people = new Map((membersRes.success ? membersRes.profiles : []).map((p) => [p.username, p]));
    const group = groupRes.group;
    const report = reportRes.report;
    title.textContent = group.group_name;
    sub.textContent = `Moderation · ${group.moderation_sensitivity} strictness`;
    render(report);
  }

  function render(report) {
    clear(body);
    if (!report.total_messages) {
      body.append(h('div.empty', {},
        h('div.art', {}, icon('monitoring')),
        h('h2.title-large', {}, 'Nothing to show yet'),
        h('p.body-medium', {}, 'Once people start chatting, you will see what the AI moderator allowed and held back here.')));
      return;
    }
    body.append(kpis(report), h('div.dash-grid', {},
      h('div.dash-col', {}, reviewPanel(report)),
      h('div.dash-col', {}, activityPanel(report), reasonsPanel(report), membersPanel(report))));
  }

  // ── KPI tiles ─────────────────────────────────────────────────────────
  function kpis(report) {
    const tile = (label, iconName, value, suffix, attention) => h(`div.kpi${attention ? '.attention' : ''}`, {},
      h('div.k.label-large', {}, icon(iconName), label),
      h('div.v', {}, String(value), suffix ? h('small', {}, suffix) : null));
    return h('div.kpis', {},
      tile('Checked', 'fact_check', report.total_messages),
      tile('Delivered', 'check_circle', report.pass_rate, '%'),
      tile('Held', 'block', report.flagged_count),
      tile('Appeals waiting', 'gavel', report.pending_appeals, null, report.pending_appeals > 0));
  }

  // ── Review queue ──────────────────────────────────────────────────────
  function reviewPanel(report) {
    const pending = report.flagged_messages.filter((m) => m.appeal_status === 'PENDING_ADMIN');
    const list = h('div');
    const chips = h('div.row-wrap', {});
    const panel = h('section.panel', {},
      h('header', {}, h('h2.title-medium', {}, 'Held messages'), chips), list);

    function draw() {
      clear(chips).append(
        chip('review', `Needs review (${pending.length})`),
        chip('all', `All held (${report.flagged_messages.length})`));
      clear(list);
      const items = queueFilter === 'review' ? pending : report.flagged_messages;
      if (!items.length) {
        list.append(h('p.body-medium.muted', { style: { padding: '12px 0' } }, queueFilter === 'review'
          ? 'No appeals waiting. Nice and quiet.'
          : 'Nothing has been held.'));
        return;
      }
      for (const item of items.slice(0, 50)) list.append(reviewItem(item));
    }
    function chip(value, label) {
      const selected = queueFilter === value;
      return h(`button.chip.state${selected ? '.selected' : ''}`, { type: 'button', 'aria-pressed': String(selected), onclick: () => { queueFilter = value; draw(); } },
        selected ? icon('check') : null, label);
    }
    draw();
    return panel;
  }

  function reviewItem(item) {
    let content;
    if (item.type === 'image') {
      content = h('div.content', {},
        item.media_url ? h('img', { src: item.media_url, alt: item.display, loading: 'lazy', onclick: () => openImageViewer(item.media_url, item.display) }) : null,
        h('span.body-small.muted', {}, `AI description: ${item.display}`));
    } else if (item.type === 'audio') {
      content = h('div.content', {},
        item.media_url ? h('audio', { src: item.media_url, controls: true, preload: 'none', style: { width: '100%', marginBottom: '6px' } }) : null,
        h('span.body-small.muted', {}, `AI summary: ${item.display}`));
    } else {
      content = h('div.content', {}, item.display);
    }

    const pending = item.appeal_status === 'PENDING_ADMIN';
    const node = h('article.review-item', {},
      h('div.who', {}, avatar(person(item.username), 'sm'),
        h('div.text', {}, h('div.title-small', {}, person(item.username).full_name),
          h('div.body-small.muted', {}, whenLabel(item.timestamp))),
        h('span.tag', {}, CATEGORY_LABELS[item.category] || 'Other rule')),
      content,
      h('div.reason.body-medium', {}, icon('block'), h('span', {}, item.reason || 'Breaks a group rule.')));

    if (pending) {
      const aiAllows = item.appeal_ai_status === 'PASS';
      node.append(h('div.appeal', {},
        h('div.label-medium.muted', {}, 'Appeal from the sender'),
        h('div.body-medium', {}, item.appeal_text),
        h('div.row-wrap', {},
          h(`span.tag${aiAllows ? '.primary' : '.error'}`, {}, icon(aiAllows ? 'thumb_up' : 'thumb_down'),
            aiAllows ? 'AI second look: probably fine' : 'AI second look: still breaks rules'),
          item.appeal_ai_reason ? h('span.body-small.muted', {}, item.appeal_ai_reason) : null)));
      const noteInput = h('input', { type: 'text', placeholder: 'Note to the sender (optional)', 'aria-label': 'Note to the sender', maxlength: 1000 });
      const note = h('div.field.dense', {}, noteInput);
      const decide = async (decision, btn) => {
        btn.disabled = true;
        const res = await api.reviewAppeal(groupId, item.message_id, decision, noteInput.value.trim());
        if (!res.success) {
          btn.disabled = false;
          return snackbar(res.message || 'Could not save the decision.');
        }
        snackbar(decision === 'approve' ? 'Message allowed and delivered to the group.' : 'Message stays held.');
        refreshGroups();
        load();
      };
      node.append(h('div.decide', {}, note,
        button('Keep held', { variant: 'outlined', onClick: (e) => decide('reject', e.currentTarget) }),
        button('Allow', { variant: 'filled', iconName: 'check', onClick: (e) => decide('approve', e.currentTarget) })));
    } else if (item.appeal_status === 'REJECTED') {
      node.append(h('div.row-wrap', {}, h('span.tag', {}, icon('gavel'), 'Appeal declined')));
    }
    return node;
  }

  function whenLabel(ts) {
    const day = formatListTime(ts);
    const clock = formatClock(ts);
    return day === clock ? `Today, ${clock}` : `${day}, ${clock}`;
  }

  // ── Activity chart ────────────────────────────────────────────────────
  function activityPanel(report) {
    const points = report.trend_points;
    const showTable = { value: false };
    const holder = h('div.chart-wrap');
    const toggle = button('Table', { variant: 'text', iconName: 'table_rows', onClick: () => { showTable.value = !showTable.value; draw(); } });
    const panel = h('section.panel', {},
      h('header', {}, h('h2.title-medium', {}, 'Activity by day'), toggle),
      holder,
      h('div.legend', {},
        h('span', {}, h('i', { style: { background: 'var(--chart-pass)' } }), 'Delivered'),
        h('span', {}, h('i', { style: { background: 'var(--chart-held)' } }), 'Held')));

    function draw() {
      clear(holder);
      toggle.lastChild.textContent = showTable.value ? 'Chart' : 'Table';
      toggle.querySelector('.ms').textContent = showTable.value ? 'bar_chart' : 'table_rows';
      if (showTable.value) {
        holder.append(h('table.data-table', {},
          h('thead', {}, h('tr', {}, h('th', {}, 'Day'), h('th', {}, 'Delivered'), h('th', {}, 'Held'))),
          h('tbody', {}, points.map((p) => h('tr', {}, h('td', {}, dayLabel(p.date)), h('td', {}, String(p.passed)), h('td', {}, String(p.flagged)))))));
        return;
      }
      const width = Math.round(holder.clientWidth);
      if (width > 0) holder.append(barChart(points, holder, width));
    }
    resizeObserver?.disconnect();
    let lastWidth = 0;
    resizeObserver = new ResizeObserver(() => {
      const width = Math.round(holder.clientWidth);
      if (width && width !== lastWidth) {
        lastWidth = width;
        draw();
      }
    });
    resizeObserver.observe(holder);
    return panel;
  }

  function dayLabel(date) {
    const parsed = parseTime(`${date} 12:00:00`);
    return parsed ? parsed.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : date;
  }

  function barChart(points, holder, W) {
    const H = 220;
    const pad = { top: 12, right: 8, bottom: 26, left: 30 };
    const innerW = W - pad.left - pad.right;
    const innerH = H - pad.top - pad.bottom;
    const max = Math.max(1, ...points.map((p) => p.passed + p.flagged));
    const step = niceStep(max);
    const top = Math.ceil(max / step) * step;
    const y = (value) => pad.top + innerH - (value / top) * innerH;
    const slot = innerW / Math.max(points.length, 1);
    const barW = Math.max(6, Math.min(28, slot * 0.56));
    const svg = s('svg', { viewBox: `0 0 ${W} ${H}`, class: 'chart', role: 'img', 'aria-label': 'Delivered and held messages per day' });

    for (let v = 0; v <= top; v += step) {
      svg.append(s('line', { x1: pad.left, x2: W - pad.right, y1: y(v), y2: y(v), stroke: 'var(--chart-grid)', 'stroke-width': v === 0 ? 1 : 0.5, 'stroke-dasharray': v === 0 ? null : '2 4' }));
      svg.append(s('text', { x: pad.left - 8, y: y(v) + 4, 'text-anchor': 'end' }, String(v)));
    }

    const tip = h('div.chart-tip', { hidden: true });
    holder.append(tip);

    points.forEach((p, index) => {
      const cx = pad.left + slot * index + slot / 2;
      const x = cx - barW / 2;
      const col = s('g', { class: 'col' });
      col.append(s('rect', { class: 'bar-hl', x: cx - slot / 2 + 2, y: pad.top, width: slot - 4, height: innerH, rx: 6, opacity: 0, 'fill-opacity': 0.06 }));
      const passTop = y(p.passed);
      const heldTop = y(p.passed + p.flagged);
      const gap = p.passed && p.flagged ? 2 : 0;
      if (p.passed) col.append(s('path', { d: barPath(x, passTop, barW, y(0) - passTop, p.flagged ? 0 : 4), fill: 'var(--chart-pass)' }));
      if (p.flagged) col.append(s('path', { d: barPath(x, heldTop, barW, Math.max(1, passTop - heldTop - gap), 4), fill: 'var(--chart-held)' }));
      // Narrow columns: label every other day (always including the latest).
      if (slot >= 48 || (points.length - 1 - index) % 2 === 0) {
        svg.append(s('text', { x: cx, y: H - 8, 'text-anchor': 'middle' }, dayLabel(p.date)));
      }
      const hit = s('rect', { class: 'hit', x: cx - slot / 2, y: pad.top, width: slot, height: innerH + pad.bottom });
      hit.addEventListener('pointerenter', () => {
        clear(tip).append(h('b', {}, dayLabel(p.date)), `${p.passed} delivered · ${p.flagged} held`);
        tip.hidden = false;
        tip.style.left = `${cx}px`;
        tip.style.top = `${heldTop}px`;
        col.querySelector('.bar-hl').setAttribute('opacity', '1');
      });
      hit.addEventListener('pointerleave', () => { tip.hidden = true; col.querySelector('.bar-hl').setAttribute('opacity', '0'); });
      col.append(hit);
      svg.append(col);
    });
    return svg;
  }

  function niceStep(max) {
    const rough = max / 4;
    const magnitude = 10 ** Math.floor(Math.log10(Math.max(rough, 1)));
    const options = [1, 2, 5, 10].map((m) => m * magnitude);
    return options.find((o) => o >= rough) || options[options.length - 1];
  }

  function barPath(x, yTop, w, height, radius) {
    const r = Math.min(radius, w / 2, height);
    if (height <= 0) return '';
    return `M${x},${yTop + height}V${yTop + r}Q${x},${yTop} ${x + r},${yTop}H${x + w - r}Q${x + w},${yTop} ${x + w},${yTop + r}V${yTop + height}Z`;
  }

  // ── Reasons ───────────────────────────────────────────────────────────
  function reasonsPanel(report) {
    const panel = h('section.panel', {}, h('header', {}, h('h2.title-medium', {}, 'Why messages were held')));
    if (!report.flag_categories.length) {
      panel.append(h('p.body-medium.muted', {}, 'Nothing held yet.'));
      return panel;
    }
    const max = Math.max(...report.flag_categories.map((c) => c.count));
    for (const cat of report.flag_categories) {
      panel.append(h('div.hbar', {},
        h('span.body-medium', {}, CATEGORY_LABELS[cat.category] || cat.category),
        h('div.track', { role: 'img', 'aria-label': `${cat.count} held` }, h('i', { style: { width: `${(cat.count / max) * 100}%` } })),
        h('span.n', {}, String(cat.count))));
    }
    if (report.flagged_reasons.length) {
      panel.append(h('div.label-medium.muted', { style: { marginTop: '16px' } }, 'Most common reasons'),
        h('ul.body-medium', { style: { margin: '8px 0 0', paddingLeft: '20px', display: 'grid', gap: '6px' } },
          report.flagged_reasons.slice(0, 4).map((r) => h('li', {}, `${r.reason} `, h('span.muted', {}, `(${r.count})`)))));
    }
    return panel;
  }

  // ── Members ───────────────────────────────────────────────────────────
  function membersPanel(report) {
    const panel = h('section.panel', {}, h('header', {}, h('h2.title-medium', {}, 'Members'),
      h('span.body-small.muted', {}, 'Trust score from their message history')));
    const rows = [...report.member_activity].sort((a, b) => a.trust_score - b.trust_score);
    for (const row of rows) {
      const level = row.risk_level;
      const tag = level === 'high'
        ? h('span.tag.error', {}, icon('warning'), 'High risk')
        : level === 'moderate'
          ? h('span.tag', {}, icon('visibility'), 'Watch')
          : h('span.tag.primary', {}, icon('verified'), 'Trusted');
      panel.append(h(`div.trust-row.${level}`, {},
        avatar(person(row.username), 'sm'),
        h('div.text', {}, h('b', {}, person(row.username).full_name),
          h('span.body-small.muted', {}, `${row.sent} delivered · ${row.flagged} held · trust ${row.trust_score}`),
          h('div.meter', { role: 'img', 'aria-label': `Trust ${row.trust_score} of 100` }, h('i', { style: { width: `${row.trust_score}%` } }))),
        tag));
    }
    return panel;
  }

  load();
  return () => {
    destroyed = true;
    resizeObserver?.disconnect();
  };
}
