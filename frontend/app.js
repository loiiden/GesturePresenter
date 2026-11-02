const $ = id => document.getElementById(id);
let initialized = false;
let phase = 'idle';
let pollInFlight = false;
let actionInFlight = false;
let engineReady = false;
let initInFlight = false;
let initializationFailed = false;
let pollTimer;

function values() {
  return {
    simple_mode: $('simpleMode').checked,
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
  $('simpleMode').checked = Boolean(config.simple_mode ?? true);
  renderMode();
  selectKnown('camera', config.camera_index);
  selectKnown('display', config.display_index);
}

function renderMode() {
  const simple = $('simpleMode').checked;
  $('simpleGuide').hidden = !simple;
  $('fullGuide').hidden = simple;
  $('voice').disabled = simple;
  $('voiceRow').hidden = simple;
  $('display').disabled = simple;
  $('gestureGuideHint').textContent = simple ? 'Right pinch: next / Left pinch: previous' : 'Right and left hand controls';
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

function renderStartButton() {
  $('simpleMode').disabled = phase !== 'idle' || actionInFlight || !initialized;
  const button = $('startButton');
  const labels = {
    idle: 'Start presentation',
    starting: 'Cancel startup',
    running: 'Stop tracking',
    stopping: 'Stopping…',
  };
  const label = !initialized
    ? (initializationFailed ? 'Retry loading' : 'Loading…')
    : phase === 'idle' && !engineReady ? 'Preparing engine…'
    : labels[phase] || labels.idle;
  const disabled = actionInFlight || initInFlight || phase === 'stopping'
    || (!initialized ? !initializationFailed : phase === 'idle' && !engineReady);
  // WebKit can drop a click if textContent replaces the pressed text node
  // between mouse-down and mouse-up. Polls must leave unchanged labels alone.
  if (button.textContent !== label) button.textContent = label;
  if (button.disabled !== disabled) button.disabled = disabled;
  button.classList.toggle('stop', phase === 'running' || phase === 'starting');
}

function setPhase(value, ready = engineReady) {
  phase = value || 'idle';
  engineReady = Boolean(ready);
  $('statusBadge').classList.toggle('running', phase === 'running');
  renderStartButton();
  $('statusBadge').querySelector('span').textContent =
    phase === 'running' ? 'Live' : phase === 'starting' ? 'Starting' : phase === 'stopping' ? 'Stopping' : 'Ready';
}

async function handleStart() {
  if (actionInFlight || initInFlight) return;
  if (!initialized) {
    await init();
    return;
  }
  if (phase === 'stopping' || (phase === 'idle' && !engineReady)) return;
  $('error').hidden = true;
  actionInFlight = true;
  renderStartButton();
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
    renderStartButton();
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
      renderMode();
      try { await window.pywebview.api.save_config(values()); }
      catch (error) { showError(`Could not save settings: ${error.message || error}`); }
    });
  });
}

async function init() {
  if (initialized || initInFlight) return;
  initInFlight = true;
  initializationFailed = false;
  renderStartButton();
  $('error').hidden = true;
  $('statusText').textContent = 'Loading configuration…';
  try {
    const state = await window.pywebview.api.initial_state();
    // Give the selects valid values immediately. OS device names are refreshed
    // afterward and must not block application readiness.
    applyDevices({
      cameras: [{id: state.config.camera_index, label: `Camera ${state.config.camera_index + 1}`}],
      displays: [{id: state.config.display_index, label: `Display ${state.config.display_index + 1}`}],
    }, state.config);
    apply(state.config);
    if (!state.voiceAvailable) {
      $('voiceRow').classList.add('disabled');
      $('voice').checked = false;
      $('voiceHint').textContent = 'Voice components are not installed';
    }
    initialized = true;
    setPhase(state.phase, state.engineReady);
    $('statusText').textContent = state.message || 'Camera is off';
    if (state.engineError) showError(state.engineError);
    // Start only after configuration is applied, before Start becomes enabled.
    // An early poll must not race initialization and publish stale readiness.
    if (!pollTimer) pollTimer = setInterval(poll, 120);
    // Device metadata can take several seconds on macOS. Refresh it in the
    // background after Start is already safe to use.
    refreshDevices(state.config);
  } catch (error) {
    initializationFailed = true;
    showError(`Application initialization failed: ${error.message || error}`);
  } finally {
    initInFlight = false;
    renderStartButton();
  }
}

async function poll() {
  if (!initialized || pollInFlight) return;
  pollInFlight = true;
  try {
    const state = await window.pywebview.api.poll();
    // A queued macOS bridge call may not have entered Python yet. Do not let an
    // older idle poll overwrite the disabled button and "Requesting…" feedback.
    const waitingForStart = actionInFlight && phase === 'idle' && state.phase === 'idle';
    if (!waitingForStart) {
      setPhase(state.phase, state.engineReady);
      $('statusText').textContent = state.message;
      if (state.engineError) showError(state.engineError);
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

bindControls();
window.addEventListener('pywebviewready', init);
// The bridge may already exist if this script loads after its ready event.
if (window.pywebview?.api?.initial_state) init();
