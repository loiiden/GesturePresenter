const $ = id => document.getElementById(id);
let initialized = false;
let phase = 'idle';
let pollInFlight = false;
let actionInFlight = false;

function values() {
  return {
    voice_enabled: $('voice').checked,
    camera_index: Number($('camera').value || 0),
    display_index: Number($('display').value || 0),
  };
}

function options(select, items, selected) {
  select.innerHTML = '';
  items.forEach(item => {
    const option = document.createElement('option');
    option.value = item.id;
    option.textContent = item.label;
    option.selected = Number(item.id) === Number(selected);
    select.appendChild(option);
  });
  if (select.selectedIndex < 0 && select.options.length) select.selectedIndex = 0;
}

function applyDevices(devices, config) {
  options($('camera'), devices.cameras, config.camera_index);
  options($('display'), devices.displays, config.display_index);
}

function selectKnown(id, value) {
  const select = $(id);
  select.value = value;
  if (select.selectedIndex < 0 && select.options.length) select.selectedIndex = 0;
}

function apply(config) {
  $('voice').checked = config.voice_enabled;
  selectKnown('camera', config.camera_index);
  selectKnown('display', config.display_index);
}

function showError(message) {
  $('error').textContent = message;
  $('error').hidden = false;
  $('statusText').textContent = 'Unable to continue';
}

function openGestureGuide() {
  $('gestureModal').hidden = false;
  document.querySelector('.shell').inert = true;
  document.body.classList.add('modal-open');
  $('gestureGuideClose').focus();
}

function closeGestureGuide() {
  if ($('gestureModal').hidden) return;
  $('gestureModal').hidden = true;
  document.querySelector('.shell').inert = false;
  document.body.classList.remove('modal-open');
  $('gestureGuideButton').focus();
}

function setPhase(value) {
  phase = value || 'idle';
  $('statusBadge').classList.toggle('running', phase === 'running');
  const labels = {
    idle: 'Start presentation',
    starting: 'Cancel startup',
    running: 'Stop tracking',
    stopping: 'Stopping…',
  };
  $('startButton').textContent = labels[phase] || labels.idle;
  $('startButton').classList.toggle('stop', phase === 'running' || phase === 'starting');
  $('startButton').disabled = actionInFlight || phase === 'stopping';
  $('statusBadge').querySelector('span').textContent =
    phase === 'running' ? 'Live' : phase === 'starting' ? 'Starting' : phase === 'stopping' ? 'Stopping' : 'Ready';
}

function setEngineReady(ready) {
  if (phase !== 'idle') return;
  $('startButton').disabled = actionInFlight || !ready;
  $('startButton').textContent = ready ? 'Start presentation' : 'Preparing engine…';
  if (!ready) $('statusText').textContent = 'Preparing gesture recognition…';
}

async function handleStart() {
  if (actionInFlight) return;
  if (!initialized) {
    showError('The application is still loading. Please wait a moment.');
    return;
  }
  $('error').hidden = true;
  actionInFlight = true;
  $('startButton').disabled = true;
  try {
    if (phase !== 'idle') {
      const result = await window.pywebview.api.stop_tracking();
      setPhase(result.phase);
    } else {
      $('statusText').textContent = 'Requesting camera access…';
      const result = await window.pywebview.api.start_tracking(values());
      if (!result.ok) {
        setPhase(result.phase || 'idle');
        showError(result.error || 'Unable to start tracking.');
      }
      else setPhase(result.phase);
    }
  } catch (error) {
    showError(`Unable to start: ${error.message || error}`);
  } finally {
    actionInFlight = false;
    // Stopping remains locked until the backend confirms the camera thread has
    // exited. A completed startup can be cancelled while the camera opens.
    $('startButton').disabled = phase === 'stopping';
  }
}

async function refreshDevices(config = values()) {
  $('refreshDevices').disabled = true;
  try {
    const devices = await window.pywebview.api.refresh_devices();
    applyDevices(devices, config);
  } catch (error) {
    showError(`Could not discover cameras and displays: ${error.message || error}`);
  } finally {
    $('refreshDevices').disabled = false;
  }
}

function bindControls() {
  // Bind the primary action before any potentially slow device or config calls.
  $('startButton').addEventListener('click', handleStart);
  $('refreshDevices').addEventListener('click', () => refreshDevices());
  $('gestureGuideButton').addEventListener('click', openGestureGuide);
  $('gestureGuideClose').addEventListener('click', closeGestureGuide);
  $('gestureModal').addEventListener('click', event => {
    if (event.target === $('gestureModal')) closeGestureGuide();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') closeGestureGuide();
  });
  document.querySelectorAll('select,input').forEach(element => {
    element.addEventListener('change', async () => {
      if (!initialized) return;
      try { await window.pywebview.api.save_config(values()); }
      catch (error) { showError(`Could not save settings: ${error.message || error}`); }
    });
  });
}

async function init() {
  bindControls();
  $('statusText').textContent = 'Loading configuration…';
  // Polling must begin immediately so a tracking session can never start
  // without the frontend observing its status and preview events.
  const pollTimer = setInterval(poll, 120);
  try {
    const state = await window.pywebview.api.initial_state();
    // Give the selects valid values immediately. OS device names are refreshed
    // afterward and must not block application readiness.
    applyDevices({
      cameras: [{id: state.config.camera_index, label: `Camera ${state.config.camera_index + 1}`}],
      displays: [{id: state.config.display_index, label: `Display ${state.config.display_index + 1}`}],
    }, state.config);
    apply(state.config);
    setPhase(state.phase);
    setEngineReady(state.engineReady);
    if (state.engineError) showError(state.engineError);
    if (!state.voiceAvailable) {
      $('voiceRow').classList.add('disabled');
      $('voice').checked = false;
      $('voiceHint').textContent = 'Voice components are not installed';
    }
    initialized = true;
    setPhase(state.phase);
    setEngineReady(state.engineReady);
    $('statusText').textContent = state.message || 'Camera is off';
    // Device metadata can take several seconds on macOS. Refresh it in the
    // background after Start is already safe to use.
    refreshDevices(state.config);
  } catch (error) {
    initialized = true;
    $('startButton').disabled = false;
    $('startButton').textContent = 'Retry start';
    showError(`Application initialization failed: ${error.message || error}`);
  }
}

async function poll() {
  if (pollInFlight) return;
  pollInFlight = true;
  try {
    const state = await window.pywebview.api.poll();
    // A queued macOS bridge call may not have entered Python yet. Do not let an
    // older idle poll overwrite the disabled button and "Requesting…" feedback.
    const waitingForStart = actionInFlight && phase === 'idle' && state.phase === 'idle';
    if (!waitingForStart) {
      setPhase(state.phase);
      setEngineReady(state.engineReady);
      if (state.engineError) showError(state.engineError);
      $('statusText').textContent = state.message;
      if (state.error) showError(state.error);
    }
    if (state.frame) {
      $('preview').src = state.frame;
      $('preview').style.display = 'block';
      $('emptyState').style.display = 'none';
    } else if (!state.running) {
      $('preview').style.display = 'none';
      $('emptyState').style.display = 'flex';
    }
  } catch (error) {
    showError(`Connection to the tracking service was lost: ${error.message || error}`);
  } finally {
    pollInFlight = false;
  }
}

window.addEventListener('pywebviewready', init);
