import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer
} from 'recharts';
import { useAuth } from '../context/AuthContext';
import api from '../services/api';
import {
  FiZap, FiDollarSign, FiTrendingUp, FiSun,
  FiWind, FiDroplet, FiMapPin, FiRefreshCw, FiGift
} from 'react-icons/fi';
import './Dashboard.css';

// ── Weather icon mapping (OpenWeatherMap icon codes → emoji) ──
const WEATHER_ICONS = {
  '01d': '☀️', '01n': '🌙',
  '02d': '⛅', '02n': '🌥️',
  '03d': '☁️', '03n': '☁️',
  '04d': '☁️', '04n': '☁️',
  '09d': '🌧️', '09n': '🌧️',
  '10d': '🌦️', '10n': '🌧️',
  '11d': '⛈️', '11n': '⛈️',
  '13d': '❄️', '13n': '❄️',
  '50d': '🌫️', '50n': '🌫️',
};

// ── Custom Tooltip for Recharts ───────────────────────────────
const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="custom-tooltip">
        <p className="label">{label}</p>
        <p className="value">{payload[0].value} kWh</p>
      </div>
    );
  }
  return null;
};

/**
 * Dashboard Component
 * ─────────────────────────────────────────────────────────────
 * Fetches:
 *  1. /api/energy/dashboard → Stats (today's units, cost, bill prediction)
 *  2. /api/energy/weather   → Real-time weather from OpenWeatherMap
 *  3. /api/energy/logs      → Last 7-day trend for Recharts AreaChart
 *
 * Stats show 0 until real energy log data is added to MongoDB.
 * Chart is empty until logs exist.
 * Weather is live from OpenWeatherMap API.
 */
