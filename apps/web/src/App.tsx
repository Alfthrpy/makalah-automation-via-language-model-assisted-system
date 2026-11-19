import { QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { BrowserRouter, useNavigate } from "react-router";
import { IconSprite } from "./components/icons";
import { ConfirmProvider, Dialog } from "./components/ui/Dialog";
import { ToastProvider } from "./components/ui/Toast";
import { id as t } from "./copy/id";
import { onUnauthorized } from "./lib/api";
import { AuthProvider } from "./lib/auth";
import { makeQueryClient } from "./lib/queries";
import { ThemeProvider } from "./lib/theme";
import { AppRoutes } from "./routes";

/** 401 di mana saja: dialog "Sesi kamu berakhir". Formulir tetap di perangkat (tanpa API key). */
function SessionGuard() {
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  useEffect(() => onUnauthorized(() => setOpen(true)), []);
  return (
    <Dialog open={open} onClose={() => setOpen(false)} title={t.dialog.session.title} icon="lock" iconColor="var(--accent)"
      ok={t.dialog.session.ok} cancel={null} onOk={() => { nav("/masuk"); }}>
      <p className="small">{t.dialog.session.text}</p>
    </Dialog>
  );
}

export default function App() {
  const qc = useMemo(makeQueryClient, []);
  return (
    <ThemeProvider>
      <QueryClientProvider client={qc}>
        <BrowserRouter>
          <ToastProvider>
            <ConfirmProvider>
              <AuthProvider>
                <IconSprite />
                <a className="skip" href="#main">{t.common.skip}</a>
                <div id="app"><AppRoutes /></div>
                <SessionGuard />
              </AuthProvider>
            </ConfirmProvider>
          </ToastProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
