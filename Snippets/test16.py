import matplotlib.pyplot as plt
import numpy as np
import scipy.spatial
import rtree.index

# points = np.column_stack([np.random.rand(50), np.random.rand(50)])
fig, ax = plt.subplots()
# coll = ax.scatter(points[:,0], points[:,1])
# ckdtree = scipy.spatial.cKDTree(points)

i_max = 0
points = [(5, 4), (3, 1), (6, 3), (2, 8), (7, 8), (8, 1), (2, 3), (0, 4), (3, 7), (6, 4)]
idx = rtree.index.Rtree()
for p in points:
    idx.insert(i_max, p, None)
    ax.scatter(p[0], p[1], c='blue')
    ax.text(p[0] + 0.1, p[1] + 0.1, i_max)
    i_max += 1
    print(i_max)
idx.flush()

# def closest_point_distance(ckdtree, x, y):
#     # returns distance to closest point
#     return ckdtree.query([x, y])[0]
#
#
# def closest_point_id(ckdtree, x, y):
#     # returns index of closest point
#     # print('qqq',ckdtree.query([x, y]))
#     return ckdtree.query([x, y])[1]
#
#
# def closest_point_coords(ckdtree, x, y):
#     # returns coordinates of closest point
#     return ckdtree.data[closest_point_id(ckdtree, x, y)]
#     # ckdtree.data is the same as points
#
#
# def val_shower(ckdtree):
#     # formatter of coordinates displayed on Navigation Bar
#     return lambda x, y: '[x = {}, y = {}]'.format(*closest_point_coords(ckdtree, x, y))

last_id_closest = -1
axvline1 = plt.axvline(x=0.1, color='k')
axvline2 = plt.axhline(y=0.3, color='k')


def onmove(event):
    global last_id_closest, axvline1, axvline2

    try:

        if event.inaxes is not None:
            search = (event.xdata, event.ydata)
            hits = idx.nearest(search, 1, objects=True)
            closest = next(hits)  # there may be several closest elements at the same distance, pick 1st at random
            if closest.id != last_id_closest:
                last_id_closest = closest.id
                # print(closest.bounds, closest.id, closest.object, closest.bbox, closest.owned)

                axvline1.set_data([closest.bbox[0], closest.bbox[0]], [0, 1])
                axvline2.set_data([0, 1], [closest.bbox[1], closest.bbox[1]])

                plt.draw()
    except Exception as e:
        print(e)
        pass


fig.canvas.mpl_connect('motion_notify_event', onmove)


def onclick(event):
    global i_max
    try:
        if event.inaxes is not None:
            # print(event.xdata, event.ydata)
            p = (event.xdata, event.ydata)
            idx.insert(i_max, p, None)
            ax.scatter(event.xdata, event.ydata, c='blue')
            ax.text(event.xdata + 0.1, event.ydata + 0.1, i_max)
            i_max += 1
            plt.draw()

            idx.flush()
    except Exception as e:
        print(e)
        pass


fig.canvas.mpl_connect('button_press_event', onclick)

plt.show()
