import { Icon } from "../../components/icons";
import { QuotaCard } from "../../components/QuotaCard";
import { ThemeToggle } from "../../components/shell";
import { useConfirm } from "../../components/ui/Dialog";
import { Banner, Button, Skeleton } from "../../components/ui/primitives";
import { useToast } from "../../components/ui/Toast";
import { id as t } from "../../copy/id";
import { ApiError } from "../../lib/api";
import { useAuthState } from "../../lib/auth";
import { dateTimeLabel } from "../../lib/format";
import { useConfig, useDeleteKey, useKeys } from "../../lib/queries";
import { useNavigate } from "react-router";
import { useClerk } from "@clerk/clerk-react";

const S = t.settings;

function ManageAccount() {
  const clerk = useClerk();
  return <Button onClick={() => clerk.openUserProfile()}>{S.manage}</Button>;
}

function Keys() {
  const cfg = useConfig();
  const keys = useKeys();
  const del = useDeleteKey();
  const confirm = useConfirm();
  const toast = useToast();

  const providers = (cfg.data?.providers ?? []).filter((p) => p.enabled);
  const saved = new Map((keys.data?.keys ?? []).map((k) => [k.provider, k.saved_at]));

  async function remove(id: string, label: string) {
    const ok = await confirm({
      title: S.keyDeleteTitle(label), icon: "trash", okClass: "danger-solid", ok: S.keyDelete, cancel: t.common.back,
      body: <><p className="small">{S.keyDeleteBody}</p><p className="small muted">{S.keyDeleteNote(label)}</p></>,
    });
    if (!ok) return;
    try { await del.mutateAsync(id); toast(S.keyDeleted(label), "ok"); }
    catch (e) { toast(e instanceof ApiError ? e.message : t.states.genericError, "bad"); }
  }

  if (keys.isPending || cfg.isPending) return <div style={{ display: "grid", gap: 8 }}><Skeleton h={48} /><Skeleton h={48} /></div>;
  if (keys.isError) return <Banner kind="bad" actions={<Button onClick={() => void keys.refetch()}><Icon name="refresh" />{t.common.retry}</Button>}>{keys.error.message}</Banner>;
  if (!keys.data.enabled) return <p className="small muted">{S.keysDisabled}</p>;
  return (
    <div>
      {providers.map((p) => {
        const at = saved.get(p.id);
        return (
          <div className="set-row" key={p.id}>
            <div style={{ display: "flex", gap: 12, alignItems: "center", minWidth: 0 }}>
              <span className="key-ico" aria-hidden="true">{p.label.charAt(0)}</span>
              <div style={{ minWidth: 0 }}><b>{p.label}</b>
                <div className="small muted">{at ? <><Icon name="lock" style={{ verticalAlign: -3 }} /> {S.keySaved(dateTimeLabel(at))}</> : S.keyNone}</div></div>
            </div>
            {at ? <Button variant="danger" onClick={() => void remove(p.id, p.label)}><Icon name="trash" size="md" />{S.keyDelete}</Button> : <span className="small muted">—</span>}
          </div>
        );
      })}
    </div>
  );
}

export default function Settings() {
  const auth = useAuthState();
  const nav = useNavigate();
  const toast = useToast();
  const u = auth.user;
  return (
    <main className="screen" id="main">
      <div className="wrap">
        <div className="page-head"><div><h1>{S.title}</h1><p>{S.sub}</p></div></div>
        <div className="set-grid">
          <section className="card" aria-labelledby="acc-h" style={{ display: "grid", gap: "var(--sp-4)" }}>
            <h2 className="card-title" id="acc-h">{S.account}</h2>
            <div className="acct">
              <span className="avatar" aria-hidden="true">{u?.initials}</span>
              <div style={{ flex: 1, minWidth: 180 }}><b>{u?.name}</b><div className="small muted">{u?.email}{auth.mode === "clerk" ? ` · ${t.account.signedInVia}` : ""}</div></div>
              <div className="btn-row">
                {auth.mode === "clerk" && <ManageAccount />}
                <Button variant="danger" onClick={async () => { await auth.signOut(); toast(S.loggedOut); nav("/"); }}><Icon name="logout" />{S.logout}</Button>
              </div>
            </div>
            <p className="small muted">{auth.mode === "clerk" ? S.clerkNote : S.devNote}</p>
          </section>
          <QuotaCard variant="settings" />
          <section className="card" aria-labelledby="keys-h" style={{ display: "grid", gap: "var(--sp-3)" }}>
            <h2 className="card-title" id="keys-h">{S.keys}</h2>
            <p className="small muted">{S.keysText}</p>
            <Keys />
          </section>
          <section className="card" aria-labelledby="look-h" style={{ display: "grid", gap: "var(--sp-3)" }}>
            <h2 className="card-title" id="look-h">{S.look}</h2>
            <ThemeToggle />
          </section>
        </div>
      </div>
    </main>
  );
}
