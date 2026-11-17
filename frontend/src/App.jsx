import { useEffect, useRef, useState } from 'react'

const api = {
  async signup(data) {
    return (await fetch('/api/auth/signup/', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })).json()
  },
  async login(data) {
    return (await fetch('/api/auth/login/', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })).json()
  },
  async employees() { return (await fetch('/api/employees/')).json() },
  async updateEmployee(id, data) {
    return (await fetch(`/api/employees/${id}/`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })).json()
  },
  async list() { return (await fetch('/api/routers/')).json() },
  async stats() { return (await fetch('/api/stats/')).json() },
  async detail(id) { return (await fetch(`/api/routers/${id}/`)).json() },
  async add(data) {
    return (await fetch('/api/routers/', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })).json()
  },
  async auto(data) {
    return (await fetch('/api/auto/', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })).json()
  },
  async retry(id, admin_password) {
    return (await fetch(`/api/routers/${id}/`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(admin_password ? { admin_password } : {}),
    })).json()
  },
  async remove(id) {
    return (await fetch(`/api/routers/${id}/`, { method: 'DELETE' })).json()
  },
  async scan(subnet) {
    return (await fetch('/api/scan/', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ subnet }),
    })).json()
  },
  async subnets() { return (await fetch('/api/subnets/')).json() },
  async getSettings() { return (await fetch('/api/settings/')).json() },
  async saveSettings(data) {
    return (await fetch('/api/settings/', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })).json()
  },
}

function StatusBadge({ s }) {
  return <span className={`badge ${s}`}>{s}</span>
}

function PasswordInput({ wrapStyle, inputStyle, ...props }) {
  const [show, setShow] = useState(false)
  return (
    <div className="pw-wrap" style={wrapStyle}>
      <input {...props} type={show ? 'text' : 'password'} style={inputStyle} />
      <button type="button" className="pw-toggle" onClick={() => setShow(s => !s)}>
        {show ? 'Hide' : 'Show'}
      </button>
    </div>
  )
}

function AuthPage({ onLogin }) {
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({
    first_name: '', last_name: '', email: '',
    code: '', password: '', confirm_password: '',
  })
  const [msg, setMsg] = useState('')
  const [ok, setOk] = useState(false)
  const [busy, setBusy] = useState(false)
  const f = (k) => (e) => setForm(v => ({ ...v, [k]: e.target.value }))

  const switchMode = (m) => { setMode(m); setMsg(''); setOk(false) }

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setMsg(''); setOk(false)
    try {
      if (mode === 'login') {
        const res = await api.login({ code: form.code.trim(), password: form.password })
        if (res.error) setMsg(res.error)
        else onLogin(res.employee)
      } else {
        const res = await api.signup({
          first_name: form.first_name.trim(),
          last_name: form.last_name.trim(),
          email: form.email.trim(),
          code: form.code.trim(),
          password: form.password,
          confirm_password: form.confirm_password,
        })
        if (res.error) {
          setMsg(res.error)
        } else {
          setForm(v => ({ ...v, password: '', confirm_password: '' }))
          setMode('login')
          setOk(true)
          setMsg('Account created — status: pending activation. An admin will activate it.')
        }
      }
    } catch {
      setMsg('Could not reach the server')
    }
    setBusy(false)
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card card">
        <div className="logo" style={{ margin: '0 auto 12px' }}>📡</div>
        <h1 style={{ textAlign: 'center', fontSize: '1.15rem' }}>Nokia Hotspot Provisioner</h1>
        <div className="sub" style={{ textAlign: 'center', color: '#64748b', fontSize: '0.85rem', marginBottom: 18 }}>
          {mode === 'login' ? 'Sign in with your 6-digit code' : 'Create an account'}
        </div>
        <form onSubmit={submit}>
          {mode === 'signup' && (
            <>
              <div className="form-grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
                <div className="field">
                  <label>First name</label>
                  <input value={form.first_name} onChange={f('first_name')} autoFocus required />
                </div>
                <div className="field">
                  <label>Last name</label>
                  <input value={form.last_name} onChange={f('last_name')} required />
                </div>
              </div>
              <div className="field" style={{ marginTop: 12 }}>
                <label>Email</label>
                <input type="email" value={form.email} onChange={f('email')} required />
              </div>
            </>
          )}
          <div className="field" style={{ marginTop: mode === 'signup' ? 12 : 0 }}>
            <label>6-digit code</label>
            <input
              value={form.code} onChange={f('code')} required
              inputMode="numeric" pattern="\d{6}" maxLength={6}
              placeholder="e.g. 042317" autoFocus={mode === 'login'}
            />
          </div>
          <div className="field" style={{ marginTop: 12 }}>
            <label>Password</label>
            <PasswordInput value={form.password} onChange={f('password')} required />
          </div>
          {mode === 'signup' && (
            <div className="field" style={{ marginTop: 12 }}>
              <label>Confirm password</label>
              <PasswordInput value={form.confirm_password} onChange={f('confirm_password')} required />
            </div>
          )}
          <div className="actions">
            <button className="btn-primary" type="submit" disabled={busy} style={{ width: '100%' }}>
              {busy ? 'Working…' : mode === 'login' ? 'Sign in' : 'Create account'}
            </button>
          </div>
        </form>
        {msg && <div className={`auth-msg ${ok ? 'ok' : 'err'}`}>{msg}</div>}
        <div className="auth-switch">
          {mode === 'login' ? (
            <>No account? <button type="button" className="btn-link" onClick={() => switchMode('signup')}>Create an account</button></>
          ) : (
            <>Already have an account? <button type="button" className="btn-link" onClick={() => switchMode('login')}>Sign in</button></>
          )}
        </div>
      </div>
    </div>
  )
}

