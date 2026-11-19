import { EmptyState, LinkButton } from "../../components/ui/primitives";
import { id as t } from "../../copy/id";

export default function NotFound() {
  return (
    <main className="screen" id="main"><div className="wrap">
      <EmptyState icon="doc" title={t.states.notFoundTitle} action={<LinkButton to="/">{t.states.notFoundCta}</LinkButton>}>{t.states.notFoundText}</EmptyState>
    </div></main>
  );
}
