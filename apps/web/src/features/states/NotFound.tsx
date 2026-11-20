import { EmptyState, LinkButton } from "../../components/ui/primitives";
import { id as t } from "../../copy/id";
import { useSeo } from "../../seo/useSeo";

export default function NotFound() {
  useSeo({ title: "Halaman tidak ditemukan", path: "/404", noindex: true });
  return (
    <main className="screen" id="main"><div className="wrap">
      <EmptyState icon="doc" title={t.states.notFoundTitle} action={<LinkButton to="/">{t.states.notFoundCta}</LinkButton>}>{t.states.notFoundText}</EmptyState>
    </div></main>
  );
}
