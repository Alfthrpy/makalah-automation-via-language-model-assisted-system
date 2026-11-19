import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { store } from "./storage";

export type ThemeMode = "system" | "light" | "dark";
const KEY = "malas.theme";
const MODES: ThemeMode[] = ["system", "light", "dark"];

interface ThemeCtx { mode: ThemeMode; resolved: "light" | "dark"; setMode: (m: ThemeMode) => void }
const Ctx = createContext<ThemeCtx | null>(null);

function readStored(): ThemeMode {
  const v = store.get(KEY);
  return MODES.includes(v as ThemeMode) ? (v as ThemeMode) : "system";
}
const systemDark = () => typeof matchMedia === "function" && matchMedia("(prefers-color-scheme: dark)").matches;

export function applyTheme(mode: ThemeMode) {
  const el = document.documentElement;
  if (mode === "system") el.removeAttribute("data-theme");
  else el.setAttribute("data-theme", mode);
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>(readStored);
  const [dark, setDark] = useState(systemDark);

  useEffect(() => { applyTheme(mode); }, [mode]);
  useEffect(() => {
    if (typeof matchMedia !== "function") return;
    const mq = matchMedia("(prefers-color-scheme: dark)");
    const on = () => setDark(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);

  const setMode = useCallback((m: ThemeMode) => { setModeState(m); store.set(KEY, m); }, []);
  const resolved = mode === "system" ? (dark ? "dark" : "light") : mode;
  const value = useMemo(() => ({ mode, resolved, setMode }), [mode, resolved, setMode]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useTheme(): ThemeCtx {
  const v = useContext(Ctx);
  if (!v) throw new Error("useTheme di luar ThemeProvider");
  return v;
}
