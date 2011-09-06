import sys
import random
import math
from decimal import Decimal
import scipy.io

"""
This library provides the following functions:

    * get_potential(source_packet_length):
              prints all the possible mutations of 'source_packet_length'
              along with their probabilities.

    * get_target_length(source_packet_length, random=None):
              spits out an instantly generated target packet length
              for 'source_packet_length'.


Example of its usage:

$ python2.7 morpheus.py --source=source_distr.txt --target=target_distr.txt --output=mm
$ ipython2.7
In [1]: from dream import *

In [2]: mm_csc = get_csc_from_mm("mm.mtx")

In [3]: mm = MorphingMatrix(mm_csc)

In [4]: mm.get_potential(85)
A packet of length 85 bytes can become:
  981 bytes with probability 0.082025
  982 bytes with probability 0.199468
  983 bytes with probability 0.095048
  984 bytes with probability 0.100403
  985 bytes with probability 0.149936
  986 bytes with probability 0.373120

In [5]: mm.get_target_length(85, 0.3)
Out[5]: 983

In [6]: mm.get_target_length(85)
Out[6]: 985
"""

PARANOIA = True

"""Represents a Morphing Matrix.

'self.matrix' is the matrix itself, represented as a list.
'self.size' is the number of rows of the square matrix (e.g. 1460 if
it's a 1460x1460 matrix).
"""
class MorphingMatrix:
    """Initialize MorphingMatrix.

    'matrix' is a SciPy sparse matrix in CSC format.
    """
    def __init__(self, matrix):
        self.matrix = matrix
        if (self.matrix.shape[0] != self.matrix.shape[1]):
            raise ValueError("Matrix provided is not square (%d:%d)." %
                             (self.matrix.shape[0], self.matrix.shape[1]))
        self.size = self.matrix.shape[0]

        if (PARANOIA): self.__validate()

    """Make sure that our morphing matrix indeed looks like one."""
    def __validate(self):
        for i in xrange(1,self.size+1):
            col = self.__get_matrix_column(i)
            assert(Decimal(0.99999) < Decimal(math.fsum(col)) < Decimal(1.00001))

    """Public function.
    Given 's_len', the packet length of a source packet that we want
    to morph, return the target packet length according to the
    morphing matrix.
    If 'rand' is given, use that instead of a generating a random
    number in __sample_target_size().
    """
    def get_target_length(self, s_len, rand=None):
        column = self.__get_matrix_column(s_len)

        return self.__sample_target_size(column, rand)

    """Public function.
    Given 's_len', the packet length of a source packet that we want
    to morph, print all possible mutations that can happen to it along
    with their probabilities.
    """
    def get_potential(self, s_len):
        column = self.__get_matrix_column(s_len)
        potential = []

        n = 1
        for i in column:
            if (i != 0):
                potential.append((n, i))
            n += 1

        assert(potential)

        print "A packet of length %d bytes can become:" % (s_len)
        for pot in potential:
            print "\t%d bytes with probability %s" % (pot[0], pot[1])

    """
    Given a morphing matrix 'column' as a list, and a 'random'
    number \in [0.1] return the target packet length.
    """
    def __sample_target_size(self, column, rand):
        assert(len(column) == self.size)
        cdf = 0
        i = 0

        if (not rand):
            rand = Decimal(random.random())
        else:
            rand = Decimal(rand)

        if (not (0 <= rand <= 1)):
            raise ValueError("Value of 'rand' is unacceptable! (%s)" % (rand))

        while ((rand > cdf) and (i < self.size)):
            cdf += column[i]
            i += 1

        return i

    """Return column 'i' of the morphing matrix as a list."""
    def __get_matrix_column(self, i):
        if (not (0 < i <= self.size)):
            raise ValueError("You requested column '%d' " \
                             "of matrix of size '%s'." %(i, self.size))

        col = []
        col_tmp = self.matrix.getcol(i-1).toarray().tolist()
        for elem in col_tmp:
            if (PARANOIA): assert(len(elem) == 1)
            col.append(elem[0])

        return col

def get_csc_from_mm(fname):
    mat = scipy.io.mmread(fname)
    return mat.tocsc()
