import { useState, useEffect } from 'react';
import './ConfigPanel.css';

const API_URL = 'http://localhost:8000';

// Theme toggle component
function ThemeToggle({ theme, onToggle }) {
  return (
    <button 
      className="theme-toggle" 
      onClick={onToggle}
      aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
    >
      {theme === 'dark' ? (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="5"/>
          <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
        </svg>
      ) : (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
        </svg>
      )}
    </button>
  );
}

const CONFIG_OPTIONS = [
  {
    key: 'SMOOTHING_FACTOR',
    label: 'Smoothing Factor',
    description: 'Lower is smoother but adds cursor trailing lag. Higher tracks snappier but is more jittery.',
    min: 0,
    max: 1,
    step: 0.05,
    endpoint: '/config/smoothing_factor'
  },
  {
    key: 'SENSITIVITY',
    label: 'Sensitivity',
    description: 'Multiplier for how minimal hand movements stretch across the virtual display space.',
    min: 0.1,
    max: 3,
    step: 0.1,
    endpoint: '/config/sensitivity'
  },
  {
    key: 'Y_OFFSET',
    label: 'Y Offset',
    description: 'Offsets the baseline vertical center if your cursor naturally aligns too high/low compared to your physical hand.',
    min: -0.5,
    max: 0.5,
    step: 0.05,
    endpoint: '/config/y_offset'
  },
  {
    key: 'DEADZONE',
    label: 'Deadzone',
    description: 'Your finger must translate outside this zone to move the cursor (prevents micro-shaking).',
    min: 0,
    max: 0.2,
    step: 0.005,
    endpoint: '/config/deadzone'
  },
  {
    key: 'COMMAND_COOLDOWN',
    label: 'Command Cooldown',
    description: 'Seconds mandated between actions like Mouse Clicks and Enter keypresses to prevent accidental double/triple firing.',
    min: 0.1,
    max: 3,
    step: 0.1,
    endpoint: '/config/command_cooldown'
  },
  {
    key: 'SCROLLING_SENSITIVITY',
    label: 'Scrolling Sensitivity',
    description: 'Scale factor to adjust how fast omni-directional scrolling occurs with an open palm.',
    min: 0.1,
    max: 3,
    step: 0.1,
    endpoint: '/config/scrolling_sensitivity'
  },
  {
    key: 'EDGE_THRESHOLD',
    label: 'Edge Threshold',
    description: 'Margin at the edge of the camera view where "sticky scrolling" behavior is enforced to avoid bouncing.',
    min: 0,
    max: 0.5,
    step: 0.05,
    endpoint: '/config/edge_threshold'
  },
  {
    key: 'STICKY_THRESHOLD',
    label: 'Sticky Threshold',
    description: 'Absolute velocity required to break the scroll anchor when moving backwards inside an edge threshold.',
    min: 0,
    max: 500,
    step: 10,
    endpoint: '/config/sticky_threshold'
  }
];

function ConfigSlider({ option, value, onChange, onCommit }) {
  const [localValue, setLocalValue] = useState(value);
  const [isDragging, setIsDragging] = useState(false);

  useEffect(() => {
    if (!isDragging) {
      setLocalValue(value);
    }
  }, [value, isDragging]);

  const handleChange = (e) => {
    const newValue = parseFloat(e.target.value);
    setLocalValue(newValue);
    onChange(option.key, newValue);
  };

  const handleMouseDown = () => {
    setIsDragging(true);
  };

  const handleMouseUp = () => {
    setIsDragging(false);
    onCommit(option.key, localValue, option.endpoint);
  };

  return (
    <div className="config-slider">
      <div className="config-header">
        <label htmlFor={option.key}>{option.label}</label>
        <span className="config-value">{localValue?.toFixed(option.step < 1 ? 2 : 0)}</span>
      </div>
      <input
        type="range"
        id={option.key}
        min={option.min}
        max={option.max}
        step={option.step}
        value={localValue ?? option.min}
        onChange={handleChange}
        onMouseDown={handleMouseDown}
        onMouseUp={handleMouseUp}
        onTouchStart={handleMouseDown}
        onTouchEnd={handleMouseUp}
      />
      <p className="config-description">{option.description}</p>
    </div>
  );
}

export default function ConfigPanel() {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [status, setStatus] = useState(null);
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem('theme');
    if (saved) return saved;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  });

  useEffect(() => {
    fetchConfig();
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => prev === 'dark' ? 'light' : 'dark');
  };

  const fetchConfig = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`${API_URL}/config`);
      if (!response.ok) {
        throw new Error('Failed to fetch configuration. Make sure the API server is running.');
      }
      const data = await response.json();
      setConfig(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (key, value) => {
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  const handleCommit = async (key, value, endpoint) => {
    try {
      const response = await fetch(`${API_URL}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value })
      });
      
      if (!response.ok) {
        throw new Error('Failed to save configuration');
      }
    } catch (err) {
      setStatus({ type: 'error', message: err.message });
      fetchConfig(); // Revert to server state on error
    }
  };

  const handleReset = async () => {
    const defaults = {
      SMOOTHING_FACTOR: 0.6,
      SENSITIVITY: 1.2,
      Y_OFFSET: 0,
      DEADZONE: 0.02,
      COMMAND_COOLDOWN: 1.0,
      SCROLLING_SENSITIVITY: 1.0,
      EDGE_THRESHOLD: 0.15,
      STICKY_THRESHOLD: 150.0
    };

    try {
      setStatus({ type: 'saving', message: 'Resetting...' });
      const response = await fetch(`${API_URL}/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(defaults)
      });
      
      if (!response.ok) {
        throw new Error('Failed to reset configuration');
      }
      
      setConfig(defaults);
      setStatus({ type: 'success', message: 'Reset to defaults!' });
      setTimeout(() => setStatus(null), 1500);
    } catch (err) {
      setStatus({ type: 'error', message: err.message });
    }
  };

  if (loading) {
    return (
      <div className="config-panel">
        <div className="config-loading">
          <div className="spinner"></div>
          <p>Loading configuration...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="config-panel">
        <div className="config-error">
          <h3>⚠️ Connection Error</h3>
          <p>{error}</p>
          <button onClick={fetchConfig} className="retry-btn">
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="config-panel">
      <div className="config-panel-header">
        <div className="header-top">
          <h2>Point and Click Gesture Control Settings</h2>
          <ThemeToggle theme={theme} onToggle={toggleTheme} />
        </div>
        <p className="config-panel-subtitle">
          Adjust tracking physics in real-time. Changes are applied instantly.
        </p>
      </div>

      {status && (
        <div className={`config-status ${status.type}`}>
          {status.message}
        </div>
      )}

      <div className="config-grid">
        {CONFIG_OPTIONS.map(option => (
          <ConfigSlider
            key={option.key}
            option={option}
            value={config[option.key]}
            onChange={handleChange}
            onCommit={handleCommit}
          />
        ))}
      </div>

      <div className="config-actions">
        <button onClick={handleReset} className="reset-btn">
          Reset to Defaults
        </button>
        <button onClick={fetchConfig} className="refresh-btn">
          Refresh from Server
        </button>
      </div>
    </div>
  );
}
