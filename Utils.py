import inspect
import traceback

import numpy as np
import pandas as pd


def get_closest_index_in_series(value, sorted_series):
    """
    Search sorted_series for the closest value/point index by value
    Returns the index of the closest value in sorted_series.
    Value can be float and does not need to be exactly in the sorted_series.
    Value can be less, inbetween, equal to, or greater than all values in sorted_series.
    Fast algorithm with O(log(N)) difficulty.
    Assumes sorted_series is sorted in ascending order.
    """

    try:

        if value >= sorted_series.iloc[-1]:
            return len(sorted_series) - 1

        right_index = np.searchsorted(sorted_series, value)
        right_index = min(len(sorted_series) - 1, right_index)  # cannot be outside the list
        left_index = max(right_index - 1, 0)  # cannot be negative

        if abs(sorted_series.iloc[left_index] - value) >= abs(sorted_series.iloc[right_index] - value):
            return right_index
        else:
            return left_index
    except Exception as e:
        debug()
        print(e)
        return 0


def debug():
    """Prints the most recent error and stack """
    # Prints latest error message
    print(traceback.format_exc())

    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    pd.set_option('display.max_colwidth', None)

    buff = []
    for i in inspect.stack()[1:]:
        buff.append([i.filename, i.function, i.lineno, i.code_context])

    # Prints where this function was called from
    print(pd.DataFrame(buff,
                       columns=['filename', 'function', 'lineno', 'code_context']
                       )
          )

# def twos_comp(val, bits):
#     """Computes the 2's complement of int value val
#     https://stackoverflow.com/questions/1604464/twos-complement-in-python"""
#
#     if (val & (1 << (bits - 1))) != 0:  # if sign bit is set e.g., 8bit: 128-255
#         val = val - (1 << bits)  # compute negative value
#     return val  # return positive value as is


# def hex_to_float(hex_str):
#     """Converts hex string to float"""
#     return struct.unpack('f', bytes.fromhex(hex_str))[0]
