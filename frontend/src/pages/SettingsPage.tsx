import { useState } from "react";
import { useWhitelist } from "@/api/hooks";
import { addWhitelist, removeWhitelist } from "@/api/client";

export default function SettingsPage() {
  const { data: whitelist = [], refetch } = useWhitelist();
  const [source, setSource] = useState("");
  const [dest, setDest] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!source || !dest) return;
    setError("");
    try {
      await addWhitelist(source, dest, reason);
      setSource("");
      setDest("");
      setReason("");
      refetch();
    } catch {
      setError("Failed to add whitelist entry");
    }
  }

  async function handleRemove(src: string, dst: string) {
    setError("");
    try {
      await removeWhitelist(src, dst);
      refetch();
    } catch {
      setError("Failed to remove whitelist entry");
    }
  }

  return (
    <div className="min-h-screen bg-[#1a1a2e] text-gray-200 p-8">
      <h1 className="text-2xl font-bold mb-6">Settings</h1>

      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-3">Integrations</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-3xl">
          {["Slack", "Jira", "SIEM", "GitOps"].map((name) => (
            <div key={name} className="bg-[#16213e] border border-[#0f3460] rounded-lg p-4">
              <div className="flex justify-between items-center">
                <span className="font-semibold">{name}</span>
                <button className="bg-[#0f3460] text-gray-200 rounded px-3 py-1 text-sm hover:bg-[#1a4a8a]">Test Connection</button>
              </div>
              <p className="text-xs text-gray-500 mt-1">Configure in environment variables</p>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-lg font-semibold mb-3">Whitelist</h2>
        {error && <div className="text-critical text-sm mb-2">{error}</div>}
        <form onSubmit={handleAdd} className="flex gap-2 mb-4 max-w-3xl">
          <input value={source} onChange={(e) => setSource(e.target.value)} placeholder="Source" className="bg-[#0f3460] text-gray-200 border border-[#0f3460] rounded px-3 py-1.5 text-sm flex-1" />
          <input value={dest} onChange={(e) => setDest(e.target.value)} placeholder="Destination" className="bg-[#0f3460] text-gray-200 border border-[#0f3460] rounded px-3 py-1.5 text-sm flex-1" />
          <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason" className="bg-[#0f3460] text-gray-200 border border-[#0f3460] rounded px-3 py-1.5 text-sm flex-1" />
          <button type="submit" className="bg-[#0f3460] text-gray-200 rounded px-4 py-1.5 text-sm hover:bg-[#1a4a8a]">Add</button>
        </form>
        {whitelist.length === 0 ? (
          <p className="text-gray-500 text-sm">No whitelist entries</p>
        ) : (
          <div className="max-w-3xl space-y-1.5">
            {whitelist.map((w) => (
              <div key={w.id} className="bg-[#16213e] border border-[#0f3460] rounded-lg px-4 py-2 flex justify-between items-center">
                <div>
                  <span className="font-mono text-sm">{w.source} → {w.destination}</span>
                  {w.reason && <span className="text-xs text-gray-500 ml-2">({w.reason})</span>}
                </div>
                <button onClick={() => handleRemove(w.source, w.destination)} className="text-critical text-sm hover:underline">Remove</button>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
