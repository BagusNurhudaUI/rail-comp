/* Klien API tunggal. Semua panggilan lewat sini supaya penanganan token,
   error, dan sesi kedaluwarsa hanya ada di satu tempat. */

const TOKEN_KEY = "rct_token";
const USER_KEY = "rct_user";

export const session = {
  get token() {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  get user() {
    try {
      return JSON.parse(localStorage.getItem(USER_KEY) || "null");
    } catch {
      return null;
    }
  },
  save(token, user) {
    try {
      localStorage.setItem(TOKEN_KEY, token);
      localStorage.setItem(USER_KEY, JSON.stringify(user));
    } catch {
      /* mode privat: sesi hanya bertahan selama tab hidup */
    }
  },
  clear() {
    try {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
    } catch {
      /* diabaikan */
    }
  },
};

/** Dipanggil ketika server menolak token; disetel oleh AuthProvider. */
let onUnauthorized = () => {};

export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler;
}

// Basis URL API. Diisi VITE_API_BASE_URL saat frontend dan backend beda origin
// (mis. frontend di Vercel, backend di Cloud Run). Kosong = same-origin: cocok
// untuk dev lokal (proxy vite) maupun kalau backend menyajikan frontend.
const API_BASE = import.meta.env.VITE_API_BASE_URL || window.location.origin;

function buildUrl(path, params) {
  const url = new URL(path, API_BASE);

  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, value);
    }
  });

  return url.toString();
}

async function request(path, { method = "GET", params, body, raw = false } = {}) {
  const headers = {};
  const token = session.token;

  if (token) headers.Authorization = `Bearer ${token}`;

  let payload;

  if (body instanceof FormData) {
    payload = body;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const response = await fetch(buildUrl(path, params), {
    method,
    headers,
    body: payload,
  });

  if (response.status === 401) {
    session.clear();
    onUnauthorized();
    throw new Error("Sesi berakhir, silakan masuk kembali");
  }

  if (!response.ok) {
    let detail = `Permintaan gagal (${response.status})`;

    try {
      const data = await response.json();

      if (typeof data.detail === "string") detail = data.detail;
      else if (Array.isArray(data.detail)) detail = data.detail[0]?.msg || detail;
    } catch {
      /* biarkan pesan bawaan */
    }

    throw new Error(detail);
  }

  return raw ? response : response.json();
}

export const api = {
  login: (email, password) =>
    request("/api/auth/login", { method: "POST", body: { email, password } }),
  me: () => request("/api/auth/me"),
  changePassword: (current_password, new_password) =>
    request("/api/auth/change-password", {
      method: "POST",
      body: { current_password, new_password },
    }),

  summary: (params) => request("/api/dashboard/summary", { params }),
  charts: (params) => request("/api/dashboard/charts", { params }),
  alerts: () => request("/api/dashboard/alerts"),
  activity: (params) => request("/api/dashboard/activity", { params }),
  filters: () => request("/api/dashboard/filters"),

  locomotives: (params) => request("/api/locomotives", { params }),
  locomotive: (key) => request(`/api/locomotives/${encodeURIComponent(key)}`),

  components: (params) => request("/api/components", { params }),
  componentHistory: (code) => request("/api/components/history", { params: { code } }),
  exportComponents: (params) =>
    request("/api/components/export", { params, raw: true }),

  maintenance: (params) => request("/api/maintenance", { params }),
  maintenanceDetail: (id) => request(`/api/maintenance/${id}`),

  masterSummary: () => request("/api/master/summary"),
  masterFilters: () => request("/api/master/filters"),
  masterLocomotives: (params) => request("/api/master/locomotives", { params }),
  masterLocomotive: (equipment) =>
    request(`/api/master/locomotives/${encodeURIComponent(equipment)}`),
  masterComponents: (params) => request("/api/master/components", { params }),
  masterComponent: (id) => request(`/api/master/components/${id}`),
  masterFiles: () => request("/api/master/files"),
  masterImport: (file_name) =>
    request("/api/master/import", {
      method: "POST",
      body: { file_name: file_name || null },
    }),
  masterUpload: (target, file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/api/master/upload", { method: "POST", params: { target }, body: form });
  },

  importHistory: () => request("/api/imports/history"),
  importSources: () => request("/api/imports/sources"),
  reingest: (file_name) =>
    request("/api/imports/reingest", { method: "POST", body: { file_name } }),
  flush: (body) => request("/api/imports/flush", { method: "POST", body }),
  upload: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/api/imports/upload", { method: "POST", body: form });
  },

  availability: () => request("/api/reports/availability"),
  anomalies: () => request("/api/reports/anomalies"),
  topComponents: (params) => request("/api/reports/top-components", { params }),

  users: () => request("/api/users"),
  createUser: (body) => request("/api/users", { method: "POST", body }),
  updateUser: (id, body) => request(`/api/users/${id}`, { method: "PATCH", body }),
  deleteUser: (id) => request(`/api/users/${id}`, { method: "DELETE" }),

  health: () => request("/api/health"),
};
