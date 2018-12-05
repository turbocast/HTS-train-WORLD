#ifndef _H_THEQ_
#define _H_THEQ_

static void mv_mul(double *t, double *x, double *y);

static void mm_mul(double *t, double *x, double *y);

static int inverse(double *x, double *y, const double eps);

static void crstrns(double *x, double *y);

static double **mtrx2(const int a, const int b);

static int cal_p0(double **p, double **r, double *b, const int n,
                  const double eps);

static void cal_ex(double *ex, double **r, double **x, const int i);

static void cal_ep(double *ep, double **r, double **p, const int i);

static int cal_bx(double *bx, double *vx, double *ex, const double eps);

static void cal_x(double **x, double **xx, double *bx, const int i);

static void cal_vx(double *vx, double *ex, double *bx);

static int cal_g(double *g, double *vx, double *b, double *ep,
                 const int i, const int n, const double eps);

static void cal_p(double **p, double **x, double *g, const int i);

int theq(double *t, double *h, double *a, double *b, const int n, double eps);
#endif