const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const TOKEN_KEY = "rt_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string) {
  window.localStorage.setItem(TOKEN_KEY, token);
}
export function clearToken() {
  window.localStorage.removeItem(TOKEN_KEY);
}

export interface User {
  id: number;
  email: string;
  name: string | null;
  is_admin?: boolean;
}

export interface AdminStats {
  users: number;
  races: number;
  runners: number;
  predictions: number;
}

export interface AdminUser {
  id: number;
  email: string;
  name: string | null;
  created_at: string | null;
  last_login_at: string | null;
  races_owned: number;
  memberships: number;
}

export interface AdminRace {
  id: number;
  name: string;
  owner_email: string | null;
  start_time: string | null;
  total_distance_m: number | null;
  total_ascent_m: number | null;
  runners: number;
  aid_stations: number;
  created_at: string | null;
}

export interface Race {
  id: number;
  name: string;
  start_time: string | null;
  total_distance_m: number | null;
  total_ascent_m: number | null;
  owner_id: number | null;
}

export interface ProfilePoint {
  km: number;
  ele: number;
}

export interface RaceProfile {
  race_id: number;
  total_distance_m: number;
  total_ascent_m: number;
  points: ProfilePoint[];
}

export interface Runner {
  id: number;
  race_id: number;
  name: string;
  target_time_s: number;
  feel: number;
  livetrack_url: string | null;
}

export interface AidStation {
  id?: number;
  name: string;
  distance_m: number;
  expected_stop_s: number;
}

export interface Member {
  user_id: number;
  email: string;
  role: string;
  login_link?: string | null;
}

export interface Percentiles {
  p10: number;
  p50: number;
  p90: number;
}

export interface Prediction {
  runner_id: number;
  created_at: string;
  finish: Percentiles;
  per_km: (Percentiles & { km: number })[];
  aid_stations: (Percentiles & { name: string; distance_m: number })[];
  runner_position_m: number | null;
}

export interface SyncedActivity {
  strava_id: string;
  name: string;
  start_date: string;
  distance_m: number;
  moving_time_s: number;
  elevation_gain_m: number;
  used_for_calibration: boolean;
}

class AuthError extends Error {}

async function authFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const headers = new Headers(options.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const resp = await fetch(`${API}${path}`, { ...options, headers });
  if (resp.status === 401) {
    clearToken();
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
    throw new AuthError("Nepřihlášeno");
  }
  return resp;
}

async function json<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`${resp.status}: ${body}`);
  }
  return resp.json();
}

function jsonHeaders(): HeadersInit {
  return { "Content-Type": "application/json" };
}

export const api = {
  // --- Auth ---
  requestMagicLink: (email: string) =>
    fetch(`${API}/auth/request`, { method: "POST", headers: jsonHeaders(), body: JSON.stringify({ email }) }).then(
      (r) => json<{ sent: boolean; dev_magic_link?: string }>(r)
    ),
  verifyMagicLink: (token: string) =>
    fetch(`${API}/auth/verify`, { method: "POST", headers: jsonHeaders(), body: JSON.stringify({ token }) }).then(
      (r) => json<{ access_token: string; user: User }>(r)
    ),
  me: () => authFetch(`/auth/me`).then((r) => json<User>(r)),

  // --- Admin ---
  adminStats: () => authFetch(`/admin/stats`).then((r) => json<AdminStats>(r)),
  adminUsers: () => authFetch(`/admin/users`).then((r) => json<AdminUser[]>(r)),
  adminRaces: () => authFetch(`/admin/races`).then((r) => json<AdminRace[]>(r)),

  // --- Races ---
  listRaces: () => authFetch(`/races`).then((r) => json<Race[]>(r)),
  createRace: (name: string, startTime: string | null) =>
    authFetch(`/races`, { method: "POST", headers: jsonHeaders(), body: JSON.stringify({ name, start_time: startTime }) }).then(
      (r) => json<Race>(r)
    ),
  updateRace: (raceId: number, changes: { name?: string; start_time?: string | null }) =>
    authFetch(`/races/${raceId}`, { method: "PATCH", headers: jsonHeaders(), body: JSON.stringify(changes) }).then((r) => json<Race>(r)),
  deleteRace: (raceId: number) => authFetch(`/races/${raceId}`, { method: "DELETE" }).then((r) => json<unknown>(r).catch(() => null)),
  uploadGpx: (raceId: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return authFetch(`/races/${raceId}/gpx`, { method: "POST", body: form }).then((r) => json<Race>(r));
  },
  getProfile: (raceId: number) => authFetch(`/races/${raceId}/profile`).then((r) => json<RaceProfile>(r)),

  // --- Sharing ---
  listMembers: (raceId: number) => authFetch(`/races/${raceId}/members`).then((r) => json<Member[]>(r)),
  inviteMember: (raceId: number, email: string) =>
    authFetch(`/races/${raceId}/members`, { method: "POST", headers: jsonHeaders(), body: JSON.stringify({ email }) }).then(
      (r) => json<Member>(r)
    ),
  removeMember: (raceId: number, userId: number) =>
    authFetch(`/races/${raceId}/members/${userId}`, { method: "DELETE" }).then(() => null),

  // --- Runners ---
  listRunners: (raceId: number) => authFetch(`/races/${raceId}/runners`).then((r) => json<Runner[]>(r)),
  createRunner: (raceId: number, runner: { name: string; target_time_s: number; feel: number; livetrack_url: string | null }) =>
    authFetch(`/races/${raceId}/runners`, { method: "POST", headers: jsonHeaders(), body: JSON.stringify(runner) }).then((r) => json<Runner>(r)),
  updateRunner: (runnerId: number, changes: Partial<Pick<Runner, "name" | "target_time_s" | "feel" | "livetrack_url">>) =>
    authFetch(`/runners/${runnerId}`, { method: "PATCH", headers: jsonHeaders(), body: JSON.stringify(changes) }).then((r) => json<Runner>(r)),
  listAidStations: (raceId: number) => authFetch(`/races/${raceId}/aid-stations`).then((r) => json<AidStation[]>(r)),
  setAidStations: (raceId: number, stations: AidStation[]) =>
    authFetch(`/races/${raceId}/aid-stations`, {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify(stations.map(({ name, distance_m, expected_stop_s }) => ({ name, distance_m, expected_stop_s }))),
    }).then((r) => json<AidStation[]>(r)),
  predict: (runnerId: number) => authFetch(`/runners/${runnerId}/predict`, { method: "POST" }).then((r) => json<Prediction>(r)),
  latestPrediction: (runnerId: number) => authFetch(`/runners/${runnerId}/prediction/latest`).then((r) => json<Prediction>(r)),
  syncStravaHistory: (runnerId: number) =>
    authFetch(`/strava/runners/${runnerId}/sync`, { method: "POST" }).then((r) =>
      json<{ activities_used: number; calibration: Record<string, number> }>(r)
    ),
  listSyncedActivities: (runnerId: number) => authFetch(`/strava/runners/${runnerId}/activities`).then((r) => json<SyncedActivity[]>(r)),
  connectStrava: (runnerId: number) =>
    authFetch(`/strava/connect?runner_id=${runnerId}`).then((r) => json<{ authorize_url: string }>(r)),
};

export function wsUrl(runnerId: number): string {
  return `${API.replace(/^http/, "ws")}/ws/runners/${runnerId}`;
}

export function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}:${m.toString().padStart(2, "0")}`;
}

export function formatDurationLong(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}
