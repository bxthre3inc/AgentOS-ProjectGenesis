/**
 * Zo ↔ Antigravity Sync Dashboard — Main JS
 */

const API = 'http://localhost:7880';
let ws;

// ── WebSocket ──────────────────────────────────────────────────────────────────
function connectWS() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws`);

  ws.onopen = () => {
    setWSStatus(true);
    loadAll();
    setInterval(() => ws.readyState === 1 && ws.send('ping'), 20_000);
  };

  ws.onmessage = ({ data }) => {
    const evt = JSON.parse(data);
    if (evt.type === 'pong') return;
    appendEvent(evt);
    handleLiveEvent(evt);
    
    // Mesh Topology Pulses
    if (evt.agent && evt.target_agent) {
      pulseLine(evt.agent, evt.target_agent);
    }
  };

  ws.onclose = () => {
    setWSStatus(false);
    setTimeout(connectWS, 3000);
  };
}

function setWSStatus(online) {
  const dot = document.getElementById('ws-dot');
  const label = document.getElementById('ws-label');
  dot.className = `status-dot ${online ? 'online' : 'offline'}`;
  label.textContent = online ? 'Connected' : 'Reconnecting…';
}

// ── Event stream ───────────────────────────────────────────────────────────────
function appendEvent(evt) {
  const stream = document.getElementById('event-stream');
  const item = document.createElement('div');
  const kind = evt.type || evt.kind || 'event';
  item.className = `event-item ${kind.split('_')[0]}`;

  const now = new Date();
  const time = now.toTimeString().slice(0, 8);

  item.innerHTML = `
    <span class="event-time">${time}</span>
    <span class="event-kind">${kind}</span>
    <span class="event-path">${evt.path || evt.flag || evt.name || evt.command || evt.topic || ''}</span>
  `;
  stream.prepend(item);
  if (stream.children.length > 200) stream.lastChild?.remove();
}

document.getElementById('btn-clear-events')?.addEventListener('click', () => {
  document.getElementById('event-stream').innerHTML = '';
});

// ── Live event handler ─────────────────────────────────────────────────────────
function handleLiveEvent(evt) {
  switch (evt.type) {
    case 'feature_changed': loadFeatures(); break;
    case 'secret_updated':  loadSecrets(); break;
    case 'extension_changed': loadExtensions(); break;
    case 'command_issued':  loadCommands(); break;
    case 'message_sent':    loadMessages(); break;
    case 'session_updated': loadStatus(); loadCockpits(); break;
    default:
      if (evt.kind) loadWorkspace();
  }
}

function pulseLine(from, to) {
  const mapping = {
    'zo': { 'antigravity': 'line-zo-ag', 'agenticbusinessempire': 'line-zo-ao' },
    'antigravity': { 'zo': 'line-zo-ag', 'agenticbusinessempire': 'line-ag-ao' },
    'agenticbusinessempire': { 'zo': 'line-zo-ao', 'antigravity': 'line-ag-ao' }
  };
  const lineId = mapping[from]?.[to] || mapping[to]?.[from];
  if (!lineId) return;
  const el = document.getElementById(lineId);
  if (el) {
    el.classList.remove('pulsing');
    void el.offsetWidth; // trigger reflow
    el.classList.add('pulsing');
    setTimeout(() => el.classList.remove('pulsing'), 800);
  }
}

// ── API helpers ────────────────────────────────────────────────────────────────
async function get(path) {
  const r = await fetch(API + path);
  return r.json();
}
async function post(path, body) {
  const r = await fetch(API + path, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  return r.json();
}
async function del(path) {
  const r = await fetch(API + path, { method: 'DELETE' });
  return r.json();
}

// ── Load all panels ────────────────────────────────────────────────────────────
async function loadAll() {
  await Promise.all([
    loadStatus(), loadWorkspace(), loadFeatures(),
    loadSecrets(), loadExtensions(), loadCommands(), loadMessages(),
    loadCockpits()
  ]);
}

// ── Status ────────────────────────────────────────────────────────────────────
async function loadStatus() {
  const d = await get('/api/status');
  document.getElementById('file-count').textContent = `${d.workspace_files} files`;
  document.getElementById('conn-count').textContent = `${d.connections} clients`;

  const agents = await get('/api/agents');
  for (const a of agents.agents || []) {
    const badge = document.getElementById(`badge-${a.agent_id}`);
    const card  = document.getElementById(`card-${a.agent_id}`);
    if (badge) { badge.textContent = a.status; badge.className = `agent-badge ${a.status}`; }
    if (card)  card.classList.toggle('is-online', a.status === 'online');
  }

  // Also pull peer registry for AgenticBusinessEmpire (may not be in DB sessions yet)
  try {
    const peers = await get('/api/peers');
    for (const p of peers.peers || []) {
      const badge = document.getElementById(`badge-${p.agent_id}`);
      const card  = document.getElementById(`card-${p.agent_id}`);
      const online = p.status === 'online';
      
      if (badge) { 
        let text = p.status;
        if (online && p.latency_ms) text += ` (${p.latency_ms}ms)`;
        badge.textContent = text; 
        badge.className = `agent-badge ${p.status}`; 
      }
      if (card) {
        card.classList.toggle('is-online', online);
        // Update latency sparkline or tag
        let ltag = card.querySelector('.latency-tag');
        if (!ltag) {
          ltag = document.createElement('div');
          ltag.className = 'latency-tag';
          card.appendChild(ltag);
        }
        ltag.textContent = online && p.latency_ms ? `${p.latency_ms} ms` : '--';
      }
    }
  } catch (_) {}
}
setInterval(loadStatus, 8_000);

// ── Workspace ─────────────────────────────────────────────────────────────────
async function loadWorkspace() {
  const d = await get('/api/workspace');
  const grid = document.getElementById('file-grid');
  const files = Object.entries(d.files || {});
  if (!files.length) {
    grid.innerHTML = emptyState('📁', 'No files yet');
    return;
  }
  grid.innerHTML = files.map(([path, info]) => `
    <div class="file-card">
      <div class="file-name">${path.split('/').pop()}</div>
      <div class="file-meta">${path}</div>
      <div class="file-meta">${formatBytes(info.size)}</div>
    </div>
  `).join('');
}
document.getElementById('btn-refresh-ws')?.addEventListener('click', loadWorkspace);

// ── Features ──────────────────────────────────────────────────────────────────
async function loadFeatures() {
  const d = await get('/api/features');
  const grid = document.getElementById('flag-grid');
  grid.innerHTML = (d.features || []).map(f => `
    <div class="flag-item">
      <div class="flag-toggle">
        <input type="checkbox" class="toggle-input" id="flag-${f.name}"
          ${f.enabled ? 'checked' : ''} onchange="toggleFlag('${f.name}', this.checked)" />
        <label class="toggle-label" for="flag-${f.name}"></label>
      </div>
      <div class="flag-info">
        <div class="flag-name">${f.name}</div>
        <div class="flag-desc">${f.description}</div>
      </div>
      <span class="flag-owner">${f.owner}</span>
    </div>
  `).join('');
}

async function toggleFlag(flag, enabled) {
  await post('/api/features/toggle', { flag, enabled, agent_id: 'dashboard', global_scope: true });
  appendEvent({ type: 'feature_changed', flag });
}

// ── Secrets ───────────────────────────────────────────────────────────────────
async function loadSecrets() {
  const d = await get('/api/secrets');
  const list = document.getElementById('secret-list');
  if (!(d.secrets || []).length) {
    list.innerHTML = emptyState('🔐', 'Vault is empty');
    return;
  }
  list.innerHTML = (d.secrets || []).map(s => `
    <div class="secret-item">
      <span class="secret-name">${s.name}</span>
      <span class="secret-vis">${s.visibility}</span>
      <span class="secret-owner">${s.owner}</span>
      <button class="btn-icon" onclick="deleteSecret('${s.name}')" title="Delete">🗑</button>
    </div>
  `).join('');
}

document.getElementById('secret-form')?.addEventListener('submit', async e => {
  e.preventDefault();
  const name  = document.getElementById('sec-name').value.trim();
  const value = document.getElementById('sec-value').value;
  const vis   = document.getElementById('sec-vis').value;
  if (!name || !value) return;
  await post('/api/secrets', { name, value, agent_id: 'dashboard', visibility: vis });
  e.target.reset();
  loadSecrets();
});

async function deleteSecret(name) {
  await del(`/api/secrets/${name}`);
  loadSecrets();
}

// ── Extensions ────────────────────────────────────────────────────────────────
async function loadExtensions() {
  const d = await get('/api/extensions');
  const grid = document.getElementById('ext-grid');
  grid.innerHTML = (d.extensions || []).map(e => `
    <div class="ext-card ${e.enabled ? 'enabled' : ''}">
      <div class="ext-header">
        <span class="ext-name">${e.name}</span>
        <span class="ext-version">v${e.version}</span>
      </div>
      <div class="ext-desc">${e.description}</div>
      <div class="ext-caps">${(e.capabilities || []).map(c => `<span class="ext-cap">${c}</span>`).join('')}</div>
      <div class="ext-compat">Compatible: ${(e.compatible_with || []).join(', ')}</div>
      <div class="form-row" style="margin-top:8px">
        <button class="btn-${e.enabled ? 'ghost' : 'primary'}"
          onclick="toggleExt('${e.id}', ${!e.enabled})">
          ${e.enabled ? 'Disable' : 'Enable'}
        </button>
      </div>
    </div>
  `).join('');
}

async function toggleExt(id, enabled) {
  await post('/api/extensions/toggle', { extension_id: id, enabled });
  loadExtensions();
}

// ── Commands ──────────────────────────────────────────────────────────────────
async function loadCommands() {
  const d = await get('/api/commands');
  const log = document.getElementById('command-log');
  if (!(d.commands || []).length) {
    log.innerHTML = emptyState('⚡', 'No commands yet');
    return;
  }
  log.innerHTML = (d.commands || []).slice(0, 30).map(c => `
    <div class="cmd-item">
      <span class="cmd-issuer">${c.issuer}</span>
      <span class="cmd-arrow">→ ${c.target}</span>
      <span class="cmd-name">${c.command}</span>
      <span class="cmd-status ${c.status}">${c.status}</span>
    </div>
  `).join('');
}

document.getElementById('command-form')?.addEventListener('submit', async e => {
  e.preventDefault();
  const issuer  = document.getElementById('cmd-issuer').value;
  const target  = document.getElementById('cmd-target').value;
  const command = document.getElementById('cmd-name').value;
  const argsRaw = document.getElementById('cmd-args').value.trim();
  let args = {};
  try { if (argsRaw) args = JSON.parse(argsRaw); } catch {}
  await post('/api/commands', { issuer, target, command, args });
  document.getElementById('cmd-args').value = '';
  loadCommands();
});

// ── Messages ──────────────────────────────────────────────────────────────────
async function loadMessages() {
  const d = await get('/api/messages/all?unread_only=false');
  const list = document.getElementById('message-list');
  if (!(d.messages || []).length) {
    list.innerHTML = emptyState('💬', 'No messages yet');
    return;
  }
  list.innerHTML = (d.messages || []).slice(0, 30).map(m => `
    <div class="msg-item ${m.read ? '' : 'msg-unread'}">
      <div class="msg-header">
        <span class="msg-from">${m.from_agent}</span>
        <span class="msg-arrow">→</span>
        <span class="msg-to">${m.to_agent}</span>
        <span class="msg-topic">${m.topic}</span>
        <span class="msg-time">${m.created_at ? m.created_at.slice(11, 19) : ''}</span>
      </div>
      <div class="msg-body">${typeof m.body === 'string' ? m.body : JSON.stringify(m.body)}</div>
    </div>
  `).join('');
}

document.getElementById('message-form')?.addEventListener('submit', async e => {
  e.preventDefault();
  const from_agent = document.getElementById('msg-from').value;
  const to_agent   = document.getElementById('msg-to').value;
  const topic      = document.getElementById('msg-topic').value;
  const bodyRaw    = document.getElementById('msg-body').value.trim();
  let body = bodyRaw;
  try { body = JSON.parse(bodyRaw); } catch {}
  await post('/api/messages', { from_agent, to_agent, topic, body });
  e.target.reset();
  loadMessages();
});

// ── Cockpits ──────────────────────────────────────────────────────────────────
async function loadCockpits() {
  await Promise.all([loadZoCockpit(), loadAGCockpit(), loadAOCockpit()]);
}

async function loadZoCockpit() {
  const msgs = await get('/api/messages/all?unread_only=true');
  const box = document.getElementById('zo-inbox');
  box.innerHTML = (msgs.messages || []).filter(m => m.to_agent === 'zo').map(m => `
    <div class="msg-item msg-unread" style="padding:8px">
      <div style="font-weight:600;font-size:11px">${m.from_agent} · ${m.topic}</div>
      <div style="font-size:11px;color:var(--text-muted)">${m.body}</div>
    </div>
  `).join('') || '<div class="empty-state">No new mail for Zo</div>';
  
  const secs = await get('/api/secrets');
  const sbox = document.getElementById('zo-secrets');
  sbox.innerHTML = (secs.secrets || []).filter(s => s.visibility === 'zo' || s.visibility === 'shared').map(s => `
    <div class="secret-item" style="padding:6px 10px">
      <span style="font-size:11px">${s.name}</span>
      <span class="secret-vis" style="font-size:9px">${s.visibility}</span>
    </div>
  `).join('') || '<div class="empty-state">No secrets</div>';
}

async function loadAGCockpit() {
  // Mocking IDE state for demo — in production this comes from ag_server/get_session
  const tabs = document.getElementById('ag-tabs');
  tabs.innerHTML = ['main.py', 'sync_engine/api.py', 'shared/actions.log'].map(t => `
    <div class="file-card" style="padding:8px 12px;cursor:pointer">
      <div class="file-name" style="font-size:11px">📄 ${t}</div>
    </div>
  `).join('');
  
  const terms = document.getElementById('ag-terminals');
  terms.innerHTML = ['zsh (bridge)', 'npm run dev'].map(t => `
    <div class="file-card" style="padding:8px 12px;border-left:3px solid var(--ag)">
      <div class="file-name" style="font-size:11px"># ${t}</div>
    </div>
  `).join('');
}

async function loadAOCockpit() {
  const workersEl = document.getElementById('ao-workforce');
  const objectiveEl = document.getElementById('ao-objective');
  const progressEl = document.querySelector('#ao-progress .progress-fill');

  try {
    const [wData, sData] = await Promise.all([
      get('/api/agenticbusinessempire/workforce'),
      get('/api/agenticbusinessempire/status')
    ]);

    if (workersEl) {
      workersEl.innerHTML = (wData.workforce || []).map(w => `
        <div class="cmd-item" style="padding:8px;grid-template-columns:1fr auto">
          <div style="font-weight:600">${w.name}: <span style="font-weight:400;color:var(--text-muted)">${w.task}</span></div>
          <span class="cmd-status ${w.state === 'active' ? 'done' : 'queued'}" style="font-size:9px">${w.state}</span>
        </div>
      `).join('') || '<div class="empty-state">No workforce active</div>';
    }

    if (objectiveEl) objectiveEl.textContent = sData.objective || 'Idle';
    if (progressEl)  progressEl.style.width = `${sData.progress || 0}%`;

  } catch (err) {
    console.error('Failed to load AgenticBusinessEmpire Cockpit:', err);
  }
}

// ── Tabs ──────────────────────────────────────────────────────────────────────
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById(`panel-${tab.dataset.tab}`)?.classList.add('active');
  });
});

// ── Utils ─────────────────────────────────────────────────────────────────────
function formatBytes(b) {
  if (b < 1024) return `${b} B`;
  if (b < 1024 ** 2) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1024 ** 2).toFixed(1)} MB`;
}

