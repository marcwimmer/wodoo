"""
Puts all settings into one settings file
"""
import sys
from module_tools.myconfigparser import MyConfigParser

outfile = sys.argv[1]
setting_files = sys.argv[2].split("\n")

c = MyConfigParser(outfile)

for file in setting_files:
    if not file:
        continue
    c2 = MyConfigParser(file)
    c.apply(c2)
c.write()
