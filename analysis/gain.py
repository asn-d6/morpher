#!/usr/bin/python2.7

"""
This little program should help you decide if using Traffic Morphing
is worth it. It will morph thousands of packets, both using morpher
and direct sampling, and compare the overhead by plotting it.

It's not very user friendly, and might be buggy, but it gets the job
done...
"""

import matplotlib
matplotlib.use('Agg') # to be able to plot in machines without X.org
import matplotlib.pyplot as plt
import numpy
import scipy.stats
import decimal
import math
import sys

sys.path.append("../dreams/python/")
import dream

# CHANGE THESE FILENAMES TO POINT TO YOUR PROB. DISTRS AND MORPHING MATRICES
SC_HTTPS_PROB_DISTR_FILENAME = "../data/https_sc_distr.txt"
SC_TOR_PROB_DISTR_FILENAME = "../data/tor_sc_distr.txt"
SC_MORPHING_MATRIX_FILENAME = "../__personal_lol_sc"

CS_HTTPS_PROB_DISTR_FILENAME = "../data/https_cs_distr.txt"
CS_TOR_PROB_DISTR_FILENAME = "../data/tor_cs_distr.txt"
CS_MORPHING_MATRIX_FILENAME = "../__personal_lol_cs"

"""Return True if 'string' represents a floating point number."""
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

    tmp = map(decimal.Decimal, distr)
    assert(math.fsum(tmp) == decimal.Decimal(1))

    return distr

"""Given a filename containing a probability distribution, and a name
for the distribution, return a scipy prob. distribution
representation."""
def get_prob_distr_from_file(filename, name):
    tmp = get_distr_from_file(filename)
    https_cs_distr = map(numpy.double, tmp)
    https_cs_vals = [numpy.arange(1460), https_cs_distr]
    return scipy.stats.rv_discrete(name=name, values=https_cs_vals)

DEBUG = True

# How many bytes of penalty overhead to add when we split a packet.
SPLIT_PENALTY = 50

# Client->Server (CS) or Server->Client (SC)
MODE = 'CS'

"""Given a packet of 'packet_size' bytes, return the total morphing overhead in bytes.
If 'method' is "sampling", use the traditional sampling method. If
'method' is "morphing" use packet morphing.

'arg' is a method-specific argument. In the case of sampling, its the
target protocol probability distribution. In the case of morphing, its
a list with a morphing matrix as the first element, and the target
protocol probability distribution as the second element.
"""
def get_overhead_for_packet_size(packet_size, method, arg):
    overhead = 0
    first_split = True

    """If we are "morphing", we use the morphing matrix to get the
    first target packet size, and the probability distribution for any
    subsequent packets in the case of splitting.

    If we are "samplign" we only use the probability distribution.
    """

    while (True):
        if (method == 'morphing'):
            if (first_split):
                target_randv = arg[0].get_target_length(packet_size)
            else:
                target_randv = arg[1].rvs()
        elif (method == 'sampling'):
            target_randv = arg.rvs()
        else:
            print("???")
            sys.exit(1)

        if (target_randv >= packet_size):
            if (DEBUG):
                print "%s: Got packet size %d. We must morph it to %d. " \
                    "Padding with %d and sending." % \
                    (method, packet_size, target_randv, target_randv - packet_size)

            overhead += target_randv - packet_size
            break # exit the loop. we sent the whole packet.
        else:
            if (DEBUG):
                print "%s: Got packet size %d. We must morph it to %d. " \
                    "Splitting to %d and sending the first part..." % \
                    (method, packet_size, target_randv, packet_size - target_randv)

            overhead += SPLIT_PENALTY
            packet_size -= target_randv
            # loop again. we haven't sent the whole packet yet.

        first_split = False

    return overhead

