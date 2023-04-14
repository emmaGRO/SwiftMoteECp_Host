import asyncio
import datetime
import json
import math
import os
import struct
import tkinter as tk
import warnings
from tkinter import filedialog
from tkinter import messagebox
from tkinter import ttk

import matplotlib
import nest_asyncio
import numpy as np
import pandas as pd
from dateutil import tz
from matplotlib import pyplot as plt

import BLE_connector_Bleak
import Dummy_connector
from SW_Voltammogram import SW_Voltammogram
from Utils import get_closest_index_in_series, debug

# hotfix to run nested asyncio to correctly close Bleak without having to wait for timeout to reconnect to device again
nest_asyncio.apply()

matplotlib.use('TkAgg')  # Makes sure that all windows are rendered using tkinter

address_default = 'FE:B7:22:CC:BA:8D'
uuids_default = ['340a1b80-cf4b-11e1-ac36-0002a5d5c51b', ]
write_uuid = '330a1b80-cf4b-11e1-ac36-0002a5d5c51b'

DUMMY_DATA = True  # set to True to use dummy data instead of data sent over Bluetooth
# SMOOTHING_COEFFICIENT = 100  # number of raw samples to use for calculation of each filtered point
# SIGN = -1  # set to 1 or -1 if filtered_currents plot looks inverted

if DUMMY_DATA:
    sender_SWV = 0
else:
    # This represents electrode number 1, in case there will be several electrodes in the future.
    # This number changes depending on in which order services/characteristics/descriptors are announced,
    # it can be changed in the firmware
    sender_SWV = 17

    sender_battery_voltage = "battery_voltage"

SUPPRESS_WARNINGS = True
if SUPPRESS_WARNINGS:
    warnings.filterwarnings("ignore")


