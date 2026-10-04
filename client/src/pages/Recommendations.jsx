import React, { useState, useEffect, useCallback } from 'react';
import { FiThumbsUp, FiAlertTriangle, FiClock, FiZap, FiRefreshCw, FiInfo, FiX } from 'react-icons/fi';

import api from '../services/api';
import './Recommendations.css';

const Recommendations = () => {
  const [recommendations, setRecommendations] = useState([]);
  const [systemData, setSystemData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState('all'); // all, action, optimal
  const [lockModal, setLockModal] = useState(null); // { id, reason, pendingStatus, pendingActive }

  // Load custom settings if set, else use KERC default
  const sanctionedLoadWatts = Number(localStorage.getItem('sanctionedLoad')) || 4000;
  const tariffRate = Number(localStorage.getItem('tariffRate')) || 5.80;

  // ── Fetch Recommendations from Backend ───────────────────────
  const fetchRecommendations = useCallback(async (isRefresh = false) => {
    try {
      if (isRefresh) setRefreshing(true);
      else setLoading(true);

      const res = await api.post('/energy/recommendations', {
        sanctionedLoadWatts
      });
      setSystemData(res.data);

      // Combine recommendations with the full appliance details from database
      const dbAppliancesRes = await api.get('/appliances');
      const dbAppliances = dbAppliancesRes.data;

      const combined = res.data.recommendations.map(rec => {
        const appInfo = dbAppliances.find(a => a._id === rec.id) || {};
        return {
          ...rec,
          power: appInfo.power || 0,
          quantity: appInfo.quantity || 1,
          active: appInfo.active || 0,
          status: appInfo.status || false,
          priority: appInfo.priority || 'Medium',
        };
      });

      setRecommendations(combined);
      setError('');
    } catch (err) {
      setError('Failed to fetch recommendations. Make sure the server and Python environment are ready.');
      console.error(err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [sanctionedLoadWatts]);

  useEffect(() => {
    fetchRecommendations();
  }, [fetchRecommendations]);

  // ── Toggle Status directly ────────────────────────────────────
  const toggleApplianceStatus = async (id, currentStatus, activeCount, override = false) => {
    const newStatus = !currentStatus;
    const newActive = newStatus && activeCount === 0 ? 1 : newStatus ? activeCount : 0;

    // Lock guard — find the rec to check lockedBySystem
    const rec = recommendations.find(r => r.id === id);
    if (newStatus && rec?.lockedBySystem && !override) {
      setLockModal({ id, reason: rec.lockReason, pendingStatus: newStatus, pendingActive: newActive });
      return;
    }

    try {
      // Optimistic update
      setRecommendations(prev => prev.map(r => r.id === id ? { ...r, status: newStatus, active: newActive, lockedBySystem: false, lockReason: null } : r));
      await api.put(`/appliances/${id}`, { status: newStatus, active: newActive, ...(override && { override: true }) });
      // Recalculate recommendations
      fetchRecommendations(true);
    } catch (err) {
      console.error('Failed to toggle status', err);
      fetchRecommendations(true);
    }
  };

  // ── Confirm override from lock modal ──────────────────────────
  const confirmOverride = async () => {
    if (!lockModal) return;
    const { id, pendingStatus, pendingActive } = lockModal;
    setLockModal(null);
    // Find current rec to pass current values
    const rec = recommendations.find(r => r.id === id);
    if (rec) await toggleApplianceStatus(id, !pendingStatus, pendingStatus ? pendingActive : 0, true);
  };

  // ── Batch turn off all Suggest_OFF appliances ──────────────────
  const optimizeAll = async () => {
    const offTargets = recommendations.filter(r => r.action === 'Suggest_OFF' && r.status);
    if (offTargets.length === 0) return;

    try {
      setRefreshing(true);
      const updatePromises = offTargets.map(r =>
        api.put(`/appliances/${r.id}`, { status: false, active: 0 })
      );
      await Promise.all(updatePromises);
      await fetchRecommendations();
    } catch (err) {
      console.error('Failed to run batch optimization', err);
      fetchRecommendations(true);
    }
  };

  // ── Computations ──────────────────────────────────────────────
  const activeLoadWatts = recommendations
    .filter(r => r.status)
    .reduce((sum, r) => sum + r.power * r.active, 0);

  const loadRatio = sanctionedLoadWatts > 0 ? (activeLoadWatts / sanctionedLoadWatts) : 0;

  // Potential savings if user acts on recommendations
  const suggestOffSavingsWatts = recommendations
    .filter(r => r.action === 'Suggest_OFF' && r.status)
    .reduce((sum, r) => sum + r.power * r.active, 0);

  const delayLoadSavingsWatts = recommendations
    .filter(r => r.action === 'Delay_Load' && r.status)
    .reduce((sum, r) => sum + r.power * r.active, 0);

  const hourlySavingsCost = ((suggestOffSavingsWatts + delayLoadSavingsWatts) / 1000 * tariffRate).toFixed(2);

  // Filters logic
  const filteredRecommendations = recommendations.filter(r => {
    if (filter === 'action') return r.action === 'Suggest_OFF' || r.action === 'Delay_Load';
    if (filter === 'optimal') return r.action === 'No_Action';
    return true;
  });

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div className="recommendations-page">
      {/* ── Header ─────────────────────────────────────────── */}
      <div className="recs-header">
        <div>
          <h1>AI recommendations</h1>
          <p>Real-time energy optimization powered by machine learning</p>
        </div>
        <button
          className="btn-refresh"
          onClick={() => fetchRecommendations(true)}
          disabled={refreshing}
        >
          <FiRefreshCw size={14} className={refreshing ? 'spin' : ''} />
          {refreshing ? 'Analyzing...' : 'Run AI Analysis'}
        </button>
      </div>

      {error && (
        <div className="alert alert-error" style={{ marginBottom: 20 }}>
          ⚠️ {error}
        </div>
      )}

      {/* ── System Status Dashboard ────────────────────────── */}
      {systemData && (
        <div className="system-grid">
          {/* Load Ratio Card */}
          <div className="system-card load-meter">
            <h3>⚡ System Load Status</h3>
            <div className="meter-values">
              <span className="current-load">{activeLoadWatts} W</span>
              <span className="slash">/</span>
              <span className="limit-load">{sanctionedLoadWatts} W Limit</span>
            </div>

            <div className="progress-bar-container">
              <div
                className={`progress-bar ${loadRatio > 0.8 ? 'critical' : loadRatio > 0.5 ? 'warning' : 'optimal'}`}
                style={{ width: `${Math.min(100, loadRatio * 100)}%` }}
              />
            </div>
            <div className="ratio-text">
              System is operating at <strong>{(loadRatio * 100).toFixed(1)}%</strong> capacity.
            </div>
          </div>

          {/* Savings Box */}
          <div className="system-card savings-box">
            <h3>💰 Potential Hourly Savings</h3>
            <div className="savings-value">₹{hourlySavingsCost}<span>/ hr</span></div>
            <p>By switching off suggested appliances, you can save {((suggestOffSavingsWatts + delayLoadSavingsWatts) / 1000).toFixed(2)} kWh per hour.</p>
            {suggestOffSavingsWatts > 0 && (
              <button className="btn-optimize-now" onClick={optimizeAll}>
                Optimize System Now
              </button>
            )}
          </div>

          {/* Context Factors */}
          <div className="system-card context-box">
            <h3>🌤️ AI Context Parameters</h3>
            <div className="context-items">
              <div className="context-item">
                <span className="label">Season</span>
                <span className="value">{systemData.season}</span>
              </div>
              <div className="context-item">
                <span className="label">Time Slot</span>
                <span className="value">{systemData.timeSlot}</span>
              </div>
              <div className="context-item">
                <span className="label">Temperature</span>
                <span className="value">{systemData.temp}°C</span>
              </div>
              <div className="context-item">
                <span className="label">Humidity</span>
                <span className="value">{systemData.humidity}%</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Tabs & Filter ──────────────────────────────────── */}
      <div className="filter-row">
        <div className="filter-tabs">
          <button
            className={`filter-tab ${filter === 'all' ? 'active' : ''}`}
            onClick={() => setFilter('all')}
          >
            All Appliances ({recommendations.length})
          </button>
          <button
            className={`filter-tab ${filter === 'action' ? 'active' : ''}`}
            onClick={() => setFilter('action')}
          >
            Action Required ({recommendations.filter(r => r.action !== 'No_Action').length})
          </button>
          <button
            className={`filter-tab ${filter === 'optimal' ? 'active' : ''}`}
            onClick={() => setFilter('optimal')}
          >
            Running Optimally ({recommendations.filter(r => r.action === 'No_Action').length})
          </button>
        </div>
      </div>

      {/* ── Recommendations Grid ───────────────────────────── */}
      <div className="recs-grid">
        {filteredRecommendations.length === 0 ? (
          <div className="no-items-card">
            <FiInfo size={28} />
            <p>No appliances found in this category.</p>
          </div>
        ) : (
          filteredRecommendations.map((rec) => {
            const isSuggestOff = rec.action === 'Suggest_OFF';
            const isDelayLoad = rec.action === 'Delay_Load';
            const isNoAction = rec.action === 'No_Action';

            let cardClass = 'rec-card';
            let icon = <FiThumbsUp />;
            let statusText = 'Optimized';

            if (isSuggestOff) {
              cardClass += ' suggest-off';
              icon = <FiAlertTriangle />;
              statusText = 'Suggest OFF';
            } else if (isDelayLoad) {
              cardClass += ' delay-load';
              icon = <FiClock />;
              statusText = 'Delay Load';
            }

            return (
              <div key={rec.id} className={cardClass}>
                <div className="card-top">
                  <div className="app-info">
                    <h4>
                      {rec.name}
                      {rec.lockedBySystem && (
                        <span className="lock-badge" title={rec.lockReason || 'Turned off by system'}> 🔒</span>
                      )}
                    </h4>
                    <span className="power-draw">{rec.power}W draw</span>
                  </div>
                  <span className={`action-badge ${rec.action.toLowerCase()}`}>
                    {icon} {statusText}
                  </span>
                </div>

                <p className="reason-text">{rec.reason}</p>

                <div className="card-footer">
                  <div className="app-status">
                    Status: <strong className={rec.status ? 'status-on' : 'status-off'}>
                      {rec.status ? `ON (${rec.active} active)` : 'OFF'}
                    </strong>
                  </div>
                  <button
                    className={`btn-toggle-app ${rec.status ? 'on' : 'off'}`}
                    onClick={() => toggleApplianceStatus(rec.id, rec.status, rec.active)}
                  >
                    {rec.status ? 'Turn OFF' : 'Turn ON'}
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

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
                Turning it back on may cause overload or exceed usage limits. Are you sure you want to override?
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

export default Recommendations;
