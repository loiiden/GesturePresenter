<script>
  import { gestures } from '../lib/content.js';
</script>

<section id="gestures" class="wrap">
  <div class="head">
    <h2>A vocabulary of gestures.</h2>
    <p>Ten movements cover everything you need to run a talk — mapped to how your hand naturally moves.</p>
  </div>

  <ul class="grid">
    {#each gestures as g}
      <li>
        <span class="g">{g.gesture}</span>
        <span class="a">{g.action}</span>
      </li>
    {/each}
  </ul>
</section>

<style>
  .wrap {
    max-width: var(--maxw);
    margin: 0 auto;
    padding: 96px 22px;
    border-top: 1px solid var(--line);
  }
  .head {
    max-width: 620px;
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
  .grid {
    list-style: none;
    margin: 46px 0 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 1px;
    background: var(--line);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    overflow: hidden;
  }
  li {
    background: var(--bg);
    padding: 22px 24px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    transition: background 0.15s;
  }
  li:hover {
    background: var(--bg-soft);
  }
  .g {
    font-size: 15.5px;
    font-weight: 560;
    letter-spacing: -0.01em;
  }
  .a {
    font-size: 13.5px;
    color: var(--ink-soft);
  }
  @media (max-width: 640px) {
    .grid {
      grid-template-columns: 1fr;
    }
  }
</style>
