<script>
  import { REPO } from '../lib/content.js';
</script>

<nav>
  <div class="inner">
    <a class="brand" href="#home">
      <img src="./icon.png" alt="" width="26" height="26" />
      <span>Gesture Presenter</span>
    </a>
    <div class="links">
      <a href="#guide">How to use</a>
      <a class="install" href="#install">Get the app ↓</a>
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
  .install { background: #1e3328; color: white; padding: 9px 15px; border-radius: 99px; }
  .links .install:hover { color: white; background: #304f3d; }
  .ghub {
    color: var(--ink);
    font-weight: 500;
  }
  @media (max-width: 480px) {
    .links { gap: 14px; }
    .brand span { display: none; }
  }
  @media (max-width: 640px) {
    .links a.ghub {
      display: none;
    }
  }
</style>
