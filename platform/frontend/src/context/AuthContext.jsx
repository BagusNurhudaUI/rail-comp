import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, session, setUnauthorizedHandler } from "../lib/api";

const AuthContext = createContext(null);

const ROLE_RANK = { viewer: 1, supervisor: 2, admin: 3 };

export function AuthProvider({ children }) {
  const [user, setUser] = useState(session.user);
  const [ready, setReady] = useState(!session.token);

  const logout = useCallback(() => {
    session.clear();
    setUser(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null));
  }, []);

  // Token bisa saja sudah kedaluwarsa sejak kunjungan terakhir, jadi
  // profil selalu diverifikasi ulang ke server saat aplikasi dibuka.
  useEffect(() => {
    // Nilai awal `ready` sudah `!session.token`, jadi tidak ada yang perlu
    // diubah ketika memang tidak ada token.
    if (!session.token) return undefined;

    let active = true;

    api
      .me()
      .then((profile) => {
        if (!active) return;
        session.save(session.token, profile);
        setUser(profile);
      })
      .catch(() => active && setUser(null))
      .finally(() => active && setReady(true));

    return () => {
      active = false;
    };
  }, []);

  const login = useCallback(async (email, password) => {
    const data = await api.login(email, password);
    session.save(data.access_token, data.user);
    setUser(data.user);
    return data.user;
  }, []);

  const value = useMemo(
    () => ({
      user,
      ready,
      login,
      logout,
      can: (minimum) => ROLE_RANK[user?.role] >= ROLE_RANK[minimum],
    }),
    [user, ready, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) throw new Error("useAuth harus dipakai di dalam AuthProvider");

  return context;
}
