// spa/main.js

const API = window.location.protocol + '//' + window.location.hostname + ':13401';

let token = localStorage.getItem('hopsec_token') || '';
let role  = localStorage.getItem('hopsec_role')  || '';

function inferRoleFromToken(t){
  try {
    const i = t.lastIndexOf('.');
    if (i <= 0) return '';
    const payload = t.slice(0, i);
    const j = JSON.parse(payload);
    return j.role || '';
  } catch(e){ return ''; }
}

function authedFetch(url, opts = {}) {
  opts.headers = Object.assign({ 'Authorization': 'Bearer ' + token }, (opts.headers || {}));
  return fetch(url, opts);
}

const timeFmt = new Intl.DateTimeFormat('fr-FR', {
  timeZone:'Europe/Paris', year:'numeric', month:'2-digit', day:'2-digit',
  hour:'2-digit', minute:'2-digit', second:'2-digit'
});
function startClock(){
  const el = document.getElementById('hudTime');
  if (!el) return;
  el.textContent = timeFmt.format(new Date());
  setInterval(() => { el.textContent = timeFmt.format(new Date()); }, 1000);
}

let hls = null;
const video   = (() => document.getElementById('v') || document.getElementById('player'))();
const hudSig  = document.getElementById('hudSignal');
const blocked = document.getElementById('blocked');

function setActiveCamera(id, title) {
  const el = document.getElementById('hudCam');
  if (el) el.textContent = (title || id || 'â€”').toUpperCase();
}

function clearPlayer(){
  try {
    if (hls) {
      try { hls.stopLoad(); } catch(e){}
      try { hls.detachMedia(); } catch(e){}
      try { hls.destroy(); } catch(e){}
      hls = null;
    }
    if (video) {
      video.pause();
      video.removeAttribute('src');
      video.load();
    }
  } catch(e){}
  if (hudSig) hudSig.style.display = 'none';
}

function attachWithReconnect(src) {
  if (blocked) blocked.style.display='none';
  if (hudSig) hudSig.style.display = 'none';
  if (!video) return;

  if (hls) { try { hls.destroy(); } catch(e){} hls = null; }

  if (window.Hls && Hls.isSupported()) {
    hls = new Hls({ backBufferLength: 30, enableWorker: true });
    hls.on(Hls.Events.ERROR, (_, data) => {
      if (data.fatal) {
        if (hudSig) hudSig.style.display = 'inline-block';
        setTimeout(() => attachWithReconnect(src), 1500);
      }
    });
    hls.on(Hls.Events.MANIFEST_PARSED, () => { if (hudSig) hudSig.style.display = 'none'; });
    hls.loadSource(src);
    hls.attachMedia(video);
  } else {
    video.src = src;
    video.addEventListener('error', () => {
      if (hudSig) hudSig.style.display = 'inline-block';
      setTimeout(() => { video.load(); }, 1500);
    }, { once:true });
  }
  video.play().catch(()=>{});
}

async function loadCameras() {
  const r = await authedFetch(API + '/v1/cameras');
  if (!r.ok) throw new Error('cameras: ' + r.status);
  const j = await r.json();

  const listA = document.getElementById('camList');
  const listGuard = document.getElementById('guardCams');
  const listRestr = document.getElementById('restrictedCams');

  if (listA) listA.innerHTML = '';
  if (listGuard) listGuard.innerHTML = '';
  if (listRestr) listRestr.innerHTML = '';

  j.cameras.forEach(cam => {
    const name = cam.name || cam.desc || cam.id;
    const desc = cam.desc || cam.site || '';
    const required = cam.required_role || 'guard';
    const isAdminCam = cam.id === 'cam-admin';

    const el = document.createElement('div');
    el.className = (listA ? 'cam' : 'card');

    if (listA) {
      el.innerHTML = `
        <div>
          <div><strong>${name}</strong></div>
          <small>${desc}</small>
        </div>
        <span class="badge">${required}${isAdminCam ? ' Â· restricted' : ''}</span>
      `;
      el.addEventListener('click', () => handleCameraClick(cam));
      listA.appendChild(el);
    } else {
      if (required === 'admin') {
        const disabled = (role !== 'admin') ? 'disabled' : '';
        el.innerHTML = `
          <strong>${cam.id}</strong> <span class="badge">${cam.site}</span>
          <div>${desc}</div>
          <div class="note">Admin-only</div>
          <button data-id="${cam.id}" class="admin" ${disabled}>Admin View</button>`;
        (listRestr || listGuard).appendChild(el);
      } else {
        el.innerHTML = `
          <strong>${cam.id}</strong> <span class="badge">${cam.site}</span>
          <div>${desc}</div>
          <div>tier: guard</div>
          <button data-id="${cam.id}" class="req">Request Ticket</button>`;
        (listGuard || listA).appendChild(el);
      }
    }
  });

  document.querySelectorAll(".req").forEach(b => b.onclick = () => requestTicket(b.getAttribute("data-id"), "guard"));
  document.querySelectorAll(".admin").forEach(b => b.onclick = () => requestTicket(b.getAttribute("data-id"), "admin"));
}

