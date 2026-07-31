"use client";

import { useAuth } from "../lib/AuthContext";

export function AppHeader() {
  const { user, signOut } = useAuth();

  return (
    <header className="app-header">
      <p className="brand">
        Travel<span className="title-accent">Sense</span>
      </p>
      <div className="account-bar">
        <span>{user?.email ?? user?.displayName ?? "Signed in"}</span>
        <button className="secondary-button" onClick={() => void signOut()} type="button">
          Sign out
        </button>
      </div>
    </header>
  );
}
