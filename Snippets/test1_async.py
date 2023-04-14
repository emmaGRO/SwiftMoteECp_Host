import asyncio
from cProfile import label
import tkinter as tk   # PEP8: `import *` is not preferred
import datetime


async def update_time():
    global label

    for i in range(10):
        current_time = datetime.datetime.now().strftime("Time: %H:%M:%S")
        label.config(text=current_time)
        #label['text'] = current_time
        # root.update()
        print('test1')

        await asyncio.sleep(2)


async def gui():
    global label

    root = tk.Tk()
    label = tk.Label(root)
    label.pack()
    asyncio.sleep(1)

    root.mainloop()


async def main():
    global label

    task1 = asyncio.create_task(update_time())
    task2 = asyncio.create_task(gui())
    # value1 = await task1
    # value2 = await task2

    asyncio.sleep(10)


asyncio.run(main())
