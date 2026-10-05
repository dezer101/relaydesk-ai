const $ = (selector) => document.querySelector(selector);
const state = { tickets: [], activeId: null, current: null, toastTimer: null };

function initials(name = '') { return name.split(/\s+/).map((part) => part[0] || '').slice(0, 2).join('').toUpperCase(); }
function escapeHtml(value = '') { return String(value).replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch]); }
function showToast(message) { const toast = $('#toast'); toast.textContent = message; toast.classList.add('show'); clearTimeout(state.toastTimer); state.toastTimer = setTimeout(() => toast.classList.remove('show'), 2600); }
async function api(path, options = {}) {
  const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || 'The request could not be completed.');
  return payload;
}

function renderTickets() {
  $('#ticket-count').textContent = String(state.tickets.length).padStart(2, '0');
  $('#queue-open-count').textContent = String(state.tickets.length).padStart(2, '0');
  $('#ticket-list').innerHTML = state.tickets.map((ticket) => `
    <button class="ticket-card ${ticket.id === state.activeId ? 'selected' : ''}" data-ticket="${escapeHtml(ticket.id)}">
      <div class="ticket-topline"><span class="ticket-id">${escapeHtml(ticket.id)}</span><span class="ticket-time">${escapeHtml(ticket.received)}</span></div>
      <h3>${escapeHtml(ticket.subject)}</h3><p>${escapeHtml(ticket.message)}</p>
      <div class="ticket-bottom"><span class="ticket-company">${escapeHtml(ticket.company)}</span><span class="category-chip">${escapeHtml(ticket.channel)}</span></div>
    </button>`).join('');
  document.querySelectorAll('[data-ticket]').forEach((button) => button.addEventListener('click', () => selectTicket(button.dataset.ticket)));
}

function renderEvidence(evidence) {
  $('#evidence-count').textContent = `${evidence.length} SOURCE${evidence.length === 1 ? '' : 'S'}`;
  if (!evidence.length) {
    $('#evidence-list').innerHTML = '<p class="no-evidence">No matching guidance was found. The safe next step is specialist review.</p>';
    return;
  }
  $('#evidence-list').innerHTML = evidence.map((item) => `<details class="evidence-card" ${evidence[0].id === item.id ? 'open' : ''}>
    <summary><span class="source-id">${escapeHtml(item.id)}</span><span class="source-title">${escapeHtml(item.title)}</span><span class="source-score">match ${Math.round(item.score * 100)}%</span></summary>
    <p class="evidence-body">${escapeHtml(item.body)}</p>
  </details>`).join('');
}

function showCase(result) {
  state.current = result;
  const ticket = result.ticket;
  $('#empty-state').classList.add('hidden');
  $('#case-content').classList.remove('hidden');
  $('#analysis-title').textContent = ticket.id;
  $('#ticket-status').textContent = 'REVIEW READY';
  $('#ticket-status').classList.add('ready');
  $('#customer-avatar').textContent = initials(ticket.customer);
  $('#customer-name').textContent = ticket.customer;
  $('#customer-company').textContent = ticket.company;
  $('#ticket-channel').textContent = ticket.channel.toUpperCase();
  $('#ticket-received').textContent = ticket.received;
  $('#ticket-subject').textContent = ticket.subject;
  $('#ticket-message').textContent = ticket.message;
  $('#run-id').textContent = result.run_id;
  $('#category-value').textContent = result.triage.category;
  $('#priority-value').textContent = result.triage.priority;
  $('#priority-value').className = `priority-value ${result.triage.priority.toLowerCase()}`;
  $('#confidence-value').textContent = result.confidence;
  $('#action-reason').textContent = `${result.triage.action.label}: ${result.triage.action.reason}`;
  $('#draft-text').value = result.draft;
  $('#draft-mode').textContent = result.draft_mode;
  $('#approve-btn').disabled = false;
  $('#approve-btn').innerHTML = 'Approve suggested action <span>→</span>';
  $('#approval-feedback').textContent = '';
  $('#rerun-btn').disabled = false;
  renderEvidence(result.evidence);
}

async function selectTicket(ticketId) {
  state.activeId = ticketId;
  renderTickets();
  $('#empty-state').classList.add('hidden');
  $('#case-content').classList.add('hidden');
  $('#analysis-title').textContent = 'Reviewing request…';
  try { showCase(await api('/api/triage', { method: 'POST', body: JSON.stringify({ ticket_id: ticketId }) })); }
  catch (error) { $('#analysis-title').textContent = 'Could not review request'; showToast(error.message); }
}

function shortTime(value) {
  try { return new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit' }).format(new Date(value)); }
  catch { return ''; }
}

async function renderAudit() {
  const data = await api('/api/audit');
  if (!data.events.length) {
    $('#audit-list').innerHTML = '<div class="audit-empty">No activity yet. Triage a sample request, then approve an action to see its history here.</div>';
    return;
  }
  $('#audit-list').innerHTML = data.events.map((event) => `<div class="audit-item">
    <span class="audit-time">${shortTime(event.at)}</span>
    <span class="audit-kind">${event.kind === 'triage' ? 'Triage completed' : 'Action approved'}</span>
    <span class="audit-meta">${escapeHtml(event.ticket_id)}${event.kind === 'triage' ? ` · ${escapeHtml(event.category)} · ${escapeHtml(event.priority)} priority` : ` · ${escapeHtml(event.action_key.replaceAll('_', ' '))}`}</span>
    <span class="audit-tag">${event.kind === 'triage' ? escapeHtml(event.run_id) : 'LOCAL DEMO'}</span>
  </div>`).join('');
}

async function approveAction() {
  if (!state.current) return;
  const button = $('#approve-btn'); button.disabled = true;
  try {
    const action = await api('/api/actions/approve', { method: 'POST', body: JSON.stringify({ ticket_id: state.current.ticket.id, action_key: state.current.triage.action.key }) });
    $('#approval-feedback').textContent = `Approved locally as ${action.id}. No external system was contacted.`;
    button.innerHTML = 'Approved locally <span>✓</span>';
    showToast('Demo action recorded in the local audit trail.');
  } catch (error) { button.disabled = false; showToast(error.message); }
}

async function load() {
  try { state.tickets = await api('/api/tickets'); renderTickets(); }
  catch { showToast('Could not load the sample queue. Restart the local app and try again.'); }
}

document.querySelectorAll('[data-view]').forEach((button) => button.addEventListener('click', async () => {
  const activity = button.dataset.view === 'activity';
  $('#queue-view').classList.toggle('hidden', activity);
  $('#activity-view').classList.toggle('hidden', !activity);
  $('#crumb-current').textContent = activity ? 'Activity log' : 'Triage queue';
  document.querySelectorAll('[data-view]').forEach((nav) => nav.classList.toggle('active', nav === button));
  if (activity) await renderAudit();
}));
$('#approve-btn').addEventListener('click', approveAction);
$('#rerun-btn').addEventListener('click', () => state.activeId && selectTicket(state.activeId));
$('#refresh-btn').addEventListener('click', load);
load();

