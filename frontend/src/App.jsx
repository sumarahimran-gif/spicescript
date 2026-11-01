import { useCallback, useEffect, useState } from "react";
import { api, getToken, setToken, setUnauthorizedHandler } from "./api.js";
import LoginPage from "./components/LoginPage.jsx";
import TopBar from "./components/TopBar.jsx";
import Workspace from "./components/Workspace.jsx";
import LogsPage from "./components/LogsPage.jsx";
import "./styles/app.css";

export default function App() {
  const [user, setUser] = useState(null);
  const [booting, setBooting] = useState(Boolean(getToken()));
  const [view, setView] = useState("workspace");

  const dropSession = useCallback(() => {
    setToken(null);
    setUser(null);
    setView("workspace");
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(dropSession);
  }, [dropSession]);

  // Restore the session if there is a saved token.
  useEffect(() => {
    if (!getToken()) return;
    api
      .me()
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setBooting(false));
  }, []);

  const handleAuth = ({ token, user: signedIn }) => {
    setToken(token);
    setUser(signedIn);
  };

  const signOut = async () => {
    try {
      await api.logout();
    } catch {
      /* the session is dropped locally either way */
    }
    dropSession();
  };

  if (booting) return <div className="boot" role="status">Loading…</div>;
  if (!user) return <LoginPage onAuth={handleAuth} />;

  return (
    <div className="app">
      <TopBar user={user} view={view} onView={setView} onSignOut={signOut} />
      <main className="app__main">
        {/* Stays mounted so code and results survive a visit to the log page. */}
        <Workspace hidden={view !== "workspace"} />
        {view === "logs" && <LogsPage user={user} />}
      </main>
    </div>
  );
}
