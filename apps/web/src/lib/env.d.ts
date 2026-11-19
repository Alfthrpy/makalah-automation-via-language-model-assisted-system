/// <reference types="vite/client" />
interface ImportMetaEnv {
  readonly VITE_AUTH_MODE?: "dev" | "clerk";
  readonly VITE_CLERK_PUBLISHABLE_KEY?: string;
}
interface ImportMeta { readonly env: ImportMetaEnv }
