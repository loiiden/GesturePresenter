<script>
  import { platforms, REPO } from '../lib/content.js';
  import { urlFor, sizeFor, release } from '../lib/downloads.svelte.js';
  import PlatformIcon from './PlatformIcon.svelte';

  let { os } = $props();
  let selectedOS = $state();
  let voice = $state(false);
  let copied = $state('');

  $effect.pre(() => {
    if (selectedOS === undefined) selectedOS = os ?? 'mac';
  });

  const selectedPlatform = $derived(platforms.find((platform) => platform.id === selectedOS));
  const isWindows = $derived(selectedOS === 'windows');

  const uvCommand = $derived(
    isWindows
      ? 'powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'
      : 'curl -LsSf https://astral.sh/uv/install.sh | sh'
  );

  const packageSpec = $derived.by(() => {
    const repo = 'git+https://github.com/loiiden/GesturePresenter.git';
    if (selectedOS === 'linux') {
      return voice
        ? `"gesture-presenter[gui-qt,voice] @ ${repo}"`
        : `"gesture-presenter[gui-qt] @ ${repo}"`;
    }
    return voice
      ? `"gesture-presenter[voice] @ ${repo}"`
      : repo;
  });

  const appCommand = $derived(`uv tool install ${packageSpec}`);
  const forceInstallCommand = $derived(`uv tool install --force ${packageSpec}`);
  const updateCommand = 'uv tool upgrade gesture-presenter --refresh';

  async function copyCommand(value, key) {
    try {
      await navigator.clipboard.writeText(value);
      copied = key;
      window.setTimeout(() => {
        if (copied === key) copied = '';
      }, 1600);
    } catch {
      copied = '';
    }
  }
</script>

