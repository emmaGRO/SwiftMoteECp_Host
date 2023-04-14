# https://stackoverflow.com/questions/24849265/how-do-i-create-an-automatically-updating-gui-using-tkinter

import tkinter as tk   # PEP8: `import *` is not preferred
import datetime

# --- functions ---
# PEP8: all functions before main code
# PEP8: `lower_case_name` for funcitons
# PEP8: verb as function's name


def update_clock():
    # get current time as text
    current_time = datetime.datetime.now().strftime("Time: %H:%M:%S")

    # udpate text in Label
    lab.config(text=current_time)
    #lab['text'] = current_time

    # run itself again after 1000 ms
    root.after(1000, update_clock)

# --- main ---


root = tk.Tk()

lab = tk.Label(root)
lab.pack()

# run first time at once
update_clock()

# run furst time after 1000ms (1s)
#root.after(1000, update_clock)

root.mainloop()
