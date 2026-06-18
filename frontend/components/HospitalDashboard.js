import React, { useEffect, useRef, useState } from "react";

const BASE_URL = "http://10.115.90.114:5000";

function HospitalDashboard({ token }) {
  const [connected, setConnected] = useState(false);
  const intervalRef = useRef(null);

  const checkIn = async () => {
    await fetch(`${BASE_URL}/check-in`, {
      method: "POST",
      headers: { "x-access-token": token },
    });
  };

  const connect = () => {
    setConnected(true);
    checkIn();
    intervalRef.current = setInterval(checkIn, 30000);
  };

  useEffect(() => () => clearInterval(intervalRef.current), []);

  return (
    <div className="card">
      <h2>Hospital Node</h2>
      <button onClick={connect} disabled={connected}>
        {connected ? "Connected" : "Connect to Federation"}
      </button>
    </div>
  );
}

export default HospitalDashboard;
