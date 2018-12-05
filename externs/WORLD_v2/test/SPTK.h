/* ----------------------------------------------------------------- */
/*             The Speech Signal Processing Toolkit (SPTK)           */
/*             developed by SPTK Working Group                       */
/*             http://sp-tk.sourceforge.net/                         */
/* ----------------------------------------------------------------- */
/*                                                                   */
/*  Copyright (c) 1984-2007  Tokyo Institute of Technology           */
/*                           Interdisciplinary Graduate School of    */
/*                           Science and Engineering                 */
/*                                                                   */
/*                1996-2017  Nagoya Institute of Technology          */
/*                           Department of Computer Science          */
/*                                                                   */
/* All rights reserved.                                              */
/*                                                                   */
/* Redistribution and use in source and binary forms, with or        */
/* without modification, are permitted provided that the following   */
/* conditions are met:                                               */
/*                                                                   */
/* - Redistributions of source code must retain the above copyright  */
/*   notice, this list of conditions and the following disclaimer.   */
/* - Redistributions in binary form must reproduce the above         */
/*   copyright notice, this list of conditions and the following     */
/*   disclaimer in the documentation and/or other materials provided */
/*   with the distribution.                                          */
/* - Neither the name of the SPTK working group nor the names of its */
/*   contributors may be used to endorse or promote products derived */
/*   from this software without specific prior written permission.   */
/*                                                                   */
/* THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND            */
/* CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,       */
/* INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF          */
/* MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE          */
/* DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS */
/* BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,          */
/* EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED   */
/* TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,     */
/* DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON */
/* ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,   */
/* OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY    */
/* OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE           */
/* POSSIBILITY OF SUCH DAMAGE.                                       */
/* ----------------------------------------------------------------- */

/***********************************************************
   $Id$

   Speech Signal Processing Toolkit
   SPTK.h
***********************************************************/
#ifndef _H_SPTK_
#define _H_SPTK_
#ifndef PI
#define PI  3.14159265358979323846
#endif                          /* PI */

#ifndef PI2
#define PI2 6.28318530717958647692
#endif                          /* PI2 */

#ifndef M_PI
#define M_PI  3.1415926535897932384626433832795
#endif                          /* M_PI */

#ifndef M_2PI
#define M_2PI 6.2831853071795864769252867665590
#endif                          /* M_2PI */

#define LN_TO_LOG 4.3429448190325182765

#define LZERO (-1.0e+10)
#define LSMALL (-0.5e+10)

/* #ifndef ABS(x) */
#define ABS(x) ((x<0.0) ? -x : x)
/* #endif */

#ifdef __BIG_ENDIAN
#if __BYTE_ORDER == __BIG_ENDIAN
#define WORDS_BIGENDIAN
#endif
#endif

/* enum for Boolean */
typedef enum _Boolean { FA, TR } Boolean;

/* enum for window type */
typedef enum _Window {
   BLACKMAN,
   HAMMING,
   HANNING,
   BARTLETT,
   TRAPEZOID,
   RECTANGULAR
} Window;

/* struct for complex */
typedef struct {
   double re;
   double im;
} complex;

/* struct for Gaussian distribution */
typedef struct _Gauss {
   double *mean;
   double *var;
   double **cov;
   double **inv;
   double gconst;
} Gauss;

/* structure for GMM */
typedef struct _GMM {
   int nmix;
   int dim;
   Boolean full;
   double *weight;
   Gauss *gauss;
} GMM;

typedef struct _deltawindow {
   size_t win_size;
   size_t win_max_width;
   int *win_l_width;
   int *win_r_width;
   double **win_coefficient;
} DELTAWINDOW;

/* structure for wavsplit and wavjoin */
typedef struct _wavfile {
   int file_size;               /* file size */
   int fmt_chunk_size;          /* size of 'fmt ' chunk (byte) */
   int data_chunk_size;         /* size of 'data' chunk (byte) */
   short format_id;             /* format ID (PCM(1) or IEEE float(3)) */
   short channel_num;           /* mono:1��stereo:2 */
   int sample_freq;             /* sampling frequency (Hz) */
   int byte_per_sec;            /* byte per second */
   short block_size;            /* 16bit, mono => 16bit*1=2byte */
   short bit_per_sample;        /* bit per sample */
   short extended_size;         /* size of 'extension' */

   char input_data_type;
   char format_type;

   char *data;                  /* waveform data */

} Wavfile;

typedef struct _filelist {
   int num;
   char **name;
} Filelist;
#endif