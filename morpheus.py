#!/usr/bin/python2.7

import sys
import math
import subprocess
import os
import decimal
import itertools
import getopt
from scipy.sparse import lil_matrix
import scipy.io
import numpy

PARANOIA = True

# 1500b ethernet MTU - 20b min. ip headers - 20b min. tcp headers
MAX_TCP_PAYLOAD_SIZE = 1460

GLPK_FILENAME = "morpher.mod"
SOLUTION_FILENAME = "morpher.sol"

# Strings necessary for the GLPK file format.
PROLOGUE = "data;\n\n"
SET_STRING = "set PACKET_SIZE"
SOURCE_PARAM_STRING = "param source :="
TARGET_PARAM_STRING = "param target :="
EPILOGUE = "end;\n"

# this is our GLPK model
MODEL = \
"""set PACKET_SIZE;

param source{i in PACKET_SIZE};
param target{j in PACKET_SIZE};

/* variables: the morphing matrix; its elements must be >= 0 */
var morph{i in PACKET_SIZE, j in PACKET_SIZE}, >= 0;

/* the linear function to be minimized; the padding overhead */
minimize min_padding: sum{i in PACKET_SIZE, j in PACKET_SIZE} (source[j] * morph[i,j]*(abs(i - j)));

subject to column_prob {j in PACKET_SIZE}: sum{i in PACKET_SIZE} (morph[i,j]) = 1;
subject to morphing_creation {i in PACKET_SIZE} : sum{j in PACKET_SIZE} (morph[i,j]*source[j]) = target[i];

"""

"""
Represents a Linear Programming problem of trying to find the Morphing
Matrix between two probability distributions.

'self.source' is the source distribution.
'self.target' is the target distribution.
'self.result' is the morphing matrix.
"""
class MorphingMatrixLP:
    """Initialize a GLPK run.
    'source' is the source distribution.
    'target' is the target distribution'.
    """
    def __init__(self, source, target):
        if (len(source) != len(target)):
            print "Packet length distributions have different size."
            sys.exit(1)
        if (len(source) <= 0):
            print "0 size distribution"
            sys.exit(1)

        self.source = source
        self.target = target
        self.size = len(self.source)
        self.result = []

    """Public function.
    Run GLPK and return the morphing matrix.
    """
    def harvest(self):
        self.__run()
        self.__parse_solution_file()
        self.__clean_mess()

        return self.result

    """Write GLPK file to disk."""
    def __create_glpk_file(self):
        f = open(GLPK_FILENAME, 'w')
        f.write(MODEL)

        f.write(PROLOGUE)
        f.write(self.__get_set_string())
        f.write(self.__get_param_string(type="source"))
        f.write(self.__get_param_string(type="false"))
        f.write(EPILOGUE)

    """Return 'set' string of the data section of the GLPK file."""
    def __get_set_string(self):
        string = ""

        string += SET_STRING
        for i in xrange(1,self.size+1):
            string += " %s" % (str(i))

        string += ";\n\n"
        return string


    """Return 'param' string of the data section of the GLPK file."""
    def __get_param_string(self, type):
        string = ""

        if type == "source":
            string += SOURCE_PARAM_STRING
            distr = self.source
        else:
            string += TARGET_PARAM_STRING
            distr = self.target

        for num in xrange(1,self.size+1):
            string += "\n"
            string += "\t%s %s" % (str(num), str(distr[num-1]))

        string += ";\n\n"
        return string

    """Run GLPK."""
    def __run(self):
        self.__create_glpk_file()

        subprocess.check_output([
            "glpsol",
            "--math", GLPK_FILENAME,
            "--output", SOLUTION_FILENAME
        ])

    """Parse the solution file of glpsol and return the morphing matrix."""
    def __parse_solution_file(self):
        INTERESTING_FILE_SECTION = \
