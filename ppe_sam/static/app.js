(() => {
  const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
  const f = $('#f');
  const st = {src:'cec', loc:null, module:null, inverter:null, racking:null, gmode:'pitch', job:null, doneJob:null,
              info:null, jobPrompted:false, touched:new Set(), running:false, geo:null, complete:null,
              wx:null, showing:null, view:'cfg', shadeAuto:true};
  const IN = 0.0254;
  const SHADE_NAME = {none:'None', standard:'Standard', thin_film:'Thin film'};
  const fmt = (v,d=2) => (v===null||v===undefined||v===''||isNaN(v)) ? '—' : Number(v).toFixed(d);
  const fnum = (v,d=0) => (v===null||v===undefined||isNaN(v)) ? '—' : Number(v).toLocaleString(undefined,{maximumFractionDigits:d});
  const val = n => (f.elements[n] ? String(f.elements[n].value).trim() : '');
  const num = n => { const x = parseFloat(val(n)); return isNaN(x) ? null : x; };
  const metres = n => { const x = num(n); return x===null ? null : x * (val(n+'_units')==='in' ? IN : 1); };
  const esc = s => String(s??'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const isBif = () => st.src==='custom' ? $('#customBif').checked : !!(st.module && (st.module.bifacial || $('#bifOverride').checked));
  const isThin = () => st.src==='custom' ? ['2','3','4','5'].includes(val('custom_celltech')) : !!(st.module && st.module.thin_film);
  const ppeShade = () => !isBif() ? 'none' : (isThin() ? 'thin_film' : 'standard');
  const haveModule = () => st.src==='custom' ? (!!val('custom_celltech') || $('#customBif').checked) : !!st.module;
  // Self-shading follows the PPE standard for the module (Default) until the engineer picks another option.
  function syncShade(){ if(st.shadeAuto) f.elements.self_shading.value = haveModule() ? ppeShade() : ''; }
  // 'input' fires before the form's own input handler re-renders (and would re-apply the default).
  f.elements.self_shading.addEventListener('input', () => { const v = val('self_shading'); st.shadeAuto = !v || v===ppeShade(); });
  const mm = m => (m===null||m===undefined) ? '' : String(Math.round(m*10000)/10);
  const RACK_NAME = {tracker:'Single-axis tracker', fixed:'Fixed-tilt', carport:'Carport'};
  const HIGH_TIP = {
    tracker:'This should be the number of “stacked” modules. This is usually 1 or 2, but sometimes can be 3.',
    fixed:'This should be the number of “stacked” modules. This is usually 1 or 2, but sometimes can be 3.',
    carport:'This should be the number of “stacked” modules in one full subarray. This is between 2 and 20.'};
  const GC_TYPICAL = {m:{tracker:'2.5', fixed:'1.0', carport:'5.0'}, in:{tracker:'98', fixed:'39', carport:'197'}};
  const LABELS = {location_mode:'Location input', address:'Address lookup', lat:'Latitude', lon:'Longitude', interval:'Weather time step', module_name:'Module',
    isc_datasheet:'Isc (datasheet)', module_length:'Module length', module_width:'Module width', bifaciality_base:'Bifaciality', bifaciality_tol:'Tolerance',
    bifacial_gain:'Bifacial gain', custom_name:'Module name', custom_celltech:'Cell type', custom_nser:'Cells in series',
    custom_voc:'Voc', custom_isc:'Isc', custom_vmp:'Vmp', custom_imp:'Imp', custom_bvoc:'Voc coefficient',
    custom_aisc:'Isc coefficient', custom_gpmp:'Pmp coefficient', custom_tnoct:'NOCT', custom_fit:'Datasheet values',
    inverter_name:'Inverter', modules_per_string:'Modules per string', system_voltage:'System voltage', racking:'Mounting type',
    tilt:'Tilt', rotlim:'Rotation limit', azimuth:'Azimuth', orientation:'Orientation', ground_clearance:'Ground clearance',
    modules_high:'Modules High', modules_across:'Modules Across', rows:'Number of rows', self_shading:'Self-shading',
    pitch:'Row pitch', gap:'Module spacing', gcr:'GCR'};

  // ================= source indicator =================
  const SRC_TXT = {db:'Database', user:'User entered', def:'Default', calc:'Calculated'};
  const dbVals = {};
  function same(a,b){ const x=String(a).trim(), y=String(b).trim();
    if(x!=='' && y!=='' && !isNaN(Number(x)) && !isNaN(Number(y))) return Math.abs(Number(x)-Number(y)) < 1e-9; return x===y; }
  function fillDb(name, value){ const v=(value===null||value===undefined)?'':String(value); f.elements[name].value=v;
    if(v==='') delete dbVals[name]; else dbVals[name]=v; }
  function srcOf(name){
    if(name==='lat' || name==='lon'){ if(st.loc==='address') return 'calc'; }
    if(name==='address'){ if(st.loc==='coords') return 'def'; }
    const v=val(name); if(name==='interval') return v==='60' ? 'def' : 'user'; if(name==='rows' && v==='1') return 'def'; if(!v) return null;
    if(name==='self_shading') return st.shadeAuto ? 'def' : 'user';
    return (name in dbVals && same(v, dbVals[name])) ? 'db' : 'user'; }
  function renderSources(){
    $$('.fld[data-field]').forEach(box => { const n=box.dataset.field, el=f.elements[n]; if(!el || !el.tagName) return;
      const s = srcOf(n);
      const tip = s==='calc' && (n==='lat'||n==='lon') ? 'Source: Calculated (address lookup)'
                : s==='def' && n==='address' ? 'Not used (Coordinates selected)'
                : s ? `Source: ${SRC_TXT[s]}${s==='db'?' (CEC library)':''}` : '';
      if(s){ box.dataset.s=s; box.title=tip; } else { delete box.dataset.s; box.removeAttribute('title'); } });
    ['module_length','module_width'].forEach(n => { const box=fieldBox(n); let note=box.querySelector('.fnote');
      const show = !val(n) && st.src==='cec' && st.module && !(n==='module_length' ? st.module.length : st.module.width);
      if(show && !note){ note=document.createElement('div'); note.className='fnote'; note.textContent='Not in the CEC database. Enter from the datasheet.'; box.appendChild(note); }
      if(!show && note) note.remove(); });
  }
  const dbFields = () => Object.keys(dbVals).filter(n => srcOf(n)==='db');

  // ================= views =================
  // 'cfg' and 'set' are two pages of the same form (Configure / Settings) beside the summary panel.
  const TABS = {cfg:'#tabCfg', set:'#tabSet', res:'#tabRes', about:'#tabAbout'};
  function showView(v){ st.view = v; const form = v==='cfg' || v==='set';
    $('#viewCfg').classList.toggle('hidden', !form); $('#pageCfg').classList.toggle('hidden', v!=='cfg'); $('#pageSet').classList.toggle('hidden', v!=='set');
    $('#viewRes').classList.toggle('hidden', v!=='res'); $('#viewAbout').classList.toggle('hidden', v!=='about');
    Object.entries(TABS).forEach(([k,id]) => $(id).setAttribute('aria-selected', String(k===v)));
    window.scrollTo({top:0}); }
  Object.entries(TABS).forEach(([k,id]) => $(id).onclick = () => showView(k)); $('#backBtn').onclick = () => showView('cfg');
  // Fields on the page not shown still count; only fields hidden because they do not apply are left out.
  const notApplicable = el => !!el.closest('.hidden:not(.page):not(.view)');

  // ================= modals =================
  let modalCb = null, lastFocus = null;
  function openModal(id){ lastFocus = document.activeElement; $(id).classList.remove('hidden'); const b=$(id).querySelector('.btn.primary,.btn'); b && b.focus(); }
  function closeModal(id){ $(id).classList.add('hidden'); lastFocus && lastFocus.focus && lastFocus.focus(); }
  function ask(msg, yesText, cb){ $('#modalMsg').textContent = msg; $('#modalYes').textContent = yesText || 'Continue'; modalCb = cb; openModal('#modal'); }
  $('#modalYes').onclick = () => { closeModal('#modal'); const c=modalCb; modalCb=null; c && c(true); };
  $('#modalNo').onclick  = () => { closeModal('#modal'); const c=modalCb; modalCb=null; c && c(false); };
  document.addEventListener('keydown', e => { if(e.key!=='Escape') return;
    $$('.tip.open').forEach(t=>t.classList.remove('open'));
    if(!$('#modal').classList.contains('hidden')) $('#modalNo').click();
    else if(!$('#reviewModal').classList.contains('hidden')) closeModal('#reviewModal'); });

  // ================= info / about / logo =================
  fetch('/api/info').then(r=>r.json()).then(j=>{
    if(j.error){ $('#sideStatus').innerHTML = `<span class="bad">Library load failed: ${esc(j.error)}</span>`; return; }
    st.info = j; $$('[data-tip=cec]').forEach(el => el.textContent = j.cec_tip);   // text lives in report.py
    $('#wxYears').textContent = `${j.weather.first}–${j.weather.last} (${j.weather.requested} requested; missing years are skipped)`;
    if(j.logo){ const im=$('#logoImg'); im.onload=()=>im.classList.remove('hidden'); im.onerror=()=>im.classList.add('hidden'); im.src=j.logo; }
    renderAbout(); update();
  }).catch(e => { $('#sideStatus').innerHTML = `<span class="bad">Could not reach the app: ${esc(e.message)}</span>`; });
  function renderAbout(){
    const j = st.info || {}, L = j.libraries || {}, W = j.weather || {};
    $('#aboutBody').innerHTML = `<dl class="kv">
      <dt>Version</dt><dd>v${esc(j.version||'')}</dd>
      <dt>Date updated</dt><dd>${esc(j.date||'')}</dd>
      <dt>Engine</dt><dd>NLR-PySAM 8.0.0, Detailed PV, no financial model</dd>
      <dt>Modules</dt><dd>${fnum(L.module_count)} (CEC Database)</dd>
      <dt>Inverters</dt><dd>${fnum(L.inverter_count)} (CEC Database)</dd>
      <dt>Library</dt><dd>SAM Github commit ${esc((L.commit||'').slice(0,12))}</dd>
      <dt>Weather</dt><dd>${esc(W.dataset||'')}, ${W.first||''}–${W.last||''}</dd>
      <dt>Address lookup</dt><dd>US Census Geocoder, then OpenStreetMap Nominatim</dd></dl>
      <h3 style="font-size:13px;margin:16px 0 4px">Method</h3>
      <ul class="note" style="margin:0 0 0 18px;padding:0">
        <li>Runs once per weather year. All strings are on one inverter; results are per string.</li>
        <li>3-hour average = mean of 3 consecutive hourly steps (6 for 30-minute data).</li></ul>`; }
  function refreshCache(){ fetch('/api/cache').then(r=>r.json()).then(c=>{ $('#cacheNote').textContent = `Weather cache: ${c.files} files, ${c.mb} MB`; }).catch(()=>{}); }
  refreshCache();

  // ================= tooltips (delegated, capture phase so a "?" inside a button/label never activates it) =================
  document.addEventListener('click', e => {
    const t = e.target.closest('.tip');
    if(t){ e.preventDefault(); e.stopPropagation(); const o=t.classList.contains('open'); $$('.tip.open').forEach(x=>x.classList.remove('open')); if(!o) t.classList.add('open'); return; }
    $$('.tip.open').forEach(x=>x.classList.remove('open'));
  }, true);
  $$('.collapse').forEach(b => b.addEventListener('click', () => setCollapsed(b.closest('.card'), b.getAttribute('aria-expanded')==='true')));
  function setCollapsed(card, c){ card.classList.toggle('collapsed', c); const b=card.querySelector('.collapse'); b.setAttribute('aria-expanded', String(!c)); b.textContent = c ? 'Expand' : 'Collapse'; }
  ['#sec2','#sec3','#sec4'].forEach(s => setCollapsed($(s), true));

  // ================= radio groups =================
  function radioGroup(sel, onPick){
    const g = $(sel), items = () => [...g.querySelectorAll('[role=radio]')];
    function sync(cur){ items().forEach(x => { const on = x===cur; x.setAttribute('aria-checked', String(on)); x.tabIndex = (on || (!cur && x===items()[0])) ? 0 : -1; }); }
    g.addEventListener('click', e => { const b = e.target.closest('[role=radio]'); if(!b) return; sync(b); onPick(b); });
    g.addEventListener('keydown', e => { const k=e.key; if(!['ArrowRight','ArrowDown','ArrowLeft','ArrowUp'].includes(k)) return;
      e.preventDefault(); const it=items(), i=it.indexOf(document.activeElement), n=it.length;
      const nx = it[(i + (k==='ArrowRight'||k==='ArrowDown' ? 1 : -1) + n) % n]; nx.focus(); nx.click(); });
    return {sync, clear(){ sync(null); }};
  }
  const locG = radioGroup('#locGroup', b => setLoc(b.dataset.loc));
  const srcG = radioGroup('#srcGroup', b => { st.src = b.dataset.src; update(); scheduleValidate(); });
  const rackG = radioGroup('#rack', b => { st.racking = b.dataset.r; clearFieldError($('#rack')); update(); scheduleValidate(); });
  const gcrG = radioGroup('#gcrMode', b => { st.gmode = b.dataset.g; update(); scheduleValidate(); });
  locG.clear(); srcG.sync($('[data-src=cec]')); rackG.clear(); gcrG.sync($('[data-g=pitch]'));

  // ================= location: address or coordinates =================
  function setLatLon(lat, lon){ f.elements.lat.value = (lat??''); f.elements.lon.value = (lon??''); }
  function setLoc(mode){
    const prev = st.loc; st.loc = mode; clearFieldError($('#locGroup'));
    if(mode==='address' && prev!=='address'){
      if(st.geo && st.geo.address===val('address')) setLatLon(st.geo.lat, st.geo.lon); else setLatLon('', '');
    }
    ['lat','lon','address'].forEach(n => clearFieldError(f.elements[n]));
    update(); scheduleValidate();
  }
  function setGeoNote(html){ $('#geoNote').innerHTML = html; }
  $('#address').addEventListener('input', () => {
    if(st.loc!=='address') return;
    if(!(st.geo && st.geo.address===val('address'))){ setLatLon('', ''); f.elements.geocode_match.value=''; f.elements.geocode_source.value=''; setGeoNote(''); }
  });
  $('#address').addEventListener('keydown', e => { if(e.key==='Enter'){ e.preventDefault(); if(st.loc==='address' && val('address')) runGeocode(); } });
  async function runGeocode(){
    const q = val('address'), btn = $('#geoRun'); if(!q) return;
    btn.disabled = true; btn.textContent = '…'; setGeoNote('Looking up the address…');
    try{ const r = await fetch('/api/geocode?q=' + encodeURIComponent(q)); const j = await r.json();
      if(!r.ok) throw new Error(j.error || ('HTTP ' + r.status));
      if(val('address')!==q) return;
      st.geo = {address:q, lat:j.lat, lon:j.lon}; setLatLon(j.lat, j.lon);
      f.elements.geocode_match.value = j.matched || ''; f.elements.geocode_source.value = j.source || '';
      setGeoNote(`<span class="ok">Found:</span> ${esc(j.matched || q)} <span class="note">(${esc(j.source)})</span>`);
      clearFieldError(f.elements.address);
    }catch(err){ setGeoNote(`<span class="bad">${esc(err.message)}</span>`); }
    finally{ btn.disabled = false; btn.textContent = 'Run'; update(); scheduleValidate(); }
  }
  $('#geoRun').onclick = runGeocode;

  // ================= background weather retrieval =================
  function wxKey(){ const a=num('lat'), o=num('lon');
    return (a!==null && o!==null && Math.abs(a)<=90 && Math.abs(o)<=180) ? `${a}|${o}|${val('interval')}` : null; }
  function renderWxBtn(){
    const b=$('#wxBtn'), k=wxKey(); b.classList.toggle('hidden', !k); if(!k) return;
    const s = st.wx && st.wx.key===k ? st.wx.status : null;
    b.classList.toggle('done', s==='done');
    if(s==='queued' || s==='downloading'){ b.disabled=true; b.innerHTML='<span class="spin"></span>'; b.setAttribute('aria-label','Retrieving weather'); b.title='Retrieving weather in the background (progress on the Results tab)'; }
    else if(s==='done'){ b.disabled=true; b.innerHTML='✓ Complete'; b.removeAttribute('aria-label'); b.title='Weather retrieved and cached. Run simulation will use it.'; }
    else if(s==='error'){ b.disabled=false; b.textContent='Retry weather retrieval'; b.removeAttribute('aria-label'); b.title='The last retrieval failed. See the Results tab.'; }
    else { b.disabled=false; b.textContent='Retrieve weather'; b.removeAttribute('aria-label'); b.title='Download the weather years now, in the background, while you finish the rest of the page'; }
  }
  $('#wxBtn').onclick = async () => {
    const k = wxKey(); if(!k) return;
    let r, j; try{ r = await fetch('/api/weather',{method:'POST',body:JSON.stringify({lat:num('lat'), lon:num('lon'), interval:val('interval')})}); j = await r.json(); }
    catch(e){ st.wx = {key:k, status:'error'}; renderWxBtn(); return; }
    if(!r.ok){ st.wx = {key:k, status:'error'}; renderWxBtn(); return; }
    st.wx = {key:k, job:j.job, status:'downloading'}; $('#tabRes').disabled = false;
    if(!st.running){ st.showing = 'wx:'+j.job; prepProgress(false); $('#resTitle').textContent = 'Weather retrieval'; }
    renderWxBtn(); pollWx(j.job);
  };
  async function pollWx(id){
    let j; try{ j = await (await fetch('/api/job/'+id)).json(); }catch(e){ setTimeout(()=>pollWx(id), 2000); return; }
    if(j.error && !j.status){ return; }
    if(st.wx && st.wx.job===id){ st.wx.status = j.status; renderWxBtn(); }
    if(!st.running && st.showing==='wx:'+id) renderProgress(j);
    if(['done','error','cancelled'].includes(j.status)){ refreshCache(); return; }
    setTimeout(()=>pollWx(id), 1000);
  }

  // ================= equipment pickers =================
  function makePicker(kind){
    const M = kind==='module';
    const P = M ? {q:'#modq', list:'#modlist', status:'#modstatus', card:'#modcard', search:'#modsearch', cancel:'#modcancel', url:'/api/modules'}
                : {q:'#invq', list:'#invlist', status:'#invstatus', card:'#invcard', search:'#invsearch', cancel:'#invcancel', url:'/api/inverters'};
    const inp=$(P.q), list=$(P.list), status=$(P.status), sel = () => M ? st.module : st.inverter;
    let timer, seq=0;
    const setStatus = (t, cls) => { status.className = 'pk-status ' + (cls||''); status.textContent = t; };
    const closeList = () => { list.innerHTML=''; list.classList.add('hidden'); inp.setAttribute('aria-expanded','false'); };
    const idle = () => setStatus(sel() ? `Current selection kept: ${sel().name}` : 'Type at least 2 characters.');
    const rowHtml = r => M ? `${esc(r.name)}<div class="lmeta">${fnum(r.stc)} W · Isc ${fmt(r.i_sc_ref)} A · Voc ${fmt(r.v_oc_ref)} V · Imp ${fmt(r.i_mp_ref)} A · Vmp ${fmt(r.v_mp_ref)} V</div>`
                           : `${esc(r.name)}<div class="lmeta">${fmt(r.paco/1000,1)} kWac · Vdc max ${fnum(r.vdcmax)} V · MPPT ${fnum(r.mppt_low)}–${fnum(r.mppt_high)} V</div>`;
    inp.addEventListener('input', () => {
      clearTimeout(timer); const q = inp.value.trim();
      if(q.length < 2){ closeList(); idle(); return; }
      setStatus('Searching…', 'busy');
      timer = setTimeout(async () => { const my = ++seq;
        try{ const r = await fetch(P.url + '?q=' + encodeURIComponent(q)); const j = await r.json();
          if(my!==seq) return; if(!r.ok || j.error) throw new Error(j.error || ('HTTP ' + r.status)); render(q, j); }
        catch(err){ if(my!==seq) return; closeList(); setStatus(`Search failed: ${err.message}. Is the console window still open?`, 'bad'); }
      }, 250); });
    function render(q, rows){ list.innerHTML = '';
      if(!rows.length){ closeList(); setStatus(`No matches for “${q}”. Try fewer words.`, 'warn'); return; }
      rows.forEach(r => { const li=document.createElement('li'), b=document.createElement('button');
        b.type='button'; b.setAttribute('role','option'); b.innerHTML = rowHtml(r); b.addEventListener('click', () => choose(r));
        b.addEventListener('keydown', e => { if(e.key==='ArrowDown'){ e.preventDefault(); const n=li.nextElementSibling; n && n.querySelector('button').focus(); }
          if(e.key==='ArrowUp'){ e.preventDefault(); const p=li.previousElementSibling; p ? p.querySelector('button').focus() : inp.focus(); }
          if(e.key==='Escape'){ closeList(); inp.focus(); } });
        li.appendChild(b); list.appendChild(li); });
      list.classList.remove('hidden'); inp.setAttribute('aria-expanded','true');
      setStatus(`${rows.length}${rows.length>=40?'+':''} match${rows.length===1?'':'es'}`); }
    inp.addEventListener('keydown', e => { if(e.key==='ArrowDown' && !list.classList.contains('hidden')){ e.preventDefault(); const b=list.querySelector('button'); b && b.focus(); }
      if(e.key==='Escape') closeList(); if(e.key==='Enter') e.preventDefault(); });
    function choose(r){ closeList(); inp.value=''; setSel(r); showCard(); clearFieldError(inp); update(); scheduleValidate();
      const ch=$(P.card).querySelector('[data-act=change]'); if(ch && !$(P.card).closest('.collapsed')) ch.focus(); }
    function setSel(r){ if(M){ if(!r || !st.module || r.name!==st.module.name){ f.elements.isc_datasheet.value=''; clearFieldError(f.elements.isc_datasheet); }
        st.module = r; $('#bifOverride').checked = false;
        if(r){ fillDb('module_length', mm(r.length)); fillDb('module_width', mm(r.width)); } } else st.inverter = r; }
    function showCard(){
      const r = sel(), card = $(P.card); $(P.cancel).classList.add('hidden');
      if(!r){ card.classList.add('hidden'); $(P.search).classList.remove('hidden'); idle(); return; }
      const mfr = M ? (r.manufacturer || '') : (r.name.includes(':') ? r.name.split(':')[0] : '');
      const specs = M ? [['Power', `${fnum(r.stc)} W`], ['Isc', `${fmt(r.i_sc_ref)} A`], ['Voc', `${fmt(r.v_oc_ref)} V`], ['Imp', `${fmt(r.i_mp_ref)} A`], ['Vmp', `${fmt(r.v_mp_ref)} V`]]
                      : [['AC power', `${fmt(r.paco/1000,1)} kW`], ['AC voltage', `${fnum(r.vac)} V`], ['Nominal DC', `${fnum(r.vdco)} V`],
                         ['Max DC', `${fnum(r.vdcmax)} V`], ['MPPT', `${fnum(r.mppt_low)}–${fnum(r.mppt_high)} V`]];
      card.innerHTML = `${mfr?`<div class="eq-mfr">${esc(mfr)}</div>`:''}<div class="eq-name">${esc(r.name)}</div>
        <dl class="eq-specs">${specs.map(([k,v])=>`<div><dt>${k}</dt><dd>${v}</dd></div>`).join('')}</dl>
        <div class="eq-act"><button type="button" class="btn btn-sm" data-act="change">Change</button><button type="button" class="btn btn-sm" data-act="clear">Clear</button></div>`;
      card.classList.remove('hidden'); $(P.search).classList.add('hidden');
      card.querySelector('[data-act=change]').onclick = () => { card.classList.add('hidden'); $(P.search).classList.remove('hidden'); $(P.cancel).classList.remove('hidden'); inp.value=''; idle(); inp.focus(); };
      card.querySelector('[data-act=clear]').onclick = () => { setSel(null); if(M){ fillDb('module_length',''); fillDb('module_width',''); } inp.value=''; showCard(); update(); scheduleValidate(); inp.focus(); };
    }
    $(P.cancel).onclick = () => { closeList(); showCard(); };
    idle();
    return {showCard, reset(){ setSel(null); inp.value=''; closeList(); showCard(); },
            pick(r){ setSel(r); inp.value=''; closeList(); showCard(); }};
  }
  const modPicker = makePicker('module'), invPicker = makePicker('inverter');
  ['#bifOverride','#customBif','#bifMismatch'].forEach(s => $(s).addEventListener('change', () => { update(); scheduleValidate(); }));

  // ================= custom module =================
  const CUSTOM_FIELDS = ['custom_name','custom_celltech','custom_nser','custom_voc','custom_isc','custom_vmp','custom_imp',
                         'custom_bvoc','custom_bvoc_units','custom_aisc','custom_aisc_units','custom_gpmp','custom_tnoct'];
  $('#copyBtn').onclick = () => {
    const m = st.module; if(!m) return;
    const code = m.celltech, C = (n,v) => { fillDb(n, v); clearFieldError(f.elements[n]); };
    C('custom_name', `${m.name} (from CEC database)`); C('custom_celltech', code===null ? '' : code);
    C('custom_nser', m.n_s); C('custom_voc', m.v_oc_ref); C('custom_isc', m.i_sc_ref); C('custom_vmp', m.v_mp_ref); C('custom_imp', m.i_mp_ref);
    C('custom_bvoc', m.beta_oc); f.elements.custom_bvoc_units.value = 'abs';
    C('custom_aisc', m.alpha_sc); f.elements.custom_aisc_units.value = 'abs';
    C('custom_gpmp', m.gamma_r); C('custom_tnoct', m.t_noct);
    $('#customBif').checked = !!(m.bifacial || $('#bifOverride').checked);
    if(m.length) fillDb('module_length', mm(m.length)); if(m.width) fillDb('module_width', mm(m.width));
    const noGamma = (m.gamma_r===null || m.gamma_r===undefined);
    $('#copyNote').innerHTML = `<span class="ok">Copied.</span> Check against the datasheet.`
      + (code===null ? ` <span class="warn">No matching cell type: select one.</span>` : '')
      + (noGamma ? ` <span class="warn">No Pmp coefficient in the library: enter it.</span>` : '');
    if(noGamma) setFieldError(fieldBox('custom_gpmp'), 'Not in the CEC database. Enter from the datasheet.');
    update(); scheduleValidate();
  };
  $('#saveModBtn').onclick = () => { const o={format:'PPE SAM custom module', version:1};
    CUSTOM_FIELDS.forEach(n=>o[n.replace('custom_','')]=val(n)); o.bifacial=$('#customBif').checked; o.length_mm=val('module_length'); o.width_mm=val('module_width');
    if(!o.name){ $('#saveNote').innerHTML='<span class="bad">Enter a module name first.</span>'; return; }
    const a=document.createElement('a'); a.href=URL.createObjectURL(new Blob([JSON.stringify(o,null,2)],{type:'application/json'}));
    a.download=(o.name.replace(/[^A-Za-z0-9._-]+/g,'_').replace(/^_+|_+$/g,'')||'custom_module')+'.json';
    document.body.appendChild(a); a.click(); setTimeout(()=>{URL.revokeObjectURL(a.href); a.remove();},1000); $('#saveNote').textContent=`Saved ${a.download}`; };
  $('#loadModBtn').onclick = () => $('#loadModFile').click();
  $('#loadModFile').addEventListener('change', async e => { const file=e.target.files[0]; e.target.value=''; if(!file) return;
    try{ const o=JSON.parse(await file.text()); if(o.format!=='PPE SAM custom module') throw new Error('not a PPE SAM custom module file');
      CUSTOM_FIELDS.forEach(n=>{ const k=n.replace('custom_',''); if(k in o){ delete dbVals[n]; f.elements[n].value=o[k]; clearFieldError(f.elements[n]); } });
      $('#customBif').checked=!!o.bifacial;
      if(o.length_mm){ delete dbVals.module_length; f.elements.module_length.value=o.length_mm; }
      if(o.width_mm){ delete dbVals.module_width; f.elements.module_width.value=o.width_mm; }
      $('#saveNote').innerHTML=`<span class="ok">Loaded ${esc(file.name)}.</span>`; update(); scheduleValidate();
    }catch(err){ $('#saveNote').innerHTML=`<span class="bad">Could not load ${esc(file.name)}: ${esc(err.message)}</span>`; } });

  // ================= layout drawing =================
  function drawLayout(c){
    const wrap=$('#layoutSvgWrap'), note=$('#layoutNote'), H=parseInt(val('modules_high')), A=parseInt(val('modules_across'));
    if(!st.racking || !(H>0) || !(A>0)){ wrap.innerHTML=''; note.textContent='Enter Modules High and Modules Across.'; return; }
    const R = Math.max(1, parseInt(val('rows'))||1), MAXR = 12, Rd = Math.min(R, MAXR);
    const total=H*A; if(total*Rd>6000){ wrap.innerHTML=''; note.textContent=`${(total*R).toLocaleString()} modules (too many to draw).`; return; }
    let L=num('module_length'), W=num('module_width'); if(!(L>0&&W>0)){ L=2000; W=1000; }
    const portrait = val('orientation')!=='landscape', tracker = st.racking==='tracker';
    const azRaw = num('azimuth'), az = (azRaw===null ? 180 : ((azRaw % 360) + 360) % 360), rot = az - 180;
    let cols, rws, cw, ch;
    if(!tracker){ cols=A; rws=H; cw = portrait ? W : L; ch = portrait ? L : W; } else { cols=H; rws=A; cw = portrait ? L : W; ch = portrait ? W : L; }
    const bw=cols*cw, bh=rws*ch, depth = tracker ? bw : bh;
    let P = c.pitchM ? c.pitchM*1000 : null, toScale = true;
    if(st.racking==='carport' || !P || P < depth){ P = depth*1.5; toScale = Rd===1; }
    const Wt = tracker ? bw+(Rd-1)*P : bw, Ht = tracker ? bh : bh+(Rd-1)*P;
    const target=520, s=Math.min(target/Wt, target/Ht), gw=Wt*s, gh=Ht*s;
    const rad=rot*Math.PI/180, co=Math.abs(Math.cos(rad)), sn=Math.abs(Math.sin(rad));
    const bbw=gw*co+gh*sn, bbh=gw*sn+gh*co, pad=70, VW=bbw+2*pad, VH=bbh+2*pad, cx=VW/2, cy=VH/2, x0=cx-gw/2, y0=cy-gh/2;
    let rects='';
    for(let r=0;r<Rd;r++){ const ox = tracker ? r*P*s : 0, oy = tracker ? 0 : r*P*s;
      for(let i=0;i<rws;i++) for(let j=0;j<cols;j++)
        rects+=`<rect x="${(x0+ox+j*cw*s).toFixed(2)}" y="${(y0+oy+i*ch*s).toFixed(2)}" width="${(cw*s).toFixed(2)}" height="${(ch*s).toFixed(2)}"/>`; }
    const aL=`Modules Across: ${A}`, hL=`Modules High: ${H}`, top = tracker ? hL : aL, side = tracker ? aL : hL;
    const bwp = bw*s, bhp = bh*s;
    const ah = Math.min(40, Math.max(22, Math.min(gw,gh)*0.25));
    const arrow = `<line x1="${cx}" y1="${y0+gh+6}" x2="${cx}" y2="${y0+gh+6+ah}" marker-end="url(#ah)"/>`;
    const norm = a => (((a % 360) + 540) % 360) - 180;
    const flipTop = Math.abs(norm(rot)) > 90 ? 180 : 0, flipSide = Math.abs(norm(rot - 90)) > 90 ? 180 : 0;
    const compassX=VW-28, compassY=30;
    wrap.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="${VW.toFixed(0)}" height="${VH.toFixed(0)}" viewBox="0 0 ${VW.toFixed(1)} ${VH.toFixed(1)}" role="img" aria-label="${esc(top+', '+side+', '+R+' rows, azimuth '+az+' degrees')}">
      <defs><marker id="ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#1f4e8c"/></marker></defs>
      <g transform="rotate(${rot.toFixed(2)} ${cx.toFixed(1)} ${cy.toFixed(1)})">
        <g fill="#fff" stroke="#000" stroke-width="1">${rects}</g>
        <g stroke="#1f4e8c" stroke-width="2.5">${arrow}</g>
        <text transform="translate(${(x0+bwp/2).toFixed(1)},${(y0-10).toFixed(1)}) rotate(${flipTop})" dy="${flipTop?'0.8em':'0'}" text-anchor="middle" font-size="13" font-family="Segoe UI, Arial">${esc(top)}</text>
        <text transform="translate(${(x0-12).toFixed(1)},${(y0+bhp/2).toFixed(1)}) rotate(${-90+flipSide})" dy="${flipSide?'0.8em':'0'}" text-anchor="middle" font-size="13" font-family="Segoe UI, Arial">${esc(side)}</text>
      </g>
      <g font-family="Segoe UI, Arial" font-size="12" font-weight="700" fill="#374151">
        <line x1="${compassX}" y1="${compassY+16}" x2="${compassX}" y2="${compassY-8}" stroke="#374151" stroke-width="2" marker-end="url(#ah)"/>
        <text x="${compassX}" y="${compassY-12}" text-anchor="middle">N</text>
      </g>
      <text x="10" y="${(VH-10).toFixed(1)}" font-family="Segoe UI, Arial" font-size="13" fill="#1f4e8c" font-weight="600">Azimuth ${fnum(az,1)}°${tracker?' (axis)':' (facing)'} · ${R} row${R>1?'s':''}</text>
    </svg>`;
    note.textContent = `${R} row${R>1?'s':''} of ${H} × ${A} = ${(total*R).toLocaleString()} modules, ${portrait?'portrait':'landscape'}. Plan view, north up; blue arrow = ${tracker?'tracker axis direction':'direction the modules face'} (180° = due south).`
      + (R>MAXR ? ` First ${MAXR} rows drawn.` : '') + (!toScale ? ' Row spacing not to scale.' : '')
      + (azRaw===null ? ' Enter an azimuth to rotate the array.' : '');
  }

  // ================= calculated values =================
  const setCalc = (id, text) => { $(id).value = (text===null||text===undefined) ? '' : text; };
  function calcState(){
    const L=num('module_length'), W=num('module_width'), r=st.racking, c={ar:(L>0&&W>0)?L/W:null, area:(L>0&&W>0)?L*W/1e6:null};
    const b=num('bifaciality_base'), t=num('bifaciality_tol'); c.bif = (b!==null&&t!==null) ? (b+t)/100 : null;
    const H=parseInt(val('modules_high')), A=parseInt(val('modules_across')), M=parseInt(val('modules_per_string')), R=parseInt(val('rows'));
    if(H>0 && A>0 && M>0 && R>0){ c.sub=H*A; c.ns=Math.max(1,Math.ceil(R*c.sub/M)); c.rowsActual=Math.floor(c.ns*M/c.sub); c.R=R; }
    const o=val('orientation'), along = o ? (o==='portrait' ? L : W)/1000 : null, n=Math.max(1,H||1); c.along=along; c.n=n;
    const gapM = n>1 ? (num('gap')===null ? null : num('gap')*IN) : 0;
    c.pitchM = null;
    if(r==='carport') c.gcr = 0.01;
    else if(st.gmode==='gcr'){ c.gcr = num('gcr'); c.pitchM = (c.gcr && along>0) ? n*along/c.gcr : null; }
    else { const P=metres('pitch'); c.pitchM = P; c.gcr = (P>0 && along>0 && gapM!==null) ? (n*along + gapM*(n-1))/P : null; }
    const vmp=num('custom_vmp'), imp=num('custom_imp'); c.pmp = (vmp>0&&imp>0) ? vmp*imp : null;
    return c;
  }
  function renderCalc(c){
    setCalc('#cAr', c.ar ? c.ar.toFixed(3) : null);
    setCalc('#cArea', c.area ? c.area.toFixed(3) : null);
    setCalc('#cBif', c.bif!==null ? c.bif.toFixed(3) : null);
    setCalc('#cPmp', c.pmp ? c.pmp.toFixed(1) : null);
    setCalc('#cEff', (c.pmp && c.area) ? (c.pmp/(c.area*1000)*100).toFixed(2) : null);
    const iscNote=$('#iscDsNote'), iscDs=num('isc_datasheet'), iscLib=st.module ? st.module.i_sc_ref : null;
    if(iscLib){ const pct = iscDs>0 ? (iscDs/iscLib-1)*100 : null, far = pct!==null && Math.abs(pct)>10;
      iscNote.className = 'note' + (far ? ' warn' : '');
      iscNote.textContent = `CEC library: ${fmt(iscLib,2)} A` + (pct===null ? '' : ` (datasheet ${pct>=0?'+':''}${pct.toFixed(1)}%)`) + (far ? '. Check the datasheet value.' : ''); }
    else iscNote.textContent = '';
    const eq=(raw,units,ref,absUnit)=>{ const x=parseFloat(raw); if(isNaN(x)||!(ref>0)) return '';
      const a = units==='pct' ? x/100*ref : x; return units==='pct' ? `= ${a.toPrecision(4)} ${absUnit}` : `= ${(a/ref*100).toFixed(4)} %/°C`; };
    $('#bvocEq').textContent = eq(val('custom_bvoc'), val('custom_bvoc_units'), num('custom_voc'), 'V/°C');
    $('#aiscEq').textContent = eq(val('custom_aisc'), val('custom_aisc_units'), num('custom_isc'), 'A/°C');
    const leq = n => { const x=num(n); return (x!==null && val(n+'_units')==='in') ? `= ${(x*IN).toFixed(3)} m` : ''; };
    $('#pitchEq').textContent = leq('pitch'); $('#gcEq').textContent = leq('ground_clearance');
    if(st.racking!=='carport'){
      setCalc('#cGcr', (st.gmode==='pitch' && c.gcr) ? c.gcr.toFixed(3) : null);
      setCalc('#cPitch', (st.gmode==='gcr' && c.pitchM) ? c.pitchM.toFixed(2) : null);
      $('#cGcr').title = (st.gmode==='pitch' && c.gcr && (c.gcr>0.99 || c.gcr<0.01)) ? 'Outside 0.01–0.99: check the row pitch' : '';
    }
    setCalc('#cStr', c.ns || null);
    $('#rowsNote').classList.toggle('hidden', !(parseInt(val('rows'))>1));
    $('#mismatchNote').classList.toggle('hidden', !(isBif() && $('#bifMismatch').checked));
    const sn = $('#strNote');
    if(c.ns && c.rowsActual!==c.R){ sn.textContent = `SAM cannot model exactly ${c.R} row(s) with these values; the nearest is ${c.rowsActual}.`; sn.classList.remove('hidden'); }
    else sn.classList.add('hidden');
    // self-shading: PPE standard for the current module + warning when the selection differs
    const ppe = ppeShade(), sel = val('self_shading'), haveMod = haveModule();
    $('#shadeStd').textContent = haveMod ? `PPE standard for this module: ${SHADE_NAME[ppe]}` : '';
    const w = $('#shadeWarn');
    if(haveMod && sel && sel!==ppe){
      w.textContent = `Warning: PPE Standard for this module is ${SHADE_NAME[ppe]}. ` + (ppe==='none'
        ? 'Adding self-shading to a monofacial module will produce a lower & more aggressive Isc value.'
        : (sel==='none' ? 'Turning self-shading off removes rear-side shading effects from the bifacial model.'
                        : `${SHADE_NAME[sel]} is meant for ${sel==='thin_film'?'thin-film':'crystalline silicon'} modules.`));
      w.classList.remove('hidden');
    } else w.classList.add('hidden');
  }

  // ================= modeling assumptions (config page) =================
  const T3 = rows => `<table><tr><th>Item</th><th>Simulation</th><th>Why</th></tr>`
    + rows.map(r => `<tr><td>${esc(r[0])}</td><td><b>${esc(r[1])}</b></td><td class="why">${esc(r[2])}</td></tr>`).join('') + '</table>';
  function renderAssumptions(c){
    const bif=isBif();
    const mrows = [
      ['Module model', st.src==='custom' ? 'CEC User Entered Specifications' : 'CEC Module Database', st.src==='custom' ? 'SAM calculates the single-diode parameters from the datasheet values' : 'Uses the library’s single-diode parameters'],
      ['Temperature model', 'NOCT, ground or rack mounted, one story', 'PPE decision'],
      ['Module losses', '0 % (soiling, mismatch, diodes, nameplate)', 'Worst case (PPE guide 7–8)']];
    if(bif){ mrows.push(['Bifaciality used', 'Bifaciality + tolerance', 'Upper end of the range (worst case)']);
             mrows.push(['Bifacial electrical mismatch', $('#bifMismatch').checked ? 'Calculated by SAM (not PPE standard)' : 'Off (PPE standard)', 'Ignoring it gives the worst-case (higher) Isc']);
             mrows.push(['Bifacial transmission fraction', '0.013', 'SAM default (PPE guide 4.3)']); }
    $('#modAssume').innerHTML = T3(mrows);
    const inv = st.inverter, sv = val('system_voltage'), V = x => (x===null||x===undefined) ? 'n/a' : `${fnum(x)} V`, svT = sv ? `${Number(sv).toLocaleString()} V` : 'system max. voltage';
    const sel = val('self_shading');
    const srows = [
      ['Inverter MPPT low', `0 V${inv?` (library ${V(inv.mppt_low)})`:''}`, 'Inverter window never limits Vmp (PPE guide 6.5)'],
      ['Inverter MPPT high', `${svT}${inv?` (library ${V(inv.mppt_high)})`:''}`, 'System maximum voltage (PPE guide 6.5)'],
      ['Inverter max DC voltage', `${svT}${inv?` (library ${V(inv.vdcmax)})`:''}`, 'System maximum voltage (PPE guide 6.5)'],
      ['Strings and inverters', c.ns ? `${c.ns} string(s) on one inverter` : 'All strings on one inverter', 'Fills the rows modeled; results per string'],
      ['Number of rows', 'As entered on Settings (PPE standard 1)', 'More than 1 row adds row-to-row self-shading (lower Isc)'],
      ['Self-shading', sel ? SHADE_NAME[sel] : 'PPE standard for the module', 'PPE guide 7.3: bifacial → Standard (Thin film for thin-film cells); monofacial → None'],
      ['Tracker', 'Tilt 0°, backtracking on', 'PPE guide 6.3'],
      ['Wiring and system losses', '0 %', 'Worst case'],
      ['Albedo', 'Weather file (0.2 where missing or invalid)', 'PPE guide 3.4'],
      ['Sky model', 'DNI + DHI, Perez', 'PPE guide 3.4'], ['Grid limits', 'None', 'PPE guide 9']];
    $('#sysAssume').innerHTML = T3(srows);
  }

  // ================= readiness + auto-expand =================
  function missing(){
    const m={1:[],2:[],3:[],4:[],5:[]}, need=(s,n,cond=true)=>{ if(cond && !val(n)) m[s].push(n); };
    if(!st.loc) m[1].push('location_mode');
    else if(st.loc==='address'){ if(!val('address') || !val('lat') || !val('lon')) m[1].push('address'); }
    else { need(1,'lat'); need(1,'lon'); }
    if(st.src==='cec'){ if(!st.module) m[2].push('module_name'); else need(2,'isc_datasheet'); }
    else ['custom_name','custom_celltech','custom_nser','custom_voc','custom_isc','custom_vmp','custom_imp','custom_bvoc','custom_aisc','custom_gpmp','custom_tnoct'].forEach(n=>need(2,n));
    const dims = st.src==='custom' || st.module; need(2,'module_length',dims); need(2,'module_width',dims);
    if(isBif()){ need(2,'bifaciality_base'); need(2,'bifaciality_tol'); need(2,'bifacial_gain'); }
    if(!st.inverter) m[3].push('inverter_name');
    if(!st.racking) m[4].push('racking');
    need(4,'modules_per_string'); need(4,'system_voltage');
    if(st.racking){ need(4,'tilt',st.racking!=='tracker'); need(4,'rotlim',st.racking==='tracker'); need(4,'azimuth'); need(4,'orientation');
      if(isBif()) need(4,'ground_clearance'); need(4,'modules_high'); need(4,'modules_across');
      if(st.racking!=='carport'){ if(st.gmode==='gcr') need(4,'gcr'); else { need(4,'pitch'); need(4,'gap', (parseInt(val('modules_high'))||1)>=2); } } }
    need(5,'self_shading', haveModule()); need(5,'rows');
    return m;
  }
  let lastReady = null;
  const SEC_NAME = {1:'Site and weather', 2:'Module', 3:'Inverter', 4:'System design', 5:'Settings'};
  function renderReadiness(m){
    // Rewrite only on change: leaving a field re-renders, and replacing a link mid-click loses the click.
    const html = [1,2,3,4,5].map(s => { const L=m[s];
      return `<li class="${L.length?'':'ok'}"><div class="rh"><span class="ri"></span>${SEC_NAME[s]}</div>`
        + (L.length ? `<div class="rm">${L.slice(0,4).map(n=>`<button type="button" class="linkbtn" data-jump="${n}">${esc(LABELS[n]||n)}</button>`).join(', ')}${L.length>4?` +${L.length-4}`:''}</div>` : '') + '</li>'; }).join('');
    if(html !== lastReady){ lastReady = html; $('#ready').innerHTML = html; }
    [1,2,3,4].forEach(s => { const ch=$('#chip'+s); ch.classList.toggle('done', !m[s].length); ch.textContent = m[s].length ? 'Incomplete' : 'Complete'; });
    const now = [1,2,3,4].map(s => !m[s].length);
    if(st.complete){ [1,2,3].forEach(s => { if(now[s-1] && !st.complete[s-1]){ const nx=$('#sec'+(s+1)); if(nx.classList.contains('collapsed')) setCollapsed(nx, false); } }); }
    st.complete = now;
  }
  document.addEventListener('click', e => { const b=e.target.closest('[data-jump]'); if(b) jumpTo(b.dataset.jump); });
  function jumpTo(field){ const box = fieldBox(field); if(!box) return; showView(box.closest('#pageSet') ? 'set' : 'cfg'); const card = box.closest('.card'); if(card && card.classList.contains('collapsed')) setCollapsed(card, false);
    box.scrollIntoView({behavior:'smooth', block:'center'}); const i = box.querySelector('input:not([type=checkbox]):not([readonly]),select,[role=radio],button'); i && i.focus({preventScroll:true}); }

  // ================= summary =================
  const hemi = (v,p,n) => `${Math.abs(v).toFixed(5)}° ${v>=0?p:n}`;
  function renderSummary(c){
    const E = t => `<span class="empty">${t}</span>`, lat=num('lat'), lon=num('lon'), okLL = lat!==null && lon!==null && Math.abs(lat)<=90 && Math.abs(lon)<=180;
    const site = okLL ? `${hemi(lat,'N','S')}, ${hemi(lon,'E','W')}` : null;
    $('#sProject').innerHTML = val('project') ? esc(val('project')) : E('Not named');
    const addr = st.loc==='address' && val('address') ? `${esc(val('address'))}<br>` : '';
    $('#sSite').innerHTML = site ? `${addr}${site} · ${val('interval')}-min` : E(st.loc==='address' ? 'Run the address lookup' : st.loc ? 'Coordinates needed' : 'Choose Address or Coordinates');
    let mod = null;
    if(st.src==='cec' && st.module) mod = `${esc(st.module.name)} · ${fnum(st.module.stc)} W${isBif()?' · bifacial':''}`;
    if(st.src==='custom' && val('custom_name')) mod = `${esc(val('custom_name'))}${c.pmp?` · ${c.pmp.toFixed(0)} W`:''}${isBif()?' · bifacial':''}`;
    $('#sModule').innerHTML = mod || E('Not selected');
    $('#sInverter').innerHTML = st.inverter ? `${esc(st.inverter.name)} · ${fmt(st.inverter.paco/1000,1)} kWac` : E('Not selected');
    $('#sString').innerHTML = (val('modules_per_string')||val('system_voltage')) ? `${val('modules_per_string')||'?'} modules · ${val('system_voltage')?val('system_voltage')+' V':'voltage?'}` : E('Not set');
    const r=st.racking, R=val('rows'), sh=val('self_shading');
    $('#sMount').innerHTML = r ? `${RACK_NAME[r]} · ${val('modules_high')||'?'} × ${val('modules_across')||'?'}${R?` · ${R} row${R==='1'?'':'s'}`:''}${c.gcr?` · GCR ${c.gcr.toFixed(3)}`:''}${sh?` · self-shading ${SHADE_NAME[sh]}`:''}` : E('Not chosen');
    $('#csum1').textContent = site ? `${st.loc==='address'&&val('address')?val('address')+' · ':''}${site} · ${val('interval')}-min` : 'Location needed';
    $('#csum2').textContent = st.src==='cec' ? (st.module ? `${st.module.name} · ${fnum(st.module.stc)} W` : 'No module selected') : (val('custom_name') || 'Custom module incomplete');
    $('#csum3').textContent = st.inverter ? st.inverter.name : 'No inverter selected';
    $('#csum4').textContent = r ? `${RACK_NAME[r]} · ${val('modules_per_string')||'?'} modules · ${val('system_voltage')||'?'} V · ${val('modules_high')||'?'} × ${val('modules_across')||'?'}${R?` · ${R} row(s)`:''}${c.gcr?` · GCR ${c.gcr.toFixed(3)}`:''}` : 'Not chosen';
    $('#verifyLoc').disabled = !okLL; $('#locText').textContent = okLL ? site : '';
  }
  $('#verifyLoc').onclick = () => { const a=num('lat'), o=num('lon'); if(a===null||o===null) return;
    window.open(`https://www.bing.com/maps?cp=${a}~${o}&lvl=16&style=h&sp=point.${a}_${o}_Site`, '_blank', 'noopener'); };

  // ================= visibility / update =================
  function setRO(name, ro){ const el=f.elements[name], box=fieldBox(name); el.readOnly = ro; el.tabIndex = ro ? -1 : 0; box.classList.toggle('ro', ro); }
  function applyVisibility(){
    const custom = st.src==='custom', r = st.racking, bif = isBif();
    $('#locPrompt').classList.toggle('hidden', !!st.loc);
    setRO('address', st.loc!=='address'); setRO('lat', st.loc!=='coords'); setRO('lon', st.loc!=='coords');
    f.elements.address.placeholder = st.loc==='coords' ? 'Not used' : 'e.g. 1 Main St, Stamford, CT';
    f.elements.lat.placeholder = st.loc==='address' ? 'From address lookup' : st.loc ? 'e.g. 39.18886' : '';
    f.elements.lon.placeholder = st.loc==='address' ? 'From address lookup' : st.loc ? 'e.g. -76.60095' : '';
    $('#geoRun').classList.toggle('hidden', !(st.loc==='address' && val('address')));
    if(st.loc!=='address') $('#geoNote').textContent = '';
    $('#cecBox').classList.toggle('hidden', custom); $('#customBox').classList.toggle('hidden', !custom);
    $('#copyBox').classList.toggle('hidden', !(custom && st.module));
    $('#ovBox').classList.toggle('hidden', !(st.module && !st.module.bifacial));
    $('#iscDsBox').classList.toggle('hidden', !st.module);
    $('#bifMismatch').disabled = !bif; $('#mismatchNA').classList.toggle('hidden', bif);
    $('#bifBox').classList.toggle('hidden', !bif);
    $('#rackFields').classList.toggle('hidden', !r); $('#rackPrompt').classList.toggle('hidden', !!r);
    $$('.r-tracker,.r-fixed,.r-carport').forEach(el => el.classList.toggle('hidden', !(r && el.classList.contains('r-'+r))));
    $$('.bif-only').forEach(el => el.classList.toggle('hidden', !bif));
    $('#highTip').textContent = HIGH_TIP[r || 'tracker'];
    f.elements.ground_clearance.placeholder = `e.g. ${GC_TYPICAL[val('ground_clearance_units')==='m'?'m':'in'][r || 'tracker']}`;
    f.elements.pitch.placeholder = val('pitch_units')==='m' ? 'e.g. 6.0' : 'e.g. 236';
    $('#spacingBox').classList.toggle('hidden', !r || r==='carport'); $('#carportGcr').classList.toggle('hidden', r!=='carport');
    $$('.g-pitch').forEach(el=>el.classList.toggle('hidden', st.gmode!=='pitch')); $$('.g-gcr').forEach(el=>el.classList.toggle('hidden', st.gmode!=='gcr'));
    if(st.gmode==='pitch') $('#gapBox').classList.toggle('hidden', (parseInt(val('modules_high'))||1) < 2);
  }
  function update(){ applyVisibility(); syncShade(); const c = calcState(); renderCalc(c); drawLayout(c); renderSources();
    renderAssumptions(c); renderSummary(c); renderReadiness(missing()); renderWxBtn(); }
  f.addEventListener('input', e => { clearFieldError(e.target); update(); });
  f.addEventListener('change', e => { clearFieldError(e.target); update(); });

  // ================= validation =================
  function fieldBox(field){ return document.querySelector(`[data-field="${field}"]`); }
  function setFieldError(box, msg){ if(!box) return; box.classList.add('invalid'); let m=box.querySelector(':scope > .fielderr');
    if(!m){ m=document.createElement('div'); m.className='fielderr'; box.appendChild(m); } m.textContent=msg;
    const i=box.querySelector('input,select'); i && i.setAttribute('aria-invalid','true'); }
  function clearBox(box){ if(!box) return; box.classList.remove('invalid'); const m=box.querySelector(':scope > .fielderr'); m && m.remove();
    const i=box.querySelector('input,select'); i && i.removeAttribute('aria-invalid'); }
  function clearFieldError(el){ const box = el && el.closest ? el.closest('[data-field]') : null; clearBox(box);
    if(box && box.parentElement){ const outer = box.parentElement.closest('[data-field=custom_fit]'); outer && clearBox(outer); } }
  function clearAllErrors(){ $$('[data-field].invalid').forEach(clearBox); hideSummary(); }
  function payload(){
    const o={}; [...f.elements].forEach(el=>{ if(el.name && el.type!=='checkbox' && !notApplicable(el)) o[el.name]=String(el.value).trim(); });
    o.location_mode=st.loc||''; o.module_source=st.src; o.module_name=st.module&&st.module.name; o.inverter_name=st.inverter&&st.inverter.name; o.racking=st.racking;
    o.gcr_mode=st.gmode; o.bifacial_override=(st.src==='cec'&&st.module&&!st.module.bifacial&&$('#bifOverride').checked)?'1':'0';
    o.custom_bifacial=(st.src==='custom'&&$('#customBif').checked)?'1':'0';
    o.bifacial_mismatch=(isBif() && $('#bifMismatch').checked)?'1':'0';
    o.db_fields = dbFields(); o.db_values = Object.fromEntries(o.db_fields.map(n => [n, dbVals[n]]));
    if(st.loc!=='address'){ delete o.address; delete o.geocode_match; delete o.geocode_source; }
    if(!isBif()){ delete o.ground_clearance; delete o.ground_clearance_units; }
    return o; }
  async function serverValidate(){ const r = await fetch('/api/validate',{method:'POST',body:JSON.stringify(payload())}); return r.json(); }
  let vTimer;
  function scheduleValidate(){ clearTimeout(vTimer); vTimer = setTimeout(validateTouched, 350); }
  async function validateTouched(){ if(!st.touched.size) return;
    let j; try{ j = await serverValidate(); }catch(e){ return; }
    const by={}; (j.errors||[]).forEach(e=>{ if(e.field && !(e.field in by)) by[e.field]=e.message; });
    st.touched.forEach(n => { const box=fieldBox(n); if(!box) return;
      if(by[n] && !notApplicable(box)) setFieldError(box, by[n]); else if(box.classList.contains('invalid') && n!=='custom_gpmp') clearBox(box); });
    if(!$('#errSummary').classList.contains('hidden')) showSummary(j.errors||[], false); }
  f.addEventListener('focusout', e => { let n = e.target.name; if(!n) return; n = n.replace(/_units$/,'');
    if(n==='address') return;
    st.touched.add(n); if(n.startsWith('custom_')) st.touched.add('custom_fit'); scheduleValidate(); });
  function showSummary(errors, focus=true){ const box=$('#errSummary'); if(!errors.length){ hideSummary(); return; }
    box.innerHTML = `<h2>Fix ${errors.length} item${errors.length>1?'s':''} before running</h2><ul>`
      + errors.map(e => `<li>${e.field ? `<button type="button" class="linkbtn" data-jump="${esc(e.field)}">${esc(e.message)}</button>` : esc(e.message)}</li>`).join('') + '</ul>';
    box.classList.remove('hidden'); if(focus){ if(st.view!=='set') showView('cfg'); box.scrollIntoView({behavior:'smooth',block:'start'}); box.focus({preventScroll:true}); }
    $('#sideStatus').innerHTML = `<span class="bad">${errors.length} item${errors.length>1?'s':''} to fix (listed at the top).</span>`; }
  function hideSummary(){ $('#errSummary').classList.add('hidden'); $('#errSummary').innerHTML=''; if(!st.running) $('#sideStatus').textContent=''; }

  // ================= progress card (shared by runs and background weather retrieval) =================
  function stage(k, cls, label){ $('#st'+k).className = 'stage ' + (cls||''); $('#st'+k+'s').textContent = label; }
  function prepProgress(isRun){
    ['W','S','A'].forEach(k=>{ $('#st'+k).className='stage'; $('#st'+k+'d').textContent=''; $('#st'+k+'s').textContent='Waiting'; $('#st'+k+'b').style.width='0'; });
    $('#runErr').classList.add('hidden'); $('#progress').classList.remove('hidden'); $('#plog').textContent='';
    $('#cancelBtn').classList.toggle('hidden', !isRun);
  }
  function renderWeatherStage(j, finishedBeyond){
    const w=j.weather||{};
    $('#stWb').style.width = (finishedBeyond ? 100 : w.requested ? w.processed/w.requested*100 : 0) + '%';
    $('#stWd').innerHTML = `${w.processed||0} of ${w.requested||0} years (${w.first}–${w.last}) · ${w.downloaded||0} downloaded · ${w.cached||0} cached · ${w.unavailable||0} not available · ${w.failed||0} failed`
      + ((w.unavailable_years||[]).length ? `<br>Not available: ${w.unavailable_years.join(', ')}` : '')
      + ((w.failed_years||[]).length ? `<br><span class="bad">Failed: ${w.failed_years.join(', ')}</span>` : '');
  }
  function renderProgress(j){
    const S=j.status, lg=$('#plog'); $('#pmsg').textContent = j.message || S;
    lg.textContent=(j.log||[]).join('\n'); lg.scrollTop=lg.scrollHeight;
    if(j.kind==='weather'){
      renderWeatherStage(j, S==='done');
      if(S==='done'){ stage('W','done','Done'); stage('S','','Waiting for Run simulation'); stage('A','','Waiting'); $('#resTitle').textContent='Weather retrieval complete'; }
      else if(S==='error'){ stage('W','failed','Failed'); $('#runErr').innerHTML = `<b>Weather retrieval failed.</b> ${esc(j.error)}`; $('#runErr').classList.remove('hidden'); $('#resTitle').textContent='Weather retrieval failed'; }
      else if(S==='cancelled'){ stage('W','cancelled','Cancelled'); }
      else { stage('W','active','In progress'); stage('S','','Waiting'); stage('A','','Waiting'); }
      return;
    }
    const s=j.sim||{}, a=j.analysis||{};
    const after = {downloading:0, confirm:0, simulating:1, analyzing:2, done:3}[S];
    renderWeatherStage(j, after>0);
    $('#stSb').style.width = (s.total ? s.done/s.total*100 : 0) + '%';
    $('#stSd').innerHTML = s.total ? `${s.done} of ${s.total} years simulated` + ((s.failed_years||[]).length ? ` · <span class="bad">failed: ${s.failed_years.join(', ')}</span>` : '') : '';
    $('#stAb').style.width = (S==='done' ? 100 : a.total ? a.done/a.total*100 : 0) + '%';
    $('#stAd').textContent = S==='done' ? '3-hour averages calculated' : (a.total ? `${Math.min(a.done, a.total-1)} of ${a.total-1} years read` : '');
    if(after!==undefined){
      stage('W', after>0 ? 'done' : 'active', after>0 ? 'Done' : (S==='confirm' ? 'Waiting for you' : 'In progress'));
      stage('S', after>1 ? 'done' : after===1 ? 'active' : '', after>1 ? 'Done' : after===1 ? 'In progress' : 'Waiting');
      stage('A', after>2 ? 'done' : after===2 ? 'active' : '', after>2 ? 'Done' : after===2 ? 'In progress' : 'Waiting'); }
  }

  // ================= run =================
  $('#runBtn').onclick = async () => {
    let j; try{ j = await serverValidate(); } catch(e){ showSummary([{field:null, message:'Could not reach the app. Is the console window still open?'}]); return; }
    if(!j.ok){ (j.errors||[]).forEach(e=>{ if(e.field) st.touched.add(e.field); }); clearAllErrors();
      (j.errors||[]).forEach(e=>{ const b=fieldBox(e.field); if(b && !notApplicable(b)){ setFieldError(b, e.message); const card=b.closest('.card'); if(card && card.classList.contains('collapsed')) setCollapsed(card,false); } }); showSummary(j.errors||[]); return; }
    hideSummary();
    $('#revBody').innerHTML = '<table>' + j.groups.map(([g, rows]) => `<tr class="grp"><td colspan="2">${esc(g)}</td></tr>`
      + rows.map(r => `<tr><th style="width:120px">${esc(r[0])}</th><td>${esc(r[1])}</td></tr>`).join('')).join('') + '</table>';
    openModal('#reviewModal'); };
  $('#revBack').onclick = () => closeModal('#reviewModal');
  $('#revRun').onclick = async () => { closeModal('#reviewModal');
    let r, j; try{ r=await fetch('/api/run',{method:'POST',body:JSON.stringify(payload())}); j=await r.json(); }
    catch(e){ showSummary([{field:null, message:'Could not reach the app. Is the console window still open?'}]); return; }
    if(!r.ok){ showSummary(j.errors || [{field:null,message:j.error}]); return; }
    st.job=j.job; st.jobPrompted=false; st.running=true; st.showing='run'; $('#runBtn').disabled=true;
    $('#tabRes').disabled=false; $('#results').classList.add('hidden'); prepProgress(true); $('#resTitle').textContent='Running…';
    showView('res'); poll(); };
  $('#cancelBtn').onclick = () => st.job && fetch(`/api/job/${st.job}/cancel`,{method:'POST',body:'{}'});

  async function poll(){
    let j; try{ j=await (await fetch('/api/job/'+st.job)).json(); }catch(e){ setTimeout(poll,2000); return; }
    const w=j.weather||{}, s=j.sim||{}, S=j.status;
    renderProgress(j);
    $('#sideStatus').innerHTML = S==='downloading' ? `Retrieving weather: ${w.processed||0} of ${w.requested||0}` : S==='simulating' ? `Simulating: ${s.done} of ${s.total}`
      : S==='analyzing' ? 'Analyzing…' : S==='confirm' ? '<span class="warn">Waiting for your answer (Results tab)</span>' : '';
    if(S==='confirm' && !st.jobPrompted){ st.jobPrompted=true; ask(j.message,'Continue',ok=>fetch(`/api/job/${st.job}/continue`,{method:'POST',body:JSON.stringify({proceed:ok})})); }
    if(['done','error','cancelled'].includes(S)){
      st.running=false; $('#runBtn').disabled=false; $('#cancelBtn').classList.add('hidden'); refreshCache();
      if(S==='error'){ const k={validation:'W',weather:'W',simulation:'S',analysis:'A'}[j.failed_stage]||'W', order=['W','S','A'];
        order.forEach((x,i)=>{ if(i<order.indexOf(k)) stage(x,'done','Done'); }); stage(k,'failed','Failed');
        const kept=(w.downloaded||0)+(w.cached||0);
        $('#runErr').innerHTML = `<b>Run failed during ${({W:'weather retrieval',S:'simulation',A:'analysis'})[k]}.</b> ${esc(j.error)}<br>Inputs are unchanged.${kept?` ${kept} weather years are cached.`:''}`;
        $('#runErr').classList.remove('hidden'); $('#resTitle').textContent='Run failed'; $('#sideStatus').innerHTML = '<span class="bad">Run failed. See the Results tab.</span>'; }
      if(S==='cancelled'){ ['W','S','A'].forEach(k=>{ if($('#st'+k).classList.contains('active')) stage(k,'cancelled','Cancelled'); }); $('#resTitle').textContent='Run cancelled'; $('#sideStatus').textContent='Run cancelled.'; }
      if(S==='done'){ st.doneJob=st.job; $('#finalLog').textContent = (j.log||[]).join('\n'); $('#progress').classList.add('hidden');
        show(j.result); $('#sideStatus').innerHTML = '<span class="ok">Complete. See the Results tab.</span>'; }
      return; }
    setTimeout(poll,1000);
  }

  // ================= exports / print =================
  $$('[data-export]').forEach(b=>b.addEventListener('click',async()=>{
    $('#exportErr').textContent=''; if(!st.doneJob){ $('#exportErr').textContent='Run the simulation first.'; return; } b.disabled=true;
    try{ const r=await fetch(`/api/job/${st.doneJob}/export/${b.dataset.export}`);
      if(!r.ok){ const j=await r.json().catch(()=>({})); $('#exportErr').textContent=j.error||'Download failed.'; return; }
      const cd=r.headers.get('Content-Disposition')||'', m=cd.match(/filename="([^"]+)"/), blob=await r.blob(), a=document.createElement('a');
      a.href=URL.createObjectURL(blob); a.download=m?m[1]:'export'; document.body.appendChild(a); a.click(); setTimeout(()=>{URL.revokeObjectURL(a.href); a.remove();},1000);
    }catch(e){ $('#exportErr').textContent='Download failed: '+e; } finally{ b.disabled=false; } }));
  let openBefore=[];
  window.addEventListener('beforeprint',()=>{ const t=`PPE SAM Multi-Year Simulation v${(st.info&&st.info.version)||''} · printed ${new Date().toLocaleString()}`;
    $('#printStamp').textContent=t; $('#printStamp2').textContent=t; openBefore=$$('details').map(d=>d.open); $$('details').forEach(d=>d.open=true); });
  window.addEventListener('afterprint',()=>{ $$('details').forEach((d,i)=>d.open=openBefore[i]); });
  $('#printBtn').onclick = $('#printBtn2').onclick = () => window.print();

  // ================= reset =================
  function resetAll(){
    f.reset(); clearAllErrors(); st.touched.clear(); Object.keys(dbVals).forEach(k=>delete dbVals[k]);
    Object.assign(st,{src:'cec', loc:null, racking:null, gmode:'pitch', geo:null, complete:null, shadeAuto:true}); locG.clear(); srcG.sync($('[data-src=cec]')); rackG.clear(); gcrG.sync($('[data-g=pitch]'));
    modPicker.reset(); invPicker.reset(); ['#customBif','#bifMismatch','#bifOverride'].forEach(s=>$(s).checked=false); ['#copyNote','#saveNote','#geoNote'].forEach(s=>$(s).textContent='');
    $('#cCarGcr').value='0.01';
    setCollapsed($('#sec1'), false); ['#sec2','#sec3','#sec4'].forEach(s=>setCollapsed($(s), true));
    $('#layoutBox').open=false; update(); window.scrollTo({top:0,behavior:'smooth'}); }
  $('#resetBtn').onclick=()=>ask('Clear all inputs? Results and the weather cache are not affected.','Reset inputs',ok=>ok&&resetAll());

  // ================= save / load inputs (.json) =================
  // File = {format, version, app_version, saved, inputs}; "inputs" is exactly what Run sends to the server,
  // so the same file comes from Save inputs here and from Results > Downloads > Inputs (.json).
  const INPUTS_FORMAT = 'PPE SAM inputs';
  function saveFile(name, text){ const a=document.createElement('a'); a.href=URL.createObjectURL(new Blob([text],{type:'application/json'}));
    a.download=name; document.body.appendChild(a); a.click(); setTimeout(()=>{URL.revokeObjectURL(a.href); a.remove();},1000); }
  $('#saveInBtn').onclick = () => {
    const o = {format:INPUTS_FORMAT, version:1, app_version:(st.info&&st.info.version)||'', saved:new Date().toISOString(), inputs:payload()};
    const name = ((val('project')||'PPE_SAM').replace(/[^A-Za-z0-9._-]+/g,'_').replace(/^_+|_+$/g,'')||'PPE_SAM') + '_inputs.json';
    saveFile(name, JSON.stringify(o, null, 2)); $('#inNote').textContent = `Saved ${name}`; };
  $('#loadInBtn').onclick = () => $('#loadInFile').click();
  $('#loadInFile').addEventListener('change', async e => { const file=e.target.files[0]; e.target.value=''; if(!file) return;
    let o; try{ o = JSON.parse(await file.text()); if(!o || o.format!==INPUTS_FORMAT || typeof o.inputs!=='object') throw new Error('not a PPE SAM inputs file'); }
    catch(err){ $('#inNote').innerHTML = `<span class="bad">Could not load ${esc(file.name)}: ${esc(err.message)}</span>`; return; }
    ask(`Load ${file.name}? This replaces every input on the Configure and Settings pages.`, 'Load inputs', async ok => { if(!ok) return;
      const probs = await applyInputs(o.inputs);
      $('#inNote').innerHTML = `<span class="ok">Loaded ${esc(file.name)}</span>${o.app_version?` (saved with v${esc(o.app_version)})`:''}.`
        + (probs.length ? `<ul class="bad" style="margin:4px 0 0 18px;padding:0">${probs.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>` : ''); }); });
  async function libraryRecord(kind, name){ if(!name) return null;
    try{ const r = await fetch(`/api/${kind}?name=${encodeURIComponent(name)}`), j = await r.json(); return (r.ok && j.length) ? j[0] : null; }catch(e){ return null; } }
  async function applyInputs(I){
    const probs = [];
    const [mod, inv] = await Promise.all([libraryRecord('modules', I.module_name), libraryRecord('inverters', I.inverter_name)]);
    resetAll();
    if(I.module_name && !mod) probs.push(`Module “${I.module_name}” is not in the CEC library. Select a module.`);
    if(I.inverter_name && !inv) probs.push(`Inverter “${I.inverter_name}” is not in the CEC library. Select an inverter.`);
    if(mod) modPicker.pick(mod); if(inv) invPicker.pick(inv);     // before the fields: picking fills the module dimensions
    if(I.location_mode==='address' || I.location_mode==='coords'){ st.loc = I.location_mode; locG.sync($(`[data-loc=${st.loc}]`)); }
    st.src = I.module_source==='custom' ? 'custom' : 'cec'; srcG.sync($(`[data-src=${st.src}]`));
    if(RACK_NAME[I.racking]){ st.racking = I.racking; rackG.sync($(`[data-r=${st.racking}]`)); }
    st.gmode = I.gcr_mode==='gcr' ? 'gcr' : 'pitch'; gcrG.sync($(`[data-g=${st.gmode}]`));
    $('#bifOverride').checked = I.bifacial_override==='1'; $('#customBif').checked = I.custom_bifacial==='1'; $('#bifMismatch').checked = I.bifacial_mismatch==='1';
    [...f.elements].forEach(el => { if(!el.name || el.type==='checkbox' || !(el.name in I)) return; const v = String(I[el.name] ?? '');
      if(el.tagName==='SELECT' && ![...el.options].some(x => x.value===v)){ probs.push(`${LABELS[el.name]||el.name}: “${v}” is not one of the options.`); return; }
      el.value = v; st.touched.add(el.name.replace(/_units$/,'')); });
    Object.entries(I.db_values || {}).forEach(([n,v]) => { if(f.elements[n] && same(val(n), v)) dbVals[n] = String(v); });
    st.shadeAuto = !val('self_shading') || val('self_shading')===ppeShade();
    if(st.loc==='address' && val('address') && val('lat') && val('lon')) st.geo = {address:val('address'), lat:num('lat'), lon:num('lon')};
    ['#sec2','#sec3','#sec4'].forEach(s => setCollapsed($(s), false)); st.complete = null;
    update(); scheduleValidate(); showView('cfg');
    return probs;
  }

  // ================= results =================
  const METH = {'Database':'db','User entered':'user','Calculated':'calc','Default':'def'};
  const SUB_TITLE = {cec:'CEC database module specs'};
  function kpi(t, w, u, d, sub){ return `<div class="kpi"><div class="t">${t}</div><div class="v">${w?fmt(w.value,d):'—'} ${u}</div><div class="s">${sub||''}</div></div>`; }
  function show(res){
    const W=res.summary.worst, n=res.nec, pass = !n.floor_governs;     // same test as the NEC table below
    $('#resTitle').textContent = `Results${res.project?`: ${res.project}`:''}`;
    $('#kpis').innerHTML =
        kpi('Isc · max 3-hr avg', W.isc_max, 'A', 2, `70% of Isc = ${fmt(n.floor_70pct,2)} A <span class="mark ${pass?'yes':'no'}" title="${pass?'Simulated Isc is at or above the 70% floor':'Simulated Isc is below the 70% floor: the floor governs'}">${pass?'✓':'✕'}</span>`)
      + kpi('Voc · max 3-hr avg', W.voc_max, 'V', 1, '')
      + kpi('Vmp · max 3-hr avg', W.vmp_max, 'V', 1, W.vmp_min ? `Min (operating) = ${fmt(W.vmp_min.value,1)} V` : '');
    $('#nec').innerHTML = `<table><tr><th>Item</th><th class="num">Value</th></tr><tr><td>Module Isc at STC (datasheet)</td><td class="num">${fmt(n.isc_stc_module,3)} A</td></tr>
      ${n.bifacial_gain_pct!==null?`<tr><td>Bifacial gain</td><td class="num">${fmt(n.bifacial_gain_pct,1)} %</td></tr>`:''}
      <tr><td>70% floor = 0.70 × 1.25 × Isc${n.bifacial_gain_pct!==null?' × (1 + gain)':''}</td><td class="num">${fmt(n.floor_70pct,3)} A</td></tr>
      <tr><td>Simulated max 3-hr avg Isc</td><td class="num">${fmt(n.simulated_3hr,3)} A</td></tr>
      <tr><td><b>Governing current</b></td><td class="num"><b>${fmt(n.governing,3)} A</b> ${n.floor_governs?'<span class="warn">(70% floor governs)</span>':'<span class="ok">(simulation governs)</span>'}</td></tr></table>`;
    const rows = res.inputs_used, tipTxt = res.cec_tip, started = {};
    let last='', h='<table><tr><th>Input</th><th>Value</th><th>Units</th><th>Method</th></tr>';
    rows.forEach(r => {
      if(r.section!==last){ h += `<tr class="grp"><td colspan="4">${esc(r.section)}</td></tr>`; last=r.section; }
      if(r.sub && !started[r.sub]){ started[r.sub]=true; const cnt = rows.filter(x=>x.sub===r.sub).length;
        h += `<tr class="subhead"><td colspan="4"><button type="button" class="subtog" aria-expanded="false" data-sub="${esc(r.sub)}">▸ ${esc(SUB_TITLE[r.sub]||'Details')} (${cnt} items)</button></td></tr>`; }
      const tip = r.tip ? `<span class="tip tip-l">?<span class="tiptext">${esc(tipTxt)}</span></span>` : '';
      const cls = r.sub ? ` class="subrow" data-sub="${esc(r.sub)}"` : (r.key ? ' class="key"' : '');
      h += `<tr${cls}><td>${esc(r.input)}${tip}</td><td>${esc(r.value)}</td><td>${esc(r.units)}</td><td><span class="meth ${METH[r.method]||'user'}">${esc(r.method)}</span></td></tr>`; });
    $('#inputsUsed').innerHTML = h + '</table>';
    $('#samJsonNote').textContent = res.sam_json_year ? `SAM case inputs (.json): every SAM input for ${res.sam_json_year} (the worst-case Isc year), in SAM's own "JSON for inputs" format, with that year's weather file.` : '';
    $('#exportErr').textContent=''; $('#results').classList.remove('hidden');
  }
  $('#inputsUsed').addEventListener('click', e => { const b=e.target.closest('.subtog'); if(!b) return;
    const open = b.getAttribute('aria-expanded')!=='true'; b.setAttribute('aria-expanded', String(open));
    b.textContent = (open?'▾':'▸') + b.textContent.slice(1);
    $$(`#inputsUsed tr.subrow[data-sub="${b.dataset.sub}"]`).forEach(tr => tr.classList.toggle('show', open)); });
  update();
})();
