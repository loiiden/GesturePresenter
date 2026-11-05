<script>
  import GesturePreview from './GesturePreview.svelte';
  const slides = [
    { hand: 'Right hand', title: 'Next slide', kind: 'next' },
    { hand: 'Left hand', title: 'Previous slide', kind: 'previous' },
  ];
  const controls = [
    { title: 'Move the pointer', kind: 'pointer', emoji: '👆', hint: 'Right hand · point with your index finger, thumb tucked.' },
    { title: 'Left click', kind: 'click', hint: 'Either hand · index straight, thumb out in an L. Release to click.' },
    { title: 'Scroll', kind: 'scroll', hint: 'Right hand · index and middle together. Move up or down.' },
    { title: 'Change slide', kind: 'swipe', emoji: '🖐️', hint: 'Right hand · swipe an open palm left for next, right for previous.' },
    { title: 'Black screen', kind: 'black', emoji: '✊', hint: 'Right hand · hold a fist to toggle.' },
    { title: 'Play / pause', kind: 'media', emoji: '👍', hint: 'Right hand · hold a thumbs-up.' },
    { title: 'Task overview', kind: 'overview', emoji: '✌️', hint: 'Right hand · hold a wide V sign.' },
    { title: 'Speak and paste', kind: 'voice', emoji: '✊', hint: 'Left hand · hold a fist and speak. Release to paste. Requires the voice edition.' },
  ];
</script>

<section class="guide">
  <header><p class="eyebrow">Gesture guide</p><h1>See it. Try it.</h1><p class="intro">A quick reference for your hands.</p></header>
  <div class="section-heading"><h2>Simple mode</h2><span class="badge">Default</span></div>
  <p class="description">Touch thumb and index finger, then release. One hand at a time.</p>
  <div class="pinches">
    {#each slides as slide}
      <article><GesturePreview kind={slide.kind} left={slide.hand === 'Left hand'} /><div class="card-copy"><p class="hand-label">{slide.hand}</p><h3>{slide.title}</h3><p>Pinch → release</p></div></article>
    {/each}
  </div>
  <p class="tip">Release triggers the action. Holding a pinch won’t repeat it.</p>

  <details class="full">
    <summary><div><h2>Full mode</h2><p>Pointer, scrolling, voice & more</p></div><span class="expand" aria-hidden="true">+</span></summary>
    <p class="description">Turn off Simple mode in the app to use these controls.</p>
    <div class="controls">
      {#each controls as control}
        <article><GesturePreview kind={control.kind} emoji={control.emoji} left={control.kind === 'voice'} /><div class="card-copy"><h3>{control.title}</h3><p>{control.hint}</p></div></article>
      {/each}
    </div>
  </details>
</section>

<style>
  .guide{max-width:var(--maxw);margin:0 auto;padding:72px 22px 64px}header{margin-bottom:58px}.eyebrow{font-size:11px;text-transform:uppercase;letter-spacing:.14em;color:#6c766e;margin-bottom:18px}h1{font-size:clamp(42px,7vw,68px);line-height:1.05;letter-spacing:-.05em;font-weight:650}.intro{font-size:18px;color:var(--ink-soft);margin-top:18px}
  .section-heading{display:flex;align-items:center;gap:12px}h2{font-size:26px;letter-spacing:-.035em;font-weight:620}.badge{font-size:11px;color:#38563e;background:#edf2e8;border-radius:99px;padding:5px 10px}.description{color:var(--ink-soft);font-size:15px;line-height:1.6;margin-top:12px}
  .pinches,.controls{display:grid;gap:18px;margin-top:24px}.pinches{grid-template-columns:repeat(2,1fr)}.controls{grid-template-columns:repeat(3,1fr)}article{border:1px solid var(--line);border-radius:22px;padding:12px;overflow:hidden}.card-copy{padding:18px 10px 12px}.hand-label{font-size:11px!important;text-transform:uppercase;letter-spacing:.09em;margin:0 0 8px!important}h3{font-size:19px;letter-spacing:-.02em;font-weight:600}.card-copy p{font-size:13px;color:var(--ink-soft);line-height:1.6;margin-top:8px}.tip{font-size:13px;color:var(--ink-soft);line-height:1.5;margin-top:16px}
  .full{margin-top:48px;padding-top:28px;border-top:1px solid var(--line)}summary{list-style:none;display:flex;align-items:center;justify-content:space-between;gap:20px;cursor:pointer;padding:10px 0}summary::-webkit-details-marker{display:none}summary p{font-size:14px;color:var(--ink-soft);margin-top:7px}.expand{font-size:28px;font-weight:300}.full[open] .expand{transform:rotate(45deg)}
  @media(max-width:800px){.controls{grid-template-columns:repeat(2,1fr)}}@media(max-width:540px){.guide{padding-top:44px}header{margin-bottom:40px}.pinches,.controls{grid-template-columns:1fr}}
</style>
