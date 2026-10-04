import React, { useState, useEffect, useRef } from 'react';
import { FiPlus, FiMinus, FiEdit2, FiTrash2, FiX, FiZap, FiClock } from 'react-icons/fi';
import api from '../services/api';
import './Appliances.css';

// ── Appliance emoji map ───────────────────────────────────────
const ICONS = {
  'AC': '❄️',
  'Fridge': '🧊',
  'Geyser': '🚿',
  'Water Purifier': '💧',
  'WiFi Router': '📶',
  'Washing Machine': '🫧',
  'Lights': '💡',
  'TV': '📺',
  'Mixer': '🥤',
  'Cooler': '🌬️',
  'Iron Box': '🔲',
};
const getIcon = (name) => ICONS[name] || '⚡';

// ── Default appliance list with specs for auto-seeding ─────────
const DEFAULT_APPLIANCES = [
  { name: 'AC',              power: 1500, quantity: 2,  priority: 'Medium' },
  { name: 'Fridge',          power: 180,  quantity: 1,  priority: 'Essential' },
  { name: 'Geyser',          power: 2000, quantity: 2,  priority: 'Medium' },
  { name: 'Water Purifier',  power: 50,   quantity: 1,  priority: 'Essential' },
  { name: 'WiFi Router',     power: 15,   quantity: 1,  priority: 'Essential' },
  { name: 'Washing Machine', power: 500,  quantity: 1,  priority: 'Non-essential' },
  { name: 'Lights',          power: 9,    quantity: 12, priority: 'Essential' },
  { name: 'TV',              power: 120,  quantity: 1,  priority: 'Non-essential' },
  { name: 'Mixer',           power: 750,  quantity: 1,  priority: 'Non-essential' },
  { name: 'Cooler',         power: 200,  quantity: 1,  priority: 'Medium' },
  { name: 'Iron Box',       power: 1000, quantity: 1,  priority: 'Non-essential' },
];

