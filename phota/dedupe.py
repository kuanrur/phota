import imagehash

from phota.config import PHASH_SIMILAR_DISTANCE


def find_duplicate_groups(idx, threshold=PHASH_SIMILAR_DISTANCE):
    """Cluster photos whose perceptual hashes are within <= threshold Hamming distance.

    Returns a list of groups (each a list of photo ids, size >= 2), with the
    highest-sharpness photo first (the suggested keeper).
    """
    photos = [p for p in idx.all_photos() if p.phash]
    parent = {p.id: p.id for p in photos}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    hashes = {p.id: imagehash.hex_to_hash(p.phash) for p in photos}
    ids = list(hashes)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            if hashes[ids[i]] - hashes[ids[j]] <= threshold:
                union(ids[i], ids[j])
    from collections import defaultdict

    groups = defaultdict(list)
    sharp = {p.id: (p.sharpness or 0.0) for p in photos}
    for pid in ids:
        groups[find(pid)].append(pid)
    out = []
    for members in groups.values():
        if len(members) >= 2:
            out.append(sorted(members, key=lambda m: -sharp[m]))
    return out
