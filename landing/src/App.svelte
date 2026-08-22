<script>
  import Nav from './components/Nav.svelte';
  import Hero from './components/Hero.svelte';
  import Gestures from './components/Gestures.svelte';
  import Steps from './components/Steps.svelte';
  import Downloads from './components/Downloads.svelte';
  import Footer from './components/Footer.svelte';
  import { detectOS } from './lib/os.js';

  const os = detectOS();
</script>

<Nav />
<main>
  <Hero {os} />
  <Gestures />
  <Steps />
  <Downloads {os} />
</main>
<Footer />
