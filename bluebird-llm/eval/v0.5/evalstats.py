# Bluebird v1.0 eval @0.1: exact/score statistics for the bars (review H3). Stdlib only; used by score.py and sim/simulate.py.
import functools, math
Z95 = 1.959963984540054
def wilson(k, n, z=Z95):
    """Wilson score 95 % interval for k successes of n."""
    if not n: return (None, None)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))
def binom_cdf(k, n, p):
    """P(X <= k), X ~ Bin(n, p); log-space terms, exact enough for n <= a few thousand."""
    if k < 0: return 0.0
    if k >= n: return 1.0
    if p <= 0: return 1.0
    if p >= 1: return 0.0
    lp, lq = math.log(p), math.log1p(-p); lg = math.lgamma
    t = [lg(n + 1) - lg(i + 1) - lg(n - i + 1) + i * lp + (n - i) * lq for i in range(0, k + 1)]
    m = max(t); return min(1.0, math.exp(m) * sum(math.exp(x - m) for x in t))
def binom_sf_half(b, n):
    """Exact P(X >= b), X ~ Bin(n, 1/2), integer arithmetic."""
    if b <= 0: return 1.0
    if b > n: return 0.0
    return sum(math.comb(n, i) for i in range(b, n + 1)) / (1 << n)
def mcnemar_one_sided(b, c):
    """Exact (conditional binomial) McNemar, one-sided: H1 = the b-cell is larger. b, c = discordant counts."""
    return binom_sf_half(b, b + c)
def mcnemar_two_sided(b, c):
    return min(1.0, 2 * min(binom_sf_half(b, b + c), binom_sf_half(c, b + c))) if b + c else 1.0
@functools.lru_cache(maxsize=None)
def floor_kmin(n, p_star, alpha):
    """Smallest passing count for an accuracy floor: pass iff k >= k_min, where k_min is the largest k with P(X < k) <= alpha
    under X ~ Bin(n, p_star). A reader whose true accuracy is p_star (or better) misses the floor with probability <= alpha."""
    k = 0
    while k < n and binom_cdf(k, n, p_star) <= alpha: k += 1
    return k
