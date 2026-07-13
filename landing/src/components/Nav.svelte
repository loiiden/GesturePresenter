<script>
  import { REPO } from '../lib/content.js';
</script>

<nav>
  <div class="inner">
    <a class="brand" href="#top">
      <img src="./icon.png" alt="" width="26" height="26" />
      <span>Gesture Presenter</span>
    </a>
    <div class="links">
      <a href="#gestures">Gestures</a>
      <a href="#how">How it works</a>
      <a href="#download">Install</a>
      <a class="ghub" href={REPO} target="_blank" rel="noreferrer">GitHub ↗</a>
    </div>
  </div>
</nav>

<style>
  nav {
    position: sticky;
    top: 0;
    z-index: 50;
    background: rgba(255, 255, 255, 0.72);
    backdrop-filter: saturate(180%) blur(20px);
    -webkit-backdrop-filter: saturate(180%) blur(20px);
    border-bottom: 1px solid var(--line);
  }
  .inner {
    max-width: var(--maxw);
    margin: 0 auto;
    height: 52px;
    padding: 0 22px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 9px;
    font-size: 15px;
    font-weight: 600;
    letter-spacing: -0.02em;
  }
  .brand img {
    border-radius: 7px;
  }
  .links {
    display: flex;
    align-items: center;
    gap: 26px;
    font-size: 13px;
    color: var(--ink-soft);
  }
  .links a {
    transition: color 0.15s;
  }
  .links a:hover {
    color: var(--ink);
  }
  .ghub {
    color: var(--ink);
    font-weight: 500;
  }
  @media (max-width: 640px) {
    .links a:not(.ghub) {
      display: none;
    }
  }
</style>
