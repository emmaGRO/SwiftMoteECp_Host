"""Proof of concept: integrate tkinter, asyncio and async iterator.

Terry Jan Reedy, 2016 July 25
"""

# https://stackoverflow.com/questions/47895765/use-asyncio-and-tkinter-or-another-gui-lib-together-without-freezing-the-gui
# https://docs.python.org/3/library/asyncio-task.html

import asyncio
from random import randrange as rr
import tkinter as tk


class App(tk.Tk):

    def __init__(self, loop, interval=1/60):
        super().__init__()
        self.loop = loop
        self.protocol("WM_DELETE_WINDOW", self.close)

        self.tasks = []
        self.tasks.append(loop.create_task(
            self.rotator(interval=interval, d_per_tick=2)))
        self.tasks.append(loop.create_task(self.updater(interval=interval)))

    async def rotator(self, interval, d_per_tick):
        canvas = tk.Canvas(self, height=600, width=600)
        canvas.pack()

        deg = 0
        color = 'black'
        arc = canvas.create_arc(
            100,
            100,
            500,
            500,
            style=tk.PIESLICE,
            start=0,
            extent=deg,
            fill=color
        )
        
        while True:
            await asyncio.sleep(interval)
            deg, color = deg_color(deg, d_per_tick, color)
            canvas.itemconfigure(arc, extent=deg, fill=color)

    async def updater(self, interval):
        while True:
            await asyncio.sleep(interval)
            self.update()

    def close(self):
        for task in self.tasks:
            task.cancel()
        self.loop.stop()
        self.destroy()


def deg_color(deg, d_per_tick, color):
    deg += d_per_tick
    if 360 <= deg:
        deg %= 360
        color = '#%02x%02x%02x' % (rr(0, 256), rr(0, 256), rr(0, 256))
    return deg, color


loop = asyncio.get_event_loop()
app = App(loop, interval=1/60)
loop.run_forever()
loop.close()
