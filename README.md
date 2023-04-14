# SwiftMote

Host side PC application software



# Design decisions

Use JSON as format to store and load data to hard drive.
In the future, if RAM consumption becomes an issue, use 'dask dataframe', 'shelve', 'klepto', etc. 
to save data to hard drive while keeping cache(?) in RAM, if all data does not fit in RAM at once.

- It will be easier to implement backward compatibility between multiple versions of a program.

# Setup environment:
Use Python 3.9 or 3.10, you can get it from https://www.python.org/downloads/

Use Anaconda environment with:
conda env create -f environment.yml

As IDE use PyCharm or VSCode

Build the application as a .exe file:
install pyinstaller and run in the project folder
 $ pyinstaller --onefile  --distpath . --clean -w -i .\ico\SwiftLogo.ico SwiftMote_gui.py
 
if there is recursion errors try:
$ pyinstaller SwiftMote_gui.py
then open .spec file and add 

import sys
sys.setrecursionlimit(5000)

to the beginning of the file

then run pyinstaller SwiftMote_gui.spec

To create an installer for ease of portability:
copy the .exe file in the /dist folder to the main folder, then zip the main folder and run NSIS
<<<<<<< HEAD
 Dowload NSIS and use Installer based on .zip file on the zipped folder of the project
=======
 Download NSIS and use Installer based on .zip file on the zipped folder
>>>>>>> abc496be995a0f97d0377ffe69ab9774f08f8abb
 
 # DLLs folder
Using SensorPal api for eval-board management. Must be deleted since swiftmote will run on own firmware,not on sensorpal's api
