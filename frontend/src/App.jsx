import { useEffect, useState, useCallback } from "react";

const STATUS_COLORS = {
  received: "#94a3b8", // gray — just logged, no verdict yet
  pending: "#f7b500",  // yellow
  success: "#22c55e",  // green
  failed: "#d81e05",   // red
};

/** Small colored pill showing a push's current status. */
function StatusBadge({ status }) {
  const color = STATUS_COLORS[status] || STATUS_COLORS.received;
  return (
    <span
      style={{
        backgroundColor: color,
        color: "#0f172a",
        padding: "2px 10px",
        borderRadius: "999px",
        fontSize: "0.75rem",
        fontWeight: 700,
        textTransform: "uppercase",
      }}
    >
      {status}
    </span>
  );
}

/** One row in the push table. */
function PushRow({ push, onSelect }) {
  return (
    <tr onClick={() => onSelect(push.id)} style={{ cursor: "pointer" }}>
      <td>{push.repo}</td>
      <td>{push.branch}</td>
      <td title={push.commit_sha}>{push.commit_sha.slice(0, 7)}</td>
      <td>{push.commit_message}</td>
      <td>{push.author}</td>
      <td><StatusBadge status={push.status} /></td>
    </tr>
  );
}

/** Detail panel for one selected push, with manual status controls. */
function PushDetail({ pushId, onClose, onStatusChanged }) {
  const [push, setPush] = useState(null);

  const load = useCallback(() => {
    fetch(`/api/pushes/${pushId}`)
      .then((r) => r.json())
      .then(setPush);
  }, [pushId]);

  useEffect(() => {
    load();
  }, [load]);

  const setStatus = async (status) => {
    await fetch(`/api/pushes/${pushId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    load();
    onStatusChanged();
  };

  if (!push) return null;

  return (
    <div className="detail-panel">
      <button className="close-btn" onClick={onClose}>× close</button>
      <h2>{push.repo}</h2>
      <p><strong>Branch:</strong> {push.branch}</p>
      <p><strong>Commit:</strong> <code>{push.commit_sha}</code></p>
      <p><strong>Message:</strong> {push.commit_message}</p>
      <p><strong>Author:</strong> {push.author}</p>
      <p><strong>Pushed at:</strong> {push.pushed_at}</p>
      <p><strong>Received at:</strong> {push.received_at}</p>
      <p><strong>Status:</strong> <StatusBadge status={push.status} /></p>
      <div className="status-buttons">
        {["pending", "success", "failed"].map((s) => (
          <button key={s} onClick={() => setStatus(s)}>{s}</button>
        ))}
      </div>
    </div>
  );
}

export default function App() {
  const [pushes, setPushes] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [repoFilter, setRepoFilter] = useState("");
  const [branchFilter, setBranchFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const loadPushes = useCallback(() => {
    const params = new URLSearchParams();
    if (repoFilter) params.set("repo", repoFilter);
    if (branchFilter) params.set("branch", branchFilter);
    if (statusFilter) params.set("status", statusFilter);
    fetch(`/api/pushes?${params.toString()}`)
      .then((r) => r.json())
      .then(setPushes);
  }, [repoFilter, branchFilter, statusFilter]);

  useEffect(() => {
    loadPushes();
  }, [loadPushes]);

  return (
    <div className="app">
      <header>
        <h1>Push Dashboard</h1>
        <button onClick={loadPushes}>↻ Refresh</button>
      </header>

      <div className="filters">
        <input
          placeholder="Filter by repo…"
          value={repoFilter}
          onChange={(e) => setRepoFilter(e.target.value)}
        />
        <input
          placeholder="Filter by branch…"
          value={branchFilter}
          onChange={(e) => setBranchFilter(e.target.value)}
        />
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          <option value="received">received</option>
          <option value="pending">pending</option>
          <option value="success">success</option>
          <option value="failed">failed</option>
        </select>
      </div>

      <table>
        <thead>
          <tr>
            <th>Repo</th>
            <th>Branch</th>
            <th>Commit</th>
            <th>Message</th>
            <th>Author</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {pushes.length === 0 ? (
            <tr>
              <td colSpan={6} className="empty">No pushes yet — waiting for a webhook.</td>
            </tr>
          ) : (
            pushes.map((p) => <PushRow key={p.id} push={p} onSelect={setSelectedId} />)
          )}
        </tbody>
      </table>

      {selectedId && (
        <PushDetail
          pushId={selectedId}
          onClose={() => setSelectedId(null)}
          onStatusChanged={loadPushes}
        />
      )}
    </div>
  );
}
