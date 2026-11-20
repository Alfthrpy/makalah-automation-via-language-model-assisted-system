"""Anggaran token tahap LLM enhancing (docs/enhancing-engine.md §6.1 prinsip 5, §6.5).

Satu instance per run (`MalasFlow`), batas dari `config.enhance_budget()`. Semua tahap LLM enhancing (blueprint,
kartu bukti; nanti kritik/tambal) memesan taksiran token sebelum memanggil LLM dan mencatat pemakaian sesudahnya.
Anggaran habis = tahap DILEWATI (bukan gagal). Aman dipakai dari beberapa thread (kartu bukti paralel).
"""
import threading


def estimate_tokens(text: str) -> int:
    """Taksiran kasar 4 karakter ~ 1 token (panggilan `LLM.call` langsung tidak melaporkan usage)."""
    return len(text or "") // 4


class Budget:
    """Penghitung token berbatas. `limit <= 0` berarti tahap enhancing ber-LLM tidak boleh berjalan."""

    def __init__(self, limit: int):
        self.limit = max(0, int(limit))
        self.spent = 0
        self._lock = threading.Lock()

    @property
    def remaining(self) -> int:
        with self._lock:
            return max(0, self.limit - self.spent)

    @property
    def exhausted(self) -> bool:
        return self.remaining <= 0

    def spend(self, tokens: int) -> None:
        """Catat pemakaian (boleh negatif untuk mengoreksi pesanan yang terlalu besar)."""
        with self._lock:
            self.spent = max(0, self.spent + int(tokens))

    def reserve(self, tokens: int) -> bool:
        """Pesan `tokens` secara atomik; False (tanpa mencatat apa pun) bila sisa anggaran tidak cukup."""
        tokens = max(0, int(tokens))
        with self._lock:
            if self.limit - self.spent < tokens or self.limit - self.spent <= 0:
                return False
            self.spent += tokens
            return True

    def settle(self, reserved: int, actual: int) -> None:
        """Ganti pesanan `reserved` dengan pemakaian `actual` setelah panggilan selesai."""
        self.spend(int(actual) - int(reserved))
