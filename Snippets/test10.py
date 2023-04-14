import pandas as pd

multi_index = pd.MultiIndex.from_tuples([("r0", "rA"),
                                         ("r1", "rB")],
                                        names=['Courses', 'Fee'])

print(multi_index)
