#!/bin/python

import sys
import math
import subprocess
import os
import decimal
import itertools

# 1500b ethernet MTU - 20b min. ip headers - 20b min. tcp headers
MAX_PAYLOAD_SIZE = 1460

# 20 * 73 = 1460. Sounds like a nice balance.
N_PARTITIONS = 20
N_PARTITION_ELEMENTS = 73
assert(N_PARTITIONS * N_PARTITION_ELEMENTS == MAX_PAYLOAD_SIZE)

GLPK_FILENAME = "morpher.mod"
SOLUTION_FILENAME = "morpher.sol"

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

# this is the section in the default glpsol output which contains the morphing matrix
INTERESTING_FILE_SECTION = \
"""
   No. Column name  St   Activity     Lower bound   Upper bound    Marginal
------ ------------ -- ------------- ------------- ------------- -------------
"""
#    8 morph[0,7]   B          0.625



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

            substr = ' '.join(substr.split())
            morphing_matrix.append(substr.split(" ")[3])


        n = len(morphing_matrix)
        size = math.sqrt(n)
        assert(size == int(size)) # must not be a float

        self.result = morphing_matrix

    """Remove files that were created for GLPK."""
    def __clean_mess(self):
        os.remove(GLPK_FILENAME)
        os.remove(SOLUTION_FILENAME)

"""This class represents a probability distribution.

'self.distr' contains the probability distribution as a list.

The rest of this class' data is used to implement section
"3.4 Dealing With Large Sample Spaces" of the Traffic Morphing paper:

'self.partitions' is a list of N_PARTITIONS lists. Each of these lists
is called a 'partition' because it contains a subset (of size
N_PARTITION_ELEMENTS) of self.distr elements.
The partition elements values are adjusted within the partition to
represent the probability mass function of the partition (see
example).

'self.repr' is a list of N_PARTITIONS elements. Each of its elements
is the sum of the probabilities of its respective partition.

EXAMPLE:

A probability distribution of 8 values could be:
self.distr = [0.2, 0.2, 0.1, 0.2, 0.1, 0.02, 0.08, 0.1]

Splitting the above example into 4 partitions of 2 elements we get:
self.partitions[0] concerns elements '0.2' and '0.2' which become
'0.5' and '0.5' within the partition (0.2/0.4 = 0.5).
self.partitions[1] concerns elements '0.1' and '0.2' which become
'0.333...' and '0.666...' within the partition (0.1/0.3 = 0.333...).
...

Finally self.repr contains:
self.repr[0] = 0.2 + 0.2 = 0.4
self.repr[1] = 0.1 + 0.2 = 0.3
...
"""
class Distribution:
    def __init__(self, distr_list):
        self.distr = distr_list
        if (len(self.distr) != MAX_PAYLOAD_SIZE):
            print "We only support distributions of size %d." % (MAX_PAYLOAD_SIZE)
            sys.exit(1)

        self.partitions = [] # x_1 ... x_n
        self.repr = [] # X'

        self.__do_partition()

    """Split the distribution into N_PARTITIONS partitions of
    N_PARTITION_ELEMENTS elements each. Also fill self.repr."""
    def __do_partition(self):
        start = 0
        end = N_PARTITION_ELEMENTS
        for _ in xrange(N_PARTITIONS):
            tmp = map(decimal.Decimal, self.distr[start:end])
            tmp_sum = sum(tmp)

            self.partitions.append(map(lambda x: x/tmp_sum, tmp))
            self.repr.append(tmp_sum)

            start += N_PARTITION_ELEMENTS
            end += N_PARTITION_ELEMENTS

        assert(start == MAX_PAYLOAD_SIZE)
        assert(len(self.partitions[-1]) == N_PARTITION_ELEMENTS)

"""Given a file of the format '<packet length: probability>\n':

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
            if ((len(subline) != 2) or (not subline[0].startswith(str(i)))):
                print "Wrong file format (%d %s %s)" % (len(subline), subline[0], str(i))
                sys.exit(1)
            distr.append(subline[1].rstrip())
            i+=1
    return distr

"""Spit usage instructions and exit"""
def usage():
    print """Wrong arguments.
    Usage:
    \tglp_creator <source_distr_file> <dest_distr_file>"""
    sys.exit()

"""Given 'matrix_list', a list representing a square matrix, print it."""
def print_square_matrix(matrix_list):
        n = len(matrix_list)
        size = math.sqrt(n)
        assert(size == int(size)) # must not be a float

        for i in xrange(1,n+1):
            if ((i % size) == 0):
                print "%.6f" %(float(matrix_list[i-1]))
            else:
                print "%.6f" %(float(matrix_list[i-1])),

def main():
    if ((len(sys.argv) != 3) or
        (not os.path.isfile(sys.argv[1])) or
        (not os.path.isfile(sys.argv[2]))):
        usage()

    source_distr = Distribution(get_distr_from_file(sys.argv[1]))
    target_distr = Distribution(get_distr_from_file(sys.argv[2]))

    """Partition morphing matrix.
    It's the morphing matrix that links a source partition to a target
    partition."""
    p_m_m_glpk = MorphingMatrixLP(source_distr.repr,
                                  target_distr.repr)
    p_m_m = p_m_m_glpk.harvest()

    """Interpartition matrices.
    N_PARTITIONS^2 morphing matrices. Each of them advices on how to
    morph packets from a source partition to a target partition.
    Since there are N_PARTITIONS^2 of them, we can use them to find
    how to morph packets from *any* source partition to *any* target
    partition.

    The interpartition_matrices list contains tuples of the form:
    (matrix, source, target) where 'source' and 'target' are integers
    pointing to the partitions that were used to create the morphing
    'matrix'.
    """
    interpartition_matrices = []
    for i,j in itertools.product(range(N_PARTITIONS),repeat=2):
        interpartition_glpk = MorphingMatrixLP(source_distr.partitions[i],
                                               target_distr.partitions[j])
        interpartition_matrices.append((interpartition_glpk.harvest(), i, j))

    print "Partition morphing matrix:"
    print_square_matrix(p_m_m)
    for m in interpartition_matrices:
        print "Interpartition matrix (%d->%d):" % (m[1],m[2])
        print_square_matrix(m[0])

if __name__ == "__main__":
    main()

