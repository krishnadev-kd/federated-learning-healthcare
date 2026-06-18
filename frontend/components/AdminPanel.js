import React, { useState } from 'react';

const AdminPanel = () => {
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('admin_password'); // Default for demo
  const [token, setToken] = useState(null);
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState('');

  // 1. Handle Login
  const handleLogin = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch('http://localhost:5000/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      const data = await res.json();
      
      if (data.token) {
        if (data.role !== 'ADMIN') {
          setError("Login successful, but you are not an ADMIN.");
        } else {
          setToken(data.token);
          setError('');
          fetchLogs(data.token); // Load logs immediately
        }
      } else {
        setError('Invalid credentials');
      }
    } catch (err) {
      setError('Server error. Is Flask running?');
    }
  };

  // 2. Fetch Blockchain Data (Securely)
  const fetchLogs = async (authToken) => {
    try {
      const res = await fetch('http://localhost:5000/admin/audit-log', {
        method: 'GET',
        headers: {
          'x-access-token': authToken // <--- CRITICAL: Sending the key
        }
      });
      if (res.status === 403) {
         setError("Access Denied.");
         return;
      }
      const data = await res.json();
      setLogs(data);
    } catch (err) {
      console.error(err);
    }
  };

  // 3. Render
  if (!token) {
    return (
      <div style={styles.container}>
        <h2>🛡️ Admin Login</h2>
        <form onSubmit={handleLogin} style={styles.form}>
          <input 
            style={styles.input}
            type="text" 
            placeholder="Username" 
            value={username} 
            onChange={e => setUsername(e.target.value)} 
          />
          <input 
            style={styles.input}
            type="password" 
            placeholder="Password" 
            value={password} 
            onChange={e => setPassword(e.target.value)} 
          />
          <button style={styles.button} type="submit">Access Secure Ledger</button>
        </form>
        {error && <p style={{color: 'red'}}>{error}</p>}
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h2>⛓️ Immutable Audit Ledger</h2>
        <button style={styles.refreshBtn} onClick={() => fetchLogs(token)}>🔄 Refresh Chain</button>
      </div>

      <table style={styles.table}>
        <thead>
          <tr style={styles.tr}>
            <th style={styles.th}>Block #</th>
            <th style={styles.th}>Time</th>
            <th style={styles.th}>Client ID</th>
            <th style={styles.th}>Status</th>
            <th style={styles.th}>Digital Signature (Hash)</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log) => (
            <tr key={log.index} style={styles.tr}>
              <td style={styles.td}>{log.index}</td>
              <td style={styles.td}>{log.timestamp}</td>
              <td style={styles.td}><b>{log.client}</b></td>
              <td style={styles.td}>
                <span style={{
                  ...styles.badge,
                  backgroundColor: log.status.includes('REJECTED') ? '#e74c3c' : '#2ecc71'
                }}>
                  {log.status}
                </span>
              </td>
              <td style={styles.td}>
                <code style={styles.code}>{log.short_hash}</code>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p style={{fontSize: '0.8rem', color: '#666'}}>* This ledger is cryptographically linked. Any tampering breaks the chain.</p>
    </div>
  );
};

// Simple inline styles for a professional look
const styles = {
  container: { padding: '20px', fontFamily: 'Arial, sans-serif' },
  form: { display: 'flex', flexDirection: 'column', gap: '10px', maxWidth: '300px' },
  input: { padding: '10px', borderRadius: '5px', border: '1px solid #ccc' },
  button: { padding: '10px', backgroundColor: '#2c3e50', color: 'white', border: 'none', borderRadius: '5px', cursor: 'pointer' },
  refreshBtn: { padding: '8px 15px', backgroundColor: '#3498db', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' },
  table: { width: '100%', borderCollapse: 'collapse', boxShadow: '0 4px 8px rgba(0,0,0,0.1)' },
  th: { backgroundColor: '#2c3e50', color: 'white', padding: '12px', textAlign: 'left' },
  td: { padding: '12px', borderBottom: '1px solid #ddd' },
  tr: { backgroundColor: 'white' },
  badge: { padding: '5px 10px', borderRadius: '15px', color: 'white', fontSize: '0.85rem', fontWeight: 'bold' },
  code: { fontFamily: 'monospace', backgroundColor: '#f4f4f4', padding: '2px 5px', borderRadius: '3px' }
};

export default AdminPanel;