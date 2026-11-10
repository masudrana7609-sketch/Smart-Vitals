import { useState, type FormEvent } from "react";
import { login } from "../api";
import { useAuth } from "../auth";

export function Login() {
  const { signIn } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      signIn(await login(username.trim(), password));
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : "Could not log in");
    } finally {
      setBusy(false);
      setPassword("");
    }
  }

  return (
    <main className="login">
      <form className="panel login-form" onSubmit={submit} aria-labelledby="login-heading">
        <h1 id="login-heading">Smart Vitals</h1>
        <p className="muted">Clinician sign-in</p>
        <label>
          Clinician ID
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required />
        </label>
        <label>
          Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password" required />
        </label>
        <button type="submit" className="button" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <p className="muted small">Prototype with simulated data only. Not a medical device.</p>
      </form>
    </main>
  );
}