class App(tk.Tk):
    """Main window of app based on tkinter framework.
    Runs asynchronously, dynamically scheduling which loop to run next depending on intervals."""

    def __init__(self, loop: asyncio.AbstractEventLoop):
        """

        :param loop: parent event loop for asynchronous execution, it is not unique in this app
        """
        super().__init__()
        self.loop = loop

        def on_button_close():  # stop tasks before close the window.
            try:
                print('Exiting...')
                try:
                    self.loop.run_until_complete(self.stop_scanning_handle())
                    self.loop.run_until_complete(self.BLE_connector_instance.disconnect())
                except Exception as e:  # in case DUMMY_DATA==True, scanning handle does not exist
                    pass

                for task in self.tasks:
                    task.cancel()
                self.loop.stop()
                self.destroy()
                print('Exiting finished!')
            except Exception as e:
                print(e)
                debug()
                tk.messagebox.showerror('Error', e.__str__())

        self.protocol("WM_DELETE_WINDOW", on_button_close)  # the red x button
        self.wm_title("SwiftMoteEC")
        self.iconbitmap('ico/favicon.ico')

        self.geometry("1500x1000")  # the size of the GUI

        # initialize the right part of the GUI
        frameGraph = tk.Frame(master=self,
                              highlightbackground="black",
                              highlightthickness=1
                              )  # div
        self.init_plots(master=frameGraph)

        # Initialize the left part of the GUI
        frameControls = tk.Frame(master=self,
                                 highlightbackground="black",
                                 highlightthickness=1
                                 )  # div
        self.init_controls(master=frameControls)

        # Packing order is important. Widgets are processed sequentially and if there
        # is no space left, because the window is too small, they are not displayed.
        # The canvas is rather flexible in its size, so we pack it last which makes
        # sure the UI controls are displayed as long as possible.
        frameControls.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        frameGraph.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.init_storage()

        self.tasks = []  # list of tasks to be continuously executed at the same time (asynchronously, not in parallel)

        # Use either Bleak or BleuIO
        # self.tasks.append(
        #    loop.create_task(self.get_data_loop_bleuio(interval=0))
        # )
        self.tasks.append(
            loop.create_task(self.register_data_callbacks_bleak())
        )
        self.tasks.append(
            loop.create_task(self.update_plot_loop(interval=1.0))  # update the plot part of the window
        )  # matplotlib is slow with large amounts of data, so update every second
        self.tasks.append(
            loop.create_task(self.update_ui_loop(interval=1 / 60))  # update window in general
        )
        self.tasks.append(
            loop.create_task(self.update_battery_loop(interval=5))
        )
        self.tasks.append(
            loop.create_task(self.autosave_loop(percentage_of_time=20))
        )

    def init_plots(self, master):
        """Initializes plots

        param master: reference to parent object
        """
        plt.rcParams['axes.grid'] = True  # enables all grid lines globally

        self.fig = plt.figure(dpi=100)

        self.subplots = {}

        self.subplots[0] = self.fig.add_subplot(2, 2, 1)
        # may be make self.subplots[1] in 3d ?
        # (current differential peak (%), concentration (log Mole/L) frequency (log Hz)),
        # see test19.py or test20.py as an example
        self.subplots[1] = self.fig.add_subplot(2, 2, 2)
        self.subplots[2] = self.fig.add_subplot(2, 2, 3)
        self.subplots[3] = self.fig.add_subplot(2, 2, 4)
        # self. = self.fig.add_subplot(2, 2, 3, projection='3d')

        self.subplots[0].set_xlabel("Time (s)")
        self.subplots[0].set_ylabel("Concentration (mol/L)")
        self.subplots[1].set_xlabel("Signal gain (%)")
        self.subplots[1].set_ylabel("Concentration (mol/L)")  # Calibration curve with error bars and lookup lines
        self.subplots[2].set_xlabel("Time (s)")
        self.subplots[2].set_ylabel("Jitter(s)")  # Battery/signal strength can be also on this plot
        self.subplots[3].set_xlabel("Stimulus (mV)")
        self.subplots[3].set_ylabel("Current (mA)")  # Filtered current is on the same plot

        self.subplots[0].set_yscale('log')
        self.subplots[1].set_yscale('log')

        # For full date and time use '%Y-%m-%d %H:%M:%S.%f'
        # Automatic date and time formatting does not look good on every scale
        self.subplots[0].get_xaxis().set_major_formatter(
            matplotlib.dates.DateFormatter('', tz=tz.gettz())  # don't draw time, it takes too much space on screen
        )
        self.subplots[0].get_xaxis().set_major_locator(matplotlib.dates.AutoDateLocator())
        self.subplots[0].get_xaxis().set_minor_locator(matplotlib.ticker.AutoMinorLocator())
        self.subplots[0].get_yaxis().set_major_locator(matplotlib.ticker.LogLocator(base=10.0,
                                                                                    numticks=40
                                                                                    )
                                                       )
        self.subplots[0].get_yaxis().set_minor_locator(matplotlib.ticker.LogLocator(base=10.0,
                                                                                    subs=np.arange(2, 10) * .1,
                                                                                    numticks=100
                                                                                    )
                                                       )

        self.subplots[1].get_xaxis().set_major_locator(matplotlib.ticker.AutoLocator())
        self.subplots[1].get_xaxis().set_minor_locator(matplotlib.ticker.AutoMinorLocator())
        self.subplots[1].get_yaxis().set_major_locator(matplotlib.ticker.LogLocator(base=10.0,
                                                                                    numticks=40
                                                                                    )
                                                       )
        self.subplots[1].get_yaxis().set_minor_locator(matplotlib.ticker.LogLocator(base=10.0,
                                                                                    subs=np.arange(2, 10) * .1,
                                                                                    numticks=100
                                                                                    )
                                                       )

        self.subplots[2].get_xaxis().set_major_formatter(matplotlib.dates.DateFormatter('%Y-%m-%d %H:%M:%S.%f',
                                                                                        # display in local timezone
                                                                                        tz=tz.gettz()
                                                                                        )
                                                         )
        self.subplots[2].get_xaxis().set_major_locator(matplotlib.dates.AutoDateLocator())
        self.subplots[2].get_xaxis().set_minor_locator(matplotlib.ticker.AutoMinorLocator())
        self.subplots[2].get_yaxis().set_major_locator(matplotlib.ticker.AutoLocator())
        self.subplots[2].get_yaxis().set_minor_locator(matplotlib.ticker.AutoMinorLocator())

        self.subplots[3].get_xaxis().set_major_locator(matplotlib.ticker.AutoLocator())
        self.subplots[3].get_xaxis().set_minor_locator(matplotlib.ticker.AutoMinorLocator())
        self.subplots[3].get_yaxis().set_major_locator(matplotlib.ticker.AutoLocator())
        self.subplots[3].get_yaxis().set_minor_locator(matplotlib.ticker.AutoMinorLocator())

        plt.setp(self.subplots[0].get_xticklabels(), rotation=-45, horizontalalignment='left')
        plt.setp(self.subplots[2].get_xticklabels(), rotation=-45, horizontalalignment='left')

        self.lines = {}

        self.lines[0] = self.subplots[0].plot([], [], 'x-')[0]
        self.lines[1] = self.subplots[2].plot([], [], 'x-')[0]
        self.lines[2] = self.subplots[3].plot([], [], 'x-')[0]
        self.lines[3] = self.subplots[3].plot([], [], 'x-')[0]
        # self.lines[4] = self..scatter3D([], [], [], cmap='Greens')

        self.canvas = matplotlib.backends.backend_tkagg.FigureCanvasTkAgg(self.fig,
                                                                          master=master
                                                                          )  # A tk.DrawingArea.

        # pack_toolbar=False will make it easier to use a layout manager later on.
        self.toolbar = matplotlib.backends.backend_tkagg.NavigationToolbar2Tk(canvas=self.canvas,
                                                                              window=master,
                                                                              pack_toolbar=False
                                                                              )

        # remove some buttons at the bottom of the plot part of the window
        self.toolbar.toolitems = (
            # ('Home', 'Reset original view', 'home', 'home'),
            # ('Back', 'Back to previous view', 'back', 'back'),
            # ('Forward', 'Forward to next view', 'forward', 'forward'),
            # (None, None, None, None),
            ('Pan', 'Left button pans, Right button zooms\nx/y fixes axis, CTRL fixes aspect', 'move', 'pan'),
            ('Zoom', 'Zoom to rectangle\nx/y fixes axis', 'zoom_to_rect', 'zoom'),
            # ('Subplots', 'Configure subplots', 'subplots', 'configure_subplots'),
            # (None, None, None, None),
            ('Save', 'Save the figure', 'filesave', 'save_figure')
        )

        # Reinitialize the toolbar to apply button changes. This is a bit of a hack. Change if there is a better way.
        self.toolbar.__init__(canvas=self.canvas,
                              window=master,
                              pack_toolbar=False
                              )

        # this is for future use, for example to use a special key to complete an action
        self.canvas.mpl_connect("key_press_event",  # TODO add any bindings if required
                                lambda event: print(f"you pressed {event.key}")
                                )
        # this is for future use, will pass the action to matplotlib and reflect it in the plot
        self.canvas.mpl_connect("key_press_event",
                                matplotlib.backend_bases.key_press_handler
                                )

        # last_id_closest = -1

        self.cursors_v = {}  # define vertical lines of the cursors

        self.cursors_v[0] = self.subplots[0].axvline(x=0, color='b')
        self.cursors_v[1] = self.subplots[1].axvline(x=0, color='b')
        self.cursors_v[2] = self.subplots[2].axvline(x=0, color='b')
        self.cursors_v[3] = self.subplots[3].axvline(x=0, color='b')
        self.cursors_v['datapoint_select_x_0'] = self.subplots[0].axvline(x=0, color='k')
        self.cursors_v['datapoint_select_x_2'] = self.subplots[2].axvline(x=0, color='k')
        self.cursors_v['peak_voltage_1'] = self.subplots[1].axvline(x=0, color='r')
        self.cursors_v['peak_voltage_3'] = self.subplots[3].axvline(x=0, color='r')
        self.cursors_v['Peak_voltage_boundary_1_3'] = self.subplots[3].axvline(x=0, color='k')
        self.cursors_v['Peak_voltage_boundary_2_3'] = self.subplots[3].axvline(x=0, color='k')

        self.cursors_h = {}  # define horizontal lines of the cursors

        self.cursors_h[0] = self.subplots[0].axhline(y=0, color='b')
        self.cursors_h[1] = self.subplots[1].axhline(y=0, color='b')
        self.cursors_h[2] = self.subplots[2].axhline(y=0, color='b')
        self.cursors_h[3] = self.subplots[3].axhline(y=0, color='b')
        self.cursors_h['datapoint_select_y_0'] = self.subplots[0].axhline(y=0, color='k')
        self.cursors_h['datapoint_select_y_1'] = self.subplots[1].axhline(y=0, color='k')
        self.cursors_h['peak_current_1'] = self.subplots[1].axhline(y=0, color='r')
        self.cursors_h['peak_current_3'] = self.subplots[3].axhline(y=0, color='r')

        self.datapoint_is_fixed = False

        self.datapoint_coursors_are_visible = False  # speed optimization

        def onmove(event):
            """This function is called whenever cursor is moved on the plot part of the window"""

            def update_selected_datapoint():
                # the closest element in sorted list of time in float format (number of days since 1970.01.01)
                if self.checkbutton_show_latest_voltammogram_var.get():
                    self.cursors_v['datapoint_select_x_0'].set_visible(False)
                    self.cursors_v['datapoint_select_x_2'].set_visible(False)
                    self.cursors_h['datapoint_select_y_0'].set_visible(False)
                    self.cursors_h['datapoint_select_y_1'].set_visible(False)
                    self.datapoint_is_fixed = False
                    self.datapoint_select_N = -1  # TODO fix visualization lag when cursor is not moving
                else:
                    if not self.datapoint_is_fixed:
                        self.cursors_v['datapoint_select_x_0'].set_visible(True)
                        self.cursors_v['datapoint_select_x_2'].set_visible(True)
                        self.cursors_h['datapoint_select_y_0'].set_visible(True)
                        self.cursors_h['datapoint_select_y_1'].set_visible(True)
                        self.datapoint_select_N = get_closest_index_in_series(value=event.xdata,
                                                                              sorted_series=
                                                                              self.dfs[sender_SWV]['time']
                                                                              )
                        datapoint_select_X = self.dfs[sender_SWV]['time'].iloc[self.datapoint_select_N]
                        datapoint_select_Y = self.dfs[sender_SWV]['concentration'].iloc[self.datapoint_select_N]

                        self.cursors_v['datapoint_select_x_0'].set_data(
                            [datapoint_select_X, datapoint_select_X],
                            [0, 1])
                        self.cursors_v['datapoint_select_x_2'].set_data(
                            [datapoint_select_X, datapoint_select_X],
                            [0, 1])

                        self.cursors_h['datapoint_select_y_0'].set_data([0, 1],
                                                                        [datapoint_select_Y,
                                                                         datapoint_select_Y])
                        self.cursors_h['datapoint_select_y_1'].set_data([0, 1],
                                                                        [datapoint_select_Y,
                                                                         datapoint_select_Y])

                self.to_update_plots = True  # To update voltammogram plot

            try:
                # x = event.xdata
                # y = event.ydata
                # event.inaxes.plot(x, y, 'ro')
                # event.canvas.draw()
                if event.inaxes is not None and sender_SWV in self.dfs.keys():
                    # print(event.__dict__)
                    if not self.datapoint_coursors_are_visible:
                        for i in range(4):
                            self.cursors_v[i].set_visible(True)
                            self.cursors_h[i].set_visible(True)
                        self.datapoint_coursors_are_visible = True

                    if event.inaxes is self.subplots[0]:
                        self.cursors_v[0].set_data([event.xdata, event.xdata], [0, 1])
                        self.cursors_h[0].set_data([0, 1], [event.ydata, event.ydata])

                        # this allows updating cursor on other subplots
                        self.cursors_h[1].set_data([0, 1], [event.ydata, event.ydata])
                        self.cursors_v[2].set_data([event.xdata, event.xdata], [0, 1])

                        update_selected_datapoint()

                    elif event.inaxes is self.subplots[1]:
                        self.cursors_v[1].set_data([event.xdata, event.xdata], [0, 1])
                        self.cursors_h[1].set_data([0, 1], [event.ydata, event.ydata])

                        self.cursors_h[0].set_data([0, 1], [event.ydata, event.ydata])
                    elif event.inaxes is self.subplots[2]:
                        self.cursors_v[2].set_data([event.xdata, event.xdata], [0, 1])
                        self.cursors_h[2].set_data([0, 1], [event.ydata, event.ydata])

                        self.cursors_v[0].set_data([event.xdata, event.xdata], [0, 1])

                        update_selected_datapoint()
                    elif event.inaxes is self.subplots[3]:
                        self.cursors_v[3].set_data([event.xdata, event.xdata], [0, 1])
                        self.cursors_h[3].set_data([0, 1], [event.ydata, event.ydata])
                else:  # hide if mouse cursor is in area between axis
                    if self.datapoint_coursors_are_visible:
                        for i in range(4):
                            self.cursors_v[i].set_visible(False)
                            self.cursors_h[i].set_visible(False)
                        self.datapoint_coursors_are_visible = False

                self.canvas.draw()

            except OSError:
                pass  # No data to display, not an error
            except Exception as e:
                debug()
                print(e)

        def onclick(event):  # TODO
            try:
                # x = event.xdata
                # y = event.ydata
                # event.inaxes.plot(x, y, 'ro')
                # event.canvas.draw()
                if event.inaxes is not None:
                    # print(event.__dict__)

                    if event.inaxes is self.subplots[0]:
                        self.datapoint_is_fixed = not self.datapoint_is_fixed
                    elif event.inaxes is self.subplots[1]:
                        pass
                    elif event.inaxes is self.subplots[2]:
                        self.datapoint_is_fixed = not self.datapoint_is_fixed
                    elif event.inaxes is self.subplots[3]:
                        pass
                    self.canvas.draw()
            except Exception as e:
                debug()
                print(e)

        self.canvas.mpl_connect('motion_notify_event', onmove)
        # click on the plot, fix/unfix closest datapoint (stay still until another action)
        self.canvas.mpl_connect('button_press_event', onclick)

        def apply_tight_layout(event: tk.Event):
            """when resize the whole window, the plot part of the window is resized """
            try:
                if event.widget.widgetName == "canvas":
                    self.fig.tight_layout()
            except Exception as e:
                pass

        self.bind("<Configure>", apply_tight_layout)  # resize plots when window size changes, "Configure" comes from tk

        self.to_update_plots = False

        self.toolbar.pack(side=tk.BOTTOM, fill=tk.BOTH)
        self.canvas.get_tk_widget().pack(side=tk.BOTTOM, fill=tk.BOTH, expand=1)

    def init_controls(self, master):
        """Initializes controls

        param master: reference to parent object
        """
        font = 'Helvetica 15 bold'
        self.current_values = {}  # values from variable fields, can be changed by user in real time

        frameControlsInputOutput = tk.Frame(master=master,
                                            highlightbackground="black",
                                            highlightthickness=1
                                            )  # div
        tk.Label(master=frameControlsInputOutput,
                 text="I/O",
                 font=font,
                 ).pack(side=tk.TOP, fill=tk.BOTH)

        def on_button_load_json():
            try:
                print('Loading from .json ...')
                self.checkbutton_pause_accepting_new_data_var.set(1)
                self.init_storage()
                filename = tk.filedialog.askopenfilename(parent=self, title='Choose a file')
                print(filename)
                with open(filename, 'r') as f:
                    # https://stackoverflow.com/questions/1450957/pythons-json-module-converts-int-dictionary-keys-to-strings
                    # Standard JSON does not allow integers as keys, so convert str to int when possible
                    temp = json.load(f, object_hook=lambda d: {int(k) if k.lstrip('-').isdigit()
                                                               else k: v for k, v in d.items()
                                                               }
                                     )

                for key, value in temp.items():
                    self.dfs[int(key)] = pd.DataFrame.from_dict(temp[key],
                                                                orient='index',
                                                                )
                    self.transaction_counters[int(key)] = len(temp[key]) - 1

                self.to_update_plots = True
                print('Loading finished!')
            except Exception as e:
                print(e)
                debug()
                tk.messagebox.showerror('Error', e.__str__())

        def on_button_file_save():
            try:
                print('Saving to .json ...')

                mask = [('Json File', '*.json'),
                        ('All Files', '*.*'),
                        ]

                save_temp = {}
                for key in self.dfs.keys():
                    save_temp[key] = self.dfs[key].to_dict(orient='index')

                name = datetime.datetime.now().strftime('experiment_%Y-%m-%d_%H-%M-%S')
                extension_name = tk.StringVar()
                f = tk.filedialog.asksaveasfile(filetypes=mask,
                                                initialfile=name,
                                                defaultextension=".json",
                                                mode='x',  # does not overwrite file if it exists
                                                typevariable=extension_name
                                                )
                print(extension_name.get())
                if extension_name.get() == 'Json File':
                    # https://stackoverflow.com/questions/1450957/pythons-json-module-converts-int-dictionary-keys-to-strings
                    json.dump(save_temp, f, indent=4)  # TODO , default=str
                    f.close()
                elif extension_name.get() == 'All Files':
                    json.dump(save_temp, f, indent=4)
                    f.close()
                else:
                    print('Unknown file extension or file name was not selected')
                    # tk.messagebox.showerror('Error', 'Unknown file extension or file name was not selected')
                    return

            except Exception as e:
                print(e)
                debug()
                tk.messagebox.showerror('Error', e.__str__())


            else:
                print('Saving finished!')
                tk.messagebox.showinfo('Info', 'Saving finished!')

        def on_button_folder_save():
            """Save individual voltammograms into separate *.csv files in the same folder"""
            try:
                print('Saving to folder ...')

                current_directory = filedialog.askdirectory()

                for i, voltammogram in enumerate(self.dfs[sender_SWV].itertuples()):
                    file_name = "voltammogram_" + str(i) + ".csv"
                    file_path = os.path.join(current_directory, file_name)
                    print(file_path)

                    df = pd.DataFrame({'Potential/V': voltammogram.filtered_voltages[1::2],
                                       'i1d/A': voltammogram.filtered_currents[1::2],
                                       'i1f/A': voltammogram.raw_currents[1::2],
                                       'i1r/A': ([0] + voltammogram.raw_currents)[1:-1:2]
                                       }
                                      )

                    df.to_csv(file_path, index=False)




            except Exception as e:
                print(e)
                debug()
                tk.messagebox.showerror('Error', e.__str__())
            else:
                print('Saving to folder finished!')
                tk.messagebox.showinfo('Info', 'Saving finished!')

        tk.Button(master=frameControlsInputOutput,
                  text="Load from *.json",
                  command=on_button_load_json
                  ).pack(side=tk.BOTTOM, fill=tk.X)
        tk.Button(master=frameControlsInputOutput,
                  text="Save into 1 file",
                  command=on_button_file_save
                  ).pack(side=tk.BOTTOM, fill=tk.X)

        tk.Button(master=frameControlsInputOutput,
                  text="Save multiple files into 1 folder",
                  command=on_button_folder_save
                  ).pack(side=tk.BOTTOM, fill=tk.X)

        frameControlsConnection = tk.Frame(master=master,
                                           highlightbackground="black",
                                           highlightthickness=1
                                           )  # div
        tk.Label(master=frameControlsConnection, text="Select device", font=font).pack(side=tk.TOP)

        def refresh_BLE_devices():
            """Called when opening the drop-down with nearby devices,
            pulling info from local device dictionary, sorts by signal strength, and displays on screen"""
            try:
                # print('Click1')
                devices_list = []
                for device in self.dict_of_devices_global.values():  # dictionary of devices is updated asynchronously
                    devices_list.append(str(device.address) + "/" + str(device.name) + "/" + str(device.rssi))
                devices_list.sort(key=lambda x: -float(x.split("/")[-1]))  # sort by rssi (last element)
                self.device_cbox['values'] = devices_list
            except Exception as e:
                print(e)
                debug()
                tk.messagebox.showerror('Error',
                                        'Please set "DUMMY_DATA = False" to scan for devices\n\n' + e.__str__())

        def apply_selected_BLE_device(event):
            """Connect to the device selected, disconnect from previous device first"""
            # print('Click2')

            conected_device_address = self.device_cbox_value.get().split("/")[0]
            print("Connecting to address:", conected_device_address)
            self.loop.run_until_complete(self.BLE_connector_instance.disconnect())
            # replace address inside old instance
            # either use address or BLEDevice instance as parameter
            # self.BLE_connector_instance.__init__(self.dict_of_devices_global[conected_device_address])
            self.BLE_connector_instance.__init__(conected_device_address)

        self.device_cbox_value = tk.StringVar()
        self.device_cbox = tk.ttk.Combobox(master=frameControlsConnection,
                                           values=[],
                                           textvariable=self.device_cbox_value,
                                           postcommand=refresh_BLE_devices,
                                           width=40,
                                           )
        self.device_cbox.bind('<<ComboboxSelected>>', apply_selected_BLE_device)

        self.device_cbox.pack(side=tk.TOP, fill=tk.X)

        frameControlsFeedback = tk.Frame(master=master,
                                         highlightbackground="black",
                                         highlightthickness=1,
                                         )  # div
        tk.Label(master=frameControlsFeedback, text="Feedback", font=font).pack(side=tk.TOP)
        frameControlsFeedbackGrid = tk.Frame(master=frameControlsFeedback)
        frameControlsFeedbackGrid.pack(side=tk.TOP, anchor=tk.N)  # div 2
        width = 10

        tk.Label(master=frameControlsFeedbackGrid, text="E1").grid(row=0, column=0, sticky='W')
        self.current_values['E1'] = tk.StringVar()
        spin_box = tk.Spinbox(
            master=frameControlsFeedbackGrid,
            values=list(range(-1000, 1005, 5)),
            textvariable=self.current_values['E1'],
            wrap=True,
            width=width)
        self.current_values['E1'].set('-500')
        spin_box.grid(row=0, column=1)
        tk.Label(master=frameControlsFeedbackGrid, text="(mV)").grid(row=0, column=2, sticky='W')

        tk.Label(master=frameControlsFeedbackGrid, text="E2").grid(row=1, column=0, sticky='W')
        self.current_values['E2'] = tk.StringVar()
        spin_box = tk.Spinbox(
            master=frameControlsFeedbackGrid,
            values=list(range(-1000, 1005, 5)),
            textvariable=self.current_values['E2'],
            wrap=True,
            width=width)
        self.current_values['E2'].set('200')
        spin_box.grid(row=1, column=1)
        tk.Label(master=frameControlsFeedbackGrid, text="(mV)").grid(row=1, column=2, sticky='W')

        tk.Label(master=frameControlsFeedbackGrid, text="Ep").grid(row=2, column=0, sticky='W')
        self.current_values['Ep'] = tk.StringVar()
        spin_box = tk.Spinbox(
            master=frameControlsFeedbackGrid,
            values=list(range(-100, 101, 1)),
            textvariable=self.current_values['Ep'],
            wrap=True,
            width=width)
        self.current_values['Ep'].set('50')
        spin_box.grid(row=2, column=1)
        tk.Label(master=frameControlsFeedbackGrid, text="(mV)").grid(row=2, column=2, sticky='W')

        tk.Label(master=frameControlsFeedbackGrid, text="Estep").grid(row=3, column=0, sticky='W')
        self.current_values['Estep'] = tk.StringVar()
        spin_box = tk.Spinbox(
            master=frameControlsFeedbackGrid,
            values=list(range(0, 55, 5)),
            textvariable=self.current_values['Estep'],
            wrap=True,
            width=width)
        self.current_values['Estep'].set('1')
        spin_box.grid(row=3, column=1)
        tk.Label(master=frameControlsFeedbackGrid, text="(mV)").grid(row=3, column=2, sticky='W')

        tk.Label(master=frameControlsFeedbackGrid, text="Frequency").grid(row=4, column=0, sticky='W')
        self.current_values['Frequency'] = tk.StringVar()
        spin_box = tk.Spinbox(
            master=frameControlsFeedbackGrid,
            values=list(range(0, 10005, 5)),
            textvariable=self.current_values['Frequency'],
            wrap=True,
            width=width)
        self.current_values['Frequency'].set('1000')
        spin_box.grid(row=4, column=1)
        tk.Label(master=frameControlsFeedbackGrid, text="(Hz)").grid(row=4, column=2, sticky='W')

        tk.Label(master=frameControlsFeedbackGrid, text="Delay").grid(row=5, column=0, sticky='W')
        self.current_values['Delay'] = tk.StringVar()
        spin_box = tk.Spinbox(
            master=frameControlsFeedbackGrid,
            values=list(np.arange(0, 31, 1)),  # to support fractional values
            textvariable=self.current_values['Delay'],
            wrap=True,
            width=width)
        self.current_values['Delay'].set('2')
        spin_box.grid(row=5, column=1)
        tk.Label(master=frameControlsFeedbackGrid, text="(s)").grid(row=5, column=2, sticky='W')

        tk.Label(master=frameControlsFeedbackGrid, text="Interval").grid(row=6, column=0, sticky='W')
        self.current_values['Interval'] = tk.StringVar()
        spin_box = tk.Spinbox(
            master=frameControlsFeedbackGrid,
            values=list(range(0, 125, 5)),
            textvariable=self.current_values['Interval'],
            wrap=True,
            width=width)
        self.current_values['Interval'].set('30')
        spin_box.grid(row=6, column=1)
        tk.Label(master=frameControlsFeedbackGrid, text="(s)").grid(row=6, column=2, sticky='W')

        def on_button_send_to_device():
            # https://docs.python.org/3/library/struct.html
            try:
                buff = struct.pack('<iiHHHfH',  # TODO change data types as required
                                   int(self.current_values['E1'].get()),  # can be negative
                                   int(self.current_values['E2'].get()),  # can be negative
                                   int(self.current_values['Ep'].get()),
                                   int(self.current_values['Estep'].get()),
                                   int(self.current_values['Frequency'].get()),
                                   float(self.current_values['Delay'].get()),
                                   int(self.current_values['Interval'].get()),
                                   )
                print(buff)
                self.loop.run_until_complete(
                    self.BLE_connector_instance.write_characteristic(char_uuid=write_uuid, data=buff)
                )
            except Exception as e:
                print(e)
                debug()
                tk.messagebox.showerror('Error', e.__str__())

        tk.Button(
            master=frameControlsFeedback,
            text="Send to device",
            command=on_button_send_to_device
        ).pack(side=tk.BOTTOM, fill=tk.X)

        frameControlsPlotSettings = tk.Frame(master=master,
                                             highlightbackground="black",
                                             highlightthickness=1,
                                             )  # div
        tk.Label(master=frameControlsPlotSettings, text="Plot settings", font=font).pack(side=tk.TOP)

        self.checkbutton_autoresize_X_var = tk.IntVar(value=1)
        tk.Checkbutton(master=frameControlsPlotSettings,
                       text="Maximize X",
                       variable=self.checkbutton_autoresize_X_var
                       ).pack(side=tk.TOP, fill=tk.X)

        self.checkbutton_autoresize_Y_var = tk.IntVar(value=1)
        tk.Checkbutton(master=frameControlsPlotSettings,
                       text="Maximize Y",
                       variable=self.checkbutton_autoresize_Y_var
                       ).pack(side=tk.TOP, fill=tk.X)

        self.checkbutton_show_latest_voltammogram_var = tk.IntVar(value=1)
        tk.Checkbutton(master=frameControlsPlotSettings,
                       text="Show latest voltammogram",
                       variable=self.checkbutton_show_latest_voltammogram_var
                       ).pack(side=tk.TOP, fill=tk.X)

        self.checkbutton_pause_plotting_var = tk.IntVar(value=0)
        tk.Checkbutton(master=frameControlsPlotSettings,
                       text="Pause plotting",
                       variable=self.checkbutton_pause_plotting_var
                       ).pack(side=tk.TOP, fill=tk.X)

        self.checkbutton_pause_accepting_new_data_var = tk.IntVar(value=0)
        tk.Checkbutton(master=frameControlsPlotSettings,
                       text="Pause saving",
                       variable=self.checkbutton_pause_accepting_new_data_var
                       ).pack(side=tk.TOP, fill=tk.X)

        self.checkbutton_invert_new_voltammograms_var = tk.IntVar(value=0)
        tk.Checkbutton(master=frameControlsPlotSettings,
                       text="Invert new voltammograms",
                       variable=self.checkbutton_invert_new_voltammograms_var
                       ).pack(side=tk.TOP, fill=tk.X)

        frameControlsVoltammogramGrid = tk.Frame(master=frameControlsPlotSettings)
        frameControlsVoltammogramGrid.pack(side=tk.TOP, anchor=tk.N)  # div 2
        width = 10

        tk.Label(master=frameControlsVoltammogramGrid, text="Smoothing and bias coefficient").grid(row=0, column=0,
                                                                                                   sticky='W')
        self.current_values['Smoothing and bias coefficient'] = tk.StringVar()
        spin_box = tk.Spinbox(
            master=frameControlsVoltammogramGrid,
            values=list(range(2, 1002, 2)),
            textvariable=self.current_values['Smoothing and bias coefficient'],
            wrap=True,
            width=width)
        self.current_values['Smoothing and bias coefficient'].set('100')
        spin_box.grid(row=0, column=1)
        tk.Label(master=frameControlsVoltammogramGrid, text="(#)").grid(row=0, column=2, sticky='W')

        tk.Label(master=frameControlsVoltammogramGrid, text="Reference peak current").grid(row=1, column=0, sticky='W')
        self.current_values['Reference peak current'] = tk.StringVar()
        spin_box = tk.Spinbox(
            master=frameControlsVoltammogramGrid,
            values=list(np.arange(0.00005, 0.01, 0.00005)),
            textvariable=self.current_values['Reference peak current'],
            wrap=True,
            width=width)
        self.current_values['Reference peak current'].set('0.00005')
        spin_box.grid(row=1, column=1)
        tk.Label(master=frameControlsVoltammogramGrid, text="(A)").grid(row=1, column=2, sticky='W')

        tk.Label(master=frameControlsVoltammogramGrid, text="Peak voltage boundary 1").grid(row=2, column=0, sticky='W')
        self.current_values['Peak voltage boundary 1'] = tk.StringVar()
        spin_box = tk.Spinbox(
            master=frameControlsVoltammogramGrid,
            values=list(np.arange(-1000, 1002, 2)),
            textvariable=self.current_values['Peak voltage boundary 1'],
            wrap=True,
            width=width)
        self.current_values['Peak voltage boundary 1'].set('-500')
        spin_box.grid(row=2, column=1)
        tk.Label(master=frameControlsVoltammogramGrid, text="(mV)").grid(row=2, column=2, sticky='W')

        tk.Label(master=frameControlsVoltammogramGrid, text="Peak voltage boundary 2").grid(row=3, column=0, sticky='W')
        self.current_values['Peak voltage boundary 2'] = tk.StringVar()
        spin_box = tk.Spinbox(
            master=frameControlsVoltammogramGrid,
            values=list(np.arange(-1000, 1002, 2)),
            textvariable=self.current_values['Peak voltage boundary 2'],
            wrap=True,
            width=width)
        self.current_values['Peak voltage boundary 2'].set('500')
        spin_box.grid(row=3, column=1)
        tk.Label(master=frameControlsVoltammogramGrid, text="(mV)").grid(row=3, column=2, sticky='W')

        # frameControlsPID = tk.Frame(master=master,
        #                            highlightbackground="black",
        #                            highlightthickness=1
        #                            )  # div
        # tk.Label(master=frameControlsPID, text="PID", font=font).pack(side=tk.TOP)
        #
        frameControlsInfo = tk.Frame(master=master,
                                     highlightbackground="black",
                                     highlightthickness=1
                                     )  # div
        # tk.Label(master=frameControlsInfo, text="Info", font=font).pack(side=tk.TOP)
        # frameControlsFeedbackGrid = tk.Frame(master=frameControlsInfo)  # div 2
        # frameControlsFeedbackGrid.pack(side=tk.TOP, fill=tk.X)
        #
        # tk.Label(master=frameControlsFeedbackGrid, text="RSSI:").grid(row=0, column=0, sticky='W')
        # self.current_values['RSSI'] = tk.StringVar()
        # tk.Label(master=frameControlsFeedbackGrid, text="-127", textvariable=self.current_values['RSSI']).grid(row=0,
        #                                                                                                       column=1,
        #                                                                                                       sticky='W')

        frameControlsInputOutput.pack(side=tk.TOP, fill=tk.BOTH, expand=False)
        frameControlsConnection.pack(side=tk.TOP, fill=tk.BOTH, expand=False)
        frameControlsFeedback.pack(side=tk.TOP, fill=tk.BOTH, expand=False)

        frameControlsPlotSettings.pack(side=tk.TOP, fill=tk.BOTH, expand=False)
        # frameControlsPID.pack(side=tk.TOP, fill=tk.BOTH, expand=False)
        frameControlsInfo.pack(side=tk.TOP, fill=tk.BOTH,
                               expand=True)  # this element is pushing everything else from the bottom

    # async def get_data_loop_bleuio(self, interval):
    #    """Adds new data into Dataframe"""
    #    self.instance = await BLE_connector_BleuIO.create_BLE_connector()
    #    print(self.instance)
    #    async for data in self.instance.get_more_data(interval=interval):
    #        try:
    #            # print(data)
    #            self.df.loc[data['N']] = [twos_comp(int(data['Hex'][0:4], 16), 16),
    #                                      twos_comp(int(data['Hex'][4:8], 16), 16),
    #                                      twos_comp(int(data['Hex'][8:12], 16), 16),
    #                                      data['Time'],
    #                                      ]  # use either time or N as index
    #        except Exception as e:
    #            print(e)

    # initialize dataframes used to store raw data and the processed data, in dictionary type
    def init_storage(self):
        """internal storage for saving, loading, buffering processed data
        dictionary of data frames"""
        # TODO add a button to empty storage?
        try:
            print('Init dataframes ...')
            # self.dfs = klepto.archives.file_archive(name='output/out', dict={}, cached=True)
            self.dfs = {}
            self.transaction_counters = {}
            self.datapoint_select_N = -1
            print('Init dataframes finished!')
        except Exception as e:
            print(e)
            debug()

    async def register_data_callbacks_bleak(self):
        """Sets up notifications using Bleak, and attaches callbacks"""
        # initialize time variables
        self.last_transaction_time = datetime.datetime(2999, 1, 1, 0, 0, 0, 0,
                                                       tzinfo=datetime.timezone.utc)  # to trigger offset adjustment
        self.offest_time = datetime.timedelta(days=0, seconds=0, microseconds=0)
        self.last_time_best_effort = datetime.datetime.now(datetime.timezone.utc)
        self.time_changed_threshold = 0

        if DUMMY_DATA:
            temp_dummy_connector = Dummy_connector.Dummy_connector()
            async for debug_data_joined in temp_dummy_connector.get_dummy_data():
                await self.on_new_data_callback_SWV(sender=0,
                                                    data=bytearray(b'debug'),
                                                    debug_data_joined=debug_data_joined
                                                    )
        else:
            # create an object, but not connect yet
            self.BLE_connector_instance = BLE_connector_Bleak.BLE_connector(to_connect=False)
            await self.start_scanning_process()
            await self.BLE_connector_instance.keep_connections_to_device(uuids=uuids_default,
                                                                         callbacks=[self.on_new_data_callback_SWV,
                                                                                    ]
                                                                         # TODO add more callbacks if required,
                                                                         # TODO eg to add more electrodes or to accept different types of voltammograms
                                                                         )

    async def on_new_data_callback_SWV(self,
                                       sender,
                                       data: bytearray = bytearray(b'\x01\x02\x03\x04'),
                                       debug_data_joined=None):
        """Called whenever Bluetooth API receives a notification or indication
        Temporarily saves data packets and saves several of them to form a Transaction,
        which is later processed as SWV (Square Wave Voltammogram)

        param sender: handle, should be unique for each uuid
        param data: data received, several messages might be received together if data rate is high
        """

        if debug_data_joined is None:
            debug_data_joined = []

        try:
            # Solution:
            # https://stackoverflow.com/a/61049837
            time_delivered = datetime.datetime.now(datetime.timezone.utc)  # .timestamp()

            if DUMMY_DATA:
                # naive implementation without simulating low level protocol,
                # assumes that data is already successfully received,
                # does not use Transaction
                data_joined = debug_data_joined

                time_best_effort = time_delivered
                # jitter_best_effort = datetime.timedelta(seconds=0.1)

                jitter_best_effort = time_best_effort - self.last_time_best_effort
                self.last_time_best_effort = time_best_effort

                # transaction_min_creation = time_delivered
                # transaction_min_delivery = time_delivered
                # transaction_number = 0
            else:
                # print(data.hex())
                status, transaction = self.process_packet(data=data, time_delivered=time_delivered)
                if status != 0:  # Transaction is not complete
                    return

                data_joined = transaction.get_joined_data()
                if data_joined == None:
                    return

                    # Time can only increment. If it decremented, it likely means BlueNRG chip rebooted.
                if self.last_transaction_time <= transaction.get_min_time_of_transaction_creation():
                    # Time incremented or stayed the same
                    pass
                else:
                    #  This self.offest_time might be stale,
                    #  set offset after receiving and discarding 1 full Transaction to flush TX buffer
                    self.time_changed_threshold += 1
                    if self.time_changed_threshold > 1:
                        self.time_changed_threshold = 0

                        # Calculate new offset
                        self.offest_time = transaction.get_min_time_of_transaction_delivery() - \
                                           transaction.get_min_time_of_transaction_creation()
                        print('Time decremented, offset adjusted', self.offest_time)
                    else:
                        print("Likely stale data, discarding Transaction")
                        return
                self.last_transaction_time = transaction.get_min_time_of_transaction_creation()

                time_best_effort = transaction.get_min_time_of_transaction_creation() + self.offest_time
                jitter_best_effort = time_best_effort - self.last_time_best_effort
                self.last_time_best_effort = time_best_effort

                # transaction_min_creation = transaction.get_min_time_of_transaction_creation()
                # transaction_min_delivery = transaction.get_min_time_of_transaction_delivery()
                # transaction_number = transaction.transaction_number

            if self.checkbutton_pause_accepting_new_data_var.get():
                return

            # print(data_joined)
            # TODO add opportunity to recalculate past data
            voltammogram = SW_Voltammogram(data_joined,
                                           n=int(self.current_values['Smoothing and bias coefficient'].get()),
                                           sign=(1 if int(self.checkbutton_invert_new_voltammograms_var.get()) == 1
                                                 else -1
                                                 ),
                                           reference_peak_current=float(
                                               self.current_values['Reference peak current'].get()
                                           ),
                                           E1=float(self.current_values['E1'].get()),
                                           E2=float(self.current_values['E2'].get()),
                                           Ep=float(self.current_values['Ep'].get()),
                                           # Estep=0.0,  # affects number of points, not used
                                           # Freqw=0.0,  # not used
                                           # Delay=0.0  # not used
                                           peak_voltage_boundary_1=float(
                                               self.current_values['Peak voltage boundary 1'].get()
                                           ),
                                           peak_voltage_boundary_2=float(
                                               self.current_values['Peak voltage boundary 2'].get()
                                           ),
                                           )

            if sender not in self.dfs.keys():  # if data recieved from this sender very first time, create new Dataframe
                self.dfs[sender] = pd.DataFrame(
                    columns=[  # "N",
                        "time",
                        "readable_time",
                        # "time_of_creation_without_offset",
                        # "offset_time",
                        # "time_of_delivery",
                        "jitter",
                        # "transaction_number",

                        "E1",
                        "E2",
                        "Ep",
                        "Peak_voltage_boundary_1",
                        "Peak_voltage_boundary_2",

                        "raw_voltages",
                        "raw_currents",
                        "filtered_voltages",
                        "filtered_currents",
                        "peak_voltage",
                        "peak_current",

                        "signal_gain",
                        "concentration"
                    ]
                )
                # self.dfs[sender] = self.dfs[sender].set_index("N")  # TODO

            if sender in self.transaction_counters:
                self.transaction_counters[sender] += 1
            else:
                self.transaction_counters[sender] = 0

            #  May be not stable in case of multi threading (so have to use async)
            self.dfs[sender].loc[self.transaction_counters[sender]] = [
                time_best_effort.timestamp() / 86400,  # days since 1970-01-01 in UTC, this is required for matplotlib
                time_best_effort.astimezone().strftime("%Y-%m-%d %H:%M:%S:%f %z"),
                # transaction_min_creation.timestamp(),
                # self.offest_time.total_seconds(),
                # transaction_min_delivery.timestamp(),
                jitter_best_effort.total_seconds(),
                # for debugging, if transaction number increments by 2, it means a transaction was lost.
                # If it decrements, it likely means BlueNRG chip rebooted or transaction number has overflown
                # transaction_number,

                voltammogram.E1,
                voltammogram.E2,
                voltammogram.Ep,
                voltammogram.peak_voltage_boundary_1,
                voltammogram.peak_voltage_boundary_2,

                voltammogram.raw_voltages,
                voltammogram.raw_currents,
                voltammogram.filtered_voltages,
                voltammogram.filtered_currents,
                voltammogram.peak_voltage,
                voltammogram.peak_current,

                voltammogram.signal_gain,
                voltammogram.concentration
            ]

            self.to_update_plots = True
        except ValueError as e:
            print(e)
            debug()
        except Exception as e:
            print(e)
            debug()
            tk.messagebox.showerror('Error', e.__str__())

    def process_packet(self, data, time_delivered):
        """Processes a packet and returns transaction when finalized
        Worst part of the code, needs to be optimized, but I don't know how"""
        transaction_finished = None

        if "transaction_in_progress" not in dir(self):  # if not defined, create new transaction
            self.transaction_in_progress = Transaction()  # Transaction object, called only when the app starts
        #  -1: transaction is complete, -2: transaction was just completed because new transaction code was detected
        if self.transaction_in_progress.add_packet(data=data, time_delivered=time_delivered) in [-1, -2]:
            # if error, maybe it is beginning of a new transaction? Try to add packet second time
            transaction_finished = self.transaction_in_progress  # save reference of the previous transaction that has completed
            self.transaction_in_progress = Transaction()  # create a new Transaction object, used in the following transactions
            # -2 should never happen
            if self.transaction_in_progress.add_packet(data=data, time_delivered=time_delivered) == -1:
                # print("Error of starting new transaction, datahex: ", datahex)
                return -1, None

        if transaction_finished != None and transaction_finished.finalized:
            return 0, transaction_finished
        if self.transaction_in_progress.finalized:  # Will execute only if 1 packet was expected, in theory
            return 0, self.transaction_in_progress
        else:
            # print("Transaction is not complete yet")
            return -2, None

    async def update_plot_loop(self, interval):
        """Updates plots inside UI, at regular intervals

        param interval: minimum time between 2 updates, time of execution is taken in account
        """

        print('Plotting started')

        waiter = StableWaiter(interval=interval)
        while True:
            try:
                await waiter.wait_async()

                if self.to_update_plots == False or self.checkbutton_pause_plotting_var.get() == True:
                    # optimization to prevent re-drawing when there is no new data or when plotting is paused
                    continue
                    # pass
                self.to_update_plots = False

                limits = self.subplots[0].axis()
                plot_width_last_frame = limits[1] - limits[0]
                right_side_limit_now = self.dfs[sender_SWV]['time'].iloc[-1]

                # Don't plot invisible data-points, works well when there is no scaling between frames,
                # but may cause not rendering first several data-points properly if scale changes between steps.
                # df_visible = self.dfs[sender_SWV].loc[
                #              max(0, math.floor(right_side_limit_now - plot_width_last_frame) -
                #                  math.ceil(1 / sample_delay)):
                #              right_side_limit_now + 1
                #              ]

                df_visible = self.dfs[sender_SWV]  # TODO implement later if performance becomes an issue

                self.lines[0].set_data(df_visible['time'],
                                       df_visible['concentration'])
                self.lines[1].set_data(df_visible['time'],
                                       df_visible['jitter'])  # / np.timedelta64(1, 's')
                self.lines[2].set_data(
                    df_visible['raw_voltages'].iloc[self.datapoint_select_N],
                    df_visible['raw_currents'].iloc[self.datapoint_select_N]  # df_visible['Current'].iloc[-1]
                )  # TODO use the most recent voltammogram, change later
                self.lines[3].set_data(df_visible['filtered_voltages'].iloc[self.datapoint_select_N],
                                       df_visible['filtered_currents'].iloc[self.datapoint_select_N])

                if self.checkbutton_autoresize_X_var.get():
                    # Maximizes X axis
                    self.subplots[0].set_xlim(min(self.dfs[sender_SWV]['time']),
                                              max(self.dfs[sender_SWV]['time'])
                                              )
                    self.subplots[2].set_xlim(min(self.dfs[sender_SWV]['time']),
                                              max(self.dfs[sender_SWV]['time'])
                                              )
                    self.subplots[3].set_xlim(
                        self.dfs[sender_SWV]['E1'].iloc[self.datapoint_select_N] - self.dfs[sender_SWV]['Ep'].iloc[
                            self.datapoint_select_N] / 2,
                        self.dfs[sender_SWV]['E2'].iloc[self.datapoint_select_N] + self.dfs[sender_SWV]['Ep'].iloc[
                            self.datapoint_select_N] / 2
                    )
                else:
                    # Synchronizes X-zoom across plots(uses only subplot1 as reference) and moves to right most position
                    self.subplots[0].set_xlim(right_side_limit_now - plot_width_last_frame,
                                              right_side_limit_now
                                              )
                    self.subplots[2].set_xlim(right_side_limit_now - plot_width_last_frame,
                                              right_side_limit_now
                                              )

                if self.checkbutton_autoresize_Y_var.get():
                    self.subplots[0].set_ylim(min(df_visible['concentration']),
                                              max(df_visible['concentration'])
                                              )

                    self.subplots[2].set_ylim(min(df_visible['jitter']),
                                              max(df_visible['jitter'])
                                              )

                    self.subplots[3].set_ylim(min(min(df_visible['raw_currents'].iloc[self.datapoint_select_N]),
                                                  min(df_visible['filtered_currents'].iloc[self.datapoint_select_N])
                                                  ),
                                              max(max(df_visible['raw_currents'].iloc[self.datapoint_select_N]),
                                                  max(df_visible['filtered_currents'].iloc[self.datapoint_select_N])
                                                  )
                                              )

                self.cursors_v['peak_voltage_3'].set_data(
                    [df_visible['peak_voltage'].iloc[self.datapoint_select_N],
                     df_visible['peak_voltage'].iloc[self.datapoint_select_N]],
                    [0, 1]
                )
                self.cursors_h['peak_current_3'].set_data(
                    [0, 1],
                    [df_visible['peak_current'].iloc[self.datapoint_select_N],
                     df_visible['peak_current'].iloc[self.datapoint_select_N]]
                )
                self.cursors_v['Peak_voltage_boundary_1_3'].set_data(
                    [df_visible['Peak_voltage_boundary_1'].iloc[self.datapoint_select_N],
                     df_visible['Peak_voltage_boundary_1'].iloc[self.datapoint_select_N]],
                    [0, 1]
                )
                self.cursors_v['Peak_voltage_boundary_2_3'].set_data(
                    [df_visible['Peak_voltage_boundary_2'].iloc[self.datapoint_select_N],
                     df_visible['Peak_voltage_boundary_2'].iloc[self.datapoint_select_N]],
                    [0, 1]
                )

            except Exception as e:
                print(e)
                debug()
            finally:
                try:
                    self.canvas.draw()
                except Exception as e:
                    pass
                    # print(e)
                    # debug()

    async def update_ui_loop(self, interval):
        """Updates UI, at regular intervals

        param interval: minimum time between 2 updates, time of execution is taken in account
        """
        print('UI started')

        waiter = StableWaiter(interval=interval)
        while True:
            try:
                await waiter.wait_async()
                self.update()
            except Exception as e:
                print(e)
                debug()
                tk.messagebox.showerror('Error', e.__str__())

    async def start_scanning_process(self):
        """Starts scanning process"""

        if DUMMY_DATA:
            return

        try:
            self.stop_scanning_handle, self.dict_of_devices_global = await self.BLE_connector_instance.start_scanning()
            print('Scanning started')
            await asyncio.sleep(0.1)
        except Exception as e:
            print(e)
            debug()
            try:
                print('Stopping scanning because of an error')
                await self.stop_scanning_handle()
            except Exception as e2:
                print(e2)
                debug()
                tk.messagebox.showerror('Error', e2.__str__())
            tk.messagebox.showerror('Error', e.__str__())

    async def update_battery_loop(self, interval):
        """Updates battery voltage, at regular intervals

        param interval: minimum time between 2 updates, time of execution is taken in account
        """

        if DUMMY_DATA:
            return

        print('Battery update started')

        waiter = StableWaiter(interval=interval)
        while True:
            try:
                await waiter.wait_async()
                # self.update()
                voltage = await self.BLE_connector_instance.read_characteristic(
                    char_uuid='340a1b80-cf4b-11e1-ac36-0002a5d5c51b')
                if voltage == None:
                    continue
                print(struct.unpack('<f', voltage))
            except Exception as e:
                pass
                # print(e)
                # debug()
                # tk.messagebox.showerror('Error', e.__str__())

    async def autosave_loop(self, percentage_of_time):
        """Automatically saves data to file, at regular intervals

        param interval: minimum time between 2 updates, time of execution is taken in account
        """
        print('Battery update started')

        waiter = StableWaiter(percentage_of_time=percentage_of_time)
        i = 0
        while True:
            try:
                await waiter.wait_async_constant_avg_time()
                print(datetime.datetime.now(), 'Autosaving...', i)
                i += 1

                save_temp = {}
                for key in self.dfs.keys():
                    save_temp[key] = self.dfs[key].to_dict(orient='index')

                with open("output/autosave.json", 'w') as f:  # overwrite previous autosave
                    json.dump(save_temp, f, indent=4, default=str)
                    f.close()

            except Exception as e:
                print(e)
                debug()
                tk.messagebox.showerror('Error', e.__str__())


