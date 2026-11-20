import { useEffect } from "react";
import { absUrl, fullTitle } from "./site";

function el<T extends HTMLElement>(selector: string, make: () => T): T {
  let e = document.head.querySelector<T>(selector);
  if (!e) { e = make(); document.head.appendChild(e); }
  return e;
}

/** Perbarui judul, deskripsi, canonical, dan robots saat berpindah halaman (SPA), lalu pulihkan saat keluar.
 *  Crawler yang tidak menjalankan JS memakai HTML prerender (scripts/prerender.mjs); ini untuk Google dan pengguna. */
export function useSeo({ title, description, path, noindex }: { title: string; description?: string; path: string; noindex?: boolean }) {
  useEffect(() => {
    const prevTitle = document.title;
    const desc = el<HTMLMetaElement>('meta[name="description"]', () => Object.assign(document.createElement("meta"), { name: "description" }));
    const canon = el<HTMLLinkElement>('link[rel="canonical"]', () => Object.assign(document.createElement("link"), { rel: "canonical" }));
    const robots = el<HTMLMetaElement>('meta[name="robots"]', () => Object.assign(document.createElement("meta"), { name: "robots" }));
    const prev = { desc: desc.content, canon: canon.href, robots: robots.content };
    document.title = fullTitle(title);
    if (description) desc.content = description;
    canon.href = absUrl(path);
    robots.content = noindex ? "noindex,follow" : "index,follow,max-image-preview:large";
    return () => {
      document.title = prevTitle;
      desc.content = prev.desc; canon.href = prev.canon; robots.content = prev.robots;
    };
  }, [title, description, path, noindex]);
}
