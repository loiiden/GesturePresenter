const $ = id => document.getElementById(id);
let running = false;

function values() { return { mode:$('mode').value, voice_enabled:$('voice').checked, camera_index:Number($('camera').value), display_index:Number($('display').value), mirror_camera:$('mirror').checked }; }
function apply(config) { $('mode').value=config.mode; $('voice').checked=config.voice_enabled; $('camera').value=config.camera_index; $('display').value=config.display_index; $('mirror').checked=config.mirror_camera; }
function setRunning(value) { running=value; $('startButton').textContent=value?'Stop tracking':'Start presentation'; $('startButton').classList.toggle('stop',value); $('statusBadge').classList.toggle('running',value); $('statusBadge').querySelector('span').textContent=value?'Live':'Ready'; }

async function init() {
  const state=await window.pywebview.api.initial_state(); apply(state.config); setRunning(state.running);
  if(!state.voiceAvailable){ $('voiceRow').classList.add('disabled'); $('voice').checked=false; $('voiceHint').textContent='Voice components are not installed'; }
  document.querySelectorAll('select,input').forEach(el=>el.addEventListener('change',()=>window.pywebview.api.save_config(values())));
  $('startButton').onclick=async()=>{ if(running) await window.pywebview.api.stop_tracking(); else await window.pywebview.api.start_tracking(values()); };
  setInterval(poll,120);
}
async function poll(){ const s=await window.pywebview.api.poll(); setRunning(s.running); $('statusText').textContent=s.message; $('error').hidden=!s.error; $('error').textContent=s.error||''; if(s.frame){ $('preview').src=s.frame; $('preview').style.display='block'; $('emptyState').style.display='none'; } else if(!s.running){ $('preview').style.display='none'; $('emptyState').style.display='flex'; } }
window.addEventListener('pywebviewready',init);
