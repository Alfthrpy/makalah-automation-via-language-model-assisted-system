import { lazy, Suspense } from "react";
import { Navigate, Outlet, Route, Routes, useLocation } from "react-router";
import { AppLayout, PublicLayout } from "./components/shell";
import { Skeleton } from "./components/ui/primitives";
import { useAuthState } from "./lib/auth";
import AuthPage from "./features/auth/AuthPage";
import Landing from "./features/landing/Landing";
import NotFound from "./features/states/NotFound";
import Legal from "./features/states/Legal";

const Dashboard = lazy(() => import("./features/dashboard/Dashboard"));
const Create = lazy(() => import("./features/create/Create"));
const JobPage = lazy(() => import("./features/job/JobPage"));
const Settings = lazy(() => import("./features/settings/Settings"));
const GuidePage = lazy(() => import("./features/guides/Guides"));
const GuideIndex = lazy(() => import("./features/guides/Guides").then((m) => ({ default: m.GuideIndex })));

function Loading() {
  return <main className="screen" id="main" aria-busy="true"><div className="wrap" style={{ display: "grid", gap: 12 }}><Skeleton h={28} w="40%" /><Skeleton h={120} /></div></main>;
}

function RequireAuth() {
  const auth = useAuthState();
  const loc = useLocation();
  if (!auth.ready) return <Loading />;
  if (!auth.signedIn) return <Navigate to="/masuk" state={{ from: loc.pathname }} replace />;
  return <Outlet />;
}

export function AppRoutes() {
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route element={<PublicLayout />}>
          <Route path="/" element={<Landing />} />
          <Route path="/masuk/*" element={<AuthPage mode="masuk" />} />
          <Route path="/daftar/*" element={<AuthPage mode="daftar" />} />
          <Route path="/ketentuan" element={<Legal doc="terms" />} />
          <Route path="/privasi" element={<Legal doc="privacy" />} />
          <Route path="/panduan" element={<GuideIndex />} />
          <Route path="/panduan/:slug" element={<GuidePage />} />
        </Route>
        <Route element={<RequireAuth />}>
          <Route element={<AppLayout />}>
            <Route path="/dasbor" element={<Dashboard />} />
            <Route path="/buat" element={<Create />} />
            <Route path="/job/:id" element={<JobPage />} />
            <Route path="/pengaturan" element={<Settings />} />
          </Route>
        </Route>
        <Route element={<PublicLayout />}><Route path="*" element={<NotFound />} /></Route>
      </Routes>
    </Suspense>
  );
}
