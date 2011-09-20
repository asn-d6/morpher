#ifndef DREAM_H
#define DREAM_H

/** Represents a square sparse matrix in Compressed Sparse Column (CSC)
    format. */
typedef struct {
  int size; /* size of the matrix (e.g 1460 for a 1460x1460 matrix) */
  int entries_n; /* number of non-zero entries */

  /* elements below are specific for the CSC format. */
  double *values; /* values */
  int *row_inds; /* row indices */
  int *col_ptrs; /* column pointers */
} csc_t;

/** Status of the morphing matrix parsing. */
enum mm_ret {
  DREAM_MM_OKAY, /* matrix market parsed correctly */
  DREAM_MM_CORRUPTED, /* matrix market file was corrupted */
  DREAM_MM_NOT_MORPHING, /* matrix market file did not contain a
                            morphing matrix */
  DREAM_MM_INTERNAL /* internal error while parsing matrix market file */
};

/** Given a file handle to a Matrix Market file containing a morphing
    matrix, place the matrix in CSC format in 'csc_out'. */
enum mm_ret dream_set_csc_from_mm(csc_t **csc_out, FILE *f);

/** Given a source packet length in 'n' and a random number \in [0,1]
    in 'rand', return the target packet length according to the
    morphing matrix in 'csc'.
    - 'b_n' is given in one-based numbering. */
int dream_get_target_length(csc_t *csc, int n, double rand);

/** Given a morphing matrix 'csc' and a source packet length 'n',
    print all possible mutations that can happen to 'n' along with
    their probabilities.
    - 'b_n' is given in one-based numbering. */
void dream_print_potential(csc_t *csc, int n);

#endif /* DREAM_H */
