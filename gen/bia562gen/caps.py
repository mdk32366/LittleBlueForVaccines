"""Byte caps: §8.4 (CAP = 15360) and D-0021 (sections <= 1,500 bytes)."""
CAP = 15360          # hard per-leaf cap, L001: leaf bytes <= CAP
SPLIT_BODY = 12000   # §8.4: a clause body over 12,000 bytes is split at paragraph boundaries
SECTION_MAX = 1500   # D-0021 / §9.7: generator section bodies <= 1,500 bytes


class CapError(ValueError):
    """Raised when a leaf would exceed CAP or a section exceeds SECTION_MAX."""


def nbytes(s: str) -> int:
    return len(s.encode("utf-8"))


def check_section(doc_id: str, anchor: str, text: str) -> int:
    n = nbytes(text)
    if n > SECTION_MAX:
        raise CapError(f"section {doc_id}#{anchor} body is {n} bytes > {SECTION_MAX}")
    return n


def check_leaf(leaf_id: str, data: bytes) -> int:
    n = len(data)
    if n > CAP:
        raise CapError(f"leaf {leaf_id} is {n} bytes > CAP {CAP} (L001)")
    return n


def split_paragraphs(body: str, limit: int = SPLIT_BODY) -> list:
    """Split a body at paragraph boundaries into chunks of <= limit bytes. Raises if one paragraph alone is too big."""
    paras = body.split("\n\n")
    chunks, cur = [], ""
    for p in paras:
        if nbytes(p) > limit:
            raise CapError(f"single paragraph of {nbytes(p)} bytes cannot be split under {limit}")
        cand = p if not cur else cur + "\n\n" + p
        if nbytes(cand) > limit:
            chunks.append(cur)
            cur = p
        else:
            cur = cand
    if cur:
        chunks.append(cur)
    return chunks
