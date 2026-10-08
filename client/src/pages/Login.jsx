import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { FiMail, FiLock, FiUser, FiMapPin, FiEye, FiEyeOff } from 'react-icons/fi';

import './Login.css';

/**
 * Login Page Component
 * ─────────────────────────────────────────────────────────────
 * Dual-panel layout:
 *  - Left: Branding / feature highlights
 *  - Right: Login / Signup form tabs
 *
 * Auth handled via AuthContext → calls Express /api/auth endpoints
 * On success: stores JWT in localStorage, redirects to /dashboard
 */
const LoginPage = () => {
  const navigate = useNavigate();
  const { login, register } = useAuth();

  // Toggle between "Login" and "Signup" tabs
  const [activeTab, setActiveTab] = useState('login');

  // Form state
  const [formData, setFormData] = useState({
    name: '', email: '', password: '', city: 'Bangalore',
  });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Generic input change handler
  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
    setError(''); // Clear error on type
  };

  // ── Form Submit ──────────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      if (activeTab === 'login') {
        await login(formData.email, formData.password);
      } else {
        if (!formData.name.trim()) { setError('Name is required'); setLoading(false); return; }
        await register(formData.name, formData.email, formData.password, formData.city);
      }
      navigate('/dashboard');
    } catch (err) {
      // No response = network error = backend server is not running
      if (!err.response) {
        setError('⚠️ Cannot connect to server. Make sure the backend is running: open a terminal in the server/ folder and run "npm start"');
      } else {
        // Server responded with an error (wrong password, email not found, etc.)
        setError(err.response?.data?.message || 'Something went wrong. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  // ── Forgot Password Demo ─────────────────────────────────────────
  const handleForgotPassword = async (e) => {
    e.preventDefault();
    const email = window.prompt("🔑 Forgot Password\n\nEnter your registered email address:");
    if (!email) return;
    
    setLoading(true);
    try {
      const res = await fetch('http://localhost:5000/api/auth/reset-password-demo', {
         method: 'POST',
         headers: {'Content-Type': 'application/json'},
         body: JSON.stringify({email: email.trim()})
      });
      const data = await res.json();
      
      if (!res.ok) {
        window.alert('❌ Error: ' + (data.message || 'Could not reset password.'));
      } else {
        window.alert('✅ Success!\n\nWe have sent a new temporary password to your email. Please check your inbox and log in.');
      }
    } catch (err) {
      window.alert('❌ Network error. Make sure the backend is running.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">

      {/* ── LEFT PANEL — Branding ──────────────────────────── */}
      <div className="login-branding">
        <div className="brand-logo">⚡</div>
        <h1 className="brand-title">
          AI <span>Energy</span><br />Optimizer
        </h1>
        <p className="brand-subtitle">
          Smart Energy Today,<br />Sustainable Tomorrow
        </p>

        <div className="brand-features">
          <div className="brand-feature">
            <span className="feat-icon">📊</span>
            Real-time Energy Monitoring
          </div>
          <div className="brand-feature">
            <span className="feat-icon">🌤️</span>
            Live Weather Integration
          </div>
          <div className="brand-feature">
            <span className="feat-icon">🤖</span>
            AI-Powered Recommendations
          </div>
          <div className="brand-feature">
            <span className="feat-icon">💰</span>
            Bill Prediction & Savings
          </div>
        </div>
      </div>

      {/* ── RIGHT PANEL — Auth Form ────────────────────────── */}
      <div className="login-form-panel">
        <div className="login-form-box">
          <h2>Welcome Back! 👋</h2>
          <p className="sub-heading">
            {activeTab === 'login'
              ? 'Login to your account'
              : 'Create your free account'}
          </p>

          {/* Tab switcher */}
          <div className="tabs">
            <button
              className={`tab-btn ${activeTab === 'login' ? 'active' : ''}`}
              onClick={() => { setActiveTab('login'); setError(''); }}
            >Login</button>
            <button
              className={`tab-btn ${activeTab === 'signup' ? 'active' : ''}`}
              onClick={() => { setActiveTab('signup'); setError(''); }}
            >Sign Up</button>
          </div>

          {/* Error alert */}
          {error && <div className="alert alert-error">{error}</div>}

          {/* Form */}
          <form onSubmit={handleSubmit}>
            {/* Name (signup only) */}
            {activeTab === 'signup' && (
              <>
                <label className="form-label">Full Name</label>
                <div className="input-group">
                  <FiUser className="icon" />
                  <input
                    type="text"
                    name="name"
                    placeholder="Your full name"
                    value={formData.name}
                    onChange={handleChange}
                    required
                  />
                </div>
              </>
            )}

            {/* Email */}
            <label className="form-label">Email Address</label>
            <div className="input-group">
              <FiMail className="icon" />
              <input
                type="email"
                name="email"
                placeholder="you@example.com"
                value={formData.email}
                onChange={handleChange}
                autoComplete="email"
                required
              />
            </div>

            {/* Password */}
            <label className="form-label">Password</label>
            <div className="input-group" style={{ marginBottom: activeTab === 'login' ? 0 : 16 }}>
              <FiLock className="icon" />
              <input
                type={showPassword ? 'text' : 'password'}
                name="password"
                placeholder="••••••••"
                value={formData.password}
                onChange={handleChange}
                autoComplete={activeTab === 'login' ? 'current-password' : 'new-password'}
                required
                style={{ paddingRight: 44 }}
              />
              {/* Eye toggle */}
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={{
                  position: 'absolute', right: 14, top: '50%', transform: 'translateY(-50%)',
                  background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer',
                }}
              >
                {showPassword ? <FiEyeOff /> : <FiEye />}
              </button>
            </div>

            {activeTab === 'login' && (
              <div className="forgot-link">
                <a href="#" onClick={handleForgotPassword}>Forgot Password?</a>
              </div>
            )}

            {/* City (signup only) */}
            {activeTab === 'signup' && (
              <>
                <label className="form-label">Your City (for weather)</label>
                <div className="input-group">
                  <FiMapPin className="icon" />
                  <input
                    type="text"
                    name="city"
                    placeholder="e.g. Bangalore"
                    value={formData.city}
                    onChange={handleChange}
                  />
                </div>
              </>
            )}

            <button className="btn-primary" type="submit" disabled={loading}>
              {loading ? 'Please wait…' : activeTab === 'login' ? 'Login' : 'Create Account'}
            </button>
          </form>



          {/* Switch tab link */}
          <p className="signin-link">
            {activeTab === 'login'
              ? <>Don't have an account?{' '}<span onClick={() => setActiveTab('signup')}>Sign up</span></>
              : <>Already have an account?{' '}<span onClick={() => setActiveTab('login')}>Login</span></>
            }
          </p>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