function RouterCard({ r, onRefresh }) {
  const [open, setOpen] = useState(false)
  const [log, setLog] = useState('')
  const [newPw, setNewPw] = useState('')
  const busy = r.status === 'running' || r.status === 'pending'

  useEffect(() => {
    if (!open) return
    let alive = true
    const pull = async () => {
      const d = await api.detail(r.id)
      if (alive) setLog(d.log || '')
      if (alive && (d.status === 'running' || d.status === 'pending')) setTimeout(pull, 1500)
    }
    pull()
    return () => { alive = false }
  }, [open, r.id])

  return (
    <div className="router">
      <div className="router-top">
        <span className="ip">{r.ip}</span>
        <span className="ssid">→ {r.ssid}{r.ssid_5 ? ` / ${r.ssid_5}` : ''}{r.bridge_mode ? ' (AP mode)' : ''}</span>
        {r.detected_model && <span className="meta">{r.detected_model}</span>}
        <StatusBadge s={r.status} />
      </div>
      {r.error && <div className="meta" style={{ color: '#f87171', marginTop: 6 }}>{r.error}</div>}
      <div className="actions" style={{ marginTop: 10 }}>
        <button className="btn-sm" onClick={() => setOpen(o => !o)}>
          {open ? 'Hide log' : 'Log'}
        </button>
        {r.status === 'failed' && (
          <>
            <PasswordInput
              placeholder="paste label password" value={newPw}
              onChange={e => setNewPw(e.target.value)}
              wrapStyle={{ flex: '1 1 160px' }}
              inputStyle={{ width: '100%', padding: '6px 48px 6px 10px', borderRadius: 8, background: '#0f172a', border: '1px solid #334155', color: '#e2e8f0', fontSize: '0.85rem' }}
            />
            <button className="btn-sm" onClick={async () => { await api.retry(r.id, newPw.trim()); onRefresh() }}>Retry</button>
          </>
        )}
        {r.status !== 'failed' && !busy && <button className="btn-sm" onClick={async () => { await api.retry(r.id); onRefresh() }}>Retry</button>}
        <button className="btn-danger" onClick={async () => { await api.remove(r.id); onRefresh() }}>Delete</button>
      </div>
      {open && <pre className="logbox">{log || 'no log yet'}</pre>}
    </div>
  )
}

