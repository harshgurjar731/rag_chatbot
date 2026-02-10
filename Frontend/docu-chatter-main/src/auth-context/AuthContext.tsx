import { createContext, useContext, useState, ReactNode, useEffect } from "react";

type User = {
  id: string;
  email: string;
  department: string;
};

type AuthContextType = {
  user: User | null;
  isAuthenticated: boolean;
  isAdmin: boolean;
  isAuthInitialized: boolean;
  login: (user: User, access_token: string) => void;
  logout: () => void;
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isAuthInitialized, setIsAuthInitialized] = useState(false);

  useEffect(() => {
    const storedUser = localStorage.getItem("user");
    const token = localStorage.getItem("access_token");
    console.log("AuthContext retrieved user", storedUser)
    if (storedUser && token) {
      setUser(JSON.parse(storedUser));
    }
    setIsAuthInitialized(true);
  }, []);

  const login = (user: User, access_token: string) => {
    setUser(user);
    // optionally persist
    localStorage.setItem("user", JSON.stringify(user));
    localStorage.setItem("access_token", access_token);

  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem("user");
    localStorage.removeItem("access_token");
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isAdmin: user?.department === "Admin",
        isAuthInitialized,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
