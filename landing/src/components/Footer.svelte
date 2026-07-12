<script>
  import { REPO } from '../lib/content.js';
  const year = new Date().getFullYear();
</script>

<footer>
  <div class="inner">
    <div class="brand">
      <img src="./icon.png" alt="" width="22" height="22" />
      <span>Gesture Presenter</span>
    </div>
    <div class="links">
      <a href={REPO} target="_blank" rel="noreferrer">GitHub</a>
      <a href={`${REPO}/releases`} target="_blank" rel="noreferrer">Releases</a>
      <a href={`${REPO}#readme`} target="_blank" rel="noreferrer">Docs</a>
    </div>
    <span class="copy">© {year} · Open source</span>
  </div>
</footer>

<style>
  footer {
    border-top: 1px solid var(--line);
    background: var(--bg-soft);
  }
  .inner {
    max-width: var(--maxw);
    margin: 0 auto;
    padding: 26px 22px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 18px;
    flex-wrap: wrap;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13.5px;
    font-weight: 560;
  }
  .brand img {
    border-radius: 6px;
  }
  .links {
    display: flex;
    gap: 22px;
    font-size: 13px;
    color: var(--ink-soft);
  }
  .links a:hover {
    color: var(--ink);
  }
  .copy {
    font-size: 12px;
    color: var(--ink-faint);
  }
</style>
