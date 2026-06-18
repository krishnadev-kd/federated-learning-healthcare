import React, { useEffect, useState } from "react";

const BASE_URL = "http://10.115.90.114:5000";

function PredictionComponent({ token }) {
  const [files, setFiles] = useState([]);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [versions, setVersions] = useState([]);
  const [selectedVersion, setSelectedVersion] = useState("");

  const handleFileChange = (e) => {
    setFiles([...e.target.files]);
  };

  const handlePredict = async () => {
    if (files.length === 0) return;
    setLoading(true);
    const output = [];

    for (const file of files) {
      const formData = new FormData();
      formData.append("image", file);
      formData.append("version", selectedVersion);

      const res = await fetch(`${BASE_URL}/predict`, {
        method: "POST",
        headers: { "x-access-token": token },
        body: formData,
      });

      const data = await res.json();

      output.push({
        name: file.name,
        prediction: data.prediction,
        confidence: data.confidence,
        model_used: data.model_used,
        imageUrl: URL.createObjectURL(file),
        heatmap: data.gradcam || null,
      });
    }

    setResults(output);
    setLoading(false);
  };

  const predictionCounts = results.reduce((acc, p) => {
    acc[p.prediction] = (acc[p.prediction] || 0) + 1;
    return acc;
  }, {});

  // Optional: fetch model versions from backend
  useEffect(() => {
    const fetchVersions = async () => {
      try {
        const res = await fetch(`${BASE_URL}/predict`, {
          method: "POST",
          headers: { "x-access-token": token },
          body: new FormData(),
        });
        const data = await res.json();
        setVersions(data.model || []);
      } catch (err) {
        console.error("Error fetching model versions:", err);
      }
    };
    fetchVersions();
  }, [token]);

  return (
    <div className="prediction-card">
      <h2>🧠 Brain Tumor Detection</h2>
      <div className="controls">
        <div className="file-upload-wrapper">
          <label className="file-upload-btn">
            📂 Choose Images
            <input type="file" multiple onChange={handleFileChange} />
          </label>
          <span className="file-count">{files.length} file(s) selected</span>
        </div>

        <select
          value={selectedVersion}
          onChange={(e) => setSelectedVersion(e.target.value)}
          className="version-select"
        >
          <option value="">Latest</option>
          {versions.map((v) => {
            if (!v.filename) return null;
            const match = v.filename.match(/global_model_(v\d+)_acc_([\d.]+)\.pth$/);
            const version = match ? match[1] : "Unknown";
            const accuracy = match ? match[2] : "N/A";
            return (
              <option key={v.filename} value={v.filename}>
                {version} — Acc: {accuracy}%
              </option>
            );
          })}
        </select>

        <button
          onClick={handlePredict}
          disabled={loading || files.length === 0}
          className="analyze-btn"
        >
          {loading ? "Analyzing..." : "Analyze Images"}
        </button>
      </div>

      {results.length > 0 && (
        <div className="results-container">
          <h3>📊 Summary</h3>
          <div className="counts">
            {Object.entries(predictionCounts).map(([label, count]) => (
              <div key={label} className="count-chip">
                {label}: <span>{count}</span>
              </div>
            ))}
          </div>

          <h3>🩺 Detailed Results</h3>
          <div className="result-grid">
            {results.map((p, idx) => (
              <div key={idx} className="result-card">
                <img src={p.imageUrl} alt={p.name} className="preview" />
                <div className="result-info">
                  <h4>{p.name}</h4>
                  <p>
                    <strong>Prediction:</strong>{" "}
                    <span className={`tag ${p.prediction.toLowerCase().replace(/\s+/g, '-')}`}>
                      {p.prediction}
                    </span>
                  </p>
                  <p className="model">
                    <strong>Model:</strong> {p.model_used}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default PredictionComponent;
