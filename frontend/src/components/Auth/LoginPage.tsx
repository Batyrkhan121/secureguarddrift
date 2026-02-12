import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const login = useAuthStore((s) => s.login);
  const navigate = useNavigate();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      navigate("/");
    } catch {
      setError("Invalid email or password");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-[#1a1a2e] flex items-center justify-center">
      <form onSubmit={handleSubmit} data-testid="login-form" className="bg-[#16213e] border border-[#0f3460] rounded-xl p-8 w-[340px]">
        <h2 className="text-xl font-bold text-center mb-5">SecureGuard Drift</h2>
        <input
          type="email"
          placeholder="Email"
          data-testid="login-email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full p-2.5 mb-2.5 bg-[#0f3460] text-gray-200 border border-[#0f3460] rounded text-sm"
        />
        <input
          type="password"
          placeholder="Password"
          data-testid="login-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full p-2.5 mb-2.5 bg-[#0f3460] text-gray-200 border border-[#0f3460] rounded text-sm"
        />
        {error && <div data-testid="login-error" className="text-critical text-sm text-center mb-2">{error}</div>}
        <button
          type="submit"
          disabled={loading}
          data-testid="login-submit"
          className="w-full p-2.5 bg-[#0f3460] text-gray-200 border-none rounded text-sm cursor-pointer hover:bg-[#1a4a8a] disabled:opacity-50"
        >
          {loading ? "Logging in..." : "Login"}
        </button>
      </form>
    </div>
  );
}
