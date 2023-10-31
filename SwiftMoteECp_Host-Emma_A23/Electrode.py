import pickle
from Tests import *
import os

class Electrode:
    def __init__(self,name:str):
        self.name = name
        self.experiments = {}

    def create_experiment(self,experiment_name:str):
        self.experiments[experiment_name] = {"Titration": Titration(),
                                             "CV": CV(),
                                             "SWV":SWV()}
    def get_experiments(self) -> list:
        return list(self.experiments.keys())

    def del_experiment(self,name):
        if name in  self.experiments:
            self.experiments.pop(name)

    def get_tests(self,experiment_name:str) -> dict:
        return self.experiments[experiment_name]

    def save(self,filepath:str):
        filepath = f"{filepath}\\{self.name}"
        with open(filepath, 'wb') as outp:  # Overwrites any existing file.
            pickle.dump(self, outp, pickle.HIGHEST_PROTOCOL)

    def delete(self,filepath:str):
        os.remove(f"{filepath}\\{self.name}")
        del self
if __name__ == "__main__":
    pass


