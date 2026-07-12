const $ = id => document.getElementById(id);
let running = false;
let initialized = false;

function values() {
  return {
    mode: $('mode').value,
    voice_enabled: $('voice').checked,
    camera_index: Number($('camera').value || 0),
    display_index: Number($('display').value || 0),
    mirror_camera: $('mirror').checked,
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
  $('mode').value = config.mode;
  $('voice').checked = config.voice_enabled;
  selectKnown('camera', config.camera_index);
  selectKnown('display', config.display_index);
  $('mirror').checked = config.mirror_camera;
}

function showError(message) {
  $('error').textContent = message;
  $('error').hidden = false;
  $('statusText').textContent = 'Unable to continue';
}

function setRunning(value) {
  running = value;
  $('startButton').textContent = value ? 'Stop tracking' : 'Start presentation';
  $('startButton').classList.toggle('stop', value);
  $('statusBadge').classList.toggle('running', value);
  $('statusBadge').querySelector('span').textContent = value ? 'Live' : 'Ready';
}

async function handleStart() {
  $('error').hidden = true;
  $('startButton').disabled = true;
  try {
    if (running) {
      await window.pywebview.api.stop_tracking();
    } else {
      $('statusText').textContent = 'Requesting camera access…';
      const result = await window.pywebview.api.start_tracking(values());
      if (!result.ok) showError(result.error || 'Unable to start tracking.');
      else setRunning(true);
    }
  } catch (error) {
    showError(`Unable to start: ${error.message || error}`);
  } finally {
    $('startButton').disabled = false;
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
  try {
    const state = await window.pywebview.api.initial_state();
    apply(state.config);
    setRunning(state.running);
    if (!state.voiceAvailable) {
      $('voiceRow').classList.add('disabled');
      $('voice').checked = false;
      $('voiceHint').textContent = 'Voice components are not installed';
    }
    await refreshDevices(state.config);
    initialized = true;
    $('statusText').textContent = state.message || 'Camera is off';
  } catch (error) {
    initialized = true;
    showError(`Application initialization failed: ${error.message || error}`);
  }
  setInterval(poll, 120);
}

async function poll() {
  try {
    const state = await window.pywebview.api.poll();
    setRunning(state.running);
    $('statusText').textContent = state.message;
    if (state.error) showError(state.error);
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
  }
}

window.addEventListener('pywebviewready', init);
