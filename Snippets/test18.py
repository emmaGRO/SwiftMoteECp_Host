from collections import defaultdict
import datetime
from math import sqrt
import rtree.index

points = [(5, 4), (3, 1), (6, 3), (2, 8), (7, 8), (8, 1), (2, 3), (0, 4), (3, 7), (6, 4)]

idx = rtree.index.Rtree()

for i, p in enumerate(points):
    print(p)
    print(datetime.datetime.utcnow().timestamp() + i, i)
    t = datetime.datetime.utcnow().timestamp() + i
    idx.insert(i, (t, t), p)

t = datetime.datetime.utcnow().timestamp()
search = (t, t + 3)
print('search', search)
hits = idx.nearest(search, 1, objects=True)
for h in hits:
    print(h.handle, h.bounds, h.id, h.object, h.bbox, h.owned)

# print(l)
