import React, { useState, useEffect } from 'react';
import axios from 'axios';

const BASE_URL = process.env.REACT_APP_BASE_URL;

const SecurityMonitor = ({ token }) => {
  const [logs, setLogs] = useState([]);

  useEffect(() => {
    const fetchLogs = async () => {
      try {
        const response = await axios.get(`${BASE_URL}/admin/detailed-logs`, {
          headers: { 'x-access-token': token }
        });
        setLogs(response.data.reverse());
      } catch (error) {
        console.error("Error fetching detailed logs:", error);
      }
    };
    fetchLogs();
    const interval = setInterval(fetchLogs, 2000);
    return () => clearInterval(interval);
  }, [token]);

  return (
    <div className="security-monitor">
      <div className="card-header">
         <h2>🛡️ Security Aggregation Monitor</h2>
      </div>

      {logs.length === 0 ? (
        <p style={{textAlign:'center', padding:'40px', color:'#888'}}>Waiting for training data...</p>
      ) : (
        <div>
          {logs.map((roundLog, index) => (
            <div key={index} className="round-card">
              
              {/* Round Header */}
              <div className="round-header">
                <h3>Round {roundLog.round}</h3>
                <span className="timestamp">{roundLog.timestamp}</span>
              </div>

              {/* Metrics Bar */}
              <div className="metrics-row">
                <div className="metric-item">
                  <span className="label">🌟 Best Score</span>
                  <span className="value green">{roundLog.best_score}%</span>
                </div>
                <div className="metric-item">
                  <span className="label">🛡️ Threshold</span>
                  <span className="value yellow">{roundLog.threshold}%</span>
                </div>
                <div className="metric-item rule-item">
                  <span className="label">Security Rule</span>
                  <span className="value small">Must be within 15% of Best</span>
                </div>
              </div>

              {/* Table */}
              <table className="audit-table">
                <thead>
                  <tr>
                    <th>Client ID</th>
                    <th>Distance</th>
                    <th>Accuracy</th>
                    <th>Status</th>
                    <th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {roundLog.clients.map((client, cIndex) => (
                    <tr key={cIndex} className={client.status === "ACCEPTED" ? "row-accepted" : "row-rejected"}>
                      <td className="font-mono"><strong>{client.client_id}</strong></td>
                      <td className="font-mono">{client.distance}</td>
                      <td className="font-mono">
                        {client.accuracy}%
                        {client.accuracy < roundLog.threshold && <span className="alert-icon">📉</span>}
                      </td>
                      <td>
                        <span className={`status-badge ${client.status === "ACCEPTED" ? "accepted" : "rejected"}`}>
                          {client.status}
                        </span>
                      </td>
                      <td className="reason-cell">
                        {client.reason}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default SecurityMonitor;