// DOM elements
const authBtn = document.getElementById('auth-btn');
const appEl = document.getElementById('app');
const signedOutMsg = document.getElementById('signed-out-msg');
const sessionSelector = document.getElementById('session-selector');
const sessionTabs = document.getElementById('session-tabs');
const sessionOverview = document.getElementById('session-overview');
const dropdownMode = document.getElementById('dropdown-mode');
const liftSelect = document.getElementById('lift-select');
const liftDetail = document.getElementById('lift-detail');
const liftDetailName = document.getElementById('lift-detail-name');
const cuesText = document.getElementById('cues-text');
const historyList = document.getElementById('history-list');
const setGroups = document.getElementById('set-groups');
const addGroupBtn = document.getElementById('add-group-btn');
const notesInput = document.getElementById('notes');
const saveBtn = document.getElementById('save-btn');
const cancelEditBtn = document.getElementById('cancel-edit-btn');

let currentUser = null;
let editingEntryId = null;
let currentSessionIndex = 0;
let currentLiftId = null;
let currentRx = null;
let todayEntries = new Set();
const useSessionMode = typeof SESSIONS !== 'undefined' && SESSIONS.length > 0;

// --- Auth ---
authBtn.addEventListener('click', () => {
  if (currentUser) {
    auth.signOut();
  } else {
    const provider = new firebase.auth.GoogleAuthProvider();
    auth.signInWithPopup(provider).catch((err) => {
      console.error('Sign-in error:', err);
      alert('Sign-in failed. Please try again.');
    });
  }
});

auth.onAuthStateChanged((user) => {
  currentUser = user;
  if (user) {
    authBtn.textContent = 'Sign Out';
    appEl.classList.remove('hidden');
    signedOutMsg.classList.add('hidden');
    document.body.classList.remove('view-only');
    initApp();
  } else {
    authBtn.textContent = 'Sign In';
    appEl.classList.remove('hidden');
    signedOutMsg.classList.add('hidden');
    document.body.classList.add('view-only');
    resetAll();
    initViewOnly();
  }
});

// --- Init ---
async function initApp() {
  if (useSessionMode) {
    sessionSelector.classList.remove('hidden');
    dropdownMode.classList.add('hidden');
    currentSessionIndex = await determineCurrentSession();
    renderSessionTabs();
    loadRecentSessions();
    await loadSession(currentSessionIndex);
  } else {
    sessionSelector.classList.add('hidden');
    sessionOverview.classList.add('hidden');
    dropdownMode.classList.remove('hidden');
    populateDropdown();
  }
}

// --- Session mode ---
async function determineCurrentSession() {
  try {
    const snapshot = await db.collection('users').doc(currentUser.uid)
      .collection('entries')
      .orderBy('date', 'desc')
      .limit(1)
      .get();

    if (snapshot.empty) return 0;

    const data = snapshot.docs[0].data();
    const lastDate = data.date ? data.date.toDate() : new Date();
    const lastSessionId = data.session;

    if (!lastSessionId) return 0;

    const lastIndex = SESSIONS.findIndex((s) => s.id === lastSessionId);
    if (lastIndex === -1) return 0;

    const today = new Date();
    const isToday = lastDate &&
      lastDate.getFullYear() === today.getFullYear() &&
      lastDate.getMonth() === today.getMonth() &&
      lastDate.getDate() === today.getDate();

    return isToday ? lastIndex : (lastIndex + 1) % SESSIONS.length;
  } catch (err) {
    console.error('Error determining session:', err);
    return 0;
  }
}

async function loadRecentSessions() {
  const recentEl = document.getElementById('recent-sessions');
  recentEl.innerHTML = '';

  try {
    // Get recent entries, enough to find 3 distinct sessions
    const snapshot = await db.collection('users').doc(currentUser.uid)
      .collection('entries')
      .orderBy('date', 'desc')
      .limit(50)
      .get();

    const seen = new Map(); // sessionId -> most recent date
    snapshot.forEach((doc) => {
      const data = doc.data();
      if (data.session && !seen.has(data.session) && data.date) {
        seen.set(data.session, data.date.toDate());
      }
    });

    if (seen.size === 0) return;

    const now = new Date();
    // Show in chronological order (most recent first), up to 3
    const entries = [...seen.entries()].slice(0, 3);

    entries.forEach(([sessionId, date]) => {
      const session = SESSIONS.find((s) => s.id === sessionId);
      if (!session) return;

      const nowMidnight = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      const dateMidnight = new Date(date.getFullYear(), date.getMonth(), date.getDate());
      const diffDays = Math.round((nowMidnight - dateMidnight) / (1000 * 60 * 60 * 24));
      let agoStr;
      if (diffDays === 0) agoStr = 'today';
      else if (diffDays === 1) agoStr = '1 day ago';
      else agoStr = `${diffDays} days ago`;

      const item = document.createElement('div');
      item.className = 'recent-session-item';
      item.innerHTML = `<span class="recent-session-name">${escapeHtml(session.name)}</span> <span class="recent-session-ago">${agoStr}</span>`;
      recentEl.appendChild(item);
    });
  } catch (err) {
    console.error('Error loading recent sessions:', err);
  }
}

