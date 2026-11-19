import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ClerkProvider, useAuth as useClerkAuth, useClerk, useUser } from "@clerk/clerk-react";
import { setTokenGetter } from "./api";
import { initials } from "./format";
import { store } from "./storage";
import { id as t } from "../copy/id";
import { useTheme } from "./theme";
import { useNavigate } from "react-router";

export interface AppUser { name: string; email: string; initials: string }
export interface AuthState {
  mode: "dev" | "clerk";
  ready: boolean;
  signedIn: boolean;
  user: AppUser | null;
  /** Mode dev: tandai masuk (cookie anonim backend). Mode Clerk: tidak dipakai (komponen Clerk yang masuk). */
  signInDev: () => void;
  signOut: () => Promise<void>;
}

const Ctx = createContext<AuthState | null>(null);
const DEV_FLAG = "malas.dev.signedin";

export const AUTH_MODE: "dev" | "clerk" = import.meta.env.VITE_AUTH_MODE === "clerk" ? "clerk" : "dev";
export const CLERK_KEY = (import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as string | undefined) ?? "";

function DevAuthProvider({ children }: { children: ReactNode }) {
  const [signedIn, setSignedIn] = useState(() => store.get(DEV_FLAG) === "1");
  useEffect(() => { setTokenGetter(async () => null); }, []);
  const signInDev = useCallback(() => { store.set(DEV_FLAG, "1"); setSignedIn(true); }, []);
  const signOut = useCallback(async () => { store.remove(DEV_FLAG); setSignedIn(false); }, []);
  const value = useMemo<AuthState>(
    () => ({
      mode: "dev", ready: true, signedIn,
      user: signedIn ? { name: t.account.local, email: t.account.localMail, initials: "PL" } : null,
      signInDev, signOut,
    }),
    [signedIn, signInDev, signOut],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

function ClerkBridge({ children }: { children: ReactNode }) {
  const { isLoaded, isSignedIn, getToken } = useClerkAuth();
  const { user } = useUser();
  const clerk = useClerk();
  // Dipasang saat render agar kueri anak yang jalan lebih awal sudah punya pengambil token.
  setTokenGetter(() => getToken());
  const name = user?.fullName || user?.firstName || user?.primaryEmailAddress?.emailAddress || "Pengguna";
  const value = useMemo<AuthState>(
    () => ({
      mode: "clerk", ready: isLoaded, signedIn: !!isSignedIn,
      user: isSignedIn && user ? { name, email: user.primaryEmailAddress?.emailAddress ?? "", initials: initials(name) } : null,
      signInDev: () => {},
      signOut: async () => { await clerk.signOut(); },
    }),
    [isLoaded, isSignedIn, user, name, clerk],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

function ClerkRoot({ children }: { children: ReactNode }) {
  const { resolved } = useTheme();
  const navigate = useNavigate();
  if (!CLERK_KEY) {
    return <div className="wrap" style={{ paddingBlock: 48 }}><p className="err" role="alert">{t.auth.missingKey}</p></div>;
  }
  return (
    <ClerkProvider publishableKey={CLERK_KEY} afterSignOutUrl="/" signInUrl="/masuk" signUpUrl="/daftar"
      routerPush={(to) => navigate(to)} routerReplace={(to) => navigate(to, { replace: true })}
      signInFallbackRedirectUrl="/dasbor" signUpFallbackRedirectUrl="/dasbor" appearance={clerkAppearance(resolved)}>
      <ClerkBridge>{children}</ClerkBridge>
    </ClerkProvider>
  );
}

/** Warna selaras token prototipe. Clerk tidak memakai var() di semua tempat, jadi nilai diturunkan dari tema aktif. */
export function clerkAppearance(theme: "light" | "dark") {
  const d = theme === "dark";
  return {
    variables: {
      colorPrimary: d ? "#a3aeff" : "#2c3a9e",
      colorBackground: d ? "#171b2b" : "#ffffff",
      colorText: d ? "#e8eaf5" : "#161a2c",
      colorTextSecondary: d ? "#a3a9c2" : "#545b73",
      colorInputBackground: d ? "#171b2b" : "#ffffff",
      colorInputText: d ? "#e8eaf5" : "#161a2c",
      colorDanger: d ? "#ff8f86" : "#b3261e",
      colorSuccess: d ? "#61d08f" : "#14703a",
      borderRadius: "8px",
      fontFamily: '"Plus Jakarta Sans", system-ui, sans-serif',
    },
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  return AUTH_MODE === "clerk" ? <ClerkRoot>{children}</ClerkRoot> : <DevAuthProvider>{children}</DevAuthProvider>;
}

export function useAuthState(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuthState di luar AuthProvider");
  return v;
}
