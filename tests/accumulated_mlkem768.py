"""C2SP/CCTV accumulated test for ML-KEM-768 (procedure from words.filippo.io/accumulated)."""
import hashlib, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from vlckem import mlkem as K

EXPECTED_10000 = "8a518cc63da366322a8e7a818c7a0d63"

def run(iters: int) -> str:
    p = K.ML_KEM_768
    per = 64 + 32 + p.ct_bytes
    stream = hashlib.shake_128(b"").digest(per * iters)
    acc = hashlib.shake_128()
    off = 0
    for _ in range(iters):
        seed = stream[off:off + 64]; off += 64
        ek, dk = K.keygen_internal(p, seed[:32], seed[32:])
        acc.update(ek)
        m = stream[off:off + 32]; off += 32
        k, ct = K.encaps_internal(p, ek, m)
        acc.update(ct); acc.update(k)
        assert K.decaps_internal(p, dk, ct) == k, "decaps mismatch"
        bad = stream[off:off + p.ct_bytes]; off += p.ct_bytes
        acc.update(K.decaps_internal(p, dk, bad))
    return acc.hexdigest(16)

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10000
    t = time.time(); h = run(n); dt = time.time() - t
    print(f"iterations={n} digest={h} time={dt:.1f}s")
    if n == 10000:
        print("PASS" if h == EXPECTED_10000 else "FAIL")
