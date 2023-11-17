import json
from Data_processing import extract_gains
import pandas as pd
import pickle

class titration():
    def __init__(self, electrode_name, name, folder: str, titration_df):
        self.electrode_name = electrode_name
        self.name = name
        self.path = folder
        self.titration_df = titration_df

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
                "smooth_data",
                "concentration",
                "frequency"
            ])

    def get_df(self):
        return self.titration_df

    def save_titration(self, data):
        data.to_dict(orient='records')
        file_path = f"{self.path}//{self.electrode_name}({self.name}).csv"
        # Save DataFrame to a CSV file
        data.to_csv(file_path, index=False)  # Set index=False to not write row numbers

    def save(self, filepath:str):
        filepath = f"{filepath}\\{self.name}"
        with open(filepath, 'wb') as outp:  # Overwrites any existing file.
            pickle.dump(self, outp, pickle.HIGHEST_PROTOCOL)


    if __name__ == "__main__":
        pass