// ═══════════════════════════════════════════════════════
// Supabase 云模式兼容层
// 替换下面的 URL 和 KEY 后，所有数据自动存云端
// 留空则保持本地 localStorage 模式
// ═══════════════════════════════════════════════════════
const SUPABASE_URL = 'https://xxxxxxxxxxxx.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...';

const _SB = !!(SUPABASE_URL && SUPABASE_KEY && !SUPABASE_URL.includes('xxxx'));

if (_SB) {
  // ── Supabase REST 封装 ──
  async function _sGET(path) {
    const r = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
      headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` }
    });
    if (!r.ok) throw new Error(`GET ${path}: ${r.status}`);
    return r.json();
  }
  async function _sPOST(table, body) {
    await fetch(`${SUPABASE_URL}/rest/v1/${table}`, {
      method: 'POST', headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}`,
        'Content-Type': 'application/json', Prefer: 'return=minimal' }, body: JSON.stringify(body) });
  }
  async function _sPATCH(table, match, body) {
    await fetch(`${SUPABASE_URL}/rest/v1/${table}?${match}`, {
      method: 'PATCH', headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}`,
        'Content-Type': 'application/json', Prefer: 'return=minimal' }, body: JSON.stringify(body) });
  }
  async function _sDELETE(table, match) {
    await fetch(`${SUPABASE_URL}/rest/v1/${table}?${match}`, {
      method: 'DELETE', headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}`,
        Prefer: 'return=minimal' } });
  }

  // ── 内存缓存 ──
  const _C = { people: null, pinMap: {}, configMap: {}, dataCache: {}, noteCache: {} };

  // ── 从 Supabase 加载初始数据 ──
  async function _loadAll() {
    const [ppl, pins, cfg] = await Promise.all([
      _sGET('people?select=name&order=name'),
      _sGET('pins?select=*'),
      _sGET('config?select=*')
    ]);
    _C.people = ppl.map(r => r.name);
    _C.pinMap = {}; for (const r of pins) _C.pinMap[r.person] = { locked: true, pin: r.pin };
    _C.configMap = {}; for (const r of cfg) _C.configMap[r.key] = r.value;
  }

  // ═══ 覆盖 Storage 函数 ═══
  const _orig_loadPeople = loadPeople;
  loadPeople = function() { return _C.people ? [..._C.people] : []; };
  savePeople = function(people) {
    _C.people = [...people];
    // 异步增量同步
    (async () => {
      const old = new Set(_orig_loadPeople());
      const now = new Set(people);
      for (const n of now) { if (!old.has(n)) try { await _sPOST('people', {name: n}); } catch(e) {} }
      for (const n of old) { if (!now.has(n)) try { await _sDELETE('people', `name=eq.${encodeURIComponent(n)}`); } catch(e) {} }
    })().catch(e => console.error(e));
  };

  saveCurrentPerson = function(p) { currentPerson = p; };
  loadCurrentPerson = function() { return currentPerson || (_C.people && _C.people[0]) || ''; };

  loadData = function(person, ym) {
    const k = `${person}|${ym}`;
    return _C.dataCache[k] || _orig_loadData(person, ym);
  };
  saveData = function(person, ym, data) {
    const k = `${person}|${ym}`;
    _C.dataCache[k] = {...data};
    // 后台同步到 Supabase
    const enc = encodeURIComponent;
    for (const [dk, sd] of Object.entries(data)) {
      (async () => {
        try {
          const m = `person=eq.${enc(person)}&year_month=eq.${ym}&day_key=eq.${enc(dk)}`;
          const ex = await _sGET(`attendance?select=id&${m}`);
          if (ex.length > 0) await _sPATCH('attendance', `id=eq.${ex[0].id}`, {status_data: sd});
          else await _sPOST('attendance', {person, year_month: ym, day_key: dk, status_data: sd});
        } catch(e) { console.error(e); }
      })();
    }
  };

  loadNotes = function(person, ym) {
    const k = `${person}|${ym}`;
    return _C.noteCache[k] || _orig_loadNotes ? _orig_loadNotes(person, ym) : {};
  };
  saveNotes = function(person, ym, data) {
    const k = `${person}|${ym}`;
    _C.noteCache[k] = {...data};
    const enc = encodeURIComponent;
    for (const [dk, note] of Object.entries(data)) {
      (async () => {
        try {
          const m = `person=eq.${enc(person)}&year_month=eq.${ym}&day_key=eq.${enc(dk)}`;
          const ex = await _sGET(`notes?select=id&${m}`);
          if (ex.length > 0) await _sPATCH('notes', `id=eq.${ex[0].id}`, {note});
          else await _sPOST('notes', {person, year_month: ym, day_key: dk, note});
        } catch(e) { console.error(e); }
      })();
    }
  };

  isPersonLocked = function(name) { return !!(_C.pinMap[name] && _C.pinMap[name].locked); };
  getPersonPin = function(name) { return (_C.pinMap[name] && _C.pinMap[name].pin) || ''; };
  setPersonPin = function(name, pin) {
    _C.pinMap[name] = { locked: true, pin };
    (async () => {
      try { await _sDELETE('pins', `person=eq.${encodeURIComponent(name)}`); } catch(e) {}
      await _sPOST('pins', {person: name, pin});
    })().catch(e => console.error(e));
  };
  removePersonLock = function(name) {
    delete _C.pinMap[name];
    (async () => {
      try { await _sDELETE('pins', `person=eq.${encodeURIComponent(name)}`); } catch(e) {}
    })().catch(e => console.error(e));
  };

  getPassword = function() { return _C.configMap['admin_password'] || DEFAULT_PASSWORD; };
  setPassword = function(newPwd) {
    _C.configMap['admin_password'] = newPwd;
    (async () => {
      const m = 'key=eq.admin_password';
      const ex = await _sGET(`config?select=id&${m}`);
      if (ex.length > 0) await _sPATCH('config', `id=eq.${ex[0].id}`, {value: newPwd});
      else await _sPOST('config', {key: 'admin_password', value: newPwd});
    })().catch(e => console.error(e));
  };

  loadAdminUsers = function() {
    try { return JSON.parse(_C.configMap['admin_users'] || 'null') || DEFAULT_ADMIN_USERS; }
    catch { return DEFAULT_ADMIN_USERS; }
  };
  saveAdminUsers = function(users) {
    _C.configMap['admin_users'] = JSON.stringify(users);
    (async () => {
      const m = 'key=eq.admin_users';
      const ex = await _sGET(`config?select=id&${m}`);
      const v = JSON.stringify(users);
      if (ex.length > 0) await _sPATCH('config', `id=eq.${ex[0].id}`, {value: v});
      else await _sPOST('config', {key: 'admin_users', value: v});
    })().catch(e => console.error(e));
  };

  // ── 异步 init ──
  const _orig_init = init;
  init = async function() {
    try { await _loadAll(); } catch(e) { console.error('Supabase load error:', e); }
    _orig_init();
    // 后台加载当前月份数据
    setTimeout(async () => {
      if (currentPerson && currentYear && currentMonth) {
        const ym = currentYear + '-' + String(currentMonth).padStart(2,'0');
        try {
          const rows = await _sGET(`attendance?select=day_key,status_data&person=eq.${encodeURIComponent(currentPerson)}&year_month=eq.${ym}`);
          const d = {}; for (const r of rows) d[r.day_key] = r.status_data;
          _C.dataCache[`${currentPerson}|${ym}`] = d;
          const nr = await _sGET(`notes?select=day_key,note&person=eq.${encodeURIComponent(currentPerson)}&year_month=eq.${ym}`);
          const nd = {}; for (const r of nr) nd[r.day_key] = r.note;
          _C.noteCache[`${currentPerson}|${ym}`] = nd;
          render();
        } catch(e) { console.error(e); }
      }
    }, 500);
    // 实时轮询
    setInterval(async () => {
      if (!currentPerson || !currentYear || !currentMonth) return;
      const ym = currentYear + '-' + String(currentMonth).padStart(2,'0');
      try {
        const rows = await _sGET(`attendance?select=day_key,status_data&person=eq.${encodeURIComponent(currentPerson)}&year_month=eq.${ym}`);
        const nd = {}; for (const r of rows) nd[r.day_key] = r.status_data;
        const ck = `${currentPerson}|${ym}`;
        if (JSON.stringify(nd) !== JSON.stringify(_C.dataCache[ck] || {})) {
          _C.dataCache[ck] = nd;
          render();
        }
      } catch(e) {}
    }, 10000);
  };

  // ── 重写 removePerson ──
  const _orig_removePerson = removePerson;
  removePerson = async function(name) {
    if (!isAdmin) return;
    if (loadPeople().length <= 1) { showToast('至少保留一个人员', true); return; }
    if (!confirm(`确认删除「${name}」及其所有考勤数据？`)) return;
    const people = loadPeople().filter(p => p !== name);
    savePeople(people);
    try {
      const enc = encodeURIComponent;
      await _sDELETE('attendance', `person=eq.${enc(name)}`);
      await _sDELETE('notes', `person=eq.${enc(name)}`);
    } catch(e) {}
    if (currentPerson === name) { currentPerson = people[0]; saveCurrentPerson(currentPerson); }
    render();
  };

  // ── 重写 clearMonth ──
  const _orig_clearMonth = clearMonth;
  clearMonth = async function() {
    if (!isAdmin) return;
    if (!confirm(`确认清空「${currentPerson}」${currentYear}年${currentMonth}月的考勤数据？`)) return;
    try {
      const enc = encodeURIComponent;
      const ym = currentYear + '-' + String(currentMonth).padStart(2,'0');
      await _sDELETE('attendance', `person=eq.${enc(currentPerson)}&year_month=eq.${ym}`);
      await _sDELETE('notes', `person=eq.${enc(currentPerson)}&year_month=eq.${ym}`);
    } catch(e) {}
    localStorage.removeItem(storageKey(currentPerson, ym()));
    localStorage.removeItem(noteKey(currentPerson, ym()));
    activeDate=null;
    document.getElementById('notePanel')?.classList.remove('active');
    render();
  };

  // ── 重写 clearAllData ──
  const _orig_clearAllData = clearAllData;
  clearAllData = async function() {
    if (!isAdmin) return;
    if (!confirm('⚠️ 将清除所有人员所有月份考勤数据！\n（人员名单和密码保留）\n\n确认继续？')) return;
    try {
      await _sDELETE('attendance', 'id=gt.0');
      await _sDELETE('notes', 'id=gt.0');
      _C.dataCache = {};
      _C.noteCache = {};
      showToast('✅ 云端数据已清除');
    } catch(e) { showToast('❌ 清除失败: ' + e.message, true); }
    render();
  };

  // ── 重写 exportFullBackup ──
  const _orig_exportFullBackup = exportFullBackup;
  exportFullBackup = async function() {
    try {
      const [ppl, pins, cfg, att, nts] = await Promise.all([
        _sGET('people?select=name&order=name'),
        _sGET('pins?select=*'),
        _sGET('config?select=*'),
        _sGET('attendance?select=*'),
        _sGET('notes?select=*')
      ]);
      const backup = {
        people: ppl.map(r => r.name),
        pins: Object.fromEntries(pins.map(r => [r.person, r.pin])),
        config: Object.fromEntries(cfg.filter(r => r.key !== 'admin_password').map(r => [r.key, r.value])),
        attendance: att,
        notes: nts
      };
      const json = JSON.stringify(backup, null, 2);
      const blob = new Blob(['\uFEFF' + json], {type: 'application/json;charset=utf-8'});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `考勤数据备份_${new Date().toISOString().slice(0,10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      showToast('✅ 云端数据备份已下载');
    } catch(e) { showToast('❌ 备份失败: ' + e.message, true); }
  };

  // ── 重写 importFullBackup ──
  const _orig_importFullBackup = importFullBackup;
  importFullBackup = function() {
    if (!isAdmin) { showToast('仅管理员可恢复数据', true); return; }
    const input = document.createElement('input');
    input.type = 'file'; input.accept = '.json';
    input.addEventListener('change', async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = async (ev) => {
        try {
          const b = JSON.parse(ev.target.result);
          if (!confirm(`恢复 ${b.people?.length||0} 人、${b.attendance?.length||0} 条记录？`)) return;
          await _sDELETE('attendance', 'id=gt.0');
          await _sDELETE('notes', 'id=gt.0');
          await _sDELETE('pins', 'person=neq.__nonex__');
          await _sDELETE('people', 'name=neq.__nonex__');
          for (const n of (b.people||[])) await _sPOST('people', {name: n});
          for (const [p, pin] of Object.entries(b.pins||{})) await _sPOST('pins', {person: p, pin});
          for (const r of (b.attendance||[])) await _sPOST('attendance', r);
          for (const r of (b.notes||[])) await _sPOST('notes', r);
          showToast('✅ 数据已恢复，刷新中...');
          setTimeout(() => location.reload(), 800);
        } catch(err) { showToast('❌ 恢复失败: ' + err.message, true); }
      };
      reader.readAsText(file, 'UTF-8');
    });
    input.click();
  };

  console.log('✅ Supabase 云模式已启用');
}
