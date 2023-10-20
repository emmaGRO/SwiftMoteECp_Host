import  numpy as np
from scipy.signal import savgol_filter
from numpy import diff
from Utils import debug
import tkinter as tk
import pandas as pd
from typing import Union
from tkinter import messagebox
from scipy.optimize import curve_fit
from sklearn.metrics import r2_score


def load_experiment(master,filepath:str,df_type:str, exp_name:str):
    master.print(f"Loading {exp_name}")
    try:
        try:
            df_i = pd.read_json(filepath, orient="index", compression='infer')

            if df_type == 'titration':
                master.Titration_df.add_dataframe(exp_name)
            elif df_type == 'experiment':
                master.Experiment_df.add_dataframe(exp_name)

            for row in df_i.index:
                voltages = list(df_i.loc[row]["raw_voltages"])
                currents = list(df_i.loc[row]["raw_currents"])
                concentration = df_i.loc[row]["concentration"]
                frequency = df_i.loc[row]["frequency"]
                time = df_i.loc[row]["time"]
                readable_time = df_i.loc[row]["readable_time"]

                if df_type == 'titration':
                    master.Titration_df.add_data_to_df(exp_name,
                                                       time,
                                                       readable_time,
                                                       voltages,
                                                       currents,
                                                       concentration,
                                                       frequency)

                elif df_type == 'experiment':
                    master.Experiment_df.add_data_to_df(exp_name,
                                                       time,
                                                       readable_time,
                                                       voltages,
                                                       currents,
                                                       concentration,
                                                       frequency)

                else:
                    raise Exception("datafram type doesn't exists")
        except Exception as e:
            debug()
            tk.messagebox.showerror('Warning', "File not found")
            return 0

    except Exception as e:
        debug()
        tk.messagebox.showerror('Warning', "File not found")
        return 0

def extract_gains(voltages: list[float], currents:list[float]) -> dict:
    voltages = voltages[10:-10]
    currents = currents[10:-10]
    def get_peaks_and_valleys(values: list, offset: int):
        dt_peaks = []
        for val in values[1:]:
            try:
                if val > 0 and values[values.index(val) - 1] < 0:
                    dt_peaks.append(values.index(val) + offset)

                elif val < 0 and values[values.index(val) - 1] > 0:
                    dt_peaks.append(values.index(val) + offset)
            except Exception:
                return debug()
        return dt_peaks
    ############################################# determination of the peak current#######################################################################
    win_length = round(len(currents) / 4)
    if win_length % 2 == 0:
        win_length += 1
    poly = 6
    # noise = np.random.normal(-1e-9, 1e-9, len(currents))
    currents = currents #+ noise
    data_smooth = currents
    count = 0
    try:
        while count < 10:
            temp = [dt_smooth for dt_smooth in list(savgol_filter(data_smooth, window_length=win_length, polyorder=poly, mode='mirror'))]
            data_smooth = temp
            count +=1

    except ValueError:
        return debug()

    # isolating the "bump" from smoothed values
    dt_current = [current for current in list(savgol_filter([i for i in diff(data_smooth)], win_length, polyorder=poly, mode='mirror'))]
    bump_start = dt_current.index(max(dt_current))
    bump_end = dt_current.index(min(dt_current))
    # get zero between min and max, which represent the peak's index
    if bump_start < bump_end:
        zero_index = data_smooth.index(max(data_smooth[bump_start:bump_end]))
    elif bump_start > bump_end:
        zero_index = data_smooth.index(max(data_smooth[bump_end:bump_start]))
    else:
        zero_index = bump_start
    ################################# approximation of start and end of bump by derivative ##############################################################
    bump_start = data_smooth.index(data_smooth[100])
    bump_end = data_smooth.index(data_smooth[400])
    # dt = dt_current
    # bump_start = zero_index
    # bump_end = zero_index
    # count = 0
    # poly = 3
    # isBefore = True
    # isAfter = True
    # err = 0.1
    # while count <= 10:
    #     temp = [current for current in list(savgol_filter(diff(dt), win_length, polyorder=poly, mode='mirror'))]
    #     try:
    #         if isBefore:
    #             temp_ind = bump_start
    #             peaks_before = get_peaks_and_valleys(temp[:bump_start], 0)
    #             bump_start = max(x for x in peaks_before if x < bump_start)
    #             difference = (data_smooth[temp_ind] - data_smooth[bump_start]) / data_smooth[temp_ind]
    #             if difference < err:
    #                 isBefore = False
    #     except Exception:
    #         pass
    #     try:
    #         if isAfter:
    #             temp_ind = bump_end
    #             peaks_after = get_peaks_and_valleys(temp[zero_index:], zero_index)
    #             bump_end = min(x for x in peaks_after if x > bump_end)
    #             difference = (data_smooth[temp_ind] - data_smooth[bump_end]) / data_smooth[temp_ind]
    #             if difference < err:
    #                 isAfter = False
    #     except Exception:
    #         pass
    #     if not isBefore and not isAfter:
    #         break
    #
    #     dt = temp
    #     count += 1

    #################################### create baseline by adding values between start and end of bump#####################################################
    try:
        currents_split = np.append(data_smooth[:bump_start], data_smooth[bump_end:])
        voltages_split = np.append(voltages[:bump_start], voltages[bump_end:])
        baseline_coeff = np.poly1d(np.polyfit(voltages_split, currents_split, 2))
        data_baseline = [current for current in baseline_coeff(voltages)]
        normalized_gain = list([(data_smooth[i] - data_baseline[i])/data_baseline[i] for i in range(len(data_smooth))])
        #max_gain_index = normalized_gain.index(np.max(normalized_gain))
        max_gain_index = 249

        ######################################################## half heigth width #############################################################################
        half_gain = np.max(normalized_gain) / 2
        abs_dict = {i: abs(gain - half_gain) for i,gain in enumerate(normalized_gain[:max_gain_index])}
        pt1 = min(abs_dict, key=abs_dict.get)

        abs_dict = {i+max_gain_index: abs(gain - half_gain) for i, gain in enumerate(normalized_gain[max_gain_index:])}
        pt2 = min(abs_dict, key=abs_dict.get)

    except Exception:
        return debug()
    else:
        gain_coeff = np.poly1d(np.polyfit(voltages, normalized_gain, 6))
        return {"gain coefs":gain_coeff,
                "baseline coefs":baseline_coeff,
                "peak current": currents[max_gain_index],
                "peak voltage": voltages[max_gain_index],
                "half-height voltages": [voltages[pt1], voltages[pt2]]}


