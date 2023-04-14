import pandas as pd
import matplotlib.pyplot as plt

# files = ['./tek0006.csv',
#         './tek0007.csv',
#         './tek0010.csv',
#         './tek0003CH1.csv'
#         ]
files = ['./tek0026.csv',
         './tek0027.csv',
         './tek0028.csv',
         ]

for file in files:
    df = pd.read_csv(file, header=19, index_col=0)
    print('------------------------------------------------------')
    print(file)
    print(df.head())
    print(df.describe())
    df.hist(bins=50)
    plt.show()
    print('------------------------------------------------------')
