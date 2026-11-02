<script>
  import { platforms } from '../lib/content.js';
  let { os } = $props();
  const platform = $derived(platforms.find(p => p.id === os));
</script>

<section class="product">
  <p class="eyebrow">YOUR HANDS. YOUR NEXT SLIDE.</p>
  <h1>A little pinch.<br />A big next step.</h1>
  <p class="intro">Present with your hands. All you need is your webcam.</p>
  <div class="actions"><a class="primary" href="#install">Get Gesture Presenter{platform ? ` for ${platform.name}` : ''} ↓</a><a class="secondary" href="#guide">How to use it →</a></div>
  <p class="meta">Free & open source · macOS, Windows & Linux</p>

  <div class="demo" role="img" aria-label="Animation: a right hand pinches and releases, advancing a presentation slide.">
    <div class="window">
      <div class="bar"><i></i><i></i><i></i><span>Your presentation</span></div>
      <div class="slides">
        <div class="slide one"><span>01 / TEAM LUNCH</span><h2>One big question.<br />Tacos or pizza?</h2><span class="food" aria-hidden="true">🍕</span></div>
        <div class="slide two"><span>02 / THE VERDICT</span><h2>Tacos win.<br />Meeting adjourned.</h2><span class="food" aria-hidden="true">🌮</span></div>
      </div>
    </div>
    <div class="hand-card">
      <div class="hand-label"><span class="live-dot"></span> Right hand</div>
      <div class="emoji-stage" aria-hidden="true">
        <span class="pinch-emoji">🤏</span>
        <span class="pinch-spark">✦</span>
      </div>
      <span class="hand-hint">Thumb + index</span>
    </div>
    <div class="caption"><span class="before">Pinch & release</span><span class="after">Next slide →</span></div>
  </div>
  <p class="below">Right hand goes forward. Left hand goes back.</p>
</section>

<style>
  .product{max-width:1100px;margin:auto;padding:70px 24px 55px;text-align:center}
  .eyebrow{font-size:11px;letter-spacing:.16em;font-weight:650;color:#6c766e;margin-bottom:22px}
  h1{font-size:clamp(48px,7.8vw,86px);letter-spacing:-.06em;line-height:1.02;font-weight:650}
  .intro{font-size:clamp(17px,2.2vw,21px);color:var(--ink-soft);margin:24px 0}
  .actions{display:flex;justify-content:center;align-items:center;gap:22px;flex-wrap:wrap}
  .primary{background:#1e3328;color:white;border-radius:999px;padding:17px 25px;font-size:14px;font-weight:550}
  .primary:hover{background:#304f3d}.secondary{font-size:14px}.secondary:hover{text-decoration:underline}
  .meta{font-size:12px;color:var(--ink-faint);margin-top:20px}
  .demo{isolation:isolate;position:relative;max-width:940px;margin:55px auto 0;padding:40px 225px 70px 32px;background:#edf1e9;border-radius:28px;overflow:hidden}
  .window{background:white;border:1px solid #d3d9d0;border-radius:12px;overflow:hidden;box-shadow:0 20px 50px #253a2418;text-align:left}
  .bar{height:30px;display:flex;align-items:center;gap:5px;padding:0 12px;border-bottom:1px solid #e8ebe5}.bar i{width:6px;height:6px;background:#d6dcd3;border-radius:50%}.bar span{font-size:9px;color:#7b8279;margin:auto}
  .slides{isolation:isolate;position:relative;aspect-ratio:1.85;overflow:hidden}.slide{isolation:isolate;z-index:0;position:absolute;inset:0;padding:7%;background:#faf9f2;overflow:hidden}.slide span{font-size:9px;letter-spacing:.12em;color:#56664e}.slide h2{position:relative;z-index:1;margin-top:8%;font-size:clamp(22px,4.4vw,46px);letter-spacing:-.04em;font-weight:550;line-height:1.05}.two{z-index:1;background:#253d30;color:#f3f4e9;animation:slide 6s infinite}.two span{color:#c2d5be}
  .slide .food{position:absolute;right:4%;bottom:5%;font-family:"Apple Color Emoji","Segoe UI Emoji","Noto Color Emoji",sans-serif;font-size:clamp(48px,8vw,105px);line-height:1.2;letter-spacing:0;transform:rotate(-12deg)}
  .hand-card{position:absolute;right:24px;top:50%;transform:translateY(-50%);width:180px;background:#fff;border:1px solid #dce3d8;border-radius:20px;padding:16px 12px 14px;box-shadow:0 12px 36px #263b2412}
  .hand-label{display:flex;align-items:center;justify-content:center;gap:7px;font-size:11px;font-weight:600;color:#405443}.live-dot{width:5px;height:5px;border-radius:50%;background:#6b9562}.hand-hint{font-size:10px;color:#768373}
  .caption{position:absolute;bottom:22px;left:0;right:0;font-size:12px;color:#4b6250}.caption span{display:block}.before{animation:before 6s infinite}.after{position:absolute;inset:0;animation:after 6s infinite}.below{font-size:14px;color:var(--ink-soft);margin-top:22px}
  @keyframes slide{0%,57%{transform:translateX(101%)}65%,92%{transform:translateX(0)}99%,100%{transform:translateX(101%)}}
  .emoji-stage{position:relative;height:164px;display:grid;place-items:center;margin:8px auto}
  .pinch-emoji{display:block;font-family:"Apple Color Emoji","Segoe UI Emoji","Noto Color Emoji",sans-serif;font-size:108px;line-height:1.2;transform-origin:65% 65%;animation:squeeze 6s infinite}
  .pinch-spark{position:absolute;left:16px;top:39px;color:#6b9562;font-size:22px;animation:spark 6s infinite}
  @keyframes squeeze{0%,18%,58%,100%{transform:rotate(0deg) scale(1)}30%,46%{transform:rotate(-6deg) scale(.94)}}
  @keyframes spark{0%,27%,53%,100%{opacity:0;transform:scale(.5)}33%,46%{opacity:1;transform:scale(1)}}
  @keyframes before{0%,57%,99%,100%{opacity:1}65%,92%{opacity:0}}@keyframes after{0%,57%,99%,100%{opacity:0}65%,92%{opacity:1}}
  @media(max-width:600px){.product{padding:45px 18px 40px}.demo{padding:22px 18px 175px;margin-top:35px}.hand-card{width:120px;top:auto;bottom:34px;right:calc(50% - 60px);transform:none;padding:8px}.emoji-stage{height:91px;margin:2px auto}.pinch-emoji{font-size:68px}.pinch-spark{font-size:15px;left:2px;top:20px}.hand-label,.hand-hint{font-size:9px}.caption{bottom:12px}.slide span{font-size:7px}.actions{gap:18px}.primary{padding:16px 22px}}
  @media(prefers-reduced-motion:reduce){.two,.before,.after,.pinch-emoji,.pinch-spark{animation:none}.two,.after,.pinch-spark{display:none}}
</style>
