const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');

const script = readFileSync(join(__dirname, '../frontend/app.js'), 'utf8');

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

// Minimal DOM/bridge doubles let us control the exact ordering of asynchronous
// responses without a camera, native permissions, or a browser dependency.
function frontend(overrides = {}) {
  function element(text = '') {
    return {
      firstChild: { textContent: text },
      get textContent() { return this.firstChild.textContent; },
      set textContent(value) { this.firstChild = { textContent: value }; },
      disabledChanges: [],
      _disabled: false,
      get disabled() { return this._disabled; },
      set disabled(value) { this.disabledChanges.push(value); this._disabled = value; },
      checked: false, value: '0', options: [], selectedIndex: 0,
      hidden: true, style: {}, listeners: {},
      classList: { toggle() {}, add() {}, remove() {} },
      addEventListener(name, callback) {
        (this.listeners[name] ||= []).push(callback);
      },
      appendChild(child) { this.options.push(child); },
      querySelector() { return this.span ||= element(); },
      focus() {},
    };
  }
  const elements = new Map();
  const get = id => {
    if (!elements.has(id)) elements.set(id, element());
    return elements.get(id);
  };
  const button = get('startButton');
  button.textContent = 'Loading…';
  button.disabled = true;
  const state = {
    config: { camera_index: 0, display_index: 0, voice_enabled: false },
    voiceAvailable: true, phase: 'idle', engineReady: true,
    message: 'Camera is off', running: false,
  };
  const calls = { start: 0, stop: 0, initial: 0, poll: 0 };
  const api = {
    async initial_state() { calls.initial++; return { ...state }; },
    async refresh_devices() {
      return { cameras: [{ id: 0, label: 'Camera' }], displays: [{ id: 0, label: 'Display' }] };
    },
    async poll() { calls.poll++; return { ...state }; },
    async save_config() {},
    async start_tracking() { calls.start++; return { ok: true, phase: 'starting' }; },
    async stop_tracking() { calls.stop++; return { ok: true, phase: 'stopping' }; },
    ...overrides,
  };
  const listeners = {};
  const timers = [];
  const window = { addEventListener(name, callback) { listeners[name] = callback; } };
  const context = vm.createContext({
    window,
    document: {
      getElementById: get, createElement: () => element(),
      querySelector: get, querySelectorAll: () => [get('camera'), get('display'), get('voice')],
      addEventListener() {}, body: element(),
    },
    setInterval(callback) { timers.push(callback); return timers.length; },
  });
  vm.runInContext(script, context);
  window.pywebview = { api };
  return {
    api, state, calls, timers, button, get,
    ready: () => listeners.pywebviewready(),
    poll: () => vm.runInContext('poll()', context),
    click: () => Promise.all(button.listeners.click.map(callback => callback())),
  };
}

test('unchanged polls preserve the pressed button text in every phase', async () => {
  const ui = frontend();
  await ui.ready();
  for (const phase of ['idle', 'starting', 'running', 'stopping']) {
    ui.state.phase = phase;
    await ui.poll();
    const pressedText = ui.button.firstChild;
    ui.button.disabledChanges.length = 0;
    for (let i = 0; i < 10; i++) await ui.poll();
    assert.equal(ui.button.firstChild, pressedText, `${phase}: text node replaced during a click`);
    assert.deepEqual(ui.button.disabledChanges, [], `${phase}: redundant enabled-state writes`);
  }
});

test('engine preparation never temporarily enables or relabels Start during polling', async () => {
  const ui = frontend();
  ui.state.engineReady = false;
  await ui.ready();
  const text = ui.button.firstChild;
  ui.button.disabledChanges.length = 0;
  await ui.poll();
  assert.equal(ui.button.firstChild, text);
  assert.equal(ui.button.textContent, 'Preparing engine…');
  assert.deepEqual(ui.button.disabledChanges, []);
  await ui.click();
  assert.equal(ui.calls.start, 0);
  ui.state.engineReady = true;
  await ui.poll();
  assert.equal(ui.button.disabled, false);
  assert.equal(ui.button.textContent, 'Start presentation');
});

test('polling cannot enable Start before configuration finishes loading', async () => {
  const initial = deferred();
  const ui = frontend({ initial_state: () => initial.promise });
  const ready = ui.ready();
  await ui.poll();
  assert.equal(ui.button.disabled, true);
  await ui.click();
  assert.equal(ui.calls.start, 0);
  initial.resolve({ ...ui.state });
  await ready;
  assert.equal(ui.button.disabled, false);
  assert.equal(ui.timers.length, 1);
});

test('Start submits once and remains locked while its bridge call is pending', async () => {
  const start = deferred();
  const ui = frontend();
  ui.api.start_tracking = () => { ui.calls.start++; return start.promise; };
  await ui.ready();
  const clicked = ui.click();
  await ui.poll();
  assert.equal(ui.button.disabled, true);
  assert.equal(ui.get('statusText').textContent, 'Requesting camera access…');
  await ui.click();
  assert.equal(ui.calls.start, 1);
  start.resolve({ ok: true, phase: 'starting' });
  await clicked;
  assert.equal(ui.button.disabled, false);
  assert.equal(ui.button.textContent, 'Cancel startup');
  ui.state.phase = 'starting';
  await ui.poll();
  await ui.click();
  assert.equal(ui.calls.stop, 1);
  assert.equal(ui.button.disabled, true);
  assert.equal(ui.button.textContent, 'Stopping…');
  ui.state.phase = 'stopping';
  await ui.poll();
  assert.equal(ui.button.disabled, true);
  ui.state.phase = 'idle';
  await ui.poll();
  assert.equal(ui.button.disabled, false);
});

test('startup failure shows the error and allows another attempt', async () => {
  const ui = frontend({ start_tracking: async () => ({ ok: false, phase: 'idle', error: 'Camera unavailable' }) });
  await ui.ready();
  await ui.click();
  assert.equal(ui.get('error').textContent, 'Camera unavailable');
  assert.equal(ui.get('error').hidden, false);
  assert.equal(ui.button.disabled, false);
  ui.api.start_tracking = async () => ({ ok: true, phase: 'starting' });
  await ui.click();
  assert.equal(ui.button.textContent, 'Cancel startup');
});

test('failed initialization retries configuration and does not start with defaults', async () => {
  const ui = frontend({ initial_state: async () => { throw new Error('Bridge not ready'); } });
  await ui.ready();
  assert.equal(ui.button.textContent, 'Retry loading');
  assert.equal(ui.button.disabled, false);
  ui.api.initial_state = async () => ({ ...ui.state });
  await ui.click();
  assert.equal(ui.calls.start, 0);
  assert.equal(ui.button.textContent, 'Start presentation');
  await ui.ready();
  assert.equal(ui.timers.length, 1);
  assert.equal(ui.button.listeners.click.length, 1);
});
