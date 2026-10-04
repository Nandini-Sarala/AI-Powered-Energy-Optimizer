import re

with open('client/src/pages/Appliances.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. State
content = content.replace(
    'const [form, setForm] = useState({ name: \'\', power: \'\', quantity: \'\', priority: \'Medium\' });',
    'const [nowTime, setNowTime] = useState(Date.now());\n  useEffect(() => { const int = setInterval(() => setNowTime(Date.now()), 30000); return () => clearInterval(int); }, []);\n  const [form, setForm] = useState({ name: \'\', power: \'\', quantity: \'\', priority: \'Medium\', timerMinutes: \'\' });'
)

# 2. openAdd
content = content.replace(
    'setForm({ name: \'\', power: \'\', quantity: \'1\', priority: \'Medium\' });',
    'setForm({ name: \'\', power: \'\', quantity: \'1\', priority: \'Medium\', timerMinutes: \'\' });'
)

# 3. openEdit
content = content.replace(
    'priority: appliance.priority || \'Medium\'\n    });',
    'priority: appliance.priority || \'Medium\',\n      timerMinutes: appliance.timerMinutes ? appliance.timerMinutes.toString() : \'\'\n    });'
)

# 4. handleSave
content = content.replace(
    'const { name, power, quantity, priority } = form;',
    'const { name, power, quantity, priority, timerMinutes } = form;'
)
content = content.replace(
    'priority\n        });',
    'priority,\n          timerMinutes\n        });'
)
content = content.replace(
    'priority,\n          active: 0,',
    'priority,\n          timerMinutes,\n          active: 0,'
)

# 5. Table headers
content = content.replace(
    '<th>Active</th>\n                <th>Status</th>',
    '<th>Active</th>\n                <th>Timer</th>\n                <th>Status</th>'
)

# 6. Table row
table_td = '''                  </td>

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

                  {/* Status toggle */}'''
content = content.replace(
    '                  </td>\n\n                  {/* Status toggle */}',
    table_td
)

# 7. Form fields
form_f = '''              <div className="form-field">
                <label>Timer (minutes)</label>
                <input
                  type="number"
                  placeholder="e.g. 30 (Optional)"
                  min="1"
                  value={form.timerMinutes}
                  onChange={(e) => { setForm({ ...form, timerMinutes: e.target.value }); setFormError(''); }}
                />
              </div>
            </div>'''
content = content.replace(
    '            </div>\n\n            <div className="modal-actions">',
    form_f + '\n\n            <div className="modal-actions">'
)

# 8. Import FiClock if not there
if 'FiClock' not in content:
    content = content.replace('FiPlus, FiMinus', 'FiPlus, FiMinus, FiClock')
    content = content.replace('FiZap, FiInfo', 'FiZap, FiInfo, FiClock')
    content = content.replace('FiAlertTriangle, FiZap', 'FiAlertTriangle, FiZap, FiClock')
    content = content.replace('FiRefreshCw, FiInfo', 'FiRefreshCw, FiInfo, FiClock')
    # fallback
    if 'FiClock' not in content:
        content = content.replace('FiPlus,', 'FiPlus, FiClock,')

with open('client/src/pages/Appliances.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done modifying Appliances.jsx')
