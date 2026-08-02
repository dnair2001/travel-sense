"use client";

import { useAuth } from "../lib/AuthContext";

export function SignInScreen() {
  const { signIn } = useAuth();

  return (
    <div className="sign-in-page">
      <div className="sign-in-blob one" />
      <div className="sign-in-blob two" />
      <div className="sign-in-blob three" />

      <div className="sign-in-card">
        <p className="eyebrow">Personal RAG travel planning</p>
        <h1>
          Travel<span className="title-accent">Sense</span>
        </h1>
        <p className="lede">
          Sign in to plan trips grounded in your own sources — blog posts, YouTube videos, and
          saved notes for any destination.
        </p>
        <div className="sign-in-features">
          <span>Any destination</span>
          <span>Blog & YouTube sources</span>
          <span>Private to your account</span>
        </div>
        <button className="primary-button" onClick={() => void signIn()} type="button">
          Sign in with Google
        </button>
      </div>
    </div>
  );
}
