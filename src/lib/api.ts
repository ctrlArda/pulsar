import { env } from "./config";
import type { DashboardState, OperatingMode, WebhookPreview } from "../types/helioguard";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${env.apiBaseUrl}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    throw new Error(`API ${response.status}: ${await response.text()}`);
  }

  return (await response.json()) as T;
}

export function getDashboardState(): Promise<DashboardState> {
  return request<DashboardState>("/api/state");
}

export function setOperatingMode(mode: OperatingMode): Promise<DashboardState> {
  return request<DashboardState>(`/api/mode/${mode}`, { method: "POST" });
}

export function getTerminalStreamUrl(): string {
  return `${env.apiBaseUrl}/api/stream/terminal`;
}

export function getWebhookPreview(): Promise<WebhookPreview> {
  return request<WebhookPreview>("/api/webhooks/preview");
}

export function getLiveFlights(): Promise<{ flights: any[] }> {
  return request<{ flights: any[] }>("/api/flights/live");
}
