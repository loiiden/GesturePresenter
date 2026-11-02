<script>
  import { onMount, tick } from 'svelte';
  import Nav from './components/Nav.svelte';
  import Product from './components/Product.svelte';
  import Gestures from './components/Gestures.svelte';
  import Downloads from './components/Downloads.svelte';
  import Footer from './components/Footer.svelte';
  import { detectOS } from './lib/os.js';
  const os = detectOS();
  let page = $state(window.location.hash === '#guide' ? 'guide' : 'home');
  onMount(() => {
    const navigate = async () => {
      const hash = window.location.hash;
      page = hash === '#guide' ? 'guide' : 'home';
      await tick();
      if (hash === '#install' || hash === '#download') {
        document.getElementById('install')?.scrollIntoView({ behavior: 'smooth' });
      } else {
        window.scrollTo(0, 0);
      }
    };
    navigate();
    window.addEventListener('hashchange', navigate);
    return () => window.removeEventListener('hashchange', navigate);
  });
</script>
<Nav />
<main>
  {#if page === 'guide'}
    <Gestures />
    <div class="guide-install"><a href="#install">Get Gesture Presenter →</a></div>
  {:else}
    <Product {os} />
    <div id="install"><Downloads {os} /></div>
  {/if}
</main>
<Footer />
<style>#install{scroll-margin-top:52px}.guide-install{text-align:center;padding:0 24px 65px}.guide-install a{display:inline-block;padding:17px 25px;border-radius:99px;background:#1e3328;color:white}</style>
