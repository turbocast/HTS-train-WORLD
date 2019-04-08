//-----------------------------------------------------------------------------
// 
// Author: Yuxuan Zhang (hyperzlink@outlook.com)
// Date: 2018/12/02
//
// To synthesize from LF0, MGC and BAP to waveform with WORLD vocoder
//
// This is modified based on Msanori Morise's test.cpp.
//
// synth <input f0/lf0> <input sp/mgc> <input ap/bap> <output wave> <frame period> <fft size> <sample rate> \
//    [<enable compress & spec dimension> <aper dimension>]
//
//-----------------------------------------------------------------------------

#define ALPHA 0.55

#include <math.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

#include <sys/stat.h> 

#if (defined (__WIN32__) || defined (_WIN32)) && !defined (__MINGW32__)
#include <conio.h>
#include <windows.h>
#pragma comment(lib, "winmm.lib")
#pragma warning(disable : 4996)
#endif
#if (defined (__linux__) || defined(__CYGWIN__) || defined(__APPLE__))
#include <stdint.h>
#include <sys/time.h>
#endif

// For .wav input/output functions.
#include "audioio.h"

// WORLD core functions.
// Note: win.sln uses an option in Additional Include Directories.
// To compile the program, the option "-I $(SolutionDir)..\src" was set.
#include "world/matlabfunctions.h"
#include "world/synthesis.h"
#include "world/common.h"
#include "world/constantnumbers.h"
#include "world/codec.h"
#include "sptkfunctions.h"

#if (defined (__linux__) || defined(__CYGWIN__) || defined(__APPLE__))
// Linux porting section: implement timeGetTime() by gettimeofday(),
#ifndef DWORD
#define DWORD uint32_t
#endif
DWORD timeGetTime() {
  struct timeval tv;
  gettimeofday(&tv, NULL);
  DWORD ret = static_cast<DWORD>(tv.tv_usec / 1000 + tv.tv_sec * 1000);
  return ret;
}
#endif

//-----------------------------------------------------------------------------
// struct for WORLD
// This struct is an option.
// Users are NOT forced to use this struct.
//-----------------------------------------------------------------------------
typedef struct {
  double frame_period;
  int fs;

  double *f0;
  double *time_axis;
  int f0_length;

  double **spectrogram;
  double **aperiodicity;
  int fft_size;
} WorldParameters;

namespace {

void ToF0(double *lf0, int len, double *f0){
  for(int i = 0; i < len; i ++){
    if(lf0[i] != 0){
      f0[i] = exp(lf0[i]);
    } else {
      f0[i] = 0;
    }
  }
}

void ToDouble(float *input, int len, double *output){
  for(int i = 0; i < len; i ++){
    output[i] = (double)input[i];
  }
}

void WaveformSynthesis(WorldParameters *world_parameters, int fs,
    int y_length, double *y) {
  DWORD elapsed_time;
  // Synthesis by the aperiodicity
printf("Synthesis...\n");
  elapsed_time = timeGetTime();
  Synthesis(world_parameters->f0, world_parameters->f0_length,
      world_parameters->spectrogram, world_parameters->aperiodicity,
      world_parameters->fft_size, world_parameters->frame_period, fs,
      y_length, y);
  printf("WORLD: %d [msec]\n", timeGetTime() - elapsed_time);
}

void DestroyMemory(WorldParameters *world_parameters) {
  delete[] world_parameters->time_axis;
  delete[] world_parameters->f0;
  for (int i = 0; i < world_parameters->f0_length; ++i) {
    delete[] world_parameters->spectrogram[i];
    delete[] world_parameters->aperiodicity[i];
  }
  delete[] world_parameters->spectrogram;
  delete[] world_parameters->aperiodicity;
}

}  // namespace