function renderSessionTabs() {
  sessionTabs.innerHTML = '';
  SESSIONS.forEach((session, i) => {
    const tab = document.createElement('button');
    tab.className = 'session-tab' + (i === currentSessionIndex ? ' active' : '');
    tab.textContent = session.name;
    tab.addEventListener('click', () => {
      currentSessionIndex = i;
      renderSessionTabs();
      loadSession(i);
    });
    sessionTabs.appendChild(tab);
  });
}

async function loadSession(index) {
  currentLiftId = null;
  currentRx = null;
  liftDetail.classList.add('hidden');
  await loadTodayEntries();
  renderSessionOverview(SESSIONS[index]);
  sessionOverview.classList.remove('hidden');
}

async function loadTodayEntries() {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  try {
    const snapshot = await db.collection('users').doc(currentUser.uid)
      .collection('entries')
      .where('date', '>=', firebase.firestore.Timestamp.fromDate(today))
      .get();

    todayEntries = new Set();
    snapshot.forEach((doc) => todayEntries.add(doc.data().lift));
  } catch (err) {
    console.error('Error loading today entries:', err);
    todayEntries = new Set();
  }
}

function renderSessionOverview(session) {
  sessionOverview.innerHTML = '';

  session.lifts.forEach((item) => {
    if (item.choose) {
      const group = document.createElement('div');
      group.className = 'choice-group';

      const label = document.createElement('div');
      label.className = 'choice-label';
      label.textContent = item.note ? `pick one \u2014 ${item.note}` : 'pick one';
      group.appendChild(label);

      item.choose.forEach((choice) => {
        const lift = LIFTS.find((l) => l.id === choice.liftId);
        if (!lift) return;
        group.appendChild(createOverviewRow(lift, choice.rx, choice.liftId));
      });

      sessionOverview.appendChild(group);
    } else {
      const lift = LIFTS.find((l) => l.id === item.liftId);
      if (!lift) return;
      sessionOverview.appendChild(createOverviewRow(lift, item.rx, item.liftId));
    }
  });
}

function createOverviewRow(lift, rx, liftId) {
  const row = document.createElement('div');
  const done = todayEntries.has(liftId);
  row.className = 'session-lift' + (done ? ' completed' : '');
  row.dataset.liftId = liftId;

  row.innerHTML = `
    <span class="lift-name">${escapeHtml(lift.name)}</span>
    <span class="lift-rx">${escapeHtml(rx)}</span>
    <span class="lift-check">${done ? '\u2713' : ''}</span>
  `;

  row.addEventListener('click', () => selectLift(liftId, rx));
  return row;
}

async function selectLift(liftId, rx) {
  currentLiftId = liftId;
  currentRx = rx;
  const lift = LIFTS.find((l) => l.id === liftId);

  // Highlight in overview
  document.querySelectorAll('.session-lift').forEach((el) => {
    el.classList.toggle('selected', el.dataset.liftId === liftId);
  });

  // Show detail
  liftDetailName.textContent = lift.name;
  cuesText.textContent = lift.cues;
  liftDetail.classList.remove('hidden');

  // Reset form and auto-fill sets/reps from rx
  resetSetGroups();
  const parsed = parseRx(rx);
  if (parsed) {
    const row = setGroups.querySelector('.set-group-row');
    row.querySelector('.input-sets').value = parsed.maxSets;
    row.querySelector('.input-reps').value = parsed.maxReps;
  }

  // Load history only when signed in
  if (currentUser) {
    await loadHistory(liftId);
  } else {
    historyList.innerHTML = '';
  }

  liftDetail.scrollIntoView({ behavior: 'smooth' });
}

