'use strict';
let csrf = '', current = null, busy = false, exiting = false, waitingForCompanion = false;
const $ = id => document.getElementById(id);
function notice(message, error = false) { $('notice').textContent = message; $('notice').classList.toggle('error', error); }
async function call(path, data, retry = true) {
  const response = await fetch(path, {method: data === undefined ? 'GET' : 'POST', credentials: 'same-origin',
    headers: data === undefined ? {} : {'Content-Type': 'application/json', 'X-Irozon-CSRF': csrf},
    body: data === undefined ? undefined : JSON.stringify(data)});
  const result = await response.json();
  if (response.status === 403 && path === '/api/state' && data === undefined && retry) {
    await fetch('/', {credentials:'same-origin', cache:'no-store'});
    return call(path, undefined, false);
  }
  if (!response.ok) throw new Error(result.error || 'Request failed');
  return result;
}
function render(state, fill = false) {
  if (waitingForCompanion) { notice('Companion reconnected.'); waitingForCompanion = false; }
  current = state; csrf = state.csrf;
  $('connection-badge').textContent = {connected:'Connected', connecting:'Connecting', disconnected:'Disconnected', needs_setup:'Needs setup'}[state.connection];
  $('connection-badge').dataset.state = state.connection;
  $('connection-message').textContent = state.connection_message;
  const usage = state.usage;
  const age = usage.sampled_at ? Math.max(0, Math.floor(Date.now()/1000-usage.sampled_at)) : null;
  $('provider-status').textContent = usage.status === 'live' ? `Codex synchronized · updated ${age}s ago` :
    usage.status === 'stale' ? 'Codex data is stale. Last values are not current.' : state.provider_status;
  for (const name of ['session','weekly']) $(name+'-usage').textContent = usage[name] ? `${Math.floor(usage[name].remaining)}%` : 'Unavailable';
  $('usage').classList.toggle('stale', usage.status !== 'live');
  $('setup').hidden = state.connection === 'connected';
  $('connect').textContent = state.connection === 'connected' ? 'Test connection' : state.connection === 'connecting' ? 'Check again' : 'Connect';
  $('startup').checked = state.startup;
  $('startup').disabled = state.legacy_startup;
  $('startup-status').textContent = state.legacy_startup ? 'Previous companion startup is installed. Manage its migration in Advanced settings.' : state.startup ? 'On — this Windows app starts at sign-in.' : 'Off — start Dot when you need it.';
  $('legacy-startup').textContent = state.legacy_startup ? 'An existing task/shortcut is preserved. Remove or disable it deliberately before enabling this app at sign-in; do not install two startup entries.' : 'No previous startup entry detected.';
  $('config-path').textContent = `Settings: ${state.config_path} · Logs: logs/companion.log beside settings.`;
  $('device-state').textContent = state.device ? `Authenticated device · ${state.device.usage_status} usage · ${state.device.mode_name}` : state.connection_message;
  $('power').disabled = !state.device || state.connection !== 'connected';
  const modeCards = [...document.querySelectorAll('.mode-card')];
  for (const card of modeCards) {
    card.disabled = state.connection !== 'connected';
    card.setAttribute('aria-pressed', String(Boolean(state.device && state.device.mode === card.dataset.mode)));
  }
  $('power').textContent = state.device ? state.device.display_on ? 'Put display in standby' : 'Wake display' : 'Display unavailable';
  $('reuse').hidden = state.connection === 'connected' || !state.legacy_candidates.length;
  if (fill) {
    for (const key of ['bind','esp32_ip','codex_path']) $(key).value = state.config[key];
    $('heading').value = state.config.heading ?? 'IROZON DOT';
    $('legacy-config').replaceChildren(new Option('Choose an existing setup',''));
    for (const path of state.legacy_candidates) $('legacy-config').add(new Option(path,path));
    if (state.legacy_candidates.length === 1) $('legacy-config').value = state.legacy_candidates[0];
    for (const key of ['pairing_key','control_token']) $(key).placeholder = state.config[key+'_configured'] ? 'Saved privately; blank keeps it' : 'Not configured';
  }
}
async function refresh(fill = false) { render(await call('/api/state'), fill || !current); }
async function task(button, action) {
  if (busy) return; busy = true; button.disabled = true;
  try { await action(); } catch (error) { notice(error.message || 'Companion unavailable', true); }
  finally {
    busy = false;
    if (!exiting) button.disabled = false;
    if (current) $('startup').disabled = exiting || current.legacy_startup;
    if (button.id === 'mode' || button.id === 'power') button.disabled = !current || current.connection !== 'connected';
  }
}
$('connect').onclick = event => task(event.target, async () => {
  notice('Checking the device…'); await call('/api/test', {}); await refresh(); notice('Device connection verified.');
});
$('name-form').onsubmit = event => {event.preventDefault(); task(event.submitter, async () => {
  const result = await call('/api/save', {heading:$('heading').value.trim()});
  await refresh(true);
  notice(result.message + '. The name reaches Dot on its next usage fetch (up to 30 seconds).');
});};
$('settings-form').onsubmit = event => {event.preventDefault(); task(event.submitter, async () => {
  const result = await call('/api/save', Object.fromEntries(new FormData(event.target)));
  $('pairing_key').value = ''; $('control_token').value = ''; await refresh(true); notice(result.message);
});};
for (const card of document.querySelectorAll('.mode-card')) card.onclick = event => task(card, async () => {
  $('mode-status').textContent = 'Waiting for Dot to confirm…';
  try {
    const result = await call('/api/display',{mode:card.dataset.mode});
    await refresh(); $('mode-status').textContent = result.message;
  } catch (error) {
    $('mode-status').textContent = error.message || 'Could not change display mode.';
    throw error;
  }
});
$('power').onclick = event => task(event.target, async () => {
  if (!current.device) return; const result = await call('/api/display',{on:!current.device.display_on}); await refresh(); notice(result.message);
});
$('startup').onchange = event => task(event.target, async () => {
  try { const result = await call('/api/startup',{enabled:event.target.checked}); notice(result.message); }
  finally { await refresh(); }
});
$('discover').onclick = event => task(event.target, async () => {
  const result = await call('/api/discover',{});
  if (result.candidates.length === 1) {
    $('esp32_ip').value = result.candidates[0]; if (result.bind) $('bind').value = result.bind;
    await call('/api/save',{esp32_ip:result.candidates[0],bind:$('bind').value});
    notice('Device address found. Reuse an existing setup, or pair a new device over USB.');
  } else { $('advanced').open = true; notice('Automatic discovery found no unique device. Enter its address from your router under Connection details.',true); }
  $('candidates').textContent = result.candidates.length ? 'Found: '+result.candidates.join(', ') : 'No mDNS device found. This firmware may require manual address entry.';
});
async function listPorts() {
  const result = await call('/api/ports',{}); $('usb-port').replaceChildren(new Option('Choose a device',''));
  for (const port of result.ports) $('usb-port').add(new Option(`${port.description} (${port.port})`,port.port));
  const esp = result.ports.filter(port=>/esp32|espressif|usb jtag/i.test(port.description));
  if (esp.length === 1) $('usb-port').value = esp[0].port;
  else if (result.ports.length === 1) $('usb-port').value = result.ports[0].port;
}
$('setup-pair').onclick = event => task(event.target, async () => {$('advanced').open = true; await listPorts(); notice('Connect USB, tap RESET/EN, then choose Pair attached device. Existing installations should reuse their keys.');});
$('ports').onclick = event => task(event.target, listPorts);
$('pair').onclick = event => task(event.target, async () => {
  if (!confirm('Enroll this attached device? Use this only for a new device or a deliberately approved re-pair. Existing keys and Home Assistant access must be preserved.')) return;
  notice('Pairing over USB…'); const result = await call('/api/pair',{port:$('usb-port').value}); await refresh(true); notice(result.message);
});
async function importSetup() {
  const path = $('import-path').value || $('legacy-config').value;
  if (!path) throw new Error('Choose an existing private configuration in Advanced settings.');
  const result = await call('/api/import',{path}); await refresh(true); notice(result.message + '. Test connection next.');
}
$('import-config').onclick = event => task(event.target, importSetup);
$('reuse').onclick = event => task(event.target, async () => {$('advanced').open = true; await importSetup();});
$('export-ha').onclick = event => task(event.target, async () => {
  const response = await fetch('/api/export-ha',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-Irozon-CSRF':csrf},body:'{}'});
  if (!response.ok) throw new Error((await response.json()).error || 'Export unavailable');
  const url = URL.createObjectURL(await response.blob()); const link = document.createElement('a');
  link.href = url; link.download = 'irozon-dot-private-secret.yaml'; link.click(); URL.revokeObjectURL(url);
  notice('Private HA secret downloaded. Never publish or commit this file.');
});
$('exit').onclick = event => task(event.target, async () => {const result = await call('/api/exit',{}); notice(result.message); csrf=''; exiting=true; document.querySelectorAll('input,select,button').forEach(el=>el.disabled=true);});
function unavailable() {
  waitingForCompanion = true;
  $('connection-badge').textContent = 'Disconnected'; $('connection-badge').dataset.state = 'disconnected';
  $('connection-message').textContent = 'The Windows companion is not reachable.';
  $('provider-status').textContent = 'Usage synchronization is paused.';
  $('usage').classList.add('stale');
  document.querySelectorAll('.mode-card').forEach(card => { card.disabled = true; card.setAttribute('aria-pressed', 'false'); });
  $('power').disabled = true;
  notice('Waiting for the companion to return. This page reconnects automatically.',true);
}
refresh(true).catch(unavailable);
setInterval(async()=>{if(busy || exiting) return; try {await refresh();} catch (_) {unavailable();}},5000);
