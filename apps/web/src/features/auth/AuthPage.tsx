import { SignIn, SignUp } from "@clerk/react";
import { Navigate, useLocation } from "react-router";
import { Icon } from "../../components/icons";
import { LogoMark } from "../../components/Mascot";
import { Button, LinkButton } from "../../components/ui/primitives";
import { id as t } from "../../copy/id";
import { AUTH_MODE, useAuthState } from "../../lib/auth";

/** /masuk dan /daftar: komponen Clerk di mode produksi; kartu mode-dev tanpa Clerk saat pengembangan. */
export default function AuthPage({ mode }: { mode: "masuk" | "daftar" }) {
  const auth = useAuthState();
  const loc = useLocation();
  const from = (loc.state as { from?: string } | null)?.from ?? "/dasbor";
  if (auth.ready && auth.signedIn) return <Navigate to={from} replace />;
  const up = mode === "daftar";

  return (
    <main className="screen" id="main">
      <div className="wrap auth-wrap">
        {AUTH_MODE === "clerk" ? (
          <div className="clerk-embed">
            {up ? <SignUp routing="path" path="/daftar" signInUrl="/masuk" /> : <SignIn routing="path" path="/masuk" signUpUrl="/daftar" />}
          </div>
        ) : (
          <div className="clerk" role="region" aria-labelledby="clerk-h">
            <div className="clerk-body">
              <header>
                <LogoMark size={40} />
                <h1 id="clerk-h">{up ? t.auth.signupTitle : t.auth.loginTitle}</h1>
              </header>
              <p className="small muted">{t.auth.devNote}</p>
              <Button variant="primary" block onClick={() => auth.signInDev()}><Icon name="user" size="md" />{t.auth.devLogin}</Button>
              <LinkButton variant="ghost" block to="/">{t.auth.devBack}</LinkButton>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
