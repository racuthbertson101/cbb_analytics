import os

# Single-threaded BLAS: fits are small dense solves; threading only causes contention (10-1000x slowdowns in process pools).
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