const Dashboard = () => {
  const { user } = useAuth();

  // ── State ─────────────────────────────────────────────────────
  const [stats, setStats] = useState(null);
  const [weather, setWeather] = useState(null);
  const [chartData, setChartData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false); // silent background refresh
  const [weatherLoading, setWeatherLoading] = useState(true);
  const [error, setError] = useState('');
  const [chartPeriod, setChartPeriod] = useState('Daily');
  const [energyPoints, setEnergyPoints] = useState(null);
  const [displayedPoints, setDisplayedPoints] = useState(0);
  const [showSparkle, setShowSparkle] = useState(false);
  const prevPointsRef = useRef(null); // track last known points value to prevent spurious animations

  // notifications state
  const [notifications, setNotifications] = useState([]);

  const fetchNotifications = useCallback(async () => {
    try {
      const res = await api.get('/energy/notifications');
      setNotifications(res.data);
    } catch (err) {
      console.warn('Failed to fetch notifications');
    }
  }, []);

  const dismissNotification = async (nid) => {
    try {
      setNotifications(prev => prev.filter(n => n._id !== nid));
      await api.post('/energy/notifications/dismiss', { notificationId: nid });
    } catch (err) {
      console.error('Failed to dismiss notification', err);
      fetchNotifications();
    }
  };

  // ── Fetch dashboard stats & energy logs ───────────────────────
  const fetchDashboardData = useCallback(async (silent = false) => {
    try {
      if (silent) setIsRefreshing(true);
      else setLoading(true);

      const sanctionedLoad = user?.sanctionedLoad || localStorage.getItem('sanctionedLoad') || 4000;
      const tariffRate = user?.tariffRate || localStorage.getItem('tariffRate') || 5.80;
      const historicalAvg = user?.historicalAvg || localStorage.getItem('historicalAvg') || 113.53;

      const [statsRes, logsRes, pointsRes] = await Promise.all([
        api.get('/energy/dashboard', { params: { sanctionedLoad, tariffRate, historicalAvg } }),
        api.get('/energy/logs'),
        api.get('/energy/points'),
      ]);

      setStats(statsRes.data);
      setChartData(logsRes.data || []);
      setEnergyPoints(pointsRes.data);
    } catch (err) {
      if (!silent) {
        setStats({ todayUnits: 0, todayCost: '0.00', predictedMonthlyBill: '0', savedToday: 0 });
        setChartData([]);
      }
    } finally {
      if (silent) setIsRefreshing(false);
      else setLoading(false);
    }
  }, []);

  // ── Fetch real-time weather from OpenWeatherMap ───────────────
  const fetchWeather = useCallback(async () => {
    try {
      setWeatherLoading(true);
      const city = user?.city || 'Bangalore';
      const apiKey = import.meta.env.VITE_OPENWEATHER_API_KEY;

      if (apiKey && apiKey !== 'YOUR_OPENWEATHER_API_KEY') {
        // Step 1: Geocode city name → exact lat/lon (works for any city, including small towns)
        const geoRes = await fetch(
          `https://api.openweathermap.org/geo/1.0/direct?q=${encodeURIComponent(city)}&limit=1&appid=${apiKey}`
        );
        if (geoRes.ok) {
          const geoData = await geoRes.json();
          if (geoData.length > 0) {
            const { lat, lon, name, country } = geoData[0];
            // Step 2: Fetch weather by exact coordinates for maximum accuracy
            const owRes = await fetch(
              `https://api.openweathermap.org/data/2.5/weather?lat=${lat}&lon=${lon}&appid=${apiKey}&units=metric`
            );
            if (owRes.ok) {
              const d = await owRes.json();
              setWeather({
                city: name,
                country: country,
                temp: Math.round(d.main.temp),
                feelsLike: Math.round(d.main.feels_like),
                humidity: d.main.humidity,
                wind: (d.wind.speed * 3.6).toFixed(1),
                description: d.weather[0].description,
                icon: d.weather[0].icon,
                main: d.weather[0].main,
              });
              setWeatherLoading(false);
              return;
            }
          }
        }
        // Fallback: geocoding failed — try city name directly
        const owRes = await fetch(
          `https://api.openweathermap.org/data/2.5/weather?q=${encodeURIComponent(city)}&appid=${apiKey}&units=metric`
        );
        if (owRes.ok) {
          const d = await owRes.json();
          setWeather({
            city: d.name,
            country: d.sys.country,
            temp: Math.round(d.main.temp),
            feelsLike: Math.round(d.main.feels_like),
            humidity: d.main.humidity,
            wind: (d.wind.speed * 3.6).toFixed(1),
            description: d.weather[0].description,
            icon: d.weather[0].icon,
            main: d.weather[0].main,
          });
          setWeatherLoading(false);
          return;
        }
      }
      // Final fallback to backend proxy
      const res = await api.get('/energy/weather');
      setWeather(res.data);
    } catch (err) {
      console.warn('Weather API unavailable');
    } finally {
      setWeatherLoading(false);
    }
  }, [user]);

  // ── Count-up animation — only fires when points VALUE actually changes ──
  useEffect(() => {
    const target = stats?.rewardPoints ?? energyPoints?.points ?? 0;

    // Skip animation if the value hasn't changed (prevents glitch on every poll)
    if (target === prevPointsRef.current) return;
    prevPointsRef.current = target;

    if (target === 0) { setDisplayedPoints(0); return; }

    // Only sparkle on first load or genuine point change
    setShowSparkle(true);
    setTimeout(() => setShowSparkle(false), 1300);

    let current = 0;
    const step = Math.max(1, Math.floor(target / 40));
    const timer = setInterval(() => {
      current = Math.min(current + step, target);
      setDisplayedPoints(current);
      if (current >= target) clearInterval(timer);
    }, 30);
    return () => clearInterval(timer);
  }, [stats?.rewardPoints, energyPoints?.points]);

  useEffect(() => {
    fetchDashboardData(false); // initial load — show spinner
    fetchWeather();
    fetchNotifications();

    const interval = setInterval(() => {
      fetchDashboardData(true); // silent background refresh — no glitch
      fetchNotifications();
    }, 5000);

    return () => clearInterval(interval);
  }, [fetchDashboardData, fetchWeather, fetchNotifications]);

  // Process chartData based on chartPeriod (Daily, Weekly, Monthly)
  const displayChart = React.useMemo(() => {
    if (!chartData || chartData.length === 0) {
      // If no real logs yet, show last 7 days with value 0 (flat zero line)
      return Array.from({ length: 7 }, (_, i) => {
        const d = new Date();
        d.setDate(d.getDate() - (6 - i));
        return { date: d.toLocaleDateString('en-IN', { month: 'short', day: 'numeric' }), value: 0 };
      });
    }

    // Sort logs by date ascending
    const sortedLogs = [...chartData].sort((a, b) => new Date(a.date) - new Date(b.date));

    if (chartPeriod === 'Daily') {
      // Show last 7 days
      const last7 = sortedLogs.slice(-7).map(log => ({
        date: new Date(log.date).toLocaleDateString('en-IN', { month: 'short', day: 'numeric' }),
        value: parseFloat(log.unitsConsumed.toFixed(2))
      }));
      // Always inject today as the last point so it shows even when no DB log exists yet
      const todayStr = new Date().toLocaleDateString('en-IN', { month: 'short', day: 'numeric' });
      const lastPoint = last7[last7.length - 1];
      if (!lastPoint || lastPoint.date !== todayStr) {
        // Today not in DB yet — append as 0 (or live value if appliances are running)
        last7.push({ date: todayStr, value: parseFloat((stats?.todayUnits || 0).toFixed(2)) });
      } else {
        // Today already in DB — keep it updated with live stats value
        last7[last7.length - 1].value = parseFloat((stats?.todayUnits ?? last7[last7.length - 1].value).toFixed(2));
      }
      return last7.slice(-7);
    }
    else if (chartPeriod === 'Weekly') {
      // Group by Week (Starts on Monday)
      const weeks = {};
      sortedLogs.forEach(log => {
        const d = new Date(log.date);
        const day = d.getDay();
        const diff = d.getDate() - day + (day === 0 ? -6 : 1);
        const weekStart = new Date(d.setDate(diff));
        const weekLabel = weekStart.toLocaleDateString('en-IN', { month: 'short', day: 'numeric' });

        if (!weeks[weekLabel]) weeks[weekLabel] = 0;
        weeks[weekLabel] += log.unitsConsumed;
      });
      return Object.keys(weeks).map(weekLabel => ({
        date: `Week of ${weekLabel}`,
        value: parseFloat(weeks[weekLabel].toFixed(2))
      })).slice(-8); // Show last 8 weeks max
    }
    else if (chartPeriod === 'Monthly') {
      // Group by Month
      const months = {};
      sortedLogs.forEach(log => {
        const d = new Date(log.date);
        const monthLabel = d.toLocaleDateString('en-IN', { month: 'short', year: 'numeric' });

        if (!months[monthLabel]) months[monthLabel] = 0;
        months[monthLabel] += log.unitsConsumed;
      });
      return Object.keys(months).map(monthLabel => ({
        date: monthLabel,
        value: parseFloat(months[monthLabel].toFixed(2))
      })).slice(-12); // Show last 12 months max
    }
    return [];
  }, [chartData, chartPeriod, stats]);

  return (
    <div>
      {/* ── Notifications Alerts ─────────────────────────────── */}
      {notifications.length > 0 && (
        <div className="notifications-alert-list fade-in-up" style={{ marginBottom: 20 }}>
          {notifications.map((notif) => (
            <div key={notif._id} className={`alert-notif-card ${notif.type || 'safety'}`} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              background: notif.type === 'overload' ? '#fff1f2' : '#fef3c7',
              border: notif.type === 'overload' ? '1px solid #fecdd3' : '1px solid #fde68a',
              borderRadius: 12, padding: '14px 20px', marginBottom: 10,
              boxShadow: '0 2px 10px rgba(0,0,0,0.05)',
              animation: 'fadeInUp 0.3s ease both'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{ fontSize: '1.4rem' }}>
                  {notif.type === 'overload' ? '🚨' : '⚠️'}
                </span>
                <div>
                  <h5 style={{ margin: 0, fontSize: '0.88rem', fontWeight: 700, color: notif.type === 'overload' ? '#be123c' : '#b45309' }}>
                    {notif.title}
                  </h5>
                  <p style={{ margin: '3px 0 0 0', fontSize: '0.8rem', color: notif.type === 'overload' ? '#9f1239' : '#92400e' }}>
                    {notif.message}
                  </p>
                </div>
              </div>
              <button
                onClick={() => dismissNotification(notif._id)}
                style={{
                  background: 'none', border: 'none',
                  color: notif.type === 'overload' ? '#be123c' : '#b45309',
                  fontWeight: 600, fontSize: '0.8rem', cursor: 'pointer',
                  padding: '4px 8px', borderRadius: 4
                }}
                onMouseOver={(e) => e.target.style.textDecoration = 'underline'}
                onMouseOut={(e) => e.target.style.textDecoration = 'none'}
              >
                Dismiss
              </button>
            </div>
          ))}
        </div>
      )}

      {/* ── Header ─────────────────────────────────────────── */}
      <div className="dashboard-header">
        <div>
          <h1>Hello, {user?.name ? user.name.split(' ')[0] : 'User'} 👋</h1>
          <p>Here's what's happening with your energy today.</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {/* ── Premium Glassmorphism Gold Coin Badge ── */}
          {(stats !== null || energyPoints !== null) && (() => {
            const pts = stats?.rewardPoints ?? energyPoints?.points ?? 0;
            const hasData = !energyPoints?.noData;
            const tooltip = pts > 0
              ? `You saved units vs last year! ${pts} reward points earned.`
              : 'Consume less than last year to earn reward points!';
            return (
              <div className="eco-coin-badge-container">
                <div
                  className={`eco-coin-badge${pts === 0 ? ' no-points' : ''}`}
                  title={tooltip}
                >
                  {showSparkle && (
                    <span className="sparkle-pop">+{pts} pts ✨</span>
                  )}
                  <div className="eco-coin"></div>
                  <div className="eco-coin-text">
                    <span className="eco-coin-value">{displayedPoints}</span>
                    <span className="eco-coin-label">REWARD POINTS</span>
                  </div>
                </div>
              </div>
            );
          })()}

          {/* City badge */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 6,
            background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.2)',
            borderRadius: 20, padding: '6px 14px', fontSize: '0.82rem', color: '#16a34a',
            fontWeight: 600,
          }}>
            <FiMapPin size={12} /> {user?.city || 'Bangalore'}, India
          </div>

          {/* Refresh button */}
          <button
            onClick={() => { fetchDashboardData(); fetchWeather(); }}
            style={{
              background: '#ffffff', border: '1px solid #e8edf3',
              borderRadius: 10, padding: '8px 14px', color: '#64748b',
              cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
              fontSize: '0.85rem', fontFamily: 'Inter,sans-serif',
              boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
            }}
          >
            <FiRefreshCw size={14} /> Refresh
          </button>
        </div>
      </div>

      {/* ── Stat Cards ─────────────────────────────────────── */}
      <div className="stat-grid">
        <StatCard
          label="Units Consumed (Today)"
          value={stats ? parseFloat(stats.todayUnits).toFixed(4) : '0.0000'}
          unit="kWh"
          change="Live reading"
          changeType="positive"
          icon={<FiZap />}
          iconColor="#22c55e"
          delay="fade-in-up-1"
        />
        <StatCard
          label="Current Cost (Today)"
          value={stats ? `₹${stats.todayCost}` : '₹0.00'}
          unit=""
          change="Based on today's usage"
          changeType="positive"
          icon={<FiDollarSign />}
          iconColor="#f59e0b"
          delay="fade-in-up-2"
        />
        <StatCard
          label="Predicted Bill (This Month)"
          value={stats ? `₹${stats.predictedMonthlyBill}` : '₹0'}
          unit=""
          change={stats ? `Incl. ₹${stats.fixedCharge} fixed charge` : 'No data yet'}
          changeType="positive"
          icon={<FiTrendingUp />}
          iconColor="#8b5cf6"
          delay="fade-in-up-3"
        />
        <StatCard
          label="Final Bill (After Discount)"
          value={stats ? `₹${stats.discountApplied > 0 ? stats.finalBill : stats.predictedMonthlyBill}` : '₹0'}
          unit=""
          change={stats && stats.discountApplied > 0
            ? `🎁 -₹${stats.discountApplied} • ${stats.rewardPoints} pts used`
            : 'No reward points yet'}
          changeType={stats && stats.discountApplied > 0 ? 'positive' : 'neutral'}
          icon={<FiGift />}
          iconColor="#f59e0b"
          delay="fade-in-up-4"
        />
        <StatCard
          label="Billable Units (After Free)"
          value={stats ? stats.billableUnits : 0}
          unit="kWh"
          change={stats ? `Total: ${stats.totalUnitsMonth} kWh` : 'No data yet'}
          changeType="positive"
          icon={<FiSun />}
          iconColor="#06b6d4"
          delay="fade-in-up-5"
        />
      </div>


      {/* ── Full-Width Energy Trend Chart ───────────────────── */}
      <div className="chart-full-row fade-in-up-2">
        <div className="chart-card">
          <div className="chart-card-header">
            <h3>⚡ Energy Consumption Trend</h3>
            <div className="chart-tab-group">
              {['Daily', 'Weekly', 'Monthly'].map((p) => (
                <button
                  key={p}
                  className={`chart-tab ${chartPeriod === p ? 'active' : ''}`}
                  onClick={() => setChartPeriod(p)}
                >{p}</button>
              ))}
            </div>
          </div>
          {loading ? (
            <div className="spinner" />
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <AreaChart data={displayChart} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="energyGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.05)" vertical={false} />
                <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v) => `${v}`} />
                <Tooltip content={<CustomTooltip />} />
                <Area type="monotone" dataKey="value" stroke="#22c55e" strokeWidth={2.5}
                  fill="url(#energyGrad)" dot={{ fill: '#22c55e', r: 4, strokeWidth: 0 }} activeDot={{ r: 6, fill: '#22c55e' }} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* ── Info Row: Weather (left) | Tariff + Bill (right) ── */}
      <div className="info-row">

        {/* ── LEFT: Weather Card ───────────────────────────── */}
        <div className="info-panel weather-card fade-in-up-3">
          <h3><span>🌤️</span> Current Weather</h3>
          {weatherLoading ? (
            <div className="spinner" />
          ) : weather ? (
            <>
              <div className="weather-city-badge">
                <FiMapPin size={11} />
                {weather.city}, {weather.country}
              </div>
              <div className="weather-main">
                <span className="weather-icon">{WEATHER_ICONS[weather.icon] || '🌡️'}</span>
                <div>
                  <div className="weather-temp">{weather.temp}<span>°C</span></div>
                  <div className="weather-desc">{weather.description}</div>
                </div>
              </div>
              <div className="weather-details">
                <div className="weather-detail-item">
                  <span className="label">🌡️ Feels like</span>
                  <span className="value">{weather.feelsLike}°C</span>
                </div>
                <div className="weather-detail-item">
                  <FiDroplet style={{ color: '#60a5fa' }} />
                  <span className="label">Humidity</span>
                  <span className="value">{weather.humidity}%</span>
                </div>
                <div className="weather-detail-item">
                  <FiWind style={{ color: '#a78bfa' }} />
                  <span className="label">Wind</span>
                  <span className="value">{weather.wind} km/h</span>
                </div>
              </div>
            </>
          ) : (
            <p style={{ color: '#94a3b8', fontSize: '0.9rem', textAlign: 'center', marginTop: 40 }}>Weather unavailable</p>
          )}
        </div>

        {/* ── RIGHT: Tariff + Bill Breakdown ───────────────── */}
        <div className="info-panel fade-in-up-4">
          {/* Tariff Box */}
          <div className="tariff-box" style={{ marginBottom: 16 }}>
            <h4>⚡ KERC Active Tariff (FY26-27)</h4>
            <div className="tariff-value">₹{stats?.tariffRate ? Number(stats.tariffRate).toFixed(2) : '5.80'} / kWh</div>
            <div className="tariff-hours">Gruha Jyothi: {stats?.entitlementUnits || 125} kWh Entitlement (Free ≤200 kWh)</div>
            <div className="tariff-hours" style={{ marginTop: 4 }}>
              Fixed Charge: ₹150 / kW / month ({stats?.sanctionedLoadKw || 4} kW load)
            </div>
          </div>

          {/* Bill Breakdown Box */}
          {stats && Number(stats.predictedMonthlyBill) > 0 && (
            <div style={{
              background: 'linear-gradient(135deg, rgba(139,92,246,0.08), rgba(236,72,153,0.08))',
              border: '1px solid rgba(139,92,246,0.2)',
              borderRadius: 10, padding: '14px 16px', flex: 1
            }}>
              <h4 style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 600 }}>
                📊 Estimated Monthly Bill Breakdown
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: '0.8rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Projected consumption:</span>
                  <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{stats.totalUnitsMonth} kWh</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Gruha Jyothi Entitlement:</span>
                  <span style={{ fontWeight: 600, color: stats.subsidyForfeited ? '#ef4444' : '#16a34a' }}>
                    {stats.subsidyForfeited ? '0 kWh (Forfeited >200)' : `-${stats.freeUnits} kWh`}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Billable Units:</span>
                  <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{stats.billableUnits} kWh</span>
                </div>
                {stats.subsidyForfeited && (
                  <div style={{ fontSize: '0.72rem', color: '#ef4444', background: 'rgba(239,68,68,0.1)', padding: '4px 8px', borderRadius: 4, marginTop: 2, fontWeight: 500 }}>
                    ⚠️ Total usage &gt; 200 kWh ceiling: Gruha Jyothi subsidy forfeited (100% billable).
                  </div>
                )}
                <hr style={{ border: 'none', borderTop: '1px solid rgba(0,0,0,0.06)', margin: '4px 0' }} />
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Energy Charge:</span>
                  <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>₹{stats.energyCharge}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Fixed Charge ({stats?.sanctionedLoadKw || 4} kW):</span>
                  <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>₹{stats.fixedCharge}</span>
                </div>
                <hr style={{ border: 'none', borderTop: '1px dashed rgba(0,0,0,0.1)', margin: '4px 0' }} />
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem', fontWeight: 700 }}>
                  <span style={{ color: 'var(--text-primary)' }}>Total Predicted Bill:</span>
                  <span style={{ color: 'var(--accent-purple)' }}>₹{stats.predictedMonthlyBill}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="alert alert-error" style={{ marginTop: 8 }}>
          ⚠️ {error}
        </div>
      )}
    </div>
  );
};

// ── Reusable Stat Card component ──────────────────────────────
const StatCard = ({ label, value, unit, change, changeType, icon, iconColor, delay }) => (
  <div className={`stat-card ${delay}`}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
      <span className="stat-label">{label}</span>
      <span style={{
        color: iconColor,
        background: `${iconColor}20`,
        padding: '6px',
        borderRadius: 8,
        display: 'flex',
        fontSize: '1rem',
      }}>{icon}</span>
    </div>
    <div>
      <span className="stat-value">{value}</span>
      {unit && <span className="stat-unit">{unit}</span>}
    </div>
    <div className={`stat-change ${changeType}`}>{change}</div>
  </div>
);

export default Dashboard;