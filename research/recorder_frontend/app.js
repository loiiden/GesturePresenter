const $ = id => document.getElementById(id);

let protocol = null;
let cameraOn = false;
let running = false;      // recording loop active (not paused)
let total = 0;
let recentTrials = [];
let targets = {};         // "gesture|condition" -> required repetitions

const PHASE_LABELS = {
  prompt: 'READY', countdown: 'GET READY', recording: 'RECORDING',
  saved: 'SAVED', rejected: 'REJECTED', done: 'COMPLETE',
  block_intro: 'MOVE INTO POSITION',
};

function renderBlockIntro(state) {
  const panel = $('blockIntro');
  const block = state.block;
  const show = state.phase === 'block_intro' && block;
  panel.hidden = !show;
  if (!show) return;

  $('blockLabel').textContent = `${block.label}${block.hand === 'Left' ? ' — LEFT hand' : ''}`;
  $('blockInstruction').textContent = block.instruction;
  $('blockTrials').textContent = `${block.trials} trials in this block`;

  // The live readout is the point: it turns "move closer" into something the
  // operator can watch converge instead of estimating by eye.
  const target = $('blockTarget');
  const q = state.quality;
  let text = '', now = '';
  if (block.targetMarginMax != null) {
    text = `margin target ≤ ${block.targetMarginMax}`;
    now = `now ${q.margin ? q.margin.toFixed(2) : '—'}`;
  } else if (block.targetSpan) {
    text = `span target ${block.targetSpan[0]}–${block.targetSpan[1]}`;
    now = `now ${q.span ? q.span.toFixed(2) : '—'}`;
  }
  target.hidden = !text;
  $('targetText').textContent = text;
  $('targetNow').textContent = now;
  target.classList.toggle('hit', !!block.inTarget);
}

// ── Rendering ────────────────────────────────────────────────────────────────

function renderPhase(state) {
  const badge = $('phaseBadge');
  badge.classList.toggle('live', cameraOn && state.phase !== 'recording');
  badge.classList.toggle('rec', state.phase === 'recording');
  badge.querySelector('span').textContent =
    !cameraOn ? 'Idle' : state.paused && state.phase !== 'recording' ? 'Paused'
    : PHASE_LABELS[state.phase] || 'Ready';

  const overlay = $('phaseOverlay');
  const showOverlay = ['countdown', 'recording', 'saved', 'rejected'].includes(state.phase);
  overlay.hidden = !showOverlay;
  if (showOverlay) {
    overlay.className = `phase-overlay ${state.phase}`;
    $('phaseLabel').textContent = PHASE_LABELS[state.phase];
    $('phaseTimer').textContent = state.remaining.toFixed(1);
  }
}

function renderTrial(state) {
  const trial = state.trial;
  if (!trial) {
    $('gestureName').textContent = state.phase === 'done' ? 'All trials complete' : 'Ready';
    $('instruction').textContent = state.phase === 'done'
      ? 'Every planned trial has been recorded. You can close this window.' : '';
    $('conditionText').textContent = '';
    return;
  }
  $('trialCounter').textContent = `Trial ${state.cursor + 1} / ${state.total}`;
  $('conditionChip').textContent = trial.condition;
  const hand = $('handChip');
  hand.textContent = `${trial.hand} hand`;
  hand.classList.toggle('left', trial.hand === 'Left');
  $('gestureName').textContent = trial.gesture.replace(/_/g, ' ');
  $('instruction').textContent = state.instruction;
  $('conditionText').textContent = state.conditionText;
}

function renderQuality(state) {
  const bar = $('qualityBar');
  const q = state.quality;
  const active = cameraOn;
  bar.classList.toggle('ok', active && q.ok);
  bar.classList.toggle('bad', active && !q.ok);
  $('qualityText').textContent = !active ? 'Camera is off' : q.ok ? 'Good frame' : q.reason;
  $('mSpan').textContent = q.span ? q.span.toFixed(2) : '—';
  $('mMargin').textContent = q.margin ? q.margin.toFixed(2) : '—';
  $('mScore').textContent = q.score ? q.score.toFixed(2) : '—';
  $('mFrames').textContent = state.goodFrames;
}

function renderProgress(state) {
  const pct = state.total ? (state.cursor / state.total) * 100 : 0;
  $('progressFill').style.width = `${pct}%`;
  $('progressText').textContent =
    `${state.cursor} of ${state.total} planned · ${state.completed} saved this session`;
}

function renderRecent(list) {
  const el = $('recent');
  if (!list.length) {
    el.innerHTML = '<li class="muted">Nothing recorded yet</li>';
    return;
  }
  el.innerHTML = '';
  list.forEach(trial => {
    const li = document.createElement('li');
    const name = document.createElement('span');
    name.className = 'g';
    name.textContent = trial.gesture.replace(/_/g, ' ');
    const cond = document.createElement('span');
    cond.className = 'c';
    cond.textContent = `${trial.condition} · ${trial.hand[0]}`;
    const frames = document.createElement('span');
    frames.className = 'f';
    frames.textContent = `${trial.frames}f`;
    const remove = document.createElement('button');
    remove.textContent = '×';
    remove.title = `Delete ${trial.trial_id}`;
    remove.addEventListener('click', () => deleteTrial(trial.trial_id));
    li.append(name, cond, frames, remove);
    el.appendChild(li);
  });
}

