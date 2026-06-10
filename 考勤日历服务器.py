#!/usr/bin/env python3
"""
考勤日历 - Flask 服务端版本
使用 SQLite 集中存储数据，解决 localStorage 跨设备/清缓存问题。
启动后浏览器访问 http://localhost:5000
"""

import sqlite3
import json
import os
from datetime import datetime
from flask import Flask, request, jsonify, g

app = Flask(__name__, static_folder=None)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '考勤日历.db')
DEFAULT_ADMIN_USERS = ['琨', '景斌']
DEFAULT_PASSWORD = 'fszyy8306'


# ── Database ──
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript('''
        CREATE TABLE IF NOT EXISTS people (
            name TEXT PRIMARY KEY
        );
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person TEXT NOT NULL,
            year_month TEXT NOT NULL,
            day_key TEXT NOT NULL,
            status_data TEXT NOT NULL DEFAULT '',
            UNIQUE(person, year_month, day_key)
        );
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person TEXT NOT NULL,
            year_month TEXT NOT NULL,
            day_key TEXT NOT NULL,
            note TEXT DEFAULT '',
            UNIQUE(person, year_month, day_key)
        );
        CREATE TABLE IF NOT EXISTS pins (
            person TEXT PRIMARY KEY,
            pin TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    ''')
    # 初始化默认数据
    cur = db.execute("SELECT COUNT(*) FROM config WHERE key='admin_password'")
    if cur.fetchone()[0] == 0:
        db.execute("INSERT INTO config(key,value) VALUES('admin_password',?)", (DEFAULT_PASSWORD,))
        db.execute("INSERT INTO config(key,value) VALUES('admin_users',?)",
                   (json.dumps(DEFAULT_ADMIN_USERS, ensure_ascii=False),))
    cur = db.execute("SELECT COUNT(*) FROM people")
    if cur.fetchone()[0] == 0:
        db.execute("INSERT INTO people(name) VALUES('本人')")
        db.execute("INSERT OR IGNORE INTO people(name) VALUES('琨')")
    db.commit()
    db.close()


# ── Helpers ──
def get_config(key):
    row = get_db().execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
    return row['value'] if row else None


def set_config(key, value):
    get_db().execute("INSERT OR REPLACE INTO config(key,value) VALUES(?,?)", (key, value))
    get_db().commit()


# ── API: People ──
@app.route('/api/people', methods=['GET'])
def api_get_people():
    rows = get_db().execute("SELECT name FROM people ORDER BY name").fetchall()
    return jsonify([r['name'] for r in rows])


@app.route('/api/people', methods=['POST'])
def api_add_person():
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': '姓名不能为空'}), 400
    try:
        get_db().execute("INSERT INTO people(name) VALUES(?)", (name,))
        get_db().commit()
        return jsonify({'ok': True})
    except sqlite3.IntegrityError:
        return jsonify({'error': '该人员已存在'}), 409


@app.route('/api/people/<name>', methods=['DELETE'])
def api_remove_person(name):
    db = get_db()
    db.execute("DELETE FROM people WHERE name=?", (name,))
    db.execute("DELETE FROM attendance WHERE person=?", (name,))
    db.execute("DELETE FROM notes WHERE person=?", (name,))
    db.execute("DELETE FROM pins WHERE person=?", (name,))
    db.commit()
    return jsonify({'ok': True})


# ── API: Attendance ──
@app.route('/api/attendance/<person>/<year_month>', methods=['GET'])
def api_get_attendance(person, year_month):
    rows = get_db().execute(
        "SELECT day_key, status_data FROM attendance WHERE person=? AND year_month=?",
        (person, year_month)
    ).fetchall()
    return jsonify({r['day_key']: r['status_data'] for r in rows})


@app.route('/api/attendance/<person>/<year_month>/<day_key>', methods=['PUT'])
def api_set_attendance(person, year_month, day_key):
    data = request.get_json()
    status_data = data.get('status_data', '')
    db = get_db()
    if not status_data:
        db.execute(
            "DELETE FROM attendance WHERE person=? AND year_month=? AND day_key=?",
            (person, year_month, day_key)
        )
    else:
        db.execute('''
            INSERT INTO attendance(person, year_month, day_key, status_data)
            VALUES(?,?,?,?)
            ON CONFLICT(person, year_month, day_key) DO UPDATE SET status_data=excluded.status_data
        ''', (person, year_month, day_key, status_data))
    db.commit()
    return jsonify({'ok': True})


