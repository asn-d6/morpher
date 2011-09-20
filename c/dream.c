#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>
#include <assert.h>
#include <string.h>
#include <limits.h>

#include "mmio.h"
#include "dream.h"

/** Free space allocated by matrix 'csc'. */
static void
csc_free(csc_t *csc)
{
  if (!csc)
    return;

  if (csc->values)
    free(csc->values);
  if (csc->row_inds)
    free(csc->row_inds);
  if (csc->col_ptrs)
    free(csc->col_ptrs);

  free(csc);
}

/** Create square CSC matrix of 'cols_n' columns and of 'nz_entries'
    non-zero entries in 'csc_out'. */
static int
csc_create(csc_t **csc_out, int cols_n, int nz_entries)
{
  assert((cols_n > 0) && (nz_entries > 0));

  if (cols_n == INT_MAX) /* don't overflow cols_n. */
    return -1;

  *csc_out = calloc(1, sizeof(csc_t));
  if (!csc_out)
    return -1;

  (*csc_out)->values = malloc(nz_entries * sizeof(double));
  (*csc_out)->row_inds = malloc(nz_entries * sizeof(int));
  (*csc_out)->col_ptrs = malloc((cols_n+1) * sizeof(int));
  if ((!(*csc_out)->values) ||
      (!(*csc_out)->row_inds) ||
      (!(*csc_out)->col_ptrs)) {
    csc_free(*csc_out);
    return -1;
  }

  (*csc_out)->size = cols_n;
  (*csc_out)->entries_n = nz_entries;

  return 0;
}

/** Given a source packet length in 'n' and a random number \in [0,1]
    in 'rand', return the target packet length according to the
    morphing matrix in 'csc'.
    - 'b_n' is given in one-based numbering. */
int
dream_get_target_length(csc_t *csc, int b_n, double rand)
{
  double cdf = 0.0;
  int n = b_n - 1; /* zero based column number */
  int i = 0;
  int col_size;

  if ((rand < 0.0) || (rand > 1.0))
    return -1;
  if ((n < 0) || (n >= csc->size))
    return -1;

  /* Get the size of the column that carries the morphing information */
  col_size = csc->col_ptrs[n+1] - csc->col_ptrs[n];
  assert(col_size > 0);
  assert((csc->col_ptrs[n] + col_size) <= csc->entries_n);

  /* Iterate the probability column while synthesizing its Cumulative
     Distribution Function. We look for the row of the element that
     makes the CDF value pass 'rand'. */
  while ((rand >= cdf) && (i < col_size)) {
    cdf += csc->values[csc->col_ptrs[n]+i];
    i++;
  }

  return csc->row_inds[csc->col_ptrs[n]+i-1]+1;
}

/** Given a morphing matrix 'csc' and a source packet length 'n',
    print all possible mutations that can happen to 'n' along with
    their probabilities.
    - 'b_n' is given in one-based numbering. */
void
dream_print_potential(csc_t *csc, int b_n)
{
  int n = b_n - 1; /* zero based column number */
  int i = 0;
  int col_size;

  if ((n < 0) || (n >= csc->size)) {
    printf("Wrong packet length given.\n");
    return;
  }

  col_size = csc->col_ptrs[n+1] - csc->col_ptrs[n];
  assert(col_size > 0);
  assert((csc->col_ptrs[n] + col_size) <= csc->entries_n);

  printf("A packet of length %d bytes can become:\n", b_n);
  for (i = 0 ; i < col_size ; i++)
    printf("\t%d bytes with probability %lg\n",
           csc->row_inds[csc->col_ptrs[n]+i]+1,
           csc->values[csc->col_ptrs[n]+i]);

}

/** Compare two COO elements by their row.
    Comparison function for qsort() */
static int
cmp_elements_by_row(const void *a, const void *b)
{
  typedef struct {
    int row;
    int col;
    double value;
  } element_t;

  const element_t *elem_a = a;
  const element_t *elem_b = b;

  if (elem_a->row < elem_b->row)
    return -1;
  else if (elem_a->row > elem_b->row)
    return 1;
  else
    return 0;
}


/** Compare two COO elements by their column.
    Comparison function for qsort() */
static int
cmp_elements_by_column(const void *a, const void *b)
{
  typedef struct {
    int row;
    int col;
    double value;
  } element_t;

  const element_t *elem_a = a;
  const element_t *elem_b = b;

  if (elem_a->col < elem_b->col)
    return -1;
  else if (elem_a->col > elem_b->col)
    return 1;
  else
    return 0;
}