function ProvisioningPage() {
  const [routers, setRouters] = useState([])
  const [stats, setStats] = useState({ total: 0, success: 0, failed: 0, running: 0, pending: 0 })
  const [ssid, setSsid] = useState('')
  const [ssid5, setSsid5] = useState('')
  const [wifiPass, setWifiPass] = useState('')
  const [labelPass, setLabelPass] = useState('')
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)
  const [showAdv, setShowAdv] = useState(false)
  const [adv, setAdv] = useState({ ip: '', username: 'userAdmin', password: '', bridge_mode: true, band_24: true, band_5: true })
  const [nets, setNets] = useState([])
  const [batches, setBatches] = useState([])
  const batchId = useRef(0)
  const pollRef = useRef(null)

  const refresh = async () => {
    try {
      const [l, s] = await Promise.all([api.list(), api.stats()])
      setRouters(l.routers || [])
      setStats(s)
    } catch { /* backend not up yet */ }
  }

  useEffect(() => {
    refresh()
    api.subnets().then(s => setNets(s.subnets || [])).catch(() => {})
    pollRef.current = setInterval(refresh, 2500)
    return () => clearInterval(pollRef.current)
  }, [])

  const submit = async (e) => {
    e.preventDefault()
    if (!ssid.trim()) { setMsg('Enter the new SSID name'); return }
    setBusy(true); setMsg('')
    const res = await api.auto({
      ssid: ssid.trim(),
      ssid_5: ssid5.trim(),
      wifi_password: wifiPass,
      ...((adv.password || labelPass.trim()) ? { admin_password: labelPass.trim() || adv.password } : {}),
      ...(adv.ip ? { ip: adv.ip } : {}),
      ...(adv.username ? { username: adv.username } : {}),
    })
    setBusy(false)
    if (res.error) setMsg(res.error)
    else setMsg(`Provisioning started — watch the log on #${res.created?.id ?? ''}`)
    refresh()
  }

  const advField = (k) => (e) => setAdv(f => ({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }))

  // ---------- batches ----------
  const updBatch = (id, patch) => setBatches(bs => bs.map(b => b.id === id ? { ...b, ...patch } : b))
  const bfield = (id, k) => e => updBatch(id, { [k]: e.target.value })

  const addBatch = () => setBatches(bs => [...bs, {
    id: ++batchId.current,
    ssid, ssid5, wifiPass,          // prefill from the main form
    labelPass: '', targets: '', net: '', msg: '', busy: false, scanning: false,
  }])

  const removeBatch = (id) => setBatches(bs => bs.filter(b => b.id !== id))

  const scanBatch = async (b) => {
    updBatch(b.id, { scanning: true, msg: '' })
    const r = await api.scan(b.net.trim())
    if (r.error) { updBatch(b.id, { scanning: false, msg: r.error }); return }
    const list = r.found || []
    const have = new Set(b.targets.split('\n').map(l => l.split(/[,\s]+/)[0].trim()).filter(Boolean))
    const added = list.filter(ip => !have.has(ip))
    const existing = b.targets.trimEnd()
    updBatch(b.id, {
      scanning: false,
      targets: (existing ? existing + '\n' : '') + added.join('\n'),
      msg: list.length ? `Found ${list.length} gateway(s) — ${added.length} added to the list` : 'No Nokia gateways found',
    })
  }

  const runBatch = async (b) => {
    if (!b.ssid.trim()) { updBatch(b.id, { msg: 'Enter the hotspot name' }); return }
    updBatch(b.id, { busy: true, msg: '' })
    const rows = b.targets.split('\n').map(l => l.trim()).filter(Boolean).map(l => {
      const [ip, pw = ''] = l.split(/[,\s]+/)
      return { ip: ip || '', pw }
    }).filter(r => r.ip)

    let res
    if (!rows.length) {
      // no IP list = behave exactly like the main form: find one router
      res = await api.auto({
        ssid: b.ssid.trim(),
        ssid_5: b.ssid5.trim(),
        wifi_password: b.wifiPass,
        ...(b.labelPass.trim() ? { admin_password: b.labelPass.trim() } : {}),
        ...(adv.username ? { username: adv.username } : {}),
      })
    } else {
      res = await api.add({ routers: rows.map(r => ({
        ip: r.ip,
        // a line's own sticker wins; the batch label field is this batch's
        // shared credential; blanks fall back to the stored list
        password: r.pw.trim() || b.labelPass.trim(),
        ssid: b.ssid.trim(),
        ssid_5: b.ssid5.trim(),
        wifi_password: b.wifiPass,
        username: adv.username || 'userAdmin',
        bridge_mode: adv.bridge_mode,
        band_24: adv.band_24,
        band_5: adv.band_5,
      })) })
    }

    const created = res.created
    let msg
    if (res.error) msg = res.error
    else if (Array.isArray(created)) {
      const errs = created.filter(c => c.error)
      msg = errs.length
        ? `${created.length - errs.length} started, ${errs.length} skipped (${errs[0].error})`
        : `Provisioning ${created.length} router(s) in parallel — watch the list below`
    } else msg = `Provisioning started — watch the log on #${created?.id ?? ''}`
    updBatch(b.id, { busy: false, msg })
    refresh()
  }

  return (
    <div className="app">
      <div className="stats">
        <div className="stat total"><div className="num">{stats.total}</div><div className="lbl">Total</div></div>
        <div className="stat success"><div className="num">{stats.success}</div><div className="lbl">Success</div></div>
        <div className="stat failed"><div className="num">{stats.failed}</div><div className="lbl">Failed</div></div>
        <div className="stat running"><div className="num">{stats.running}</div><div className="lbl">Running</div></div>
        <div className="stat pending"><div className="num">{stats.pending}</div><div className="lbl">Pending</div></div>
      </div>

      <div className="card">
        <h2>Set up hotspot</h2>
        <form onSubmit={submit}>
          <div className="form-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))' }}>
            <div className="field">
              <label>Hotspot name — 2.4 GHz</label>
              <input placeholder="e.g. RICHCOM HOTSPOT" value={ssid} onChange={e => setSsid(e.target.value)} autoFocus />
            </div>
            <div className="field">
              <label>Hotspot name — 5 GHz (blank = same)</label>
              <input placeholder="e.g. RICHCOM HOTSPOT 5G" value={ssid5} onChange={e => setSsid5(e.target.value)} />
            </div>
            <div className="field">
              <label>WiFi password — leave blank for open access</label>
              <input placeholder="blank = anyone can connect" value={wifiPass} onChange={e => setWifiPass(e.target.value)} />
            </div>
            <div className="field">
              <label>Router label password — paste from sticker</label>
              <PasswordInput placeholder="e.g. LGt2t437Uv (blank = try stored list)" value={labelPass} onChange={e => setLabelPass(e.target.value)} />
            </div>
          </div>
          <div className="actions">
            <button className="btn-primary" type="submit" disabled={busy}>
              {busy ? 'Working…' : 'Find router & configure'}
            </button>
            <button className="btn-ghost" type="button" onClick={() => setShowAdv(s => !s)}>
              {showAdv ? 'Hide advanced' : 'Advanced'}
            </button>
          </div>
          {msg && <div className="meta" style={{ marginTop: 10 }}>{msg}</div>}
        </form>

        {showAdv && (
          <div style={{ marginTop: 18, borderTop: '1px solid #334155', paddingTop: 14 }}>
            <div className="form-grid">
              <div className="field">
                <label>Router IP (blank = auto-discover)</label>
                <input placeholder="auto" value={adv.ip} onChange={advField('ip')} />
              </div>
              <div className="field">
                <label>Admin username</label>
                <input value={adv.username} onChange={advField('username')} />
              </div>
              <div className="field">
                <label>Admin password (this unit's label)</label>
                <PasswordInput placeholder="try stored passwords" value={adv.password} onChange={advField('password')} />
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="card" style={{ padding: '14px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 14, flexWrap: 'wrap' }}>
        <div>
          <h2 style={{ marginBottom: 4 }}>Batches — run many setups at once</h2>
          <div className="meta">
            Each batch works like the form above, with its own button. Fill in router IPs
            (or scan) to hit many at once — leave the list blank to auto-find one router.
          </div>
        </div>
        <button className="btn-primary" type="button" onClick={addBatch}>+ Add batch</button>
      </div>

      {batches.map((b, i) => (
        <div className="card" key={b.id}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
            <h2 style={{ margin: 0 }}>Batch {i + 1} — set up hotspot</h2>
            <button className="btn-danger" type="button" onClick={() => removeBatch(b.id)}>Remove</button>
          </div>
          <div className="form-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))' }}>
            <div className="field">
              <label>Hotspot name — 2.4 GHz</label>
              <input placeholder="e.g. RICHCOM HOTSPOT" value={b.ssid} onChange={bfield(b.id, 'ssid')} />
            </div>
            <div className="field">
              <label>Hotspot name — 5 GHz (blank = same)</label>
              <input placeholder="e.g. RICHCOM HOTSPOT 5G" value={b.ssid5} onChange={bfield(b.id, 'ssid5')} />
            </div>
            <div className="field">
              <label>WiFi password — leave blank for open access</label>
              <input placeholder="blank = anyone can connect" value={b.wifiPass} onChange={bfield(b.id, 'wifiPass')} />
            </div>
            <div className="field">
              <label>Router label password — this batch's sticker</label>
              <PasswordInput placeholder="blank = stored list / per-line passwords" value={b.labelPass} onChange={bfield(b.id, 'labelPass')} />
            </div>
          </div>
          <div className="field" style={{ marginTop: 12 }}>
            <label>Router IPs — one per line: IP or IP,label password (blank = find one router automatically)</label>
            <textarea
              style={{ width: '100%', minHeight: 70, padding: 10, borderRadius: 10, background: '#0f172a', border: '1px solid #334155', color: '#e2e8f0', fontSize: '0.9rem' }}
              placeholder={'192.168.0.10, LGt2t437Uv\n192.168.0.11\n192.168.0.12, Kx91mPq2Za'}
              value={b.targets}
              onChange={bfield(b.id, 'targets')}
            />
          </div>
          <div className="actions">
            <button className="btn-primary" type="button" onClick={() => runBatch(b)} disabled={b.busy}>
              {b.busy ? 'Working…' : 'Find router & configure'}
            </button>
            <input
              list={`nets-${b.id}`}
              placeholder="scan subnet — blank = all local"
              value={b.net} onChange={bfield(b.id, 'net')}
              style={{ flex: '0 1 220px', padding: '10px 12px', borderRadius: 10, background: '#0f172a', border: '1px solid #334155', color: '#e2e8f0', fontSize: '0.85rem', outline: 'none' }}
            />
            <datalist id={`nets-${b.id}`}>{nets.map(n => <option key={n} value={n} />)}</datalist>
            <button className="btn-ghost" type="button" onClick={() => scanBatch(b)} disabled={b.scanning}>
              {b.scanning ? 'Scanning…' : 'Scan → fill IPs'}
            </button>
          </div>
          {b.msg && <div className="meta" style={{ marginTop: 10 }}>{b.msg}</div>}
        </div>
      ))}

      <div className="card" style={{ padding: '14px 16px' }}>
        <h2>Routers</h2>
        {routers.length === 0 && <div className="empty">Nothing provisioned yet — plug a router in and enter an SSID above.</div>}
        {routers.map(r => <RouterCard key={r.id} r={r} onRefresh={refresh} />)}
      </div>
    </div>
  )
}

const STATUS_LABEL = {
  pending_activation: 'Pending activation',
  active: 'Active',
  suspended: 'Suspended',
}

function HRPage({ me }) {
  const [emps, setEmps] = useState([])
  const [msg, setMsg] = useState('')
  const isAdmin = me.role === 'admin'

  const refresh = () => api.employees()
    .then(d => setEmps(d.employees || []))
    .catch(() => setMsg('Could not reach the server'))

  useEffect(() => { refresh() }, [])

  const update = async (id, patch) => {
    const res = await api.updateEmployee(id, patch)
    if (res.error) setMsg(res.error)
    refresh()
  }

  return (
    <div className="app">
      <div className="card">
        <h2>Human Resource — employees</h2>
        {msg && <div className="auth-msg err" style={{ textAlign: 'left', marginTop: 0, marginBottom: 10 }}>{msg}</div>}
        {emps.length === 0 && <div className="empty">No employee accounts yet.</div>}
        {emps.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th>Name</th><th>Email</th><th>Code</th><th>Role</th><th>Status</th>
                {isAdmin && <th>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {emps.map(e => (
                <tr key={e.id}>
                  <td>{e.first_name} {e.last_name}</td>
                  <td className="meta">{e.email}</td>
                  <td style={{ fontFamily: 'ui-monospace, monospace' }}>{e.code}</td>
                  <td>
                    {isAdmin && e.id !== me.id ? (
                      <select value={e.role} onChange={ev => update(e.id, { role: ev.target.value })}>
                        <option value="admin">admin</option>
                        <option value="cashier">cashier</option>
                        <option value="employee">employee</option>
                      </select>
                    ) : <span className={`badge role-${e.role}`} style={{ marginLeft: 0 }}>{e.role}</span>}
                  </td>
                  <td><span className={`badge st-${e.status}`} style={{ marginLeft: 0 }}>{STATUS_LABEL[e.status] || e.status}</span></td>
                  {isAdmin && (
                    <td>
                      {e.id !== me.id && e.status !== 'active' && (
                        <button className="btn-sm" style={{ marginRight: 6 }} onClick={() => update(e.id, { status: 'active' })}>Activate</button>
                      )}
                      {e.id !== me.id && e.status === 'active' && (
                        <button className="btn-danger" onClick={() => update(e.id, { status: 'suspended' })}>Suspend</button>
                      )}
                      {e.id === me.id && <span className="meta">you</span>}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

function SettingsPage() {
  const [pwds, setPwds] = useState('')
  const [username, setUsername] = useState('userAdmin')
  const [msg, setMsg] = useState('')
  const [ok, setOk] = useState(false)

  useEffect(() => {
    api.getSettings().then(s => {
      setPwds((s.admin_passwords || []).join('\n'))
      setUsername(s.default_username || 'userAdmin')
    }).catch(() => {})
  }, [])

  const save = async () => {
    const res = await api.saveSettings({
      admin_passwords: pwds.split('\n').map(s => s.trim()).filter(Boolean),
      default_username: username.trim() || 'userAdmin',
    })
    setOk(!res.error); setMsg(res.error || 'Settings saved')
  }

  return (
    <div className="app">
      <div className="card" style={{ maxWidth: 560 }}>
        <h2>Settings</h2>
        <div className="field">
          <label>Default router admin username</label>
          <input value={username} onChange={e => setUsername(e.target.value)} />
        </div>
        <div className="field" style={{ marginTop: 12 }}>
          <label>Stored admin passwords — tried automatically, one per line</label>
          <textarea
            style={{ width: '100%', minHeight: 90, padding: 10, borderRadius: 10, background: '#0f172a', border: '1px solid #334155', color: '#e2e8f0', fontSize: '0.9rem' }}
            placeholder={'e.g. LGt2t437Uv\nadmin'}
            value={pwds}
            onChange={e => setPwds(e.target.value)}
          />
        </div>
        <div className="actions">
          <button className="btn-primary" type="button" onClick={save}>Save settings</button>
        </div>
        {msg && <div className={`auth-msg ${ok ? 'ok' : 'err'}`} style={{ textAlign: 'left' }}>{msg}</div>}
      </div>
    </div>
  )
}

function Sidebar({ me, page, setPage, onLogout }) {
  const link = (id, label) => (
    <button
      type="button"
      className={`nav-link${page === id ? ' active' : ''}`}
      onClick={() => setPage(id)}
    >{label}</button>
  )
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="logo">📡</div>
        <div>
          <h1>Nokia Provisioner</h1>
          <div className="sub">Hotspot setup</div>
        </div>
      </div>
      <nav>
        {link('provision', 'Provisioning')}
        {link('hr', 'Human Resource')}
      </nav>
      <div className="sidebar-bottom">
        <div className="me-chip">
          <span>{me.first_name} {me.last_name}</span>
          <span className={`badge role-${me.role}`} style={{ marginLeft: 'auto' }}>{me.role}</span>
        </div>
        {link('settings', 'Settings')}
        <button type="button" className="nav-link" onClick={onLogout}>Sign out</button>
      </div>
    </aside>
  )
}

export default function App() {
  const [me, setMe] = useState(() => {
    try { return JSON.parse(localStorage.getItem('employee')) } catch { return null }
  })
  const [page, setPage] = useState('provision')
  const login = (emp) => { localStorage.setItem('employee', JSON.stringify(emp)); setMe(emp) }
  const logout = () => { localStorage.removeItem('employee'); setMe(null); setPage('provision') }

  if (!me) return <AuthPage onLogin={login} />

  return (
    <div className="shell">
      <Sidebar me={me} page={page} setPage={setPage} onLogout={logout} />
      <main className="content">
        {page === 'provision' && <ProvisioningPage />}
        {page === 'hr' && <HRPage me={me} />}
        {page === 'settings' && <SettingsPage />}
      </main>
    </div>
  )
}
