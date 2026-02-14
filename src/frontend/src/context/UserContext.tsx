import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import type { UserData } from '../types/index.ts';

const API_BASE = 'http://localhost:8000';

interface UserContextValue {
  currentUser: UserData | null;
  loading: boolean;
  login: (handle: string) => Promise<UserData | null>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const UserContext = createContext<UserContextValue>({
  currentUser: null,
  loading: true,
  login: async () => null,
  logout: () => {},
  refreshUser: async () => {},
});

export const useUser = () => useContext(UserContext);

export const UserProvider = ({ children }: { children: ReactNode }) => {
  const [currentUser, setCurrentUser] = useState<UserData | null>(null);
  const [loading, setLoading] = useState(true);

  // Restore session from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem('nfh_user');
    if (stored) {
      fetchUser(stored).then(user => {
        setCurrentUser(user);
        setLoading(false);
      });
    } else {
      setLoading(false);
    }
  }, []);

  const fetchUser = async (handle: string): Promise<UserData | null> => {
    try {
      const res = await fetch(`${API_BASE}/users/${encodeURIComponent(handle)}`);
      if (!res.ok) return null;
      return await res.json();
    } catch {
      return null;
    }
  };

  const login = async (handle: string): Promise<UserData | null> => {
    // Try to fetch existing user first
    let user = await fetchUser(handle);

    // Auto-register if not found
    if (!user) {
      try {
        const res = await fetch(`${API_BASE}/users/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username: handle }),
        });
        if (res.ok || res.status === 201) {
          user = await res.json();
        }
      } catch {
        return null;
      }
    }

    if (user) {
      setCurrentUser(user);
      localStorage.setItem('nfh_user', user.username);
    }
    return user;
  };

  const logout = () => {
    setCurrentUser(null);
    localStorage.removeItem('nfh_user');
  };

  const refreshUser = async () => {
    if (!currentUser) return;
    const updated = await fetchUser(currentUser.username);
    if (updated) setCurrentUser(updated);
  };

  return (
    <UserContext.Provider value={{ currentUser, loading, login, logout, refreshUser }}>
      {children}
    </UserContext.Provider>
  );
};

export default UserContext;
