import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from matplotlib.widgets import Cursor

# x and y arrays for definining an initial function
x = np.linspace(0, 10, 100)
y = np.exp(x ** 0.5) * np.sin(5 * x)
# Plotting
fig = plt.figure()
ax = fig.subplots()
ax.plot(x, y, color='b')
ax.grid()
# Defining the cursor
cursor = Cursor(ax, horizOn=True, vertOn=True, useblit=True,
                color='r', linewidth=1)

axvline1 = plt.axvline(x=0.1, color='k')
axvline2 = plt.axhline(y=0.3, color='k')


def onclick(event):
    # global axvline1, axvline2
    print(event.xdata, event.ydata)


# cursor.connect_event('button_press_event', onclick)


def onmove(event):
    global axvline1, axvline2
    print(event.__dict__)
    try:
        axvline1.set_data([event.xdata, event.xdata], [0, 1])
        axvline2.set_data([0, 1], [event.ydata, event.ydata])

        plt.draw()
    except Exception as e:
        print(e)
        pass
    # global id_last
    # if event.inaxes is not None and closest_point_id(ckdtree, event.xdata, event.ydata) != id_last:  # first part of "and" statement is executed first
    #     id_last = closest_point_id(ckdtree, event.xdata, event.ydata)
    #     #print(closest_point_id(ckdtree, event.xdata, event.ydata))
    #     print(closest_point_coords(ckdtree, event.xdata, event.ydata))
    #     #print(closest_point_distance(ckdtree, event.xdata, event.ydata))


fig.canvas.mpl_connect('motion_notify_event', onmove)

# Creating an annotating box
# annot = ax.annotate("", xy=(0, 0), xytext=(-40, 40), textcoords="offset points",
#                    bbox=dict(boxstyle='round4', fc='linen', ec='k', lw=1),
#                    arrowprops=dict(arrowstyle='-|>'))
# annot.set_visible(True)
# Function for storing and showing the clicked values
# coord = []


# def onclick(event):
#    global coord
#    coord.append((event.xdata, event.ydata))
#    x = event.xdata
#    y = event.ydata
#
#    # printing the values of the selected point
#    print([x, y])
#    annot.xy = (x, y)
#    text = "({:.2g}, {:.2g})".format(x, y)
#    annot.set_text(text)
#    annot.set_visible(True)
#    fig.canvas.draw()  # redraw the figure
#
#
# fig.canvas.mpl_connect('button_press_event', onclick)
plt.show()
# Unzipping the coord list in two different arrays
# x1, y1 = zip(*coord)
# print(x1, y1)
