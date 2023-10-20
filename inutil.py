for variable, value in test.get_params().items():
    if variable != "Rload" and variable != "Gain" and variable != "Rtia":
        self.Entry_box["state"]=tk.NORMAL)
    else:
        if variable == "Rload":
            self.Combo_box
        elif variable == "Gain":
            self.gain_Cbox
        elif variable == "Rtia":
            self.Rtia_Ebox
