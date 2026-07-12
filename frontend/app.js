const $ = id => document.getElementById(id);
let running = false;

function values() { return { mode:$('mode').value, voice_enabled:$('voice').checked, camera_index:Number($('camera').value), display_index:Number($('display').value), mirror_camera:$('mirror').checked }; }
function options(select, items, selected) { select.innerHTML=''; items.forEach(item=>{ const option=document.createElement('option'); option.value=item.id; option.textContent=item.label; option.selected=Number(item.id)===Number(selected); select.appendChild(option); }); }
function applyDevices(devices, config) { options($('camera'),devices.cameras,config.camera_index); options($('display'),devices.displays,config.display_index); }
function selectKnown(id,value) { const select=$(id); select.value=value; if(select.selectedIndex<0) select.selectedIndex=0; }
function apply(config) { $('mode').value=config.mode; $('voice').checked=config.voice_enabled; selectKnown('camera',config.camera_index); selectKnown('display',config.display_index); $('mirror').checked=config.mirror_camera; }
function setRunning(value) { running=value; $('startButton').textContent=value?'Stop tracking':'Start presentation'; $('startButton').classList.toggle('stop',value); $('statusBadge').classList.toggle('running',value); $('statusBadge').querySelector('span').textContent=value?'Live':'Ready'; }

async function init() {
  const state=await window.pywebview.api.initial_state(); applyDevices(state.devices,state.config); apply(state.config); setRunning(state.running);
  if(!state.voiceAvailable){ $('voiceRow').classList.add('disabled'); $('voice').checked=false; $('voiceHint').textContent='Voice components are not installed'; }
  document.querySelectorAll('select,input').forEach(el=>el.addEventListener('change',()=>window.pywebview.api.save_config(values())));
  $('refreshDevices').onclick=async()=>{ const devices=await window.pywebview.api.refresh_devices(); const current=values(); applyDevices(devices,current); };
  $('startButton').onclick=async()=>{
    $('error').hidden=true;
    try {
      if(running) await window.pywebview.api.stop_tracking();
      else {
        $('statusText').textContent='Requesting camera access…';
        const result=await window.pywebview.api.start_tracking(values());
        if(!result.ok){ $('error').textContent=result.error||'Unable to start tracking.'; $('error').hidden=false; }
      }
    } catch(error) {
      $('error').textContent=`Unable to start: ${error.message||error}`;
      $('error').hidden=false;
    }
  };
  setInterval(poll,120);
}
async function poll(){ const s=await window.pywebview.api.poll(); setRunning(s.running); $('statusText').textContent=s.message; $('error').hidden=!s.error; $('error').textContent=s.error||''; if(s.frame){ $('preview').src=s.frame; $('preview').style.display='block'; $('emptyState').style.display='none'; } else if(!s.running){ $('preview').style.display='none'; $('emptyState').style.display='flex'; } }
window.addEventListener('pywebviewready',init);