function parseRx(rx) {
  if (!rx) return null;
  let str = rx;

  // Handle "alt: 3x5, 4x5-6" — take the last scheme
  if (str.toLowerCase().startsWith('alt:')) {
    const parts = str.substring(4).split(',');
    str = parts[parts.length - 1].trim();
  }

  // Strip "/side" suffix
  str = str.replace(/\/side/i, '');

  const match = str.match(/(\d+)(?:\s*-\s*(\d+))?\s*[×x]\s*(\d+)(?:\s*-\s*(\d+))?/i);
  if (!match) return null;
  return {
    maxSets: parseInt(match[2] || match[1]),
    maxReps: parseInt(match[4] || match[3])
  };
}

// --- Dropdown mode (fallback when no SESSIONS) ---
function populateDropdown() {
  liftSelect.innerHTML = '<option value="">— Choose a lift —</option>';
  LIFTS.forEach((lift) => {
    const opt = document.createElement('option');
    opt.value = lift.id;
    opt.textContent = lift.name;
    liftSelect.appendChild(opt);
  });
}

liftSelect.addEventListener('change', () => {
  const liftId = liftSelect.value;
  if (!liftId) {
    liftDetail.classList.add('hidden');
    return;
  }

  const lift = LIFTS.find((l) => l.id === liftId);
  currentLiftId = liftId;
  currentRx = null;
  liftDetailName.textContent = lift.name;
  cuesText.textContent = lift.cues;
  liftDetail.classList.remove('hidden');
  resetSetGroups();
  loadHistory(liftId);
});

// --- Set groups ---
function createSetGroupRow() {
  const row = document.createElement('div');
  row.className = 'set-group-row';
  row.innerHTML = `
    <input type="number" class="input-sets" placeholder="Sets" min="1" inputmode="numeric">
    <span class="multiply">\u00d7</span>
    <input type="number" class="input-reps" placeholder="Reps" min="1" inputmode="numeric">
    <span class="at-sign">@</span>
    <input type="number" class="input-weight" placeholder="Weight" min="0" step="0.5" inputmode="decimal">
    <button type="button" class="btn-remove-group" title="Remove">&times;</button>
  `;
  row.querySelector('.btn-remove-group').addEventListener('click', () => {
    if (setGroups.children.length > 1) row.remove();
  });
  return row;
}

function resetSetGroups() {
  setGroups.innerHTML = '';
  setGroups.appendChild(createSetGroupRow());
  notesInput.value = '';
}

addGroupBtn.addEventListener('click', () => {
  setGroups.appendChild(createSetGroupRow());
});

// --- Save ---
saveBtn.addEventListener('click', async () => {
  if (!currentUser || !currentLiftId) return;

  const groups = [];
  let valid = true;

  setGroups.querySelectorAll('.set-group-row').forEach((row) => {
    const sets = parseInt(row.querySelector('.input-sets').value);
    const reps = parseInt(row.querySelector('.input-reps').value);
    const weight = parseFloat(row.querySelector('.input-weight').value);

    if (!sets || !reps || isNaN(weight)) {
      valid = false;
      return;
    }
    groups.push({ sets, reps, weight });
  });

  if (!valid || groups.length === 0) {
    alert('Please fill in sets, reps, and weight for each group.');
    return;
  }

  saveBtn.disabled = true;
  saveBtn.textContent = editingEntryId ? 'Updating...' : 'Saving...';

  try {
    if (editingEntryId) {
      await db.collection('users').doc(currentUser.uid)
        .collection('entries').doc(editingEntryId)
        .update({ sets: groups, notes: notesInput.value.trim() });

      editingEntryId = null;
      cancelEditBtn.classList.add('hidden');
      document.getElementById('edit-mode-banner').classList.add('hidden');
    } else {
      const entry = {
        lift: currentLiftId,
        date: firebase.firestore.FieldValue.serverTimestamp(),
        sets: groups,
        notes: notesInput.value.trim()
      };

      // Tag with session ID for auto-rotate
      if (useSessionMode) {
        entry.session = SESSIONS[currentSessionIndex].id;
      }

      await db.collection('users').doc(currentUser.uid)
        .collection('entries').add(entry);

      // Update completion status
      todayEntries.add(currentLiftId);

      if (useSessionMode) {
        renderSessionOverview(SESSIONS[currentSessionIndex]);
        // Re-highlight current lift
        document.querySelectorAll('.session-lift').forEach((el) => {
          el.classList.toggle('selected', el.dataset.liftId === currentLiftId);
        });
      }
    }

    resetSetGroups();
    await loadHistory(currentLiftId);

    // Re-apply auto-fill from rx
    if (currentRx) {
      const parsed = parseRx(currentRx);
      if (parsed) {
        const row = setGroups.querySelector('.set-group-row');
        row.querySelector('.input-sets').value = parsed.maxSets;
        row.querySelector('.input-reps').value = parsed.maxReps;
      }
    }
  } catch (err) {
    console.error('Save error:', err);
    alert('Failed to save. Please try again.');
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = editingEntryId ? 'Update' : 'Save';
  }
});

