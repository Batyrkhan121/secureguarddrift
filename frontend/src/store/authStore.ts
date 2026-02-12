import { create } from "zustand";
import { login as apiLogin } from "@/api/client";
import type { User } from "@/api/types";

interface AuthState {
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  hasRole: (role: string) => boolean;
  setAuth: (token: string, user: User) => void;
}

/** Decode JWT payload for UI display only. All authorization is enforced server-side. */
function decodeUser(token: string): User | null {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return {
      id: payload.sub ?? payload.user_id ?? "",
      email: payload.email ?? "",
      role: payload.role ?? "viewer",
      tenant_id: payload.tenant_id ?? "default",
    };
  } catch {
    return null;
  }
}

const savedToken = localStorage.getItem("sg_token");
const savedUser = savedToken ? decodeUser(savedToken) : null;

export const useAuthStore = create<AuthState>((set, get) => ({
  token: savedToken,
  user: savedUser,
  isAuthenticated: !!savedToken,

  login: async (email, password) => {
    const { access_token } = await apiLogin(email, password);
    localStorage.setItem("sg_token", access_token);
    const user = decodeUser(access_token);
    set({ token: access_token, user, isAuthenticated: true });
  },

  logout: () => {
    localStorage.removeItem("sg_token");
    set({ token: null, user: null, isAuthenticated: false });
  },

  hasRole: (role: string) => {
    const { user } = get();
    if (!user) return false;
    const hierarchy = ["viewer", "operator", "admin"];
    return hierarchy.indexOf(user.role) >= hierarchy.indexOf(role);
  },

  setAuth: (token, user) => {
    localStorage.setItem("sg_token", token);
    set({ token, user, isAuthenticated: true });
  },
}));
