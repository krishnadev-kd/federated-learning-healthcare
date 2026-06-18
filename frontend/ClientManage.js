import React, { useState, useEffect } from "react";
import './App.css'

const BASE_URL = process.env.REACT_APP_BASE_URL;
export default function ClientManagementPanel({ token }) {
  const [users, setUsers] = useState([]);

  const fetchUsers = async () => {
    try {
      const response = await fetch(`${BASE_URL}/admin/users`, {
        headers: { 'x-access-token': token },
      });
      if (response.ok) {
        setUsers(await response.json());
      }
    } catch (e) { 
      console.error("Failed to fetch users", e); 
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleStatusChange = async (username, status) => {
    try {
      const response = await fetch(`${BASE_URL}/admin/authorize-user`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json', 
          'x-access-token': token 
        },
        body: JSON.stringify({ username, status }),
      });
      if (response.ok) {
        fetchUsers(); // Refresh list
      }
    } catch (e) { 
      console.error(e); 
    }
  };

  const handleDelete = async (username) => {
    if (!window.confirm(`Are you absolutely sure you want to delete ${username}? This cannot be undone.`)) return;

    try {
      const response = await fetch(`${BASE_URL}/admin/delete-user/${username}`, {
        method: 'DELETE',
        headers: { 'x-access-token': token },
      });
      if (response.ok) {
        fetchUsers(); // Refresh list
      }
    } catch (e) { 
      console.error(e); 
    }
  };

  // ... (keep the existing state and functions) ...

  return (
    <div className="card client-management-card">
      <h2>👥 Client Node Management</h2>
      <p>Manage all registered hospitals in the federated network.</p>
      
      <table className="audit-table">
        <thead>
          <tr>
            <th>Username</th>
            <th>Email</th>
            <th>Current Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {users.length === 0 ? (
            <tr><td colSpan="4" style={{ textAlign: 'center', padding: '20px' }}>No hospital nodes registered yet.</td></tr>
          ) : (
            users.map(user => (
              <tr key={user.username}>
                <td><strong>{user.username}</strong></td>
                <td>{user.email}</td>
                <td>
                  {/* Using the dynamic status text as the class name! */}
                  <span className={`status-badge ${user.status}`}>
                    {user.status}
                  </span>
                </td>
                <td>
                  {user.status === 'APPROVED' ? (
                    <button onClick={() => handleStatusChange(user.username, 'UNAUTHORIZED')} className="action-btn btn-revoke">
                      Revoke Access
                    </button>
                  ) : (
                    <button onClick={() => handleStatusChange(user.username, 'APPROVED')} className="action-btn btn-authorize">
                      Authorize
                    </button>
                  )}
                  
                  <button onClick={() => handleDelete(user.username)} className="action-btn btn-delete">
                    Delete Node
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}