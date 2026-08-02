"use client";

import { useAuth } from "../lib/AuthContext";
import { AppHeader } from "./AppHeader";
import { SignInScreen } from "./SignInScreen";
import { TripPlanner } from "./TripPlanner";

export function AppShell() {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="sign-in-loading">Loading…</div>;
  }

  if (!user) {
    return <SignInScreen />;
  }

  return (
    <>
      <AppHeader />
      <TripPlanner />
    </>
  );
}