# def save_csv(self):
#    print('Saving to .csv ...')
#    self.df.to_csv(path_or_buf='output/out.csv')
#    print('Saving finished!')


class StableWaiter:
    """Generates intervals between executions of certain parts of code;
    two methods: constant time, and percentage of total execution time """

    def __init__(self, interval=1, percentage_of_time=10):
        self.interval = interval
        self.duty_cycle = percentage_of_time / 100
        self.t1 = datetime.datetime.now(datetime.timezone.utc)

    async def wait_async(self):
        """Waits at approximately the same intervals independently of CPU speed
        (if CPU is faster than certain threshold)
        This is not mandatory, but makes UI smoother
        Can be roughly simplified with asyncio.sleep(interval)"""

        t2 = datetime.datetime.now(datetime.timezone.utc)
        previous_frame_time = ((t2 - self.t1).total_seconds())
        self.t1 = t2

        await asyncio.sleep(min((self.interval * 2) - previous_frame_time, self.interval))

    async def wait_async_constant_avg_time(self):
        """Waits constant average time as a percentage of total execution time
        O(1) avg difficulty, used to accelerate O(N^2) or worse algorithms by running them less frequently as N increases
        This is not mandatory, but makes UI smoother
        Can be roughly simplified with asyncio.sleep(interval), for example, it is used by autosaving in this app"""

        t2 = datetime.datetime.now(datetime.timezone.utc)
        previous_frame_time = ((t2 - self.t1).total_seconds())
        self.t1 = t2

        await asyncio.sleep(previous_frame_time / self.duty_cycle - previous_frame_time)


