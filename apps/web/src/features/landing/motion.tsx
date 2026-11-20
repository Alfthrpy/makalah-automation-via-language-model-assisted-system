import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Icon } from "../../components/icons";
import { useToast } from "../../components/ui/Toast";
import { id as t } from "../../copy/id";

interface MotionCtx { motion: boolean; setMotion: (on: boolean, quiet?: boolean) => void }
const Ctx = createContext<MotionCtx>({ motion: true, setMotion: () => {} });
export const useMotion = () => useContext(Ctx);

const reduced = () => typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Animasi landing: nyala kecuali pengguna memilih gerak dikurangi; bisa dijeda kapan saja. */
export function MotionProvider({ children, onPause }: { children: ReactNode; onPause?: () => void }) {
  const toast = useToast();
  const [motion, setState] = useState(() => !reduced());
  const setMotion = useCallback((on: boolean, quiet = false) => {
    setState(on);
    if (!on) { onPause?.(); if (!quiet) toast(t.landing.motion.toast); }
  }, [toast, onPause]);

  useEffect(() => {
    if (typeof matchMedia !== "function") return;
    const mq = matchMedia("(prefers-reduced-motion: reduce)");
    const on = () => { if (mq.matches) setState(false); };
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);

  const value = useMemo(() => ({ motion, setMotion }), [motion, setMotion]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function MotionButton() {
  const { motion, setMotion } = useMotion();
  return (
    <button type="button" className="btn ghost motion-btn" aria-pressed={!motion} onClick={() => setMotion(!motion)}>
      <Icon name={motion ? "pause" : "arrow"} /><span>{motion ? t.landing.motion.pause : t.landing.motion.play}</span>
    </button>
  );
}

/** true setelah elemen terlihat SEKALI (tidak mengulang saat kembali ke beranda/scroll). */
export function useSeenOnce<T extends Element>(threshold: number): [React.RefObject<T | null>, boolean] {
  const ref = useRef<T | null>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || seen) return;
    if (!("IntersectionObserver" in window)) { setSeen(true); return; }
    const io = new IntersectionObserver((ents) => {
      if (ents.some((e) => e.isIntersecting)) { setSeen(true); io.disconnect(); }
    }, { threshold });
    io.observe(el);
    return () => io.disconnect();
  }, [threshold, seen]);
  return [ref, seen];
}

export function useTimers() {
  const ref = useRef<number[]>([]);
  const clear = useCallback(() => { ref.current.forEach(clearTimeout); ref.current = []; }, []);
  const later = useCallback((ms: number, fn: () => void) => { ref.current.push(window.setTimeout(fn, ms)); }, []);
  useEffect(() => clear, [clear]);
  return { clear, later };
}
