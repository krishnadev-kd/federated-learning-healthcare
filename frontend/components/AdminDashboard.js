import React, { useEffect, useRef, useState } from "react";
import PerformanceChart from "./PerformanceChart";
import "../App.css"
const BASE_URL = "http://10.115.90.114:5000";

function AdminDashboard({ token }) {
  const [status, setStatus] = useState({});
  const [numRounds, setNumRounds] = useState(10);
  const [clientsPerRound, setClientsPerRound] = useState(2);
  const intervalRef = useRef(null);

  const fetchStatus = async () => {
    const res = await fetch(`${BASE_URL}/training-status`);
    const data = await res.json();
    setStatus(data);
  };

  useEffect(() => {
    fetchStatus();
    intervalRef.current = setInterval(fetchStatus, 3000);
    return () => clearInterval(intervalRef.current);
  }, []);

  const handleStartTraining = async () => {
    await fetch(`${BASE_URL}/start-training`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-access-token": token,
      },
      body: JSON.stringify({
        total_rounds: numRounds,
        clients_per_round: clientsPerRound,
      }),
    });
  };

  const chartData =
    status.accuracy_history?.map((acc, i) => ({
      round: i + 1,
      accuracy: acc,
      loss: status.loss_history?.[i] || 0,
    })) || [];

  return (
    <>
      <div className="card">
        <h2>Admin Controls</h2>
        <input type="number" value={numRounds} onChange={e => setNumRounds(e.target.value)} />
        <input type="number" value={clientsPerRound} onChange={e => setClientsPerRound(e.target.value)} />
        <button onClick={handleStartTraining}>Start Training</button>
      </div>

      <div className="card">
        <h2>Training Performance</h2>
        <PerformanceChart data={chartData} />
      </div>
    </>
  );
}

export default AdminDashboard;