class Packet:
    transaction_number_bytes = 1  # use 1 byte to represent transaction field
    packet_number_bytes = 1  # use 1 byte to represent packet field
    time_number_bytes = 4  # 4*1-byte fields represent time: hours, minutes, seconds, microseconds
    metadata_length_total_bytes = transaction_number_bytes + packet_number_bytes + time_number_bytes
    datapoint_length_bytes = 2  # each data point is 2 bytes

    def __init__(self, data: bytearray, time_delivered):
        """Parse packet"""
        self.data = data
        self.time_delivered = time_delivered
        # self.datahex=data.hex()

        # print(data.hex())

        self.transaction_number = struct.unpack('<B', self.data[0:0 + self.transaction_number_bytes])[0]
        self.packet_number = struct.unpack('<B', self.data[1:1 + self.packet_number_bytes])[0]
        # TODO rewrite to something like struct.unpack('<I', self.data[2:2 + self.time_bytes])
        time_packet_created = struct.unpack('<BBBB', self.data[2:2 + self.time_number_bytes])[::-1]
        # time_packet_created.reverse()
        # print(time_transmitted)

        # transmit only 24 hours of time, year/month/date is not transmitted since experiment lasts only 6 hours,
        # modify if longer interval is needed with no added jitter,
        # but it is not required since overflow will lead to auto adjustment of offset
        self.time_created = datetime.datetime(year=2000, month=1, day=1,
                                              hour=time_packet_created[0],
                                              minute=time_packet_created[1],
                                              second=time_packet_created[2],
                                              microsecond=round(
                                                  1000000 * (math.pow(2, 8) - time_packet_created[3] - 1) /
                                                  (math.pow(2, 8) + 1)
                                              ),
                                              tzinfo=datetime.timezone.utc
                                              )  # .timestamp()
        # cprint(self.time_transmitted_datetime)

        length = len(data) - self.metadata_length_total_bytes  # 2 bytes are metadata
        number_of_datapoints = math.floor(length / self.datapoint_length_bytes)  # 2 bytes per datapoint

        self.datapoints = [-1] * number_of_datapoints  # initialize list of datapoints

        for i in range(number_of_datapoints):
            # TODO process this value further,
            #  because it will be compressed
            #  (need to add offset and multiply by a coefficient to get signed floating number)
            self.datapoints[i] = struct.unpack('<H',
                                               self.data[
                                               self.metadata_length_total_bytes + self.datapoint_length_bytes * i:
                                               self.metadata_length_total_bytes + self.datapoint_length_bytes * (i + 1)
                                               ]
                                               )[0]
            # self.datapoints[i] = int(self.data[
            #                          self.metadata_length_total_bytes + self.datapoint_length_bytes * i:
            #                          self.metadata_length_total_bytes + self.datapoint_length_bytes * (i + 1)
            #                          ][::-1].hex(),
            #                          16
            #                          )

    def get_datapoints(self):
        """Data load of the BLE packet"""
        return self.datapoints


