<script>
  let { kind, emoji = '🤏', left = false } = $props();
</script>

<div class="scene {kind}" aria-hidden="true">
  <div class="gesture" class:mirrored={left}>
    {#if kind === 'click'}
      <svg viewBox="0 0 100 100" fill="none" stroke-linecap="round" stroke-linejoin="round">
        <defs><linearGradient id="click-hand-gold" x1="30" y1="8" x2="75" y2="92" gradientUnits="userSpaceOnUse"><stop stop-color="#ffe785"/><stop offset=".55" stop-color="#ffd347"/><stop offset="1" stop-color="#f7b825"/></linearGradient></defs>
        <path d="M44 91 L44 70 L27 58 C20 54 19 49 23 45 C26 42 30 43 34 45 L44 51 L44 17 C44 5 61 5 61 17 L61 46 L76 46 C85 46 89 52 89 60 L89 73 C89 82 84 88 79 91 Z" fill="url(#click-hand-gold)" stroke="#d99b29" stroke-width="1.5" />
        <path d="M65 51 L65 62 M76 51 L76 62 M53 76 Q63 72 75 76" stroke="#d99b29" stroke-width="1.5" />
        <path d="M48 45 L48 18 Q48 12 52 12" stroke="#fff3b5" stroke-width="3" />
      </svg>
    {:else if kind === 'scroll'}
      <svg viewBox="0 0 100 100" fill="none" stroke-linecap="round" stroke-linejoin="round">
        <defs><linearGradient id="scroll-hand-gold" x1="37" y1="9" x2="80" y2="91" gradientUnits="userSpaceOnUse"><stop stop-color="#ffe785"/><stop offset=".55" stop-color="#ffd347"/><stop offset="1" stop-color="#f7b825"/></linearGradient></defs>
        <path d="M39 91 L39 18 C39 7 54 7 54 18 L54 44 L54 13 C54 2 70 2 70 13 L70 48 L78 48 C86 48 91 54 91 62 L91 74 C91 83 86 88 80 91 Z" fill="url(#scroll-hand-gold)" stroke="#d99b29" stroke-width="1.5" />
        <path d="M54 27 L54 49 M74 53 L74 64 M83 56 L83 65 M44 66 Q60 60 64 71 Q66 77 59 81" stroke="#d99b29" stroke-width="1.5" />
        <path d="M43 45 L43 19 Q43 13 47 13 M58 23 L58 14 Q58 8 62 8" stroke="#fff3b5" stroke-width="3" />
      </svg>
    {:else}
      <span>{emoji}</span>
    {/if}
  </div>
  <span class="connector">→</span>
  <div class="effect">
    {#if kind === 'next' || kind === 'previous' || kind === 'swipe'}
      <div class="mini-slide"><span class="first">{kind === 'previous' ? '02' : '01'}</span><span class="second">{kind === 'previous' ? '01' : '02'}</span><i></i><i></i></div>
    {:else if kind === 'pointer'}
      <div class="pointer-pad"><svg class="cursor" viewBox="0 0 24 28"><path d="M3 2 L20 17 L12 18 L8 25 Z" fill="#38563e" stroke="white" stroke-width="2" /></svg></div>
    {:else if kind === 'click'}
      <div class="click-target"><span></span></div>
    {:else if kind === 'scroll'}
      <div class="document"><div>{#each [1,2,3,4,5,6,7] as line}<i style:width={line % 3 === 0 ? '60%' : '100%'}></i>{/each}</div></div>
    {:else if kind === 'black'}
      <div class="screen"><i></i><i></i></div>
    {:else if kind === 'media'}
      <div class="media-icon"><span class="first">▶</span><span class="second">Ⅱ</span></div>
    {:else if kind === 'overview'}
      <div class="tasks">{#each [1,2,3,4] as task}<i></i>{/each}</div>
    {:else if kind === 'lock'}
      <div class="lock-icon"><span class="first">🔓</span><span class="second">🔒</span></div>
    {:else if kind === 'voice'}
      <div class="voice-result"><div class="wave">{#each [12,24,34,18,28] as height}<i style:height={`${height}px`}></i>{/each}</div><span class="transcript">Hello there.</span></div>
    {/if}
  </div>
</div>

<style>
  .scene{height:150px;background:#f0f3ed;border-radius:16px;display:flex;align-items:center;justify-content:center;gap:20px;overflow:hidden}
  .gesture{width:75px;height:90px;display:grid;place-items:center}.gesture span{font-family:"Apple Color Emoji","Segoe UI Emoji","Noto Color Emoji",sans-serif;font-size:62px;line-height:1.2;display:block;animation:pose 4.8s infinite}.gesture svg{width:67px;height:80px;animation:pose 4.8s infinite}.mirrored{transform:scaleX(-1)}
  .connector{font-size:20px;color:#98a690}.effect{width:78px;height:65px;display:grid;place-items:center;position:relative}
  .mini-slide{background:#fff;border:1px solid #d2dbcd;border-radius:7px;width:78px;height:57px;position:relative;padding:27px 10px 0;box-shadow:0 3px 5px #22332208}.mini-slide span{font-size:14px;font-weight:650;position:absolute;top:7px;left:10px;color:#38563e}.mini-slide i{display:block;height:3px;background:#dce5d5;margin:4px 0;border-radius:2px}.mini-slide i:last-child{width:60%}
  .first{animation:out 4.8s infinite}.second{animation:in 4.8s infinite}
  .pointer-pad{width:78px;height:60px;border:1px solid #d2dbcd;background:white;border-radius:7px}.cursor{width:23px;height:27px;animation:point 4.8s infinite}
  .click-target{height:45px;width:45px;background:white;border:1px solid #c7d4bf;border-radius:50%;display:grid;place-items:center}.click-target span{height:22px;width:22px;background:#93b17f;border-radius:50%;animation:click 4.8s infinite}
  .document{height:62px;width:60px;background:#fff;border:1px solid #d2dbcd;border-radius:6px;padding:8px;overflow:hidden}.document div{animation:scroll 4.8s infinite}.document i{display:block;height:4px;background:#cbd9c1;margin:7px 0;border-radius:2px}
  .screen{width:78px;height:55px;border:1px solid #d2dbcd;border-radius:6px;background:white;padding:12px;animation:blackout 4.8s infinite}.screen i{display:block;background:#cedcc4;height:4px;margin:5px 0;animation:out 4.8s infinite}
  .media-icon,.lock-icon{width:60px;height:60px;position:relative}.media-icon span,.lock-icon span{position:absolute;inset:0;display:grid;place-items:center;font-size:34px;color:#38563e}
  .tasks{display:grid;grid-template-columns:repeat(2,1fr);gap:5px;animation:overview 4.8s infinite}.tasks i{width:29px;height:22px;border:1px solid #aabd9f;background:white;border-radius:4px}
  .voice-result{position:relative;width:90px;height:55px}.wave{height:55px;display:flex;align-items:center;justify-content:center;gap:4px;animation:out 4.8s infinite}.wave i{width:4px;border-radius:5px;background:#638252;animation:wave 1s ease-in-out infinite alternate}.wave i:nth-child(2n){animation-delay:-.5s}.transcript{position:absolute;inset:0;display:grid;place-items:center;font-size:13px;color:#38563e;font-weight:550;animation:in 4.8s infinite}
  .swipe .gesture span{animation:swipe 4.8s infinite}.scroll .gesture svg{animation:scroll-hand 4.8s infinite}
  @keyframes pose{0%,15%,65%,100%{transform:scale(1)}30%,45%{transform:scale(.9) rotate(-5deg)}}
  @keyframes in{0%,48%,100%{opacity:0}55%,90%{opacity:1}}@keyframes out{0%,48%,100%{opacity:1}55%,90%{opacity:0}}
  @keyframes point{0%,100%{transform:translate(8px,23px)}45%,75%{transform:translate(42px,5px)}}
  @keyframes click{0%,45%,70%,100%{transform:scale(.6);opacity:.5}55%{transform:scale(1.3);opacity:1}}
  @keyframes scroll{0%,20%,100%{transform:translateY(0)}55%,80%{transform:translateY(-27px)}}
  @keyframes scroll-hand{0%,20%,100%{transform:translateY(8px)}55%,80%{transform:translateY(-8px)}}
  @keyframes swipe{0%,15%,100%{transform:translateX(8px)}45%,70%{transform:translateX(-15px)}}
  @keyframes blackout{0%,48%,100%{background:white}55%,90%{background:#25362b}}
  @keyframes overview{0%,15%,100%{transform:scale(.65);gap:0}55%,80%{transform:scale(1);gap:5px}}
  @keyframes wave{to{transform:scaleY(.4)}}
  @media(prefers-reduced-motion:reduce){.scene *{animation:none!important}.second,.transcript{display:none}}
</style>