<section id="download" class="wrap">
  <div class="head">
    <span class="eyebrow">Recommended installation</span>
    <h2>Set up Gesture Presenter.</h2>
    <p>
      Install from the source repository with <strong>uv</strong>. Choose your system and whether
      you want local voice transcription; the commands update automatically.
    </p>
  </div>

  <div class="installer">
    <div class="picker-block">
      <div class="step-label"><span>1</span> Choose your platform</div>
      <div class="platform-picker" role="radiogroup" aria-label="Operating system">
        {#each platforms as platform}
          <button
            type="button"
            class:active={platform.id === selectedOS}
            onclick={() => selectedOS = platform.id}
            role="radio"
            aria-checked={platform.id === selectedOS}
          >
            <PlatformIcon id={platform.id} size={22} />
            <span>{platform.name}</span>
            {#if platform.id === os}<small>Detected</small>{/if}
          </button>
        {/each}
      </div>
    </div>

    <div class="edition-block">
      <div class="step-label"><span>2</span> Choose an edition</div>
      <div class="edition-picker" role="radiogroup" aria-label="Application edition">
        <button type="button" class:active={!voice} onclick={() => voice = false}
          role="radio" aria-checked={!voice}>
          <span class="choice-head"><b>Gestures</b><i>Recommended</i></span>
          <small>Presentation control with the smallest install.</small>
        </button>
        <button type="button" class:active={voice} onclick={() => voice = true}
          role="radio" aria-checked={voice}>
          <span class="choice-head"><b>Gestures + voice</b></span>
          <small>Add local Whisper transcription. First use downloads a model.</small>
        </button>
      </div>
    </div>

    <div class="commands-block">
      <div class="step-label"><span>3</span> Run these commands</div>
      <p class="terminal-hint">
        {#if isWindows}Open PowerShell.{:else}Open Terminal.{/if}
        Install uv, restart the terminal, then install Gesture Presenter.
      </p>

      <div class="command-list">
        <div class="command-row">
          <div class="command-meta"><b>Install uv</b><small>One-time setup</small></div>
          <code>{uvCommand}</code>
          <button type="button" onclick={() => copyCommand(uvCommand, 'uv')}
            aria-label="Copy uv installation command">{copied === 'uv' ? 'Copied' : 'Copy'}</button>
        </div>
        <div class="command-row">
          <div class="command-meta"><b>Install the app</b><small>{selectedPlatform?.name} · {voice ? 'Voice edition' : 'Gesture edition'}</small></div>
          <code>{appCommand}</code>
          <button type="button" onclick={() => copyCommand(appCommand, 'app')}
            aria-label="Copy application installation command">{copied === 'app' ? 'Copied' : 'Copy'}</button>
        </div>
        <div class="command-row compact">
          <div class="command-meta"><b>Launch</b><small>Any time afterwards</small></div>
          <code>gesture-presenter</code>
          <button type="button" onclick={() => copyCommand('gesture-presenter', 'run')}
            aria-label="Copy launch command">{copied === 'run' ? 'Copied' : 'Copy'}</button>
        </div>
      </div>

      {#if selectedOS === 'linux'}
        <div class="platform-note">
          <b>Linux note</b>
          The installer includes the Qt interface. Input control currently requires an Xorg session,
          not Wayland.
        </div>
      {:else if selectedOS === 'mac'}
        <div class="platform-note">
          <b>macOS note</b>
          Grant Camera and Accessibility permission when the app asks on first launch.
        </div>
      {:else}
        <div class="platform-note">
          <b>Windows note</b>
          Restart PowerShell after installing uv so the command is available.
        </div>
      {/if}

      <details class="lifecycle">
        <summary>How to update</summary>
        <div class="lifecycle-content">
          <p>
            Close Gesture Presenter, then ask uv to refresh the GitHub source and upgrade the
            existing tool. Your selected extras and saved app settings are preserved.
          </p>
          <div class="lifecycle-command">
            <code>{updateCommand}</code>
            <button type="button" onclick={() => copyCommand(updateCommand, 'update')}
              aria-label="Copy update command">{copied === 'update' ? 'Copied' : 'Copy'}</button>
          </div>

          <div class="edge-cases">
            <b>If updating does not work</b>
            <ul>
              <li><strong>Switching editions:</strong> select Gestures or Gestures + voice above, then run the force-install command below.</li>
              <li><strong>Broken environment:</strong> run <code>uv tool upgrade gesture-presenter --reinstall</code>.</li>
              <li><strong>Command not found:</strong> restart the terminal. If needed, run <code>uv tool update-shell</code> and restart it again.</li>
              <li><strong>Linux:</strong> keep the generated <code>gui-qt</code> extra; the plain macOS/Windows command is not sufficient.</li>
              <li><strong>No visible update:</strong> only committed code from the GitHub default branch can be installed. Local or unpushed changes are unavailable.</li>
            </ul>
          </div>

          <div class="lifecycle-command secondary-command">
            <span><small>Force reinstall selected edition</small><code>{forceInstallCommand}</code></span>
            <button type="button" onclick={() => copyCommand(forceInstallCommand, 'force')}
              aria-label="Copy force reinstall command">{copied === 'force' ? 'Copied' : 'Copy'}</button>
          </div>
        </div>
      </details>

      <details class="lifecycle">
        <summary>How to uninstall</summary>
        <div class="lifecycle-content">
          <p>
            Remove Gesture Presenter and its isolated dependencies with one command.
            Saved app settings and downloaded model caches are not removed automatically.
          </p>
          <div class="lifecycle-command">
            <code>uv tool uninstall gesture-presenter</code>
            <button type="button" onclick={() => copyCommand('uv tool uninstall gesture-presenter', 'uninstall')}
              aria-label="Copy uninstall command">{copied === 'uninstall' ? 'Copied' : 'Copy'}</button>
          </div>
        </div>
      </details>
    </div>
  </div>

  <div class="builds">
    <div class="build-copy">
      <span class="warning-icon">!</span>
      <div>
        <h3>Prefer a ready-made app?</h3>
        <p>
          Prebuilt files are available, but they are <strong>not code-signed</strong>.
          Your operating system may show a security warning. Installing with uv is recommended.
        </p>
      </div>
    </div>

    <div class="build-cards">
      {#each platforms as platform}
        <a href={urlFor(platform.id)}>
          <PlatformIcon id={platform.id} size={20} />
          <span><b>{platform.name}</b><small>{sizeFor(platform.id) || platform.note}</small></span>
          <em>Unsigned download ↓</em>
        </a>
      {/each}
    </div>

    <p class="release-note">
      {#if release.version}Prebuilt release v{release.version} · {/if}
      Files are also available on <a href={`${REPO}/releases`} target="_blank" rel="noreferrer">GitHub Releases</a>.
    </p>
  </div>
</section>

<style>
  .wrap {
    max-width: var(--maxw);
    margin: 0 auto;
    padding: 96px 22px;
    border-top: 1px solid var(--line);
  }
  .head { max-width: 680px; }
  .eyebrow {
    display: block;
    margin-bottom: 13px;
    color: var(--ink-faint);
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  h2 {
    font-size: clamp(34px, 5vw, 52px);
    font-weight: 660;
    letter-spacing: -0.035em;
    line-height: 1.04;
  }
  .head p {
    margin-top: 17px;
    color: var(--ink-soft);
    font-size: 18px;
    line-height: 1.55;
  }
  .head strong { color: var(--ink); }
  .installer {
    margin-top: 46px;
    border: 1px solid var(--line);
    border-radius: 28px;
    overflow: hidden;
    background: var(--bg);
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.06);
  }
  .picker-block, .edition-block, .commands-block { padding: 30px; }
  .picker-block, .edition-block { border-bottom: 1px solid var(--line); }
  .step-label {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 18px;
    font-size: 14px;
    font-weight: 620;
  }
  .step-label > span {
    display: grid;
    place-items: center;
    width: 25px;
    height: 25px;
    border-radius: 50%;
    color: var(--white);
    background: var(--black);
    font-size: 12px;
  }
  button { font: inherit; }
  .platform-picker, .edition-picker { display: grid; gap: 10px; }
  .platform-picker { grid-template-columns: repeat(3, 1fr); }
  .edition-picker { grid-template-columns: repeat(2, 1fr); }
  .platform-picker button, .edition-picker button {
    min-width: 0;
    border: 1px solid var(--line);
    border-radius: 15px;
    background: var(--bg);
    color: var(--ink);
    cursor: pointer;
    text-align: left;
    transition: border-color 0.15s, background 0.15s, box-shadow 0.15s;
  }
  .platform-picker button:hover, .edition-picker button:hover { background: var(--bg-soft); }
  .platform-picker button.active, .edition-picker button.active {
    border-color: var(--black);
    box-shadow: inset 0 0 0 1px var(--black);
  }
  .platform-picker button {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    height: 64px;
    font-weight: 580;
  }
  .platform-picker button small {
    position: absolute;
    right: 10px;
    top: 8px;
    color: var(--ink-faint);
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .edition-picker button { padding: 19px 20px; }
  .edition-picker small {
    display: block;
    margin-top: 7px;
    color: var(--ink-soft);
    font-size: 13px;
    line-height: 1.45;
  }
  .choice-head { display: flex; align-items: center; gap: 9px; }
  .choice-head b { font-size: 15px; }
  .choice-head i {
    padding: 3px 7px;
    border-radius: 99px;
    background: var(--bg-soft);
    color: var(--ink-faint);
    font-size: 9px;
    font-style: normal;
    font-weight: 650;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .terminal-hint {
    margin: -5px 0 18px 35px;
    color: var(--ink-soft);
    font-size: 13.5px;
    line-height: 1.5;
  }
  .command-list {
    overflow: hidden;
    border-radius: 16px;
    background: #171719;
  }
  .command-row {
    display: grid;
    grid-template-columns: 150px minmax(0, 1fr) 64px;
    align-items: center;
    gap: 16px;
    min-height: 84px;
    padding: 14px 16px 14px 20px;
    border-bottom: 1px solid #303034;
  }
  .command-row:last-child { border-bottom: 0; }
  .command-meta b, .command-meta small { display: block; }
  .command-meta b { color: #fff; font-size: 13px; }
  .command-meta small { margin-top: 4px; color: #8e8e93; font-size: 11px; }
  code {
    overflow-x: auto;
    padding: 10px 0;
    color: #d8fbd1;
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
    font-size: 12px;
    line-height: 1.5;
    white-space: nowrap;
  }
  .command-row > button {
    height: 34px;
    border: 1px solid #444448;
    border-radius: 9px;
    background: #27272a;
    color: #fff;
    cursor: pointer;
    font-size: 11px;
  }
  .command-row > button:hover { background: #353539; }
  .platform-note {
    margin-top: 16px;
    padding: 13px 16px;
    border-radius: 12px;
    background: var(--bg-soft);
    color: var(--ink-soft);
    font-size: 12.5px;
    line-height: 1.5;
  }
  .platform-note b { color: var(--ink); margin-right: 5px; }
  .lifecycle {
    margin-top: 14px;
    border-top: 1px solid var(--line);
    color: var(--ink-soft);
  }
  .lifecycle + .lifecycle { margin-top: 0; }
  .lifecycle summary {
    width: fit-content;
    padding-top: 16px;
    color: var(--ink);
    cursor: pointer;
    font-size: 12.5px;
    font-weight: 600;
  }
  .lifecycle-content {
    padding-top: 12px;
  }
  .lifecycle-content > p {
    max-width: 680px;
    font-size: 12.5px;
    line-height: 1.5;
  }
  .lifecycle-command {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-top: 10px;
    padding: 9px 10px 9px 14px;
    border-radius: 11px;
    background: #171719;
  }
  .lifecycle-command code { padding: 4px 0; }
  .lifecycle-command > code, .lifecycle-command > span { min-width: 0; }
  .lifecycle-command button {
    flex: 0 0 64px;
    height: 34px;
    border: 1px solid #444448;
    border-radius: 9px;
    background: #27272a;
    color: #fff;
    cursor: pointer;
    font-size: 11px;
  }
  .lifecycle-command button:hover { background: #353539; }
  .secondary-command > span { min-width: 0; }
  .secondary-command span code { display: block; }
  .secondary-command small {
    display: block;
    margin-bottom: 3px;
    color: #8e8e93;
    font-size: 10px;
  }
  .edge-cases {
    margin-top: 14px;
    padding: 14px 16px;
    border-radius: 11px;
    background: var(--bg-soft);
    color: var(--ink-soft);
    font-size: 12px;
    line-height: 1.5;
  }
  .edge-cases > b { color: var(--ink); }
  .edge-cases ul { margin: 8px 0 0; padding-left: 19px; }
  .edge-cases li + li { margin-top: 5px; }
  .edge-cases strong { color: var(--ink); }
  .edge-cases code {
    padding: 0;
    color: #365c31;
    font-size: 11px;
    white-space: normal;
  }
  .builds {
    margin-top: 34px;
    padding: 26px;
    border: 1px solid #eadfca;
    border-radius: 22px;
    background: #fffaf0;
  }
  .build-copy { display: flex; align-items: flex-start; gap: 14px; }
  .warning-icon {
    display: grid;
    flex: 0 0 auto;
    place-items: center;
    width: 27px;
    height: 27px;
    border-radius: 50%;
    background: #f1d59d;
    color: #6f4d0d;
    font-size: 13px;
    font-weight: 750;
  }
  h3 { font-size: 17px; letter-spacing: -0.015em; }
  .build-copy p {
    margin-top: 6px;
    color: #76684e;
    font-size: 13px;
    line-height: 1.5;
  }
  .build-copy strong { color: #4e3c1c; }
  .build-cards {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 9px;
    margin-top: 20px;
  }
  .build-cards a {
    display: grid;
    grid-template-columns: auto 1fr;
    align-items: center;
    gap: 10px;
    padding: 14px;
    border: 1px solid #e7d9bd;
    border-radius: 13px;
    background: rgba(255,255,255,0.7);
    transition: background 0.15s, transform 0.15s;
  }
  .build-cards a:hover { background: #fff; transform: translateY(-1px); }
  .build-cards span b, .build-cards span small { display: block; }
  .build-cards span b { font-size: 13px; }
  .build-cards span small { margin-top: 2px; color: #88795d; font-size: 10px; }
  .build-cards em {
    grid-column: 1 / -1;
    color: #67542e;
    font-size: 11px;
    font-style: normal;
    font-weight: 600;
  }
  .release-note { margin-top: 16px; color: #88795d; font-size: 11px; }
  .release-note a { color: #4e3c1c; text-decoration: underline; text-underline-offset: 2px; }

  @media (max-width: 760px) {
    .platform-picker, .build-cards { grid-template-columns: 1fr; }
    .edition-picker { grid-template-columns: 1fr; }
    .command-row { grid-template-columns: 1fr auto; gap: 4px 12px; padding: 17px; }
    .command-meta { grid-column: 1 / -1; }
    code { grid-column: 1; }
    .command-row > button { grid-column: 2; grid-row: 2; }
    .terminal-hint { margin-left: 0; }
  }
  @media (max-width: 460px) {
    .wrap { padding-left: 16px; padding-right: 16px; }
    .picker-block, .edition-block, .commands-block { padding: 22px 18px; }
    .builds { padding: 20px 17px; }
    code { font-size: 10.5px; }
  }
</style>
