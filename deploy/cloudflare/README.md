# Web di Cloudflare Pages (alternatif Netlify)

Netlify gratis dibatasi **kredit** bulanan (deploy, bandwidth, request). Cloudflare Pages: file statis gratis tanpa batas
bandwidth; yang dihitung hanya request `/api/*` lewat Pages Function (kuota gratis Workers: 100.000 request/hari).

| Bagian | Cara |
|---|---|
| Halaman, aset | Statis dari `apps/web/dist` (gratis, tak terbatas) |
| Proxy `/api/*` ke backend HF | `functions/api/[[path]].js` (tidak bisa lewat `_redirects`: Cloudflare hanya proxy ke path internal) |
| Header keamanan, CSP, cache | `_headers`, diturunkan otomatis dari `netlify.toml` oleh `prepare.py` (satu sumber kebenaran) |
| Fallback SPA | `_redirects` berisi `/*  /index.html  200` |
| Halaman prerender (`/ketentuan`, `/panduan/...`) | `prepare.py` memindah `x/index.html` menjadi `x.html` agar URL tetap `/x` (tanpa garis miring penutup), sama dengan canonical dan sitemap |

## Deploy

```bash
VITE_AUTH_MODE=clerk VITE_CLERK_PUBLISHABLE_KEY=pk_... pnpm --filter web build
CLOUDFLARE_API_TOKEN=... CLOUDFLARE_ACCOUNT_ID=... python3 deploy/cloudflare/deploy.py --project malas-app
```

Token API (Cloudflare > My Profile > API Tokens): izin **Account > Cloudflare Pages > Edit** (dan **Zone > DNS > Edit**
bila DNS ingin diatur lewat API). Project dibuat sekali: `npx wrangler@4 pages project create malas-app --production-branch main`.

## Domain `malas.alfthrpy.my.id`

DNS `alfthrpy.my.id` ada di Cloudflare. Di project Pages: *Custom domains* > tambahkan `malas.alfthrpy.my.id`; Cloudflare
mengganti rekaman CNAME-nya ke `<project>.pages.dev`. Lepas domain itu dari situs Netlify setelah beralih. Domain tetap sama,
jadi `CLERK_AUTHORIZED_PARTIES` dan pengaturan Clerk tidak berubah.

## Setelan penting di dashboard

- **Pages > Settings > Functions > Fail open/closed**: pilih **Fail closed**. Bawaannya *fail open*: bila kuota harian fungsi
  habis, `/api/*` akan dilayani sebagai halaman HTML (bukan JSON) dan UI tampak rusak tanpa pesan jelas.
- **Variabel opsional** `BACKEND_ORIGIN` (mis. `https://pemilik-nama.hf.space`, harus https) menimpa host backend bawaan.
  Bila Space diganti, ubah juga host di `netlify.toml` (tes menjaga keduanya tetap sama).

## Tes

- `node --test deploy/cloudflare/proxy.test.mjs`: perilaku proxy (header, isi, redirect tidak diikuti, 502 saat backend mati).
- `uv run pytest apps/api/tests/test_cloudflare_edge.py`: hasil `prepare.py`.
- Lokal: `cd deploy/cloudflare && python3 prepare.py && npx wrangler@4 pages dev .stage` (emulator; `/api` memerlukan backend terjangkau).
