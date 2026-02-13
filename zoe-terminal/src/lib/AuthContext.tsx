import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';

export type UserRole = 'admin' | 'guest';

interface AuthState {
  role: UserRole;
  isAdmin: boolean;
  isGuest: boolean;
  logout: () => void;
  login: (role: UserRole) => void;
}

const AuthContext = createContext<AuthState>({
  role: 'guest',
  isAdmin: false,
  isGuest: true,
  logout: () => {},
  login: () => {},
});

const AUTH_ROLE_KEY = 'zoe_auth_role';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [role, setRole] = useState<UserRole>(() => {
    return (localStorage.getItem(AUTH_ROLE_KEY) as UserRole) || 'guest';
  });

  const logout = useCallback(() => {
    localStorage.removeItem('zoe_auth_hash');
    localStorage.removeItem(AUTH_ROLE_KEY);
    setRole('guest');
    window.location.reload();
  }, []);

  const login = useCallback((newRole: UserRole) => {
    localStorage.setItem(AUTH_ROLE_KEY, newRole);
    setRole(newRole);
  }, []);

  return (
    <AuthContext.Provider value={{
      role,
      isAdmin: role === 'admin',
      isGuest: role === 'guest',
      logout,
      login,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

/** @deprecated Use useAuth().login() instead for proper React state update */
export function setAuthRole(role: UserRole) {
  localStorage.setItem(AUTH_ROLE_KEY, role);
}