"""Given the elements on the x axis, a list containing the elements of
the y, a list containing labels, and a filename, plot the diagram and
save it to the disk."""
def plot_it(x_axis, y_axis_list, label_list, name):
    if (not (len(y_axis_list) == len(label_list))):
        print "No! (%d %d %d)" % (len(label_list), len(y_axis_list))
        sys.exit(1)

    for i in xrange(len(y_axis_list)):
        plt.plot(x_axis, y_axis_list[i], label=label_list[i])

    leg = plt.legend(loc='upper left')
    if (MODE == 'CS'):
        plt.title('Client->Server: %s packets' % (name))
    else:
        plt.title('Server->Client: %s packets' % (name))
    plt.ylabel('bytes overhead')
    plt.xlabel('packets')

    leg.get_frame().set_alpha(0.5)

    plt.savefig('%s_%s.png' % (name, MODE.lower()))

    plt.clf()

"""Plot diagram every <element> packets."""
TEST_N = [500, 2000, 8000, 16000, 50000, 100000, 500000]


if (MODE == 'SC'):
    # HTTPS S->C prob. distr.
    https_custm = get_prob_distr_from_file(SC_HTTPS_PROB_DISTR_FILENAME, "https_gain")
    # Tor S->C prob. distr.
    tor_custm = get_prob_distr_from_file(SC_TOR_PROB_DISTR_FILENAME, "tor_gain")
    # S->C morphing matrix
    mm_csc = dream.get_csc_from_mm(SC_MORPHING_MATRIX_FILENAME)
elif (MODE == 'CS'):
    # HTTPS C->S prob. distr.
    https_custm = get_prob_distr_from_file(CS_HTTPS_PROB_DISTR_FILENAME, "https_gain")
    # Tor C->S prob. distr.
    tor_custm = get_prob_distr_from_file(CS_TOR_PROB_DISTR_FILENAME, "tor_gain")
    # C->S morphing matrix
    mm_csc = dream.get_csc_from_mm(CS_MORPHING_MATRIX_FILENAME)
else:
    print "STOP... HAMMER TIME"
    sys.exit(1)

mm = dream.MorphingMatrix(mm_csc)

y_axis_sampling = []
y_axis_morphing = []
total_overhead_sampling = 0
total_overhead_morphing = 0

"""Main loop: Every iteration represents a packet morphing. We morph
the packet once using 'sampling', and once using 'morphing'. Everytime,
we add the overhead in bytes to the respective list. If DEBUG is True, we log every round.
If, according to TEST_N, it's time to plot the diagram, we plot_it().
"""
for i in xrange(1,max(TEST_N)+1):
    source_randv = tor_custm.rvs()+1

    """Morph with 'sampling'."""
    sampling_overhead = get_overhead_for_packet_size(source_randv,
                                                     'sampling', https_custm)

    total_overhead_sampling += sampling_overhead
    y_axis_sampling.append(total_overhead_sampling)

    """Morph with 'morphing'."""
    morphing_overhead = get_overhead_for_packet_size(source_randv,
                                                     'morphing', (mm, https_custm))

    total_overhead_morphing += morphing_overhead
    y_axis_morphing.append(total_overhead_morphing)

    """Print information in stdout."""
    if (DEBUG):
        print "%d: OVERHEAD ROUND SUMMARY: Sampling: %d : Morphing: %d" % \
            (i, sampling_overhead, morphing_overhead)
        rel_overhead = sampling_overhead - morphing_overhead
        if (rel_overhead >= 0):
            print "%d: OVERHEAD ROUND SUMMARY: Morpher won (%d)" % (i, rel_overhead)
        else:
            print "%d: OVERHEAD ROUND SUMMARY: Morpher lost (%d)" % (i, abs(rel_overhead))
        print "%d: SUMMARY: %s %s" % (i, str(total_overhead_sampling), str(total_overhead_morphing))

    """If it's time to plot, plot_it()."""
    if (i in TEST_N):
        plot_it(range(1,i+1), [y_axis_sampling, y_axis_morphing], ["sampling", "morphing"], str(i))

