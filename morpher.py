import sys
import random
from decimal import *

import pymprog

def print_matrix():
    for i in size_list:
        for j in size_list:
            if j == distr_size-1:
                print "%.2f" % (float(morph[i,j].primal))
            else:
                print "%.2f" % (float(morph[i,j].primal)),

""" Returns a list of 'n' random numbers supping up to 1."""
def get_random_distribution(n):
    L = [ random.uniform(0,1) for _ in xrange(n) ]
    sumL = sum(L)
    return [ l/sumL for l in L ]

def get_random_sample(n):
    return get_random_distribution(n)

size = 5

s_m = get_random_sample(size)
t_m = get_random_sample(size)

print t_m
print s_m

if (len(s_m) != len(t_m)):
    print "Packet length distributions have different size."
    sys.exit(1)

distr_size = len(s_m)

size_list = range(distr_size) # list of packet lengths: [0, 1, 2, ...]

pymprog.beginModel("traffic morphing") # we gotta start from somewhere...

matrix = pymprog.iprod(size_list,size_list) # a 2D matrix

morph = pymprog.var(matrix, 'morphing_matrix') # decision variables... matrix

source = pymprog.par(s_m, 'source_distribution') # source distribution parameter
target = pymprog.par(t_m, 'target_distribution') # target distribution parameter

pymprog.minimize(sum(source[j]*morph[i,j]*(abs(i-j)) for i,j in matrix),
                 'min_padding') # our linear function to be minimized.

pymprog.st(
    [sum(morph[i,j]*source[j] for j in size_list) == target[i] for i in size_list],
    'morphing_creation')

pymprog.st([sum(morph[i,j] for i in size_list) == 1 for j in size_list],
           'column_prob') # "column vectors of morphing matrix must sum to 1."

pymprog.st([0 <= morph[i,j] for i,j in matrix],
           'a_ij_gte_0') # "entries of morphing matrix must be positive or 0."

pymprog.solvopt(method='exact') # "exact" solving method; to avoid rounding bugs.
pymprog.solve() # solve the thing!

print_matrix()

pymprog.endModel()