// --- History ---
async function loadHistory(liftId) {
  if (!currentUser) return;

  historyList.innerHTML = '<p class="loading">Loading...</p>';

  try {
    const snapshot = await db.collection('users').doc(currentUser.uid)
      .collection('entries')
      .where('lift', '==', liftId)
      .orderBy('date', 'desc')
      .limit(5)
      .get();

    if (snapshot.empty) {
      historyList.innerHTML = '<p class="empty">No history yet.</p>';
      return;
    }

    historyList.innerHTML = '';
    let lastWeight = null;

    snapshot.forEach((doc) => {
      const data = doc.data();
      const entry = document.createElement('div');
      entry.className = 'history-entry';

      const date = data.date ? data.date.toDate() : new Date();
      const dateStr = date.toLocaleDateString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric'
      });

      const setsStr = data.sets.map((g) => `${g.sets}\u00d7${g.reps}@${g.weight}`).join(', ');

      // Grab weight from most recent entry for auto-fill
      if (lastWeight === null && data.sets.length > 0) {
        lastWeight = data.sets[0].weight;
      }

      entry.innerHTML = `
        <div class="history-header">
          <div class="history-date">${dateStr}</div>
          <button class="btn-edit-entry" type="button">Edit</button>
        </div>
        <div class="history-sets">${setsStr}</div>
        ${data.notes ? `<div class="history-notes">${escapeHtml(data.notes)}</div>` : ''}
      `;
      entry.querySelector('.btn-edit-entry').addEventListener('click', () => startEdit(doc.id, data));
      historyList.appendChild(entry);
    });

    // Auto-fill weight from last session
    if (lastWeight !== null) {
      const firstRow = setGroups.querySelector('.set-group-row');
      if (firstRow) {
        const weightInput = firstRow.querySelector('.input-weight');
        if (!weightInput.value) {
          weightInput.value = lastWeight;
        }
      }
    }
  } catch (err) {
    console.error('History load error:', err);
    historyList.innerHTML = '<p class="empty">Failed to load history.</p>';
  }
}

// --- Edit entry ---
function startEdit(docId, data) {
  editingEntryId = docId;

  setGroups.innerHTML = '';
  data.sets.forEach((g) => {
    const row = createSetGroupRow();
    row.querySelector('.input-sets').value = g.sets;
    row.querySelector('.input-reps').value = g.reps;
    row.querySelector('.input-weight').value = g.weight;
    setGroups.appendChild(row);
  });
  notesInput.value = data.notes || '';

  saveBtn.textContent = 'Update';
  cancelEditBtn.classList.remove('hidden');
  document.getElementById('edit-mode-banner').classList.remove('hidden');
  document.querySelector('.log-form').scrollIntoView({ behavior: 'smooth' });
}

cancelEditBtn.addEventListener('click', () => {
  editingEntryId = null;
  saveBtn.textContent = 'Save';
  cancelEditBtn.classList.add('hidden');
  document.getElementById('edit-mode-banner').classList.add('hidden');
  resetSetGroups();
  if (currentRx) {
    const parsed = parseRx(currentRx);
    if (parsed) {
      const row = setGroups.querySelector('.set-group-row');
      row.querySelector('.input-sets').value = parsed.maxSets;
      row.querySelector('.input-reps').value = parsed.maxReps;
    }
  }
});

// --- View-only mode (no auth) ---
function initViewOnly() {
  if (useSessionMode) {
    sessionSelector.classList.remove('hidden');
    dropdownMode.classList.add('hidden');
    currentSessionIndex = 0;
    renderSessionTabs();
    sessionOverview.classList.remove('hidden');
    renderSessionOverview(SESSIONS[0]);
  } else {
    sessionSelector.classList.add('hidden');
    sessionOverview.classList.add('hidden');
    dropdownMode.classList.remove('hidden');
    populateDropdown();
  }
}

// --- Helpers ---
function resetAll() {
  currentLiftId = null;
  currentRx = null;
  liftDetail.classList.add('hidden');
  sessionOverview.classList.add('hidden');
  setGroups.innerHTML = '';
  notesInput.value = '';
  if (liftSelect) liftSelect.value = '';
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
