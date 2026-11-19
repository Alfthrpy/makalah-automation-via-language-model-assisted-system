import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router";
import { Icon, type IconName } from "./icons";
import { LogoMark } from "./Mascot";
import { Button, LinkButton, Seg } from "./ui/primitives";
import { id as t } from "../copy/id";
import { useAuthState } from "../lib/auth";
import { useMe } from "../lib/queries";
import { useTheme, type ThemeMode } from "../lib/theme";
import { useToast } from "./ui/Toast";

export function ThemeToggle() {
  const { mode, setMode } = useTheme();
  return (
    <Seg<ThemeMode> label={t.theme.label} value={mode} onChange={setMode}
      options={[{ value: "system", label: t.theme.system }, { value: "light", label: t.theme.light }, { value: "dark", label: t.theme.dark }]} />
  );
}

/** Tombol tema ringkas untuk header publik: berputar Sistem → Terang → Gelap. */
function ThemeCycle() {
  const { mode, setMode } = useTheme();
  const order: ThemeMode[] = ["system", "light", "dark"];
  const next = order[(order.indexOf(mode) + 1) % 3] ?? "system";
  return (
    <button type="button" className="btn ghost icon" aria-label={`${t.theme.toggle}: ${t.theme[mode]}`} title={`${t.theme.label}: ${t.theme[mode]}`} onClick={() => setMode(next)}>
      <Icon name="sun" size="md" />
    </button>
  );
}

export function PublicHeader() {
  const nav = useNavigate();
  const loc = useLocation();
  function jump(e: React.MouseEvent, anchor: string) {
    e.preventDefault();
    const go = () => document.getElementById(anchor)?.scrollIntoView({ behavior: "smooth" });
    if (loc.pathname !== "/") { nav("/"); setTimeout(go, 60); } else go();
  }
  return (
    <header className="topbar">
      <div className="wrap topbar-in">
        <Link className="brand" to="/" aria-label={t.brand.homeLabel}><LogoMark /><b>{t.brand.name}</b></Link>
        <nav className="nav" aria-label={t.nav.pageSections}>
          <a href="/#cara-kerja" onClick={(e) => jump(e, "cara-kerja")}>{t.nav.howItWorks}</a>
          <a href="/#privasi" onClick={(e) => jump(e, "privasi")}>{t.nav.privacy}</a>
          <a href="/#faq" onClick={(e) => jump(e, "faq")}>{t.nav.faq}</a>
        </nav>
        <div className="right">
          <ThemeCycle />
          <LinkButton variant="ghost" to="/masuk">{t.nav.login}</LinkButton>
          <LinkButton variant="primary" to="/daftar">{t.nav.signup}</LinkButton>
        </div>
      </div>
    </header>
  );
}

export function PublicLayout() {
  return (<><PublicHeader /><Outlet /></>);
}

function Pips({ limit, remaining }: { limit: number; remaining: number }) {
  return <span className="pips" aria-hidden="true">{Array.from({ length: limit }, (_, i) => <i key={i} className={i < remaining ? "" : "used"} />)}</span>;
}

export function QuotaPill() {
  const { data } = useMe();
  const q = data?.quota;
  if (!q) return null;
  return (
    <Link className="quota-chip" to="/pengaturan" aria-label={`${t.quota.chip}: ${t.quota.left(q.remaining, q.limit)}`}>
      <Pips limit={q.limit} remaining={q.remaining} />
      <span className="qtxt"><b>{q.remaining}</b> dari {q.limit} tersisa</span>
    </Link>
  );
}

function AccountMenu() {
  const auth = useAuthState();
  const nav = useNavigate();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const btn = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => { if (!wrap.current?.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") { setOpen(false); btn.current?.focus(); } };
    document.addEventListener("click", onClick);
    document.addEventListener("keydown", onKey);
    wrap.current?.querySelector<HTMLElement>("a,button[role=menuitem]")?.focus();
    return () => { document.removeEventListener("click", onClick); document.removeEventListener("keydown", onKey); };
  }, [open]);

  const u = auth.user;
  if (!u) return null;
  return (
    <div className="rel" ref={wrap}>
      <button ref={btn} type="button" className="avatar-btn" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <span className="avatar" aria-hidden="true">{u.initials}</span>
        <span className="sr-only">{t.nav.accountMenu} {u.name}</span>
      </button>
      {open && (
        <div className="menu" role="menu">
          <div className="who"><b>{u.name}</b><div className="small muted">{u.email}</div></div>
          <Link to="/pengaturan" role="menuitem" onClick={() => setOpen(false)}><Icon name="gear" />{t.nav.settings}</Link>
          <button type="button" role="menuitem" onClick={async () => { setOpen(false); await auth.signOut(); toast(t.settings.loggedOut); nav("/"); }}>
            <Icon name="logout" />{t.nav.logout}
          </button>
        </div>
      )}
    </div>
  );
}

const NAV: { to: string; icon: IconName; label: string; short: string }[] = [
  { to: "/dasbor", icon: "grid", label: t.nav.dashboard, short: t.nav.dashboard },
  { to: "/buat", icon: "pen", label: t.nav.create, short: t.nav.createShort },
  { to: "/pengaturan", icon: "gear", label: t.nav.settings, short: t.nav.settings },
];

export function AppHeader() {
  return (
    <header className="topbar">
      <div className="wrap topbar-in">
        <Link className="brand" to="/dasbor" aria-label={t.brand.dashLabel}><LogoMark /><b>{t.brand.name}</b></Link>
        <nav className="nav" aria-label={t.nav.main}>
          {NAV.map((n) => <NavLink key={n.to} to={n.to}><Icon name={n.icon} />{n.label}</NavLink>)}
        </nav>
        <div className="right"><QuotaPill /><AccountMenu /></div>
      </div>
    </header>
  );
}

export function BottomNav() {
  return (
    <nav className="tabbar" aria-label={t.nav.main}>
      {NAV.map((n) => <NavLink key={n.to} to={n.to}><Icon name={n.icon} size="md" />{n.short}</NavLink>)}
    </nav>
  );
}

export function AppLayout() {
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  return (<><AppHeader /><Outlet /><BottomNav /></>);
}

export { Button };