int main(int argc, char *argv[]) {
  if (argc != 8 && argc != 9 && argc != 10) {
    printf("Usage: %s <input f0/lf0> <input sp/mgc> <input ap/bap> <output wave> <frame period> <fft size> <sample rate> [<enable compress & spec dimension> <aper dimension>]\n", argv[0]);
    return -2;
  }

  int fft_size = atoi(argv[6]);
  int fs = atoi(argv[7]);
  int spec_dimension = 0;
  int ap_dimension = 24;
  bool oddApl = false;
  if(argc >= 9){
    spec_dimension = atoi(argv[8]);
  }

  if(argc >= 10){
    ap_dimension = atoi(argv[9]);
    if(ap_dimension % 2 == 1){
      oddApl = true;
    }
  }

  WorldParameters world_parameters = { 0 };
  world_parameters.fs = fs;
  world_parameters.frame_period = atof(argv[5]);
  world_parameters.fft_size = fft_size;


  // find number of frames (floats) in f0 file:  
  struct stat st;
  if (stat(argv[1], &st) == -1) {
    printf("cannot read f0\n");
    return -2;
    }
  int f0_length = (st.st_size / sizeof(float));
  world_parameters.f0_length = f0_length;

//  printf("%d\n", f0_length);
  float *buffer;
  
  world_parameters.f0 = new double[f0_length];
  buffer = new float[f0_length];
  FILE *fp;
  fp = fopen(argv[1], "rb");
	fread(buffer, sizeof(float), f0_length, fp);
  fclose(fp);
  ToDouble(buffer, f0_length, world_parameters.f0);
  delete [] buffer;
  if(spec_dimension != 0){ // lf0 to f0
    double *t = new double[f0_length];
    ToF0(world_parameters.f0, f0_length, t);
    delete [] world_parameters.f0;
    world_parameters.f0 = t;
  }

  int specl = fft_size / 2 + 1;
  int apl = fft_size / 2 + 1;
  if(spec_dimension != 0){
    specl = spec_dimension;
    apl = ap_dimension;
  }

  world_parameters.aperiodicity = new double *[world_parameters.f0_length];
  world_parameters.spectrogram = new double *[world_parameters.f0_length];

  fp = fopen(argv[2], "rb");
  buffer = new float[specl];
  for (int i = 0; i < f0_length; i++) {
    world_parameters.spectrogram[i] = new double[specl];
    fread(buffer, sizeof(float), specl, fp);
    ToDouble(buffer, specl, world_parameters.spectrogram[i]);
  }
  fclose(fp);
  delete [] buffer;

  if(spec_dimension != 0){
    //decode
    double **realspec = new double*[world_parameters.f0_length];
    for(int i = 0; i < f0_length; i ++){
      realspec[i] = new double[fft_size / 2 + 1];
      world_parameters.spectrogram[i][0] -= 12.0;
      /*for(int j = 0; j < f0_length; j ++){
        world_parameters.spectrogram[i][j] *= 2;
      }*/
    }
    DecodeSpectralEnvelope(world_parameters.spectrogram, world_parameters.f0_length, world_parameters.fs,
      world_parameters.fft_size, specl, realspec);
    for(int i = 0; i < f0_length; i ++){
      delete [] world_parameters.spectrogram[i];
      for(int j = 0; j < fft_size / 2 + 1; j ++){
        realspec[i][j] /= 1e4;
      }
    }
    delete [] world_parameters.spectrogram;
    world_parameters.spectrogram = realspec;
  }

  fp = fopen(argv[3], "rb");
  buffer = new float[apl];
  for (int i = 0; i < f0_length; i++) {
    world_parameters.aperiodicity[i] = new double[specl];
    fread(buffer, sizeof(float), apl, fp);
    ToDouble(buffer, apl, world_parameters.aperiodicity[i]);
  }
  fclose(fp);
  delete [] buffer;

  if(spec_dimension != 0){
    //decode
    if(oddApl){
      apl -= 1;
    }
    double **realap = new double*[world_parameters.f0_length];
    double *xx = new double[fft_size];
    double *yy = new double[fft_size];
    double PI = acos(-1);
    for(int i = 0; i < f0_length; i ++){
      realap[i] = new double[fft_size / 2 + 1];
      world_parameters.aperiodicity[i][0] += 9.210340;
      mgc2sp(world_parameters.aperiodicity[i], apl, ALPHA, 0, xx, yy, fft_size);
      for (int j = 0; j < apl;j++){
    		realap[i][j] = exp(xx[j]) / 1e4;
    	}
    }
    delete [] xx;
    delete [] yy;
    /*DecodeSpectralEnvelope(world_parameters.aperiodicity, world_parameters.f0_length, world_parameters.fs,
      world_parameters.fft_size, apl, realap);*/
    for(int i = 0; i < f0_length; i ++){
      delete [] world_parameters.aperiodicity[i];
    }
    delete [] world_parameters.aperiodicity;
    world_parameters.aperiodicity = realap;
  }

  // The length of the output waveform
  int y_length = static_cast<int>((world_parameters.f0_length - 1) * world_parameters.frame_period / 1000.0 * fs) + 1;
  double *y = new double[y_length];
  // Synthesis
  WaveformSynthesis(&world_parameters, fs, y_length, y);

  // Output
  wavwrite(y, y_length, fs, 16, argv[4]);

  delete[] y;
  DestroyMemory(&world_parameters);
    
  printf("complete.\n");
  return 0;
}