function emptyState(icon, text) {
  return `<div class="empty-state"><div class="icon">${icon}</div>${text}</div>`;
}

// ── Actions Log ───────────────────────────────────────────────────────────────
const ALOG_COLORS = {
  resource: '#f59e0b', secret: '#f472b6', feature: '#818cf8',
  command: '#7C3AED', message: '#06B6D4', extension: '#34d399',
  session: '#60a5fa', system: '#9ca3af'
};

async function loadActionsLog() {
  const agent = document.getElementById('alog-filter-agent')?.value || '';
  const cat   = document.getElementById('alog-filter-cat')?.value || '';
  const params = new URLSearchParams({ limit: 200 });
  if (agent) params.set('agent', agent);
  if (cat)   params.set('category', cat);
  const d = await get(`/api/actions?${params}`);
  const stream = document.getElementById('alog-stream');
  if (!(d.entries || []).length) {
    stream.innerHTML = emptyState('📋', 'No actions yet');
    return;
  }
  stream.innerHTML = (d.entries || []).map(e => {
    const color = ALOG_COLORS[e.category] || '#9ca3af';
    const detail = e.detail
      ? (typeof e.detail === 'string' ? e.detail : JSON.stringify(e.detail))
      : '';
    const statusBadge = e.status && e.status !== 'ok'
      ? `<span style="color:var(--danger);margin-left:4px">[${e.status}]</span>` : '';
    return `
      <div class="event-item" style="border-color:${color}">
        <span class="event-time">${(e.ts||'').slice(11,19)}</span>
        <span class="event-kind" style="color:${color}">${e.action}</span>
        <span style="font-size:11px;color:var(--text-muted);min-width:80px">${e.agent}</span>
        <span style="font-size:11px;background:var(--surface2);padding:1px 6px;border-radius:4px">${e.category}</span>
        <span class="event-path">${e.path || detail}</span>
        ${e.target_agent ? `<span style="font-size:11px;color:var(--text-muted)">→ ${e.target_agent}</span>` : ''}
        ${statusBadge}
      </div>`;
  }).join('');
}

document.getElementById('btn-refresh-alog')?.addEventListener('click', loadActionsLog);
document.getElementById('btn-clear-alog')?.addEventListener('click', async () => {
  if (!confirm('Clear the entire actions log?')) return;
  await fetch('/api/actions', { method: 'DELETE' });
  loadActionsLog();
});
document.getElementById('alog-filter-agent')?.addEventListener('change', loadActionsLog);
document.getElementById('alog-filter-cat')?.addEventListener('change', loadActionsLog);

// Reload actions log on any live event
const origHandleLive = handleLiveEvent;

// ── Boot ──────────────────────────────────────────────────────────────────────
connectWS();
