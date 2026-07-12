import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// A relative base keeps the build portable across static hosts
// (GitHub Pages project sites, Netlify, plain file servers).
export default defineConfig({
  base: './',
  plugins: [svelte()],
});