const Appliances = () => {
  const [appliances, setAppliances] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [editItem, setEditItem]   = useState(null); // null = add, object = edit
  const [nowTime, setNowTime] = useState(Date.now());
  useEffect(() => { const int = setInterval(() => setNowTime(Date.now()), 30000); return () => clearInterval(int); }, []);
  const [form, setForm] = useState({ name: '', power: '', quantity: '', priority: 'Medium', timerMinutes: '' });
  const [formError, setFormError] = useState('');
  const isSeeding = useRef(false);
  // ── Lock-warning modal state ──────────────────────────────────
  const [lockModal, setLockModal] = useState(null); // { id, reason, pendingStatus, pendingActive }

  // ── Fetch Appliances from Backend ─────────────────────────────
  const fetchAppliances = async () => {
    try {
      setLoading(true);
      const res = await api.get('/appliances');
      if (res.data.length === 0) {
        if (isSeeding.current) return;
        isSeeding.current = true;
        
        // Auto-seed defaults if database is empty
        const seedPromises = DEFAULT_APPLIANCES.map(app => 
          api.post('/appliances', {
            name: app.name,
            power: app.power,
            quantity: app.quantity,
            priority: app.priority,
            active: 0,
            status: false
          })
        );
        const seeded = await Promise.all(seedPromises);
        setAppliances(seeded.map(r => r.data));
        isSeeding.current = false;
      } else {
        setAppliances(res.data);
      }
      setError('');
    } catch (err) {
      setError('Failed to fetch appliances from server.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAppliances();
  }, []);

  // ── Real-Time Sync (SSE) ────────────────────
  useEffect(() => {
    const sse = new EventSource('http://localhost:5000/api/stream/events');
    sse.addEventListener('update', (e) => {
      fetchAppliances(); // Refresh data instantly when server pushes update!
    });
    return () => sse.close();
  }, []);


  // ── Active count: increment ───────────────────────────────────
  const incrementActive = async (id, override = false) => {
    const item = appliances.find(a => a._id === id);
    if (!item || item.active >= item.quantity) return;

    // Lock guard — if locked and turning on, show warning first
    if (item.lockedBySystem && !override) {
      setLockModal({ id, reason: item.lockReason, pendingStatus: true, pendingActive: item.active + 1, action: 'increment' });
      return;
    }

    const newActive = item.active + 1;
    try {
      // Optimistic UI update
      setAppliances(prev => prev.map(a => a._id === id ? { ...a, active: newActive, status: true, lockedBySystem: false, lockReason: null } : a));
      await api.put(`/appliances/${id}`, { active: newActive, status: true, ...(override && { override: true }) });
    } catch (err) {
      console.error('Failed to update active count', err);
      // Revert on error
      fetchAppliances();
    }
  };

  // ── Active count: decrement ───────────────────────────────────
  const decrementActive = async (id) => {
    const item = appliances.find(a => a._id === id);
    if (!item || item.active === 0) return;

    const newActive = item.active - 1;
    const newStatus = newActive > 0;
    try {
      // Optimistic UI update
      setAppliances(prev => prev.map(a => a._id === id ? { ...a, active: newActive, status: newStatus } : a));
      await api.put(`/appliances/${id}`, { active: newActive, status: newStatus });
    } catch (err) {
      console.error('Failed to update active count', err);
      fetchAppliances();
    }
  };

  // ── Toggle ON/OFF ─────────────────────────────────────────────
  const toggleStatus = async (id, override = false) => {
    const item = appliances.find(a => a._id === id);
    if (!item) return;

    const newStatus = !item.status;
    const newActive = newStatus && item.active === 0 ? 1 : newStatus ? item.active : 0;

    // Lock guard — if locked and turning ON, show warning modal first
    if (newStatus && item.lockedBySystem && !override) {
      setLockModal({ id, reason: item.lockReason, pendingStatus: newStatus, pendingActive: newActive, action: 'toggle' });
      return;
    }

    try {
      // Optimistic UI update — also clear lock visually
      setAppliances(prev => prev.map(a => a._id === id ? { ...a, status: newStatus, active: newActive, lockedBySystem: false, lockReason: null } : a));
      await api.put(`/appliances/${id}`, { status: newStatus, active: newActive, ...(override && { override: true }) });
    } catch (err) {
      console.error('Failed to toggle status', err);
      fetchAppliances();
    }
  };

  // ── Confirm override from lock modal ──────────────────────────
  const confirmOverride = async () => {
    if (!lockModal) return;
    const { id, pendingStatus, pendingActive, action } = lockModal;
    setLockModal(null);
    if (action === 'toggle') {
      await toggleStatus(id, true);
    } else {
      await incrementActive(id, true);
    }
  };

  // ── Delete appliance ──────────────────────────────────────────
  const deleteAppliance = async (id) => {
    if (window.confirm('Delete this appliance?')) {
      try {
        setAppliances(prev => prev.filter(a => a._id !== id));
        await api.delete(`/appliances/${id}`);
      } catch (err) {
        console.error('Failed to delete appliance', err);
        fetchAppliances();
      }
    }
  };

  // ── Open add modal ────────────────────────────────────────────
  const openAdd = () => {
    setEditItem(null);
    setForm({ name: '', power: '', quantity: '1', priority: 'Medium', timerMinutes: '' });
    setFormError('');
    setShowModal(true);
  };

  // ── Open edit modal ───────────────────────────────────────────
  const openEdit = (appliance) => {
    setEditItem(appliance);
    setForm({
      name: appliance.name,
      power: appliance.power.toString(),
      quantity: appliance.quantity.toString(),
      priority: appliance.priority || 'Medium',
      timerMinutes: appliance.timerMinutes ? appliance.timerMinutes.toString() : ''
    });
    setFormError('');
    setShowModal(true);
  };

  // ── Save add / edit ───────────────────────────────────────────
  const handleSave = async () => {
    const { name, power, quantity, priority, timerMinutes } = form;
    if (!name.trim())        { setFormError('Appliance name is required'); return; }
    if (!power || Number(power) <= 0){ setFormError('Power (watts) must be > 0');  return; }
    if (!quantity || Number(quantity) < 1){ setFormError('Quantity must be at least 1'); return; }

    try {
      setLoading(true);
      if (editItem) {
        // Edit existing
        const res = await api.put(`/appliances/${editItem._id}`, {
          name: name.trim(),
          power: Number(power),
          quantity: Number(quantity),
          priority,
          timerMinutes
        });
        setAppliances(prev => prev.map(a => a._id === editItem._id ? res.data : a));
      } else {
        // Add new
        const res = await api.post('/appliances', {
          name: name.trim(),
          power: Number(power),
          quantity: Number(quantity),
          priority,
          timerMinutes,
          active: 0,
          status: false
        });
        setAppliances(prev => [...prev, res.data]);
      }
      setShowModal(false);
      setError('');
    } catch (err) {
      setFormError('Failed to save appliance. Please try again.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // ── Computed stats ────────────────────────────────────────────
  const tariffRate   = Number(localStorage.getItem('tariffRate')) || 5.80;
  const totalActive  = appliances.filter((a) => a.status).length;
  const totalWatts   = appliances
    .filter((a) => a.status)
    .reduce((sum, a) => sum + a.power * a.active, 0);

  if (loading && appliances.length === 0) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div className="appliances-page">
      {/* ── Page Header ─────────────────────────────────────── */}
      <div className="appliances-header">
        <div>
          <h1>Appliances</h1>
          <p>Add and manage your home appliances</p>
        </div>
        <button className="btn-add-appliance" onClick={openAdd}>
          <FiPlus size={16} /> Add Appliance
        </button>
      </div>

      {error && (
        <div className="alert alert-error" style={{ marginBottom: 20 }}>
          ⚠️ {error}
        </div>
      )}

      {/* ── Summary bar ─────────────────────────────────────── */}
      <div className="appliances-summary">
        <div className="summary-chip">
          <span className="chip-label">Total Appliances</span>
          <span className="chip-value">{appliances.length}</span>
        </div>
        <div className="summary-chip active">
          <span className="chip-label">Currently ON</span>
          <span className="chip-value">{totalActive}</span>
        </div>
        <div className="summary-chip power">
          <span className="chip-label">Active Load</span>
          <span className="chip-value">{totalWatts} W</span>
        </div>
        <div className="summary-chip bill">
          <span className="chip-label">Est. Cost/hr</span>
          <span className="chip-value">₹{((totalWatts / 1000) * tariffRate).toFixed(2)}</span>
        </div>
      </div>

      {/* ── Table ───────────────────────────────────────────── */}
      <div className="table-card">
        {appliances.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#94a3b8' }}>
            No appliances found. Add your first appliance above!
          </div>
        ) : (
          <table className="appliances-table">
            <thead>
              <tr>
                <th>Appliance</th>
                <th>Power (W)</th>
                <th>Priority</th>
                <th>Quantity</th>
                <th>Active</th>
                <th>Timer</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {appliances.map((a, idx) => (
                <tr key={a._id} className={`table-row ${a.status ? 'row-on' : ''}`}
                    style={{ animationDelay: `${idx * 0.04}s` }}>

                  {/* Appliance Name */}
                  <td>
                    <div className="appliance-name-cell">
                      <span className="appliance-emoji">{getIcon(a.name)}</span>
                      <span className="appliance-name">{a.name}</span>
                      {a.lockedBySystem && (
                        <span
                          className="lock-badge"
                          title={a.lockReason || 'Turned off by system'}
                        >
                          🔒
                        </span>
                      )}
                    </div>
                  </td>

                  {/* Power */}
                  <td>
                    <span className="power-badge">
                      <FiZap size={11} />
                      {a.power} W
                    </span>
                  </td>

                  {/* Priority */}
                  <td>
                    <span className={`priority-badge ${a.priority?.toLowerCase() || 'medium'}`}>
                      {a.priority || 'Medium'}
                    </span>
                  </td>

                  {/* Quantity */}
                  <td>
                    <span className="qty-value">{a.quantity}</span>
                  </td>

                  {/* Active count with +/- */}
                  <td>
                    <div className="active-counter">
                      <button
                        className="counter-btn minus"
                        onClick={() => decrementActive(a._id)}
                        disabled={a.active === 0}
                      >
                        <FiMinus size={12} />
                      </button>
                      <span className={`counter-value ${a.active > 0 ? 'nonzero' : ''}`}>
                        {a.active}
                      </span>
                      <button
                        className="counter-btn plus"
                        onClick={() => incrementActive(a._id)}
                        disabled={a.active >= a.quantity}
                      >
                        <FiPlus size={12} />
                      </button>
                    </div>
                  </td>

                  {/* Timer */}
                  <td>
                    {a.timerMinutes ? (
                      <div className="timer-badge">
                        <FiClock size={12} style={{marginRight: "4px"}} />
                        {a.status && a.turnedOnAt ? (
                          <span>
                            {Math.max(0, Math.ceil(a.timerMinutes - (nowTime - new Date(a.turnedOnAt).getTime()) / 60000))}m left
                          </span>
                        ) : (
                          <span>{a.timerMinutes}m</span>
                        )}
                      </div>
                    ) : (
                      <span className="no-timer">-</span>
                    )}
                  </td>

                  {/* Status toggle */}
                  <td>
                    <div
                      className={`toggle-switch ${a.status ? 'on' : 'off'}`}
                      onClick={() => toggleStatus(a._id)}
                      role="switch"
                      aria-checked={a.status}
                    >
                      <div className="toggle-thumb" />
                      <span className={`toggle-label ${a.status ? 'on' : 'off'}`}>
                        {a.status ? 'ON' : 'OFF'}
                      </span>
                    </div>
                  </td>

                  {/* Actions */}
                  <td>
                    <div className="action-btns">
                      <button className="action-btn edit" onClick={() => openEdit(a)} title="Edit">
                        <FiEdit2 size={14} />
                      </button>
                      <button className="action-btn delete" onClick={() => deleteAppliance(a._id)} title="Delete">
                        <FiTrash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* ── Add / Edit Modal ─────────────────────────────────── */}
      {showModal && (
        <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && setShowModal(false)}>
          <div className="modal-box">
            <div className="modal-header">
              <h3>{editItem ? 'Edit Appliance' : '+ Add New Appliance'}</h3>
              <button className="modal-close" onClick={() => setShowModal(false)}>
                <FiX size={18} />
              </button>
            </div>

            {formError && <div className="modal-error">{formError}</div>}

            <div className="modal-form">
              <div className="form-field">
                <label>Appliance Name</label>
                <input
                  type="text"
                  placeholder="e.g. Air Conditioner"
                  value={form.name}
                  onChange={(e) => { setForm({ ...form, name: e.target.value }); setFormError(''); }}
                />
              </div>
              <div className="form-field">
                <label>Power (Watts)</label>
                <input
                  type="number"
                  placeholder="e.g. 1500"
                  min="1"
                  value={form.power}
                  onChange={(e) => { setForm({ ...form, power: e.target.value }); setFormError(''); }}
                />
              </div>
              <div className="form-field">
                <label>Priority</label>
                <select
                  value={form.priority}
                  onChange={(e) => setForm({ ...form, priority: e.target.value })}
                  style={{
                    width: '100%', padding: '10px 12px', border: '1px solid #e2e8f0',
                    borderRadius: 8, outline: 'none', fontSize: '0.9rem', fontFamily: 'Inter,sans-serif'
                  }}
                >
                  <option value="Essential">Essential (Always ON, e.g. Fridge, Router)</option>
                  <option value="Medium">Medium (Regular use, e.g. AC, Lights)</option>
                  <option value="Non-essential">Non-essential (Flexible load, e.g. Washing Machine, Iron)</option>
                </select>
              </div>
              <div className="form-field">
                <label>Quantity</label>
                <input
                  type="number"
                  placeholder="e.g. 2"
                  min="1"
                  value={form.quantity}
                  onChange={(e) => { setForm({ ...form, quantity: e.target.value }); setFormError(''); }}
                />
              </div>
              <div className="form-field">
                <label>Timer (minutes)</label>
                <input
                  type="number"
                  placeholder="e.g. 30 (Optional)"
                  min="1"
                  value={form.timerMinutes}
                  onChange={(e) => { setForm({ ...form, timerMinutes: e.target.value }); setFormError(''); }}
                />
              </div>
            </div>

            <div className="modal-actions">
              <button className="btn-cancel" onClick={() => setShowModal(false)}>Cancel</button>
              <button className="btn-save" onClick={handleSave} disabled={loading}>
                {loading ? 'Saving...' : editItem ? 'Save Changes' : 'Add Appliance'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Lock Warning Modal ───────────────────────────────────── */}
      {lockModal && (
        <div className="modal-overlay" onClick={() => setLockModal(null)}>
          <div className="modal-box lock-warning-box" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>⚠️ System Lock Warning</h3>
              <button className="modal-close" onClick={() => setLockModal(null)}><FiX size={18} /></button>
            </div>
            <div className="lock-warning-body">
              <div className="lock-icon-big">🔒</div>
              <p className="lock-reason-text">
                This appliance was <strong>automatically turned off by the system</strong>.
              </p>
              <div className="lock-reason-box">
                <span className="lock-reason-label">Reason:</span>
                <span className="lock-reason-value">{lockModal.reason || 'System safety guard triggered.'}</span>
              </div>
              <p className="lock-warning-note">
                Turning it back on may cause overload or exceed usage limits. Are you sure you want to override the system?
              </p>
            </div>
            <div className="modal-actions">
              <button className="btn-cancel" onClick={() => setLockModal(null)}>Cancel</button>
              <button className="btn-override" onClick={confirmOverride}>
                🔓 Turn On Anyway
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Appliances;
