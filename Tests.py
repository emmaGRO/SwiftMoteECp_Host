import datetime
from tkinter import messagebox
import pandas as pd
import serial
from Data_processing import extract_gains
from Utils import debug
epsilon = 1e-30

class Test:
    def __init__(self,test_type:str):
        self.type = test_type
        self.parameters = {
            "E1": 0,
            "E2": 200,
            "Ep": 1,
            "Current range": 0.003,
            "Rload": 0,
            "Gain": 1
        }
        self.results = pd.DataFrame(
                        columns=[
                            "time",
                            "raw_voltages",
                            "raw_currents",
                            "baseline",
                            "normalized_gain",
                            "peak_voltage",
                            "peak_current",
                            "half_heigths",
                            "concentration",
                            "frequency"
                        ])

    def update_param(self, params:dict) -> bool:
        try:
            self.parameters.update(params)
        except Exception:
            return debug()
        return True

    def get_params(self) -> dict:
        return self.parameters

    def get_index(self):
        return self.results.index

    def get_df(self) -> pd.DataFrame:
        return self.results

    def add_result(self,index:int, _time: float, _voltage:list[float], _current:list[float], frequency:float,concentration:float = None) -> int:
        try:
            data = extract_gains(_voltage,_current)
            self.results.loc[index] = [
                _time,
                _voltage ,
                _current ,
                list(data["baseline coefs"]) ,
                list(data["gain coefs"]),
                data["peak voltage"],
                data["peak current"],
                data["half-height voltages"],
                concentration,
                frequency
                ]
            self.results.sort_index(axis=0, inplace=True)
            return 1
        except Exception:
            return debug()

    def run_test(self,comport,baudrate):
        pass


class Titration(Test):
    def __init__(self):
        super(Titration, self).__init__("Titration")
        self.parameters.update({"Frequency": 25})
        self.parameters.update({"Amplitude": 50})
        self.parameters.update({"Concentration": 0})

    def run_test(self,comport,baudrate):
        try:
            dt = datetime.datetime.now()
            dt = float(dt.timestamp() / 86400)
            ser = serial.Serial(port=comport, baudrate=baudrate)
            ser.read_all()
            data = "SWV,"
            if self.parameters["Concentration"] <= 0.0:
                return "Please enter a concentration bigger than zero"
            else:
                print(f"Titration data:")
                for param, value in self.parameters.items():
                    data = data + f"{param}:{value},"
                    print(f"{param}:{value},")
                data = data[:-1]
                ser.write(data.encode())
                _time = []
                _voltage = []
                _current = []
                _index = self.results.shape[0]
                while 1:
                    try:
                        if int(ser.inWaiting()) > 0:
                            line = ser.read(size=ser.inWaiting()).decode()
                            print(line)
                            if line.find("Done") >= 0:
                                break
                            elif line.find("time:") >= 0:
                                lst = line.split(",")
                                _time.append(float(lst[0].split(":")[1]))
                                _voltage.append(float(lst[1].split(":")[1]))
                                _current.append(float(lst[2].split(":")[1].strip()))
                    except Exception as e:
                        return e
                return self.add_result(_index, dt, _voltage, _current,self.parameters["Frequency"],self.parameters["Concentration"])
        except Exception as e:
            return e

class CV(Test):
    def __init__(self):
        super(CV,self).__init__("CV")
        self.parameters.update({"Frequency":100})
        self.parameters.update({"vertex1":0})
        self.parameters.update({"vertex2":200})
        self.parameters.update({"Cycles": 1})

    def run_test(self,comport,baudrate):
        ## do the experiment
        dt = datetime.datetime.now()
        dt = float(dt.timestamp() / 86400)
        ser = serial.Serial(port=comport, baudrate=baudrate)
        ser.read_all()
        data = "CV,"
        print(f"CV data:")
        for param, value in self.parameters.items():
            data = data + f"{param}:{value},"
            print(f"{param}:{value},")
        data = data[:-1]
        ser.write(data.encode())
        _time = []
        _voltage = []
        _current = []
        _index = self.results.shape[0]
        while 1:
            try:
                if int(ser.inWaiting()) > 0:
                    line = ser.read(size=ser.inWaiting()).decode()
                    if line.find("Done") >= 0:
                        break
                    elif line.find("experiment Starting") >= 0:
                        experiment_started = True
                    elif line.find("time:") >= 0:
                        lst = line.split(",")
                        _time.append(float(lst[0].split(":")[1]))
                        _voltage.append(float(lst[1].split(":")[1]))
                        _current.append(float(lst[2].split(":")[1].strip()))

            except Exception:
                return debug()
        return self.add_result(_index, dt, _voltage, _current, self.parameters["Frequency"])

class SWV(Test):
    def __init__(self):
        super(SWV, self).__init__("SWV")
        self.parameters.update({"Frequency": 25})
        self.parameters.update({"Amplitude": 50})

    def run_test(self,comport,baudrate):
        ## do the experiment
        dt = datetime.datetime.now()
        dt = float(dt.timestamp() / 86400)
        ser = serial.Serial(port=comport, baudrate=baudrate)
        ser.read_all()
        data = "SWV,"
        print(f"SWV data:")
        for param, value in self.parameters.items():
            data = data + f"{param}:{value},"
            print(f"{param}:{value},")
        data = data[:-1]
        ser.write(data.encode())
        _time = []
        _voltage = []
        _current = []
        _index = self.results.shape[0]
        while 1:
            try:
                if int(ser.inWaiting()) > 0:
                    line = ser.read(size=ser.inWaiting()).decode()
                    print(line)
                    if line.find("Done") >= 0:
                        break
                    elif line.find("time:") >= 0:
                        lst = line.split(",")
                        _time.append(float(lst[0].split(":")[1]))
                        _voltage.append(float(lst[1].split(":")[1]))
                        _current.append(float(lst[2].split(":")[1].strip()))
            except Exception:
                return debug()
        return self.add_result(_index, dt, _voltage, _current, self.parameters["Frequency"])

if __name__ == "__main__":
    pass