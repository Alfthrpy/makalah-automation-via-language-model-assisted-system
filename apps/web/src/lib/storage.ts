/** localStorage yang aman: selalu try/catch (mode privat, blokir data situs, pratinjau). */
export const store = {
  get(key: string): string | null {
    try { return localStorage.getItem(key); } catch { return null; }
  },
  set(key: string, value: string): void {
    try { localStorage.setItem(key, value); } catch { /* abaikan */ }
  },
  remove(key: string): void {
    try { localStorage.removeItem(key); } catch { /* abaikan */ }
  },
};