class Transaction:
    """One indivisible piece of useful data
    2 modes of operation:
    1) Size is known
    2) Size is unknown
    """

    def __init__(self, size=None):
        self.size = size
        self.packets: {Packet} = {}
        self.transaction_number = -1
        self.finalized = False

    def add_packet(self, data: bytearray, time_delivered):
        if self.finalized:
            # print("Error, this transaction is already finalized")
            return -1

        packet = Packet(data=data, time_delivered=time_delivered)  # create a Packet object

        if self.transaction_number == -1:
            # print("First packet of new transaction received")
            self.transaction_number = packet.transaction_number

        if self.transaction_number == packet.transaction_number:
            # print("Adding new packet")
            if packet.packet_number not in self.packets:
                self.packets[packet.packet_number] = packet
            else:
                print("Error, this packet was already received")
                return -1
        else:
            if self.size == None:  # if size is not set, estimate number of packets.
                print("Transaction probably finished successfully")
                self.finalized = True
                self.size = len(self.packets)
                print("Transaction size", self.size)
                return -2
            else:
                print("Error, Transaction number is different, this should never happen")
                return -1

        if len(self.packets) == self.size:
            print("Transaction finished successfully")
            self.finalized = True
            return 0
        else:
            return 1  # continue waiting for more packets

    def get_joined_data(self):
        try:
            if self.finalized:
                all_datapoints = []
                for i in range(self.size):
                    all_datapoints.extend(self.packets[i].get_datapoints())

                # removes 0s at the end, hopefully it does not delete useful data
                while len(all_datapoints) >= 1 and all_datapoints[-1] == 0:
                    all_datapoints.pop(-1)

                print(all_datapoints)

                return all_datapoints
            else:
                # print("Error, not finalized yet")
                return None
        except Exception as e:
            return None

    def get_times_of_delivery(self):
        # should be in ascending order, but no checks are done
        if self.finalized:
            all_times_of_delivery = {}
            for i in range(self.size):
                all_times_of_delivery[i] = self.packets[i].time_delivered
            return all_times_of_delivery
        else:
            # print("Error, not finalized yet")
            return None

    def get_min_time_of_transaction_delivery(self):
        if self.finalized:
            return min(self.get_times_of_delivery().values())
        else:
            return None

    def get_times_of_packet_creation(self):  # for debugging
        # should be in ascending order, but no checks are done
        if self.finalized:
            all_times_of_transmitting = {}
            for i in range(self.size):
                all_times_of_transmitting[i] = self.packets[i].time_created
            return all_times_of_transmitting
        else:
            # print("Error, not finalized yet")
            return None

    def get_min_time_of_transaction_creation(self):
        if self.finalized:
            return min(self.get_times_of_packet_creation().values())
        else:
            return None


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    app = App(loop)
    loop.run_forever()
