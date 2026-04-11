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
let currentActiveChoices = new Map();
const useSessionMode = typeof SESSIONS !== 'undefined' && SESSIONS.length > 0;

// In-memory cache: liftId -> [{id, data}]
const historyCache = new Map();
const historyRefreshSpinner = document.getElementById('history-refresh-spinner');

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

    const now = new Date();
    const nowMidnight = new Date(now.getFullYear(), now.getMonth(), now.getDate());

    // Render one label per session in tab order so they align under the buttons
    SESSIONS.forEach((session) => {
      const item = document.createElement('div');
      item.className = 'recent-session-item';

      const date = seen.get(session.id);
      if (date) {
        const dateMidnight = new Date(date.getFullYear(), date.getMonth(), date.getDate());
        const diffDays = Math.round((nowMidnight - dateMidnight) / (1000 * 60 * 60 * 24));
        if (diffDays === 0) item.textContent = 'today';
        else if (diffDays === 1) item.textContent = '1d ago';
        else item.textContent = `${diffDays}d ago`;
      }

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
  currentActiveChoices = await resolveChoiceGroups(SESSIONS[index]);
  renderSessionOverview(SESSIONS[index], currentActiveChoices);
  sessionOverview.classList.remove('hidden');
  prewarmSessionHistory(SESSIONS[index]);
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

async function resolveChoiceGroups(session) {
  const resolved = new Map();
  if (!currentUser) return resolved;

  let choiceIndex = 0;
  for (const item of session.lifts) {
    if (!item.choose) continue;

    const liftIds = item.choose.map((c) => c.liftId);

    try {
      if (item.note && item.note.includes('4-week rotation')) {
        // Do one for 4 sessions, then switch
        const snapshot = await db.collection('users').doc(currentUser.uid)
          .collection('entries')
          .where('session', '==', session.id)
          .where('lift', 'in', liftIds)
          .orderBy('date', 'desc')
          .limit(8)
          .get();

        if (snapshot.empty) {
          resolved.set(choiceIndex, liftIds[0]);
        } else {
          const entries = [];
          snapshot.forEach((doc) => entries.push(doc.data()));
          const mostRecentLift = entries[0].lift;
          let consecutiveCount = 0;
          for (const entry of entries) {
            if (entry.lift === mostRecentLift) consecutiveCount++;
            else break;
          }
          resolved.set(choiceIndex,
            consecutiveCount >= 4
              ? liftIds.find((id) => id !== mostRecentLift)
              : mostRecentLift
          );
        }
      } else {
        // Alternate: gray out the one most recently done
        const snapshot = await db.collection('users').doc(currentUser.uid)
          .collection('entries')
          .where('session', '==', session.id)
          .where('lift', 'in', liftIds)
          .orderBy('date', 'desc')
          .limit(1)
          .get();

        if (snapshot.empty) {
          resolved.set(choiceIndex, liftIds[0]);
        } else {
          const lastDone = snapshot.docs[0].data().lift;
          resolved.set(choiceIndex, liftIds.find((id) => id !== lastDone));
        }
      }
    } catch (err) {
      console.error('Error resolving choice group:', err);
      resolved.set(choiceIndex, liftIds[0]);
    }

    choiceIndex++;
  }
  return resolved;
}

function renderSessionOverview(session, activeChoices) {
  sessionOverview.innerHTML = '';
  activeChoices = activeChoices || new Map();

  let choiceIndex = 0;
  session.lifts.forEach((item) => {
    if (item.choose) {
      const group = document.createElement('div');
      group.className = 'choice-group';

      const label = document.createElement('div');
      label.className = 'choice-label';
      label.textContent = item.note ? `pick one \u2014 ${item.note}` : 'pick one';
      group.appendChild(label);

      const activeLift = activeChoices.get(choiceIndex);
      item.choose.forEach((choice) => {
        const lift = LIFTS.find((l) => l.id === choice.liftId);
        if (!lift) return;
        const inactive = activeLift && choice.liftId !== activeLift;
        group.appendChild(createOverviewRow(lift, choice.rx, choice.liftId, inactive));
      });

      choiceIndex++;
      sessionOverview.appendChild(group);
    } else {
      const lift = LIFTS.find((l) => l.id === item.liftId);
      if (!lift) return;
      sessionOverview.appendChild(createOverviewRow(lift, item.rx, item.liftId, false));
    }
  });
}

function createOverviewRow(lift, rx, liftId, inactive) {
  const row = document.createElement('div');
  const done = todayEntries.has(liftId);
  row.className = 'session-lift' + (done ? ' completed' : '') + (inactive ? ' inactive' : '');
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

  resetSetGroups();

  // Load history only when signed in
  if (currentUser) {
    await loadHistory(liftId);
  } else {
    historyList.innerHTML = '';
  }

  // Fallback: if no history pre-filled the form, use rx for sets/reps
  const firstRow = setGroups.querySelector('.set-group-row');
  if (firstRow && !firstRow.querySelector('.input-sets').value) {
    const parsed = parseRx(rx);
    if (parsed) {
      firstRow.querySelector('.input-sets').value = parsed.maxSets;
      firstRow.querySelector('.input-reps').value = parsed.maxReps;
    }
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
saveBtn.addEventListener('click', () => {
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

  const notes = notesInput.value.trim();
  const savedLiftId = currentLiftId;

  if (editingEntryId) {
    // Optimistic: update cache in place
    const cached = historyCache.get(savedLiftId);
    if (cached) {
      const idx = cached.findIndex((e) => e.id === editingEntryId);
      if (idx !== -1) {
        cached[idx] = { id: editingEntryId, data: { ...cached[idx].data, sets: groups, notes } };
        renderHistoryEntries(savedLiftId, cached, { prefillForm: false });
      }
    }

    const docId = editingEntryId;
    editingEntryId = null;
    cancelEditBtn.classList.add('hidden');
    document.getElementById('edit-mode-banner').classList.add('hidden');
    resetSetGroups();
    saveBtn.textContent = 'Save';

    // Fire-and-forget write, then reconcile
    db.collection('users').doc(currentUser.uid)
      .collection('entries').doc(docId)
      .update({ sets: groups, notes })
      .then(() => refreshHistoryInBackground(savedLiftId))
      .catch((err) => {
        console.error('Save error:', err);
        alert('Update may not have saved — check your connection.');
        historyCache.delete(savedLiftId);
        if (currentLiftId === savedLiftId) loadHistory(savedLiftId);
      });
  } else {
    const entry = {
      lift: savedLiftId,
      date: firebase.firestore.FieldValue.serverTimestamp(),
      sets: groups,
      notes
    };
    if (useSessionMode) {
      entry.session = SESSIONS[currentSessionIndex].id;
    }

    // Optimistic: inject into cache and UI immediately
    const optimisticEntry = {
      id: '_pending',
      data: { ...entry, date: { toDate: () => new Date() } }
    };
    const cached = historyCache.get(savedLiftId) || [];
    historyCache.set(savedLiftId, [optimisticEntry, ...cached].slice(0, 5));
    renderHistoryEntries(savedLiftId, historyCache.get(savedLiftId), { prefillForm: false });

    todayEntries.add(savedLiftId);
    if (useSessionMode) {
      renderSessionOverview(SESSIONS[currentSessionIndex], currentActiveChoices);
      document.querySelectorAll('.session-lift').forEach((el) => {
        el.classList.toggle('selected', el.dataset.liftId === currentLiftId);
      });
    }

    resetSetGroups();

    // Fire-and-forget write, then reconcile
    db.collection('users').doc(currentUser.uid)
      .collection('entries').add(entry)
      .then(() => {
        refreshHistoryInBackground(savedLiftId);
        // Re-resolve choices in background (for pick-one rotation)
        if (useSessionMode) {
          resolveChoiceGroups(SESSIONS[currentSessionIndex]).then((choices) => {
            currentActiveChoices = choices;
            renderSessionOverview(SESSIONS[currentSessionIndex], currentActiveChoices);
            document.querySelectorAll('.session-lift').forEach((el) => {
              el.classList.toggle('selected', el.dataset.liftId === currentLiftId);
            });
          });
        }
      })
      .catch((err) => {
        console.error('Save error:', err);
        alert('Entry may not have saved — check your connection.');
        historyCache.delete(savedLiftId);
        if (currentLiftId === savedLiftId) loadHistory(savedLiftId);
      });
  }

  // Fallback: if no history, pre-fill sets/reps from rx
  const firstRow = setGroups.querySelector('.set-group-row');
  if (firstRow && !firstRow.querySelector('.input-sets').value && currentRx) {
    const parsed = parseRx(currentRx);
    if (parsed) {
      firstRow.querySelector('.input-sets').value = parsed.maxSets;
      firstRow.querySelector('.input-reps').value = parsed.maxReps;
    }
  }
});

// --- Pre-warm history cache for all lifts in a session ---
function prewarmSessionHistory(session) {
  if (!currentUser) return;
  const liftIds = [];
  session.lifts.forEach((item) => {
    if (item.choose) {
      item.choose.forEach((c) => liftIds.push(c.liftId));
    } else {
      liftIds.push(item.liftId);
    }
  });
  liftIds.forEach((id) => {
    if (!historyCache.has(id)) {
      fetchHistoryFromFirestore(id)
        .then((entries) => historyCache.set(id, entries))
        .catch(() => {}); // swallow — just a pre-warm
    }
  });
}

// --- History ---
async function loadHistory(liftId) {
  if (!currentUser) return;

  const cached = historyCache.get(liftId);
  if (cached) {
    // Serve from cache instantly, then silently refresh in the background
    renderHistoryEntries(liftId, cached, { prefillForm: true });
    refreshHistoryInBackground(liftId);
    return;
  }

  // No cache: show loading indicator and fetch
  historyList.innerHTML = '<p class="loading"><span class="spinner"></span>Loading…</p>';
  try {
    const entries = await fetchHistoryFromFirestore(liftId);
    historyCache.set(liftId, entries);
    renderHistoryEntries(liftId, entries, { prefillForm: true });
  } catch (err) {
    console.error('History load error:', err);
    historyList.innerHTML = '<p class="empty">Failed to load history.</p>';
  }
}

async function refreshHistoryInBackground(liftId) {
  historyRefreshSpinner.classList.remove('hidden');
  try {
    const entries = await fetchHistoryFromFirestore(liftId);
    historyCache.set(liftId, entries);
    // Only re-render if the user hasn't switched to a different lift
    if (currentLiftId === liftId) {
      renderHistoryEntries(liftId, entries, { prefillForm: false });
    }
  } catch (err) {
    console.error('Background history refresh error:', err);
  } finally {
    historyRefreshSpinner.classList.add('hidden');
  }
}

async function fetchHistoryFromFirestore(liftId) {
  const snapshot = await db.collection('users').doc(currentUser.uid)
    .collection('entries')
    .where('lift', '==', liftId)
    .orderBy('date', 'desc')
    .limit(5)
    .get();
  const entries = [];
  snapshot.forEach((doc) => entries.push({ id: doc.id, data: doc.data() }));
  return entries;
}

function renderHistoryEntries(liftId, entries, { prefillForm = true } = {}) {
  if (entries.length === 0) {
    historyList.innerHTML = '<p class="empty">No history yet.</p>';
    return;
  }

  historyList.innerHTML = '';
  let lastSets = null;

  entries.forEach(({ id: docId, data }) => {
    const entry = document.createElement('div');
    entry.className = 'history-entry';

    const date = data.date ? data.date.toDate() : new Date();
    const dateStr = date.toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric'
    });

    const setsStr = data.sets.map((g) => `${g.sets}\u00d7${g.reps}@${g.weight}`).join(', ');

    if (lastSets === null) {
      lastSets = data.sets;
    }

    entry.innerHTML = `
      <div class="history-header">
        <div class="history-date">${dateStr}</div>
        <div class="history-actions">
          <button class="btn-edit-entry" type="button">Edit</button>
          <button class="btn-delete-entry" type="button">Delete</button>
        </div>
      </div>
      <div class="history-sets">${setsStr}</div>
      ${data.notes ? `<div class="history-notes">${escapeHtml(data.notes)}</div>` : ''}
    `;
    entry.querySelector('.btn-edit-entry').addEventListener('click', () => startEdit(docId, data));
    entry.querySelector('.btn-delete-entry').addEventListener('click', () => deleteEntry(docId, liftId));
    historyList.appendChild(entry);
  });

  // Pre-fill form from most recent entry only on initial load (not background refresh)
  if (prefillForm && lastSets !== null) {
    setGroups.innerHTML = '';
    lastSets.forEach((g) => {
      const row = createSetGroupRow();
      row.querySelector('.input-sets').value = g.sets;
      row.querySelector('.input-reps').value = g.reps;
      row.querySelector('.input-weight').value = g.weight;
      setGroups.appendChild(row);
    });
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

cancelEditBtn.addEventListener('click', async () => {
  editingEntryId = null;
  saveBtn.textContent = 'Save';
  cancelEditBtn.classList.add('hidden');
  document.getElementById('edit-mode-banner').classList.add('hidden');
  resetSetGroups();
  historyCache.delete(currentLiftId);
  await loadHistory(currentLiftId);
  // Fallback: if no history, pre-fill sets/reps from rx
  const firstRow = setGroups.querySelector('.set-group-row');
  if (firstRow && !firstRow.querySelector('.input-sets').value && currentRx) {
    const parsed = parseRx(currentRx);
    if (parsed) {
      firstRow.querySelector('.input-sets').value = parsed.maxSets;
      firstRow.querySelector('.input-reps').value = parsed.maxReps;
    }
  }
});

// --- Delete entry ---
async function deleteEntry(docId, liftId) {
  if (!confirm('Delete this entry?')) return;

  try {
    await db.collection('users').doc(currentUser.uid)
      .collection('entries').doc(docId).delete();

    historyCache.delete(liftId);
    await loadHistory(liftId);
    await loadTodayEntries();
    if (useSessionMode) {
      currentActiveChoices = await resolveChoiceGroups(SESSIONS[currentSessionIndex]);
      renderSessionOverview(SESSIONS[currentSessionIndex], currentActiveChoices);
      document.querySelectorAll('.session-lift').forEach((el) => {
        el.classList.toggle('selected', el.dataset.liftId === currentLiftId);
      });
    }
  } catch (err) {
    console.error('Delete error:', err);
    alert('Failed to delete. Please try again.');
  }
}

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
  historyCache.clear();
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
