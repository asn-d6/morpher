#!/bin/python

import sys
import math
import subprocess
import os

MODEL_FILENAME = "morpher.mod"
DATA_FILENAME = "morpher.data"
SOLUTION_FILENAME = "morpher.sol"

PROLOGUE = "data;\n\n"

SET_STRING = "set PACKET_SIZE"
SOURCE_PARAM_STRING = "param source :="
TARGET_PARAM_STRING = "param target :="

EPILOGUE = "end;\n"

"""
Represents a GLPK data file.
"""
class DataFile:
    def __init__(self, filename, source, target):
        self.filename = filename

        if (len(source) != len(target)):
            print "Packet length distributions have different size."
            sys.exit(1)

        self.source = source
        self.target = source
        self.size = len(self.source)

        if (self.size <= 0):
            print "0 size distribution"
            sys.exit(1)

    """Write data file to disk."""
    def create_data_file(self):
        f = open(self.filename, 'w')
        f.write(PROLOGUE)
        f.write(self.get_set_string())
        f.write(self.get_param_string(type="source"))
        f.write(self.get_param_string(type="false"))
        f.write(EPILOGUE)

    def get_set_string(self):
        string = ""
        ran = range(self.size)

        string += SET_STRING
        for i in ran:
            string += " "
            string += str(i)

        string += ";\n\n"
        return string

    def get_param_string(self, type):
        string = ""

        if type == "source":
            string += SOURCE_PARAM_STRING
            distr = self.source
        else:
            string += TARGET_PARAM_STRING
            distr = self.target

        ran = range(self.size)
        for num in ran:
            string += "\n"
            string += "\t"
            string += str(num)
            string += " "
            string += distr[num]

        string += ";\n\n"
        return string


INTERESTING_FILE_SECTION = \
"""
   No. Column name  St   Activity     Lower bound   Upper bound    Marginal
------ ------------ -- ------------- ------------- ------------- -------------
"""
#    8 morph[0,7]   B          0.625

"""
Parse the solution file of glpsol and print the morphing matrix.
"""
def parse_and_print_solution_file(filename):
    morphing_matrix = []

    f = open(SOLUTION_FILENAME)
    solution = f.read()
    f.close()

    assert(INTERESTING_FILE_SECTION in solution)
    matrix_section = solution.split(INTERESTING_FILE_SECTION)[1]

    entries = matrix_section.split("\n")
    ran = range(len(entries))

    for i in ran:
        substr = entries[i]
        if (substr == ""):
            break

        substr = ' '.join(substr.split())
        morphing_matrix.append(substr.split(" ")[3])


    n = len(morphing_matrix)
    size = math.sqrt(n)
    # must not be a float.
    assert(size == int(size))
    size = int(size)

    for i in range(n):
        if (i % (size-1) == 0):
            print morphing_matrix[i]
        else:
            print morphing_matrix[i],

"""Given a filename wit hthe following format:

<packet length : probability>
1: 0.024...
2: 0.005...
3: 0.156...
...

return a list representing the probability distribution.
"""
def get_distr_from_file(filename):
    i = 1
    distr = []
    with open(filename) as file:
        for line in file:
            subline = line.split(" ")
            if ((len(subline) != 2) or (not subline[0].startswith(str(i)))):
                print "Wrong file format (%d %s %s)" % (len(subline), subline[0], str(i))
                sys.exit(1)
            distr.append(subline[1])
            i+=1
    return distr

def usage():
    print """Faulty arguments.
    Usage:
    \tglp_creator <source_distr_file> <dest_distr_file>"""
    sys.exit()

def main():
    if ((len(sys.argv) != 3) or
        (not os.path.isfile(sys.argv[1])) or
        (not os.path.isfile(sys.argv[2]))):
        usage()

    source_distr = get_distr_from_file(sys.argv[1])
    dest_distr = get_distr_from_file(sys.argv[2])

    df = DataFile(DATA_FILENAME, source_distr, dest_distr)
    df.create_data_file()
    subprocess.check_output([
        "glpsol", "--math", MODEL_FILENAME,
        "--data", DATA_FILENAME,
        "--output", SOLUTION_FILENAME
    ])
    parse_and_print_solution_file(SOLUTION_FILENAME)

if __name__ == "__main__":
    main()

