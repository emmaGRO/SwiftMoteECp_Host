import pickle

from dateutil import parser
from tkinter import filedialog
import os
from Electrode import Electrode
from  Utils import debug
import pandas as pd


def process_CH_File(master, data_folder, test_type: str):
    try:
        data_path = find_data_filepath()
        if data_path is None:
            return
        if test_type == "Titration":
            concentration = find_concentration_file()
            if concentration is not None:
                with open(concentration) as Conc_file:
                    temp_concentration = Conc_file.read().split()
                    concentration_list = [float(item)for item in temp_concentration]
            else:
                return
            if concentration_list[0] == 0:
                concentration_list[0] = concentration_list[1]
        electrode_list = {}
        for fi in os.listdir(data_path):
            if fi.__contains__(".txt") and fi.__contains__("Hz_"):
                ##################################### opeining file to get data ################
                try:
                    df = pd.read_table(data_path + "\\" + fi, encoding='utf-8')
                except UnicodeEncodeError:
                    print("cant open utf-8")
                    try:
                        df = pd.read_table(data_path + "\\" + fi, encoding='ANSI')
                    except UnicodeEncodeError as e:
                        print("cant open ansi")
                        break
                ##############################################################
                dt = str(df.iloc[0]).split("    ")[0]
                dt = parser.parse(dt)
                exp_datetime = float(dt.timestamp() / 86400)
                df = pd.read_csv(data_path + "\\" + fi, header=7)

                file = fi.replace(".txt", "")
                for i in range(10):
                    file = file.replace("__", "_")
                file = file.split("_")
                frequency = int(file[-2].replace("Hz", ""))
                experiment_name = f'{str(file[-3])}_{frequency}Hz'
                sample = int(file[-1])
                index = 1
                for i in range(1, df.shape[1] - 1, 3): # splitting CH file into electrodes
                    electrode_name = f"E{str(index)}_{str(file[-3])}"

                    if electrode_name in os.listdir(f"{os.getcwd()}\\data"): # if electrode not in list but is saved in data, load it and add to list
                        with open(f"{os.getcwd()}\\data\\{electrode_name}", "rb") as f:
                            electrode_list[electrode_name] = (pickle.load(f))
                        # print(f'{electrode_name} already in data folder')

                    elif electrode_name in electrode_list.keys(): # if electrode is already in the list, pass
                        # print(f'{electrode_name} already in list')
                        pass

                    else:
                        electrode_list[electrode_name] = Electrode(electrode_name) # else, create new electrode
                        # print(f'creating {electrode_name}')

                    if experiment_name not in electrode_list[electrode_name].get_experiments():
                        electrode_list[electrode_name].create_experiment(experiment_name)
                        # print(f'creating experiment {experiment_name} for {electrode_name}')

                    exp = electrode_list[electrode_name].get_tests(experiment_name)
                    sorted_vals = sorted(list(zip(df.iloc[:, 0].tolist(), df.iloc[:,i].tolist())))
                    voltages = [val[0] for val in sorted_vals]
                    currents = [val[1] * 1e6 for val in sorted_vals]
                    exp[test_type].add_result(sample, exp_datetime, voltages, currents, frequency, concentration_list[sample - 1])
                    index += 1


                master.print(str(fi) + ' processed')

        master.print('All files have been processed without error')

        for electrode in electrode_list.values():
            electrode.save(data_folder)

        return electrode_list
    except Exception as e:
        debug()
        master.print(f"{e}")
        return 0


def find_data_filepath():
    filepath = filedialog.askdirectory(title="Please Select CH data folder")
    if os.path.isdir(filepath):
        return filepath


def find_concentration_file():
    filepath = filedialog.askopenfilename(title="Please Select CH concentration file", filetypes=(("text files", "*.txt"),))
    if os.path.isfile(filepath):
        return filepath
