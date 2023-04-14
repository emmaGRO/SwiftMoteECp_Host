# https://stackoverflow.com/questions/36737053/mplot3d-fill-between-extends-over-axis-limits
# https://stackoverflow.com/questions/34099518/plotting-a-series-of-2d-plots-projected-in-3d-in-a-perspectival-way
import matplotlib.pylab as plt
import numpy as np

w = 3
fig = plt.figure()
ax = fig.add_subplot(111, projection='3d', computed_zorder=False)

for depth in range(1, 11, 1):  # reverse order
    # Generated some random data
    x, y = np.arange(100), np.random.randint(0, 100 + w, 100)
    y = np.array([y[i - w:i + w].mean() for i in range(3, 100 + w)])
    z = np.ones(x.shape) * depth

    ax.add_collection3d(plt.fill_between(x=x, y1=y, y2=0, color='orange', alpha=0.1), depth, zdir='y')
    # verts = [(x[i], z[i], y[i]) for i in range(len(x))] + [(x.max(), depth, 0), (x.min(), depth, 0)]
    # ax.add_collection3d(Poly3DCollection([verts], color='orange'))  # Add a polygon instead of fill_between

    ax.plot(x, z, y, label="line plot_" + str(depth), linewidth=2.0, zorder=2-depth*0.01)

ax.legend()
ax.set_ylim(0, 11)
plt.show()
