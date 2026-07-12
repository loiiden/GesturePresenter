<script>
  import { steps } from '../lib/content.js';
</script>

<section id="how" class="band">
  <div class="wrap">
    <div class="head">
      <h2>Running in under a minute.</h2>
      <p>The camera stays off until you press Start. Your video never leaves the machine.</p>
    </div>

    <ol class="steps">
      {#each steps as s}
        <li>
          <span class="n">{s.n}</span>
          <h3>{s.title}</h3>
          <p>{s.body}</p>
        </li>
      {/each}
    </ol>
  </div>
</section>

<style>
  .band {
    background: var(--black);
    color: var(--white);
  }
  .wrap {
    max-width: var(--maxw);
    margin: 0 auto;
    padding: 96px 22px;
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
    color: rgba(255, 255, 255, 0.62);
  }
  .steps {
    list-style: none;
    margin: 52px 0 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 30px;
  }
  li {
    border-top: 1px solid rgba(255, 255, 255, 0.18);
    padding-top: 22px;
  }
  .n {
    font-size: 13px;
    font-variant-numeric: tabular-nums;
    color: rgba(255, 255, 255, 0.5);
  }
  h3 {
    margin: 16px 0 10px;
    font-size: 21px;
    font-weight: 600;
    letter-spacing: -0.02em;
  }
  li p {
    font-size: 15px;
    line-height: 1.55;
    color: rgba(255, 255, 255, 0.66);
  }
  @media (max-width: 760px) {
    .steps {
      grid-template-columns: 1fr;
      gap: 8px;
    }
  }
</style>