function renderCoverage(summary) {
  const container = $('coverage');
  container.innerHTML = '';
  const pairs = summary.per_pair || {};
  Object.entries(targets).forEach(([key, target]) => {
    const done = pairs[key] || 0;
    const [gesture, condition] = key.split('|');
    const row = document.createElement('div');
    row.className = 'cov-row';
    const name = document.createElement('span');
    name.className = 'cov-name';
    name.textContent = `${gesture.replace(/_/g, ' ')} · ${condition}`;
    const count = document.createElement('span');
    count.className = 'cov-count';
    count.textContent = `${done}/${target}`;
    const bar = document.createElement('div');
    bar.className = `cov-bar${done >= target ? ' full' : ''}`;
    const fill = document.createElement('i');
    fill.style.width = `${Math.min(100, (done / target) * 100)}%`;
    bar.appendChild(fill);
    row.append(name, count, bar);
    container.appendChild(row);
  });
}

// ── Backend calls ────────────────────────────────────────────────────────────

function showError(message) {
  $('error').textContent = message;
  $('error').hidden = false;
}

async function poll() {
  if (!window.pywebview) return;
  let state;
  try {
    state = await window.pywebview.api.poll();
  } catch (error) {
    return;
  }
  if (state.error) showError(state.error);

  if (state.frame) {
    $('preview').src = state.frame;
    $('preview').classList.add('visible');
    $('viewportEmpty').style.display = 'none';
  }

  renderPhase(state);
  renderTrial(state);
  renderQuality(state);
  renderProgress(state);
  renderBlockIntro(state);

  if (JSON.stringify(state.recent) !== JSON.stringify(recentTrials)) {
    recentTrials = state.recent;
    renderRecent(recentTrials);
    refreshStats();
  }

  $('lastResult').textContent = state.lastResult || '';
  running = !state.paused;
  syncButtons(state);
}

function syncButtons(state) {
  const active = cameraOn && state.phase !== 'done';
  $('runToggle').disabled = !active;
  $('runToggle').textContent = state.phase === 'block_intro' ? 'Start this block'
    : running ? 'Pause' : 'Begin recording';
  $('runToggle').classList.toggle('running', running);
  $('redo').disabled = !active;
  $('skip').disabled = !active;
  $('deleteLast').disabled = !recentTrials.length;
  $('startCamera').disabled = cameraOn;
  $('stopCamera').disabled = !cameraOn;
}

async function refreshStats() {
  try {
    renderCoverage(await window.pywebview.api.dataset_summary());
  } catch (error) { /* summary is advisory only */ }
}

async function deleteTrial(trialId) {
  try {
    await window.pywebview.api.delete_trial(trialId);
    await refreshStats();
  } catch (error) {
    showError(`Could not delete trial: ${error.message || error}`);
  }
}

async function refreshCameras(selected = 0) {
  try {
    const cameras = await window.pywebview.api.list_cameras();
    const select = $('camera');
    select.innerHTML = '';
    (cameras.length ? cameras : [{id: 0, label: 'Camera 1'}]).forEach(camera => {
      const option = document.createElement('option');
      option.value = camera.id;
      option.textContent = camera.label;
      option.selected = Number(camera.id) === Number(selected);
      select.appendChild(option);
    });
  } catch (error) {
    showError(`Could not list cameras: ${error.message || error}`);
  }
}

// ── Wiring ───────────────────────────────────────────────────────────────────

function computeTargets(spec) {
  const map = {};
  spec.conditions.forEach(condition => {
    spec.gestures.forEach(gesture => {
      map[`${gesture}|${condition.id}`] = condition.repetitions;
    });
  });
  return map;
}

function bind() {
  $('startCamera').addEventListener('click', async () => {
    $('error').hidden = true;
    await window.pywebview.api.start(Number($('camera').value || 0));
    cameraOn = true;
  });
  $('stopCamera').addEventListener('click', async () => {
    await window.pywebview.api.stop();
    cameraOn = false;
    $('preview').classList.remove('visible');
    $('viewportEmpty').style.display = '';
  });
  $('runToggle').addEventListener('click', () =>
    window.pywebview.api.command(running ? 'pause' : 'resume'));
  $('blockStart').addEventListener('click', () => window.pywebview.api.command('resume'));
  $('redo').addEventListener('click', () => window.pywebview.api.command('redo'));
  $('skip').addEventListener('click', () => window.pywebview.api.command('skip'));
  $('deleteLast').addEventListener('click', () => window.pywebview.api.command('delete_last'));
  $('refreshCameras').addEventListener('click', () => refreshCameras($('camera').value));
  $('refreshStats').addEventListener('click', refreshStats);

  document.addEventListener('keydown', event => {
    if (event.target.tagName === 'SELECT' || !cameraOn) return;
    const key = event.key.toLowerCase();
    if (event.code === 'Space') { event.preventDefault(); $('runToggle').click(); }
    else if (key === 'r') window.pywebview.api.command('redo');
    else if (key === 's') window.pywebview.api.command('skip');
  });
}

async function init() {
  bind();
  const state = await window.pywebview.api.initial_state();
  protocol = state.protocol;
  total = state.total;
  targets = computeTargets(protocol);
  $('sessionTag').textContent = `${state.participant} / ${state.session} → ${state.output}`;
  $('trialCounter').textContent = `Trial 1 / ${total}`;
  await refreshCameras();
  await refreshStats();
  setInterval(poll, 100);
}

window.addEventListener('pywebviewready', init);