"""
   No. Column name  St   Activity     Lower bound   Upper bound    Marginal
------ ------------ -- ------------- ------------- ------------- -------------
"""

        morphing_matrix = []

        f = open(SOLUTION_FILENAME)
        solution = f.read()
        f.close()

        assert(INTERESTING_FILE_SECTION in solution)
        matrix_section = solution.split(INTERESTING_FILE_SECTION)[1]

        entries = matrix_section.split("\n")

        for i in xrange(len(entries)):
            substr = entries[i]
            if (substr == ""):
                break

            substr = ' '.join(substr.split()).split(" ")
            strlen = len(substr)

            if ((strlen == 6) or (strlen == 7)):
                morphing_matrix.append(substr[3])
            elif ((strlen == 3) or (strlen == 4)):
                morphing_matrix.append(substr[1])
            elif (strlen == 5):
                if (substr[-1] == "eps"):
                    morphing_matrix.append(substr[1])
                else:
                    morphing_matrix.append(substr[3])

        n = len(morphing_matrix)
        size = math.sqrt(n)
        assert(size == int(size)) # must not be a float

        self.result = morphing_matrix

    """Remove files that were created for GLPK."""
    def __clean_mess(self):
        os.remove(GLPK_FILENAME)
        os.remove(SOLUTION_FILENAME)

def string_is_float(string):
    try:
        float(string)
    except ValueError, TypeError:
        return False
    return True

"""Given a file of the format '<packet length: probability>\n':

# comment
1: 0.024...
2: 0.005...
3: 0.156...
...

return a list representing its probability distribution.
"""
def get_distr_from_file(filename):
    i = 1
    distr = []
    with open(filename) as file:
        for line in file:
            subline = line.split(" ")
            if (subline[0].startswith("#")): # comment
                continue
            if ((len(subline) != 2) or
                (not subline[0].startswith(str(i))) or
                (not string_is_float(subline[1]))):
                print "Wrong file format (%d %s %s)" % (len(subline), subline[0], str(i))
                sys.exit(1)
            distr.append(subline[1].rstrip())
            i+=1

    if (PARANOIA):
        tmp = map(decimal.Decimal, distr)
        assert(math.fsum(tmp) == decimal.Decimal(1))

    return distr

"""Spit usage instructions and exit"""
def usage():
    print """Usage:
    \tmorpheus options [arguments]
    where 'options' are:
       --source=<source distribution filename>
       --target=<target distribution filename>
       --output=<morphing matrix output filename>
    """
    sys.exit()

"""
Given a 'list' and a 'size', return a list of lists representing a
square matrix.
Example: get_sqmatrix_from_list([0,1,2,3],2) = [[0,1],[2,3]]
"""
def get_sqmatrix_from_list(list, size):
    ret = []
    start = 0
    end = size
    if (len(list) != pow(size,2)):
        raise ValueError("You either gave a wrong 'size' " \
                         "or this is not a square matrix. (%d:%d)" % (len(list), size))

    tmp_list = []
    for _ in xrange(size):
        ret.append(list[start:end])
        start += size
        end += size

    assert(start == len(list))

    return ret

"""Startup morpheus."""
def startup(source_distr, target_distr, output):
    """Morphing matrix."""
    m_m_glpk = MorphingMatrixLP(source_distr, target_distr)
    m_m = m_m_glpk.harvest()

    m_size = len(m_m)
    assert(math.sqrt(m_size) == int(math.sqrt(m_size)))

    """
    XXX This cast to numpy.double introduces loss of significance.
    Unfortunately, SciPy doesn't support sparse matrices
    with Decimals or strings.
    """
    tmp_m_m = map(numpy.double, m_m)
    sq = get_sqmatrix_from_list(tmp_m_m, int(math.sqrt(m_size)))
    lm = lil_matrix(sq)
    scipy.io.mmwrite(output, lm, comment="Morphing Matrix", field="real")

"""Entry point"""
def main(argv):
    try:
        opts, args = getopt.getopt(argv, "s:t:o:p", ["source=", "target=", "output="])
    except getopt.GetoptError:
        usage()
        sys.exit(1)

    source = None
    target = None
    output = None

    for opt, arg in opts:
        if opt in ("-s", "--source"):
            source = arg
        elif opt in ("-t", "--target"):
            target = arg
        elif opt in ("-o", "--output"):
            output = arg

    if ((not source) or (not target)):
        print "Please provide a source and a target distribution."
        usage()
    if ((not os.path.isfile(source)) or (not os.path.isfile(target))):
        print "Please provide valid filenames for the distributions."
        usage()
    if ((not output) or (os.path.exists(output))):
        print "Please provide a valid output filename."
        usage()

    source_distr = get_distr_from_file(source)
    target_distr = get_distr_from_file(target)

    startup(source_distr, target_distr, output)

if __name__ == "__main__":
    if (sys.hexversion < 0x02070000):
        print "You can only run this script with a Python version >= 2.7."
        sys.exit(1)

    main(sys.argv[1:])
