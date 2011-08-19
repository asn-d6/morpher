#!/bin/python

import sys
import math
import subprocess

MODEL_FILENAME = "morpher.mod"
DATA_FILENAME = "morpher.data"
SOLUTION_FILENAME = "morpher.sol"

PROLOGUE = "data;\n\n"

SET_STRING = "set PACKET_SIZE"
SOURCE_PARAM_STRING = "param source :="
TARGET_PARAM_STRING = "param target :="

EPILOGUE = "end;\n"

class DataFile:
    def __init__(self, filename, source, target):
        self.filename = filename
#        self.source = ["10", "20", "30", "40", "50", "60", "70", "80", "90"]
#        self.target = ["90", "80", "70", "60", "50", "40", "30", "20", "10"]

        if (len(self.source) != len(self.target)):
            print "Packet length distributions have different size."
            sys.exit(1)

        self.size = len(self.source)

        if (self.size <= 0):
            print "0 size distribution"
            sys.exit(1)

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

def parse_solution_file(filename):
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

if __name__ == "__main__":
    print "Started"
    df = DataFile(DATA_FILENAME, True, True)
    df.create_data_file()
    subprocess.check_output([
        "glpsol", "--math", MODEL_FILENAME,
        "--data", DATA_FILENAME,
        "--output", SOLUTION_FILENAME
    ])
    parse_solution_file(SOLUTION_FILENAME)