class HillFit:
    def __init__(
            self,
            x_data: Union[list[float], np.ndarray],
            y_data: Union[list[float], np.ndarray],
            *,
            bottom_param: bool = True,
    ) -> None:
        self.x_data = np.array(x_data)
        self.y_data = np.array(y_data)
        self.bottom_param = bottom_param

    def _equation(self, x: np.ndarray, *params) -> np.ndarray:
        self.top = params[0]
        self.bottom = params[1] if self.bottom_param else 0
        self.ec50 = params[2]
        self.nH = params[3]

        return self.bottom + (self.top - self.bottom) * x ** self.nH / (
                self.ec50 ** self.nH + x ** self.nH)

    def _get_param(self, curve_fit_kws: dict) -> list[float]:
        try:
            min_data = np.amin(self.y_data)
            max_data = np.amax(self.y_data)

            h = abs(max_data - min_data)
            param_initial = [max_data, min_data, 0.5 * (self.x_data[-1] - self.x_data[0]), 1]
            param_bounds = (
                [max_data - 0.5 * h, min_data - 0.5 * h, self.x_data[0] * 0.1, 0.01],
                [max_data + 0.5 * h, min_data + 0.5 * h, self.x_data[-1] * 10, 100],
            )
            curve_fit_kws.setdefault("p0", param_initial)
            curve_fit_kws.setdefault("bounds", param_bounds)
            popt, _ = list(curve_fit(self._equation, self.x_data, self.y_data, **curve_fit_kws))
            return [float(param) for param in popt]
        except Exception:
            debug()

    def fitting(self,sigfigs: int = 6):
        try:
            curve_fit_kws = {}
            self.x_fit = np.logspace(
                np.log10(self.x_data[0]), np.log10(self.x_data[-1]), len(self.y_data)
            )
            params = self._get_param(curve_fit_kws)
            self.y_fit = self._equation(self.x_fit, *params)
            self.r_2 = r2_score(self.y_data, self.y_fit)
        except ValueError:
            self.r_2 = 1000
        else:
            self.equation = f"{round(self.bottom, sigfigs)} + ({round(self.top, sigfigs)}-{round(self.bottom, sigfigs)})*x**{(round(self.nH, sigfigs))} / ({round(self.ec50, sigfigs)}**{(round(self.nH, sigfigs))} + x**{(round(self.nH, sigfigs))})"
            self.params = params