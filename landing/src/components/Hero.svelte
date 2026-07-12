<script>
  import { platforms, REPO } from '../lib/content.js';
  import { urlFor, release } from '../lib/downloads.svelte.js';
  import PlatformIcon from './PlatformIcon.svelte';

  let { os } = $props();

  // If we recognised the OS, point the primary button straight at its build.
  const primary = $derived(platforms.find((p) => p.id === os));
</script>

<header id="top" class="hero">
  <img class="app-icon" src="./icon.png" alt="Gesture Presenter icon" width="120" height="120" />
  <p class="eyebrow">Desktop presentation controller</p>
  <h1>Present with<br />your hands.</h1>
  <p class="lede">
    Point, pinch, and swipe to drive your slides — no clicker, no keyboard.
    Gesture Presenter watches your webcam and turns hand gestures into precise
    on-screen control.
  </p>

  <div class="cta">
    {#if primary}
      <a class="btn btn-dark" href={urlFor(primary.id)}>
        <PlatformIcon id={primary.id} size={18} />
        Download for {primary.name}
      </a>
      <a class="btn btn-ghost" href="#download">All platforms</a>
    {:else}
      <a class="btn btn-dark" href="#download">Download</a>
      <a class="btn btn-ghost" href={REPO} target="_blank" rel="noreferrer">View source</a>
    {/if}
  </div>

  <p class="meta">
    Free and open source · macOS · Windows · Linux{#if release.version}
      · v{release.version}{/if}
  </p>
</header>

<style>
  .hero {
    max-width: var(--maxw);
    margin: 0 auto;
    padding: 84px 22px 76px;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
  }
  .app-icon {
    border-radius: 27px;
    box-shadow: 0 18px 50px rgba(0, 0, 0, 0.18);
    margin-bottom: 30px;
  }
  .eyebrow {
    font-size: 14px;
    font-weight: 500;
    color: var(--ink-faint);
    letter-spacing: 0.01em;
    margin-bottom: 14px;
  }
  h1 {
    font-size: clamp(44px, 8vw, 84px);
    line-height: 1.02;
    font-weight: 680;
    letter-spacing: -0.035em;
  }
  .lede {
    max-width: 560px;
    margin: 22px auto 0;
    font-size: clamp(16px, 2.4vw, 20px);
    line-height: 1.5;
    color: var(--ink-soft);
  }
  .cta {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 12px;
    margin-top: 34px;
  }
  .btn {
    display: inline-flex;
    align-items: center;
    gap: 9px;
    height: 50px;
    padding: 0 26px;
    border-radius: 999px;
    font-size: 15px;
    font-weight: 500;
    transition: transform 0.12s ease, background 0.15s, color 0.15s;
  }
  .btn:active {
    transform: scale(0.97);
  }
  .btn-dark {
    background: var(--black);
    color: var(--white);
  }
  .btn-dark:hover {
    background: #2a2a2c;
  }
  .btn-ghost {
    background: transparent;
    color: var(--ink);
    border: 1px solid var(--line);
  }
  .btn-ghost:hover {
    background: var(--bg-soft);
  }
  .meta {
    margin-top: 22px;
    font-size: 12.5px;
    color: var(--ink-faint);
  }
</style>