# ── API: Notes ──
@app.route('/api/notes/<person>/<year_month>', methods=['GET'])
def api_get_notes(person, year_month):
    rows = get_db().execute(
        "SELECT day_key, note FROM notes WHERE person=? AND year_month=?",
        (person, year_month)
    ).fetchall()
    return jsonify({r['day_key']: r['note'] for r in rows})


@app.route('/api/notes/<person>/<year_month>/<day_key>', methods=['PUT'])
def api_set_note(person, year_month, day_key):
    data = request.get_json()
    note = data.get('note', '')
    db = get_db()
    if not note:
        db.execute(
            "DELETE FROM notes WHERE person=? AND year_month=? AND day_key=?",
            (person, year_month, day_key)
        )
    else:
        db.execute('''
            INSERT INTO notes(person, year_month, day_key, note)
            VALUES(?,?,?,?)
            ON CONFLICT(person, year_month, day_key) DO UPDATE SET note=excluded.note
        ''', (person, year_month, day_key, note))
    db.commit()
    return jsonify({'ok': True})


# ── API: PIN ──
@app.route('/api/pin/<name>', methods=['GET'])
def api_get_pin(name):
    row = get_db().execute("SELECT pin FROM pins WHERE person=?", (name,)).fetchone()
    return jsonify({'locked': row is not None, 'pin': row['pin'] if row else ''})


@app.route('/api/pin/<name>', methods=['POST'])
def api_set_pin(name):
    data = request.get_json()
    pin = data.get('pin', '').strip()
    if not pin or len(pin) < 2:
        return jsonify({'error': '密码至少2位'}), 400
    get_db().execute("INSERT OR REPLACE INTO pins(person,pin) VALUES(?,?)", (name, pin))
    get_db().commit()
    return jsonify({'ok': True})


@app.route('/api/pin/<name>', methods=['DELETE'])
def api_remove_pin(name):
    get_db().execute("DELETE FROM pins WHERE person=?", (name,))
    get_db().commit()
    return jsonify({'ok': True})


@app.route('/api/pin/<name>/verify', methods=['POST'])
def api_verify_pin(name):
    data = request.get_json()
    pin = data.get('pin', '')
    row = get_db().execute("SELECT pin FROM pins WHERE person=?", (name,)).fetchone()
    if not row:
        return jsonify({'valid': True})  # 未锁定，直接通过
    return jsonify({'valid': row['pin'] == pin})


# ── API: Admin ──
@app.route('/api/admin/login', methods=['POST'])
def api_admin_login():
    data = request.get_json()
    user = data.get('user', '').strip()
    pwd = data.get('password', '')
    admin_users = json.loads(get_config('admin_users') or '[]')
    stored_pwd = get_config('admin_password') or DEFAULT_PASSWORD
    if user in admin_users and pwd == stored_pwd:
        return jsonify({'ok': True, 'user': user})
    return jsonify({'error': '身份验证失败'}), 403


@app.route('/api/admin/password', methods=['PUT'])
def api_change_password():
    data = request.get_json()
    old_pwd = data.get('old_password', '')
    new_pwd = data.get('new_password', '')
    stored_pwd = get_config('admin_password') or DEFAULT_PASSWORD
    if old_pwd != stored_pwd:
        return jsonify({'error': '原密码错误'}), 403
    if not new_pwd or len(new_pwd) < 2:
        return jsonify({'error': '新密码至少2位'}), 400
    set_config('admin_password', new_pwd)
    return jsonify({'ok': True})


@app.route('/api/admin/users', methods=['GET'])
def api_get_admin_users():
    return jsonify(json.loads(get_config('admin_users') or '[]'))


@app.route('/api/admin/users', methods=['PUT'])
def api_set_admin_users():
    data = request.get_json()
    users = data.get('users', [])
    set_config('admin_users', json.dumps(users, ensure_ascii=False))
    return jsonify({'ok': True})


