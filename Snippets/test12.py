import csv
import matplotlib.pyplot as plt
import numpy as np
import matplotlib

x = []
y = []
diff = {}
diff2 = {}

matplotlib.use('TkAgg')

with open('sample CV.csv') as csvfile:
    spamreader = csv.reader(csvfile)
    for row in spamreader:
        print(row)
        a = float(row[0])
        b = float(row[1])

        x.append(a)
        y.append(b)

        if a in diff:
            diff[a].append(b)
            diff2[a] = diff[a][0] - diff[a][1]
        else:
            diff[a] = [b]

# plt.style.use('seaborn-whitegrid')


plt.plot(x, y, list(diff2.keys()), list(diff2.values()), '+', color='black')
plt.show()