async function handleCameraClick(cam){
  setActiveCamera(cam.id, cam.name || cam.desc);
  const isAdmin = (role === 'admin');

  if (cam.id === 'cam-admin' && !isAdmin) {
    if (blocked) blocked.style.display='flex';
    clearPlayer();
    return;
  }

  const desiredTier = (cam.id === 'cam-admin') ? 'admin' : 'guard';

  const r = await authedFetch(API + '/v1/streams/request', {
    method:'POST',
    headers:{ 'Content-Type':'application/json' },
    body: JSON.stringify({ camera_id: cam.id, tier: desiredTier })
  });

  const j = await r.json();
  if (!r.ok || !j.ticket_id) {
    clearPlayer();
    if (blocked) blocked.style.display='flex';
    return;
  }
  const src = API + '/v1/streams/' + j.ticket_id + '/manifest.m3u8';
  attachWithReconnect(src);
}

async function requestTicket(camera_id, tier){
  const r = await authedFetch(API + '/v1/streams/request', {
    method:'POST',
    headers:{ 'Content-Type':'application/json' },
    body: JSON.stringify({ camera_id, tier })
  });
  const j = await r.json();
  if (!j.ticket_id) return;

  if (camera_id !== 'cam-admin' && j.effective_tier === 'guard') {
    attachWithReconnect(API + '/v1/streams/' + j.ticket_id + '/manifest.m3u8');
  }
  if (camera_id === 'cam-admin' && j.effective_tier === 'admin') {
    attachWithReconnect(API + '/v1/streams/' + j.ticket_id + '/manifest.m3u8');
  }
}

async function doLogin(){
  const u = (document.getElementById('u') || document.getElementById('username')).value.trim();
  const p = (document.getElementById('p') || document.getElementById('password')).value;
  const msg = document.getElementById('msg');
  if (msg) msg.textContent = '';

  try{
    const r = await fetch(API + '/v1/auth/login', {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ username: u, password: p })
    });
    const j = await r.json();
    if (!r.ok) { if (msg) msg.textContent = 'Login failed'; return; }

    token = j.token;
    role  = (j.profile && j.profile.role) ? j.profile.role : (inferRoleFromToken(token) || 'guard');
    localStorage.setItem('hopsec_token', token);
    localStorage.setItem('hopsec_role', role);

    const auth = document.getElementById('auth') || document.getElementById('loginPanel');
    const app  = document.getElementById('app')  || document.getElementById('mainGrid');

    if (auth) auth.classList.add('hidden');
    if (app)  { app.classList.remove('hidden'); app.style.display = 'grid'; }

    const pill = document.getElementById('rolepill') || document.getElementById('rolePill');
    if (pill) pill.textContent = (role === 'admin') ? 'Admin Console' : 'Guard Console';

    await loadCameras();
  } catch(e){
    if (msg) msg.textContent = 'API unreachable';
  }
}

function boot(){
  startClock();

  const loginBtn = document.getElementById('loginBtn') || document.getElementById('login');
  if (loginBtn) loginBtn.onclick = doLogin;

  if (token) {
    if (!role) role = inferRoleFromToken(token) || 'guard';
    localStorage.setItem('hopsec_role', role);

    const auth = document.getElementById('auth') || document.getElementById('loginPanel');
    const app  = document.getElementById('app')  || document.getElementById('mainGrid');
    if (auth) auth.classList.add('hidden');
    if (app)  { app.classList.remove('hidden'); app.style.display = 'grid'; }

    const pill = document.getElementById('rolepill') || document.getElementById('rolePill');
    if (pill) pill.textContent = (role === 'admin') ? 'Admin Console' : 'Guard Console';

    loadCameras().catch(()=>{});
  }
}

document.addEventListener('DOMContentLoaded', boot);