# ── API: Backup / Restore ──
@app.route('/api/backup', methods=['GET'])
def api_backup():
    db = get_db()
    backup = {
        'people': [r['name'] for r in db.execute("SELECT name FROM people").fetchall()],
        'pins': {r['person']: r['pin'] for r in db.execute("SELECT person, pin FROM pins").fetchall()},
        'attendance': {},
        'notes': {},
        'config': {r['key']: r['value'] for r in db.execute("SELECT key, value FROM config").fetchall()},
    }
    for row in db.execute("SELECT person, year_month, day_key, status_data FROM attendance").fetchall():
        key = f"{row['person']}|{row['year_month']}|{row['day_key']}"
        backup['attendance'][key] = row['status_data']
    for row in db.execute("SELECT person, year_month, day_key, note FROM notes").fetchall():
        key = f"{row['person']}|{row['year_month']}|{row['day_key']}"
        backup['notes'][key] = row['note']
    return jsonify(backup)


@app.route('/api/restore', methods=['POST'])
def api_restore():
    data = request.get_json()
    db = get_db()
    # 清空现有数据
    db.execute("DELETE FROM attendance")
    db.execute("DELETE FROM notes")
    db.execute("DELETE FROM pins")
    db.execute("DELETE FROM people")
    db.execute("DELETE FROM config")
    # 恢复
    for name in data.get('people', []):
        db.execute("INSERT INTO people(name) VALUES(?)", (name,))
    for person, pin in data.get('pins', {}).items():
        db.execute("INSERT INTO pins(person,pin) VALUES(?,?)", (person, pin))
    for key, status_data in data.get('attendance', {}).items():
        parts = key.split('|', 2)
        if len(parts) == 3:
            db.execute(
                "INSERT INTO attendance(person,year_month,day_key,status_data) VALUES(?,?,?,?)",
                (parts[0], parts[1], parts[2], status_data)
            )
    for key, note in data.get('notes', {}).items():
        parts = key.split('|', 2)
        if len(parts) == 3:
            db.execute(
                "INSERT INTO notes(person,year_month,day_key,note) VALUES(?,?,?,?)",
                (parts[0], parts[1], parts[2], note)
            )
    for key, value in data.get('config', {}).items():
        db.execute("INSERT INTO config(key,value) VALUES(?,?)", (key, value))
    db.commit()
    return jsonify({'ok': True})


# ── Serve Frontend ──
HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '考勤日历.html')


