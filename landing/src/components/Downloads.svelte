<script>
  import { platforms, REPO } from '../lib/content.js';
  import { urlFor, sizeFor, release } from '../lib/downloads.svelte.js';
  import PlatformIcon from './PlatformIcon.svelte';

  let { os } = $props();
</script>

<section id="download" class="wrap">
  <div class="head">
    <h2>Download Gesture Presenter.</h2>
    <p>
      Free on every desktop platform. Pick your system and you're one install away.{#if release.version}
        <br />Latest release · v{release.version}{/if}
    </p>
  </div>

  <div class="cards">
    {#each platforms as p}
      <a class="card" class:featured={p.id === os} href={urlFor(p.id)}>
        {#if p.id === os}<span class="tag">Detected</span>{/if}
        <span class="ic"><PlatformIcon id={p.id} size={30} /></span>
        <h3>{p.name}</h3>
        <span class="note">{p.note}{#if sizeFor(p.id)} · {sizeFor(p.id)}{/if}</span>
        <span class="get">Download ↓</span>
      </a>
    {/each}
  </div>

  <p class="foot">
    All builds are on the
    <a href={`${REPO}/releases`} target="_blank" rel="noreferrer">GitHub Releases</a>
    page. On first launch, grant camera and accessibility access when your system asks.
  </p>
</section>

<style>
  .wrap {
    max-width: var(--maxw);
    margin: 0 auto;
    padding: 96px 22px;
    border-top: 1px solid var(--line);
    text-align: center;
  }
  .head {
    max-width: 600px;
    margin: 0 auto;
  }
  h2 {
    font-size: clamp(30px, 5vw, 46px);
    font-weight: 660;
    letter-spacing: -0.03em;
    line-height: 1.05;
  }
  .head p {
    margin-top: 16px;
    font-size: 18px;
    line-height: 1.5;
    color: var(--ink-soft);
  }
  .cards {
    margin-top: 50px;
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
  }
  .card {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 36px 20px 30px;
    background: var(--bg);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    transition: transform 0.15s ease, border-color 0.15s, box-shadow 0.15s;
  }
  .card:hover {
    transform: translateY(-3px);
    border-color: #d0d0d4;
    box-shadow: 0 12px 34px rgba(0, 0, 0, 0.07);
  }
  .card.featured {
    border-color: var(--black);
  }
  .tag {
    position: absolute;
    top: 14px;
    right: 14px;
    font-size: 10.5px;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--white);
    background: var(--black);
    padding: 4px 9px;
    border-radius: 999px;
  }
  .ic {
    display: grid;
    place-items: center;
    width: 62px;
    height: 62px;
    border-radius: 16px;
    background: var(--bg-soft);
    color: var(--ink);
    margin-bottom: 18px;
  }
  h3 {
    font-size: 20px;
    font-weight: 620;
    letter-spacing: -0.02em;
  }
  .note {
    margin-top: 7px;
    font-size: 12.5px;
    color: var(--ink-faint);
  }
  .get {
    margin-top: 20px;
    font-size: 14px;
    font-weight: 560;
  }
  .foot {
    margin: 40px auto 0;
    max-width: 520px;
    font-size: 13px;
    line-height: 1.55;
    color: var(--ink-faint);
  }
  .foot a {
    color: var(--ink);
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  @media (max-width: 760px) {
    .cards {
      grid-template-columns: 1fr;
    }
  }
</style>
