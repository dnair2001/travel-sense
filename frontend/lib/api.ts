import type { User } from "firebase/auth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type Method = "GET" | "POST" | "DELETE";

export async function requestJson<T>(
  path: string,
  user: User | null,
  options?: { method?: Method; payload?: unknown },
): Promise<T> {
  if (!user) {
    throw new Error("You need to sign in first.");
  }
  const { payload } = options ?? {};
  const method = options?.method ?? (payload !== undefined ? "POST" : "GET");
  const token = await user.getIdToken();

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(payload !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: payload !== undefined ? JSON.stringify(payload) : undefined,
  });

  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, "Request failed."));
  }

  return (await response.json()) as T;
}

export async function getApiErrorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string | { msg?: string }[] };
    if (typeof body.detail === "string") {
      return body.detail;
    }
    if (Array.isArray(body.detail)) {
      return body.detail.map((item) => item.msg).filter(Boolean).join(" ") || fallback;
    }
  } catch {
    return fallback;
  }
  return fallback;
}
