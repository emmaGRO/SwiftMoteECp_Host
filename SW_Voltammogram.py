import numpy as np
import pandas as pd

from Utils import get_closest_index_in_series


class SW_Voltammogram:
    """Square wave voltammogram class
    processes and caches all square wave voltammogram data"""

    def __init__(self,
                 datapoints,
                 n=4,
                 sign=-1,
                 reference_peak_current=1.0,
                 E1=-500.,
                 E2=200.,
                 Ep=50.,
                 peak_voltage_boundary_1=-500.0,
                 peak_voltage_boundary_2=500.0
                 ):

        self.raw_currents = datapoints
        self.n = n
        self.sign = sign
        self.reference_peak_current = reference_peak_current
        self.E1 = E1
        self.E2 = E2  # Assume it is bottom of the square wave, not middle. TODO Check with oscilloscope later.
        self.Ep = Ep
        self.peak_voltage_boundary_1 = peak_voltage_boundary_1
        self.peak_voltage_boundary_2 = peak_voltage_boundary_2

        #  Store intermediate values so that there is no need to recalculate them and for easier debugging

        self.raw_voltages = self.get_estimated_raw_voltages(start=self.E1,
                                                            finish=self.E2,
                                                            step_potential=self.Ep,
                                                            number_of_samples=len(self.raw_currents)
                                                            )
        self.coefficients = self.get_coofficients(n=self.n,
                                                  sign=self.sign
                                                  )
        self.filtered_currents = self.get_convolution(raw_currents=self.raw_currents,
                                                      coefficients=self.coefficients
                                                      )
        self.filtered_voltages = self.get_estimated_filtered_voltages(start=self.E1,
                                                                      finish=self.E2,
                                                                      number_of_samples=len(self.filtered_currents)
                                                                      )

        self.peak_voltage, self.peak_current = self.get_peak(filtered_voltages=self.filtered_voltages,
                                                             filtered_currents=self.filtered_currents,
                                                             peak_voltage_boundary_1=self.peak_voltage_boundary_1,
                                                             peak_voltage_boundary_2=self.peak_voltage_boundary_2
                                                             )
        self.equalized_peak_current = self.get_equalized_peak_current(peak_current=self.peak_current,
                                                                      reference_peak_current=self.reference_peak_current
                                                                      )
        self.signal_gain = self.get_signal_gain(equalized_peak_current=self.equalized_peak_current)
        self.concentration = self.get_concentration(signal_gain=self.signal_gain)

    def get_coofficients(self, n: int = 4, sign: int = -1):
        """
        Larger n means stronger noise filtering
        Recommended to use even values >=4
        Value 3 provides the highest resolution and lowest noise filtering, allows some bias
        Value 2 ignores bias caused by hysteresis, legacy

        Properties of generated series:
        Sum must be 0
        Center of mass must be in the middle (2 is exception)
        Even number of coefficients helps remove bias and gives more equal positive/negative noise distribution
        """

        if n <= 1:
            return []
        if n == 2:
            if sign == 1:
                return [1, -1]  # ignores bias
            else:
                return [-1, 1]
        if sign == 1:
            coefficients = [0.5, -1., 0.5]  # partially ignores bias since it is odd number of coefficients
        else:
            coefficients = [-0.5, 1., -0.5]

        for _ in range(n - 3):
            new_coefficients = []
            for c1, c2 in zip([0] + coefficients,
                              coefficients + [0]):
                new_coefficients.append(sign * ((abs(c1) + abs(c2)) / 2.0))
                sign *= -1
            coefficients = new_coefficients
        return coefficients

    def get_convolution(self, raw_currents, coefficients):
        # since voltage is unknown precisely, it is easier to use "same" instead of "valid" mode for graphing,
        # but it causes some artifacts which potentially may affect determined maximum peak value
        # may shift answer either left or right by 1 because of offset rounding (causes vertical inversion)

        conv = list(np.convolve(raw_currents, coefficients, mode='same'))
        conv_final = []
        for i, element in enumerate(conv):
            if i % 2:  # negate every other value
                conv_final.append(element)
            else:
                conv_final.append(-element)
        return conv_final

    def get_peak(self, filtered_voltages, filtered_currents, peak_voltage_boundary_1, peak_voltage_boundary_2):
        # https://stackoverflow.com/questions/2474015/getting-the-index-of-the-returned-max-or-min-item-using-max-min-on-a-list
        # Fast finding of maximum peak

        peak_boundary_1_index = get_closest_index_in_series(peak_voltage_boundary_1, pd.Series(filtered_voltages))
        peak_boundary_2_index = get_closest_index_in_series(peak_voltage_boundary_2, pd.Series(filtered_voltages))

        bounded_filtered_voltages = filtered_voltages[peak_boundary_1_index: peak_boundary_2_index + 1]
        bounded_filtered_currents = filtered_currents[peak_boundary_1_index: peak_boundary_2_index + 1]

        index = max(range(len(bounded_filtered_currents)), key=bounded_filtered_currents.__getitem__)

        return bounded_filtered_voltages[index], bounded_filtered_currents[
            index]  # TODO maybe truncate to region of interest?

    def get_equalized_peak_current(self, peak_current, reference_peak_current):
        return peak_current / reference_peak_current

    def get_signal_gain(self, equalized_peak_current):
        return (equalized_peak_current - 1) * 100

    def get_concentration(self, signal_gain):
        # TODO use a smooth function (either hardcoded or modifiable at runtime), change later
        # TODO add error bands for given gain(?), use resampling(?)
        return max((signal_gain + 1) * 2, 0.000000001)  # to correctly display on log scale

    def get_estimated_raw_voltages(self, start, finish, step_potential, number_of_samples):
        """Assumes distance between samples is the same (it is not always the case!)
        This function is required if voltage is not transmitted over Bluetooth to save energy
        """

        ans = []
        for i, voltage in enumerate(
                np.linspace(start - step_potential / 2,
                            finish - step_potential / 2,
                            number_of_samples
                            )
        ):
            if i % 2:
                ans.append(voltage + step_potential)
            else:
                ans.append(voltage)
        return ans

    def get_estimated_filtered_voltages(self, start, finish, number_of_samples):
        return list(np.linspace(start, finish, number_of_samples))