/** Given a file handle to a Matrix Market file containing a morphing
    matrix, place the matrix in CSC format in 'csc_out'. */
enum mm_ret
dream_set_csc_from_mm(csc_t **csc_out, FILE *f)
{
  /** Represents a matrix element in coordinate format, */
  typedef struct { /* its elements represent: */
    int row; /* its row */
    int col; /* its column */
    double value; /* and its value. */
  } element_t;

  int i, nz_entries, rows_n, cols_n;
  int curcol = 0;
  int col_ptr = 0;
  element_t *elements = NULL;
  MM_typecode matcode;
  enum mm_ret status = DREAM_MM_OKAY;

  /* validate */

  if (mm_read_banner(f, &matcode) != 0) {
    status = DREAM_MM_CORRUPTED;
    goto err;
  }

  if (!mm_is_valid(matcode) ||
      !mm_is_matrix(matcode) ||
      !mm_is_sparse(matcode) ||
      !mm_is_real(matcode)) {
    status = DREAM_MM_NOT_MORPHING;
    goto err;
  }

  if (mm_read_mtx_crd_size(f, &rows_n, &cols_n, &nz_entries) !=0) {
    status = DREAM_MM_CORRUPTED;
    goto err;
  }

  if ((cols_n <= 0) || (rows_n != cols_n) || (nz_entries <= 0)) {
    status = DREAM_MM_NOT_MORPHING;
    goto err;
  }

  /* stop validating */

  /* The algorithm is as follows:
     The Matrix Market file is a matrix stored in coordinate format.
      * We store the whole file in an array of 'element_t's.
      * We sort the elements array first by row and then by column.
        Because of the sorting, the first element of 'elements' is the
        first non-zero value columns-first.

      * Set first 'col_ptr' of CSC to 0.

      * We iterate 'elements' and for each element:
        * If it belongs to a new column, we set 'col_ptr' in CSC.
        * We set its value in 'values' in CSC.
        * We set its row in 'row_inds' in CSC.

      * We set the last 'col_ptr' to right after the last element.

     It is based on the COO-to-CSC algorithm of:
     http://bebop.cs.berkeley.edu/smc/
  */
  elements = malloc(nz_entries * sizeof(element_t));
  if (!elements) {
    status = DREAM_MM_INTERNAL;
    goto err;
  }

  for (i = 0 ; i < nz_entries ; i++) {
    fscanf (f, "%d %d %lg\n",
            &elements[i].row,
            &elements[i].col,
            &elements[i].value);
    elements[i].row--; /* Matrix Market is one-based numbered... */
    elements[i].col--; /* ...so we transform input to zero-based. */

    /* validate */
    if ((elements[i].row < 0) ||
        (elements[i].col < 0) ||
        (elements[i].value < 0)) {
      status = DREAM_MM_NOT_MORPHING;
      goto err;
    }
  }

  qsort(elements, nz_entries, sizeof(element_t), cmp_elements_by_row);
  qsort(elements, nz_entries, sizeof(element_t), cmp_elements_by_column);

  if (csc_create(csc_out, cols_n, nz_entries) < 0) {
      status = DREAM_MM_INTERNAL;
      goto err;
  }

  curcol = elements[0].col;
  (*csc_out)->col_ptrs[col_ptr++] = curcol;

  for (i = 0 ; i < nz_entries ; i++) {
    if (elements[i].col > curcol) {
      /* morphing matrices don't have empty columns */
      if (elements[i].col - curcol != 1) {
        status = DREAM_MM_NOT_MORPHING;
        goto err;
      }

      curcol = elements[i].col;
      (*csc_out)->col_ptrs[col_ptr++] = i;

      /* more columns than claimed in the mm header? */
      if (col_ptr > cols_n) {
        status = DREAM_MM_CORRUPTED;
        goto err;
      }
    }

    (*csc_out)->values[i] = elements[i].value;
    (*csc_out)->row_inds[i] = elements[i].row;
  }

  (*csc_out)->col_ptrs[col_ptr++] = nz_entries;

  /* all columns of the morphing matrix must be populated */
  if (col_ptr != (cols_n+1)) {
    status = DREAM_MM_NOT_MORPHING;
    goto err;
  }

  free(elements);

  goto done;

 err:
  assert(status != DREAM_MM_OKAY);

  if (elements)
    free(elements);
  if (*csc_out)
    csc_free(*csc_out);

 done:
  return status;
}