@app.route('/')
def index():
    with open(HTML_PATH, 'r', encoding='utf-8') as f:
        html = f.read()
    # 注入 API 兼容层：替换 localStorage 操作为 API 调用
    api_shim = '''
<script>
// ── API 模式兼容层（替换 localStorage 为服务端 API）──
window.API_MODE = true;
window.API_BASE = "";

// 内存缓存
const _cache = {
  people: null,
  currentPerson: null,
  data: {},       // key: "person|ym" → {}
  notes: {},      // key: "person|ym" → {}
  pins: {},       // key: name → {locked, pin}
  unlocked: new Set(),
  adminPwd: null,
  adminUsers: null,
  isAdmin: false,
  currentAdmin: '',
};

async function _fetch(url, opts) {
  const resp = await fetch(window.API_BASE + url, opts);
  if (!resp.ok) {
    const err = await resp.json().catch(()=>({}));
    throw new Error(err.error || '请求失败');
  }
  return resp.json();
}

// 重写 localStorage 相关函数 — 在 init() 之前执行
const _origLoadPeople = loadPeople;
const _origSavePeople = savePeople;
const _origLoadCurrentPerson = loadCurrentPerson;
const _origSaveCurrentPerson = saveCurrentPerson;
const _origLoadData = loadData;
const _origSaveData = saveData;
const _origLoadNotes = loadNotes;
const _origSaveNotes = saveNotes;
const _origIsPersonLocked = isPersonLocked;
const _origGetPersonPin = getPersonPin;
const _origSetPersonPin = setPersonPin;
const _origRemovePersonLock = removePersonLock;
const _origIsPersonPersistedUnlocked = isPersonPersistedUnlocked;
const _origPersistUnlock = persistUnlock;
const _origClearPersistUnlock = clearPersistUnlock;
const _origGetPassword = getPassword;
const _origSetPassword = setPassword;
const _origLoadAdminUsers = loadAdminUsers;
const _origSaveAdminUsers = saveAdminUsers;

// 异步加载人员列表
async function _loadPeopleAsync() {
  if (_cache.people === null) {
    _cache.people = await _fetch('/api/people');
  }
  return _cache.people;
}

loadPeople = function() {
  if (_cache.people !== null) return [..._cache.people];
  // 同步返回缓存；首次调用由 init 中的异步加载填充
  return [];
};

savePeople = function(people) {
  _cache.people = [...people];
  // 服务端由 API 管理，不需要整体保存
};

loadCurrentPerson = function() {
  return _cache.currentPerson || '';
};

saveCurrentPerson = function(p) {
  _cache.currentPerson = p;
};

loadData = function(person, ym) {
  const k = person + '|' + ym;
  return _cache.data[k] || {};
};

saveData = async function(person, ym, data) {
  const k = person + '|' + ym;
  _cache.data[k] = {...data};
};

loadNotes = function(person, ym) {
  const k = person + '|' + ym;
  return _cache.notes[k] || {};
};

saveNotes = async function(person, ym, data) {
  const k = person + '|' + ym;
  _cache.notes[k] = {...data};
};

isPersonLocked = function(name) {
  return _cache.pins[name]?.locked || false;
};

getPersonPin = function(name) {
  return _cache.pins[name]?.pin || '';
};

setPersonPin = async function(name, pin) {
  await _fetch('/api/pin/' + encodeURIComponent(name), {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({pin})
  });
  _cache.pins[name] = {locked: true, pin};
};

removePersonLock = async function(name) {
  await _fetch('/api/pin/' + encodeURIComponent(name), {method: 'DELETE'});
  delete _cache.pins[name];
  _cache.unlocked.delete(name);
};

isPersonPersistedUnlocked = function(name) {
  return _cache.unlocked.has(name);
};

persistUnlock = function(name) {
  _cache.unlocked.add(name);
};

clearPersistUnlock = function(name) {
  _cache.unlocked.delete(name);
};

getPassword = function() {
  return _cache.adminPwd || '***';
};

setPassword = async function(newPwd) {
  // 通过 API 修改
  _cache.adminPwd = newPwd;
};

loadAdminUsers = function() {
  return _cache.adminUsers ? [..._cache.adminUsers] : ['琨','景斌'];
};

saveAdminUsers = async function(users) {
  await _fetch('/api/admin/users', {
    method: 'PUT',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({users})
  });
  _cache.adminUsers = [...users];
};

// ── API 模式下的异步 init ──
const _origInit = init;
init = async function() {
  try {
    // 加载服务器数据到缓存
    const people = await _fetch('/api/people');
    _cache.people = people;
    if (people.length === 0) {
      await _fetch('/api/people', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name: '本人'})
      });
      _cache.people = ['本人'];
    }
    _cache.currentPerson = people[0] || '本人';

    // 加载人员 PIN 状态
    for (const p of _cache.people) {
      const pinInfo = await _fetch('/api/pin/' + encodeURIComponent(p));
      _cache.pins[p] = pinInfo;
    }

    // 加载配置
    const adminUsersResp = await _fetch('/api/admin/users');
    _cache.adminUsers = adminUsersResp;

    resetStorageFunctions(); // 用同步版本替换异步版本
  } catch(e) {
    console.error('API 初始化失败:', e);
  }

  // 调用原始 init 逻辑
  _origInit();
};

// 预加载当前月份数据（在 render 之前）
const _origRender = render;
render = async function() {
  try {
    const ym = currentYear + '-' + String(currentMonth).padStart(2,'0');
    for (const p of _cache.people) {
      const dk = p + '|' + ym;
      if (!_cache.data[dk]) {
        _cache.data[dk] = await _fetch('/api/attendance/' + encodeURIComponent(p) + '/' + ym);
      }
      const nk = p + '|' + ym;
      if (!_cache.notes[nk]) {
        _cache.notes[nk] = await _fetch('/api/notes/' + encodeURIComponent(p) + '/' + ym);
      }
    }
  } catch(e) {
    console.error('加载数据失败:', e);
  }
  _origRender();
};

// 重写 saveData 为同步但后台发送
const _apiSaveData = saveData;
saveData = function(person, ym, data) {
  const k = person + '|' + ym;
  _cache.data[k] = {...data};
  // 后台同步到服务器
  for (const [dayKey, statusData] of Object.entries(data)) {
    _fetch('/api/attendance/' + encodeURIComponent(person) + '/' + ym + '/' + dayKey, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({status_data: statusData})
    }).catch(e => console.error('保存失败:', e));
  }
};

saveNotes = function(person, ym, data) {
  const k = person + '|' + ym;
  _cache.notes[k] = {...data};
  for (const [dayKey, note] of Object.entries(data)) {
    _fetch('/api/notes/' + encodeURIComponent(person) + '/' + ym + '/' + dayKey, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({note})
    }).catch(e => console.error('保存备注失败:', e));
  }
};

// 重写 addPerson / removePerson
const _origAddPerson = addPerson;
addPerson = async function() {
  if (!isAdmin) return;
  showModal('添加人员', '输入姓名...', async (name) => {
    if (!name.trim()) return;
    try {
      await _fetch('/api/people', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name: name.trim()})
      });
      _cache.people.push(name.trim());
      _cache.pins[name.trim()] = {locked: false, pin: ''};
      currentPerson = name.trim();
      saveCurrentPerson(currentPerson);
      render();
    } catch(e) {
      showToast(e.message, true);
    }
  });
};

const _origRemovePerson = removePerson;
removePerson = async function(name) {
  if (!isAdmin) return;
  if (_cache.people.length <= 1) { showToast('至少保留一个人员', true); return; }
  if (!confirm('确认删除「' + name + '」及其所有考勤数据？')) return;
  await _fetch('/api/people/' + encodeURIComponent(name), {method: 'DELETE'});
  _cache.people = _cache.people.filter(p => p !== name);
  delete _cache.pins[name];
  if (currentPerson === name) {
    currentPerson = _cache.people[0];
    saveCurrentPerson(currentPerson);
  }
  render();
};

// 重写管理员登录
const _origShowLogin = showLogin;
showLogin = function() {
  // 使用原始 UI，但登录验证走 API
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.id = 'loginOverlay';
  overlay.innerHTML = `
    <div class="modal">
      <h3>🔐 管理员登录</h3>
      <select id="loginUserSelect" style="width:100%;padding:8px;margin:6px 0;border:1px solid #ddd;border-radius:6px;">
        ${_cache.adminUsers.map(u => `<option value="${u}">${u}</option>`).join('')}
      </select>
      <input id="loginPwd" type="password" placeholder="输入密码" autofocus>
      <div class="modal-btns">
        <button class="btn-cancel" onclick="document.getElementById('loginOverlay')?.remove()">取消</button>
        <button class="btn-confirm" onclick="_apiDoLogin()">确认</button>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);
  setTimeout(() => document.getElementById('loginPwd').focus(), 50);
  document.getElementById('loginPwd').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') _apiDoLogin();
    if (e.key === 'Escape') document.getElementById('loginOverlay')?.remove();
  });
};

window._apiDoLogin = async function() {
  const user = document.getElementById('loginUserSelect').value;
  const pwd = document.getElementById('loginPwd').value;
  try {
    const resp = await _fetch('/api/admin/login', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({user, password: pwd})
    });
    document.getElementById('loginOverlay')?.remove();
    isAdmin = true;
    currentAdmin = user;
    _cache.adminPwd = pwd;
    showToast('✅ 管理员已登录：' + user);
    render();
  } catch(e) {
    showToast('❌ ' + e.message, true);
  }
};

// 重写 changePwd
const _origShowChangePwd = showChangePwd;
showChangePwd = function() {
  showModal('修改密码', '输入新密码', async (newPwd) => {
    if (!newPwd || newPwd.length < 2) { showToast('密码至少2位', true); return; }
    try {
      await _fetch('/api/admin/password', {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({old_password: _cache.adminPwd || '***', new_password: newPwd})
      });
      _cache.adminPwd = newPwd;
      showToast('✅ 密码已修改');
    } catch(e) {
      showToast('❌ ' + e.message, true);
    }
  }, true);
};

console.log('✅ API 模式已启用 — 数据存储在服务端 SQLite');
</script>'''
    html = html.replace('<script>', api_shim + '\n<script>', 1)
    return html


if __name__ == '__main__':
    init_db()
    print("=" * 50)
    print("  考勤日历服务端已启动")
    print(f"  数据库: {DB_PATH}")
    print(f"  访问: http://localhost:5000")
    print(f"  局域网访问: http://<本机IP>:5000")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=False)
