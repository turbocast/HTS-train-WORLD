//-----------------------------------------------------------------------------
// 
// Author: Yuxuan Zhang (hyperzlink@outlook.com)
// Date: 2018/12/02
//
// To extract LF0, MGC and BAP with WORLD vocoder
//
// This is modified based on Msanori Morise's test.cpp.
//
// analysis <input wav> <output f0/lf0> <output sp/mgc> <output ap/bap> \
//    [<frame period> <fft size> <enable compress & spec dimension> <aper dimension>]
//
//-----------------------------------------------------------------------------

#include <math.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

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
#include "world/d4c.h"
#include "world/dio.h"
#include "world/matlabfunctions.h"
#include "world/cheaptrick.h"
#include "world/stonemask.h"
#include "world/codec.h"
#include "world/synthesis.h"

#include "world/common.h"
#include "world/constantnumbers.h"
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
  
  //int number_of_aperiodicities;
} WorldParameters;

namespace {

void DisplayInformation(int fs, int nbit, int x_length) {
  printf("File information\n");
  printf("Sampling : %d Hz %d Bit\n", fs, nbit);
  printf("Length %d [sample]\n", x_length);
  printf("Length %f [sec]\n", static_cast<double>(x_length) / fs);
}

void F0Estimation(double *x, int x_length, WorldParameters *world_parameters) {
  DioOption option = {0};
  InitializeDioOption(&option);

  // Modification of the option
  // When you You must set the same value.
  // If a different value is used, you may suffer a fatal error because of a
  // illegal memory access.
  option.frame_period = world_parameters->frame_period;

  // Valuable option.speed represents the ratio for downsampling.
  // The signal is downsampled to fs / speed Hz.
  // If you want to obtain the accurate result, speed should be set to 1.
  option.speed = 1;

  // You should not set option.f0_floor to under world::kFloorF0.
  // If you want to analyze such low F0 speech, please change world::kFloorF0.
  // Processing speed may sacrify, provided that the FFT length changes.
  option.f0_floor = 71.0;

  // You can give a positive real number as the threshold.
  // Most strict value is 0, but almost all results are counted as unvoiced.
  // The value from 0.02 to 0.2 would be reasonable.
  option.allowed_range = 0.1;

  // Parameters setting and memory allocation.
  world_parameters->f0_length = GetSamplesForDIO(world_parameters->fs,
    x_length, world_parameters->frame_period);
  world_parameters->f0 = new double[world_parameters->f0_length];
  world_parameters->time_axis = new double[world_parameters->f0_length];
  double *refined_f0 = new double[world_parameters->f0_length];

  printf("\nAnalysis\n");
  printf("Frame period: %.0lf\n", world_parameters->frame_period);
  DWORD elapsed_time = timeGetTime();
  Dio(x, x_length, world_parameters->fs, &option, world_parameters->time_axis,
      world_parameters->f0);
  printf("DIO: %d [msec]\n", timeGetTime() - elapsed_time);

  // StoneMask is carried out to improve the estimation performance.
  elapsed_time = timeGetTime();
  StoneMask(x, x_length, world_parameters->fs, world_parameters->time_axis,
      world_parameters->f0, world_parameters->f0_length, refined_f0);
  printf("StoneMask: %d [msec]\n", timeGetTime() - elapsed_time);

  for (int i = 0; i < world_parameters->f0_length; ++i)
    world_parameters->f0[i] = refined_f0[i];

  delete[] refined_f0;
  return;
}

void SpectralEnvelopeEstimation(double *x, int x_length, int fft_size,
    WorldParameters *world_parameters) {
  CheapTrickOption option = {0};
  InitializeCheapTrickOption(world_parameters->fs, &option);

  // This value may be better one for HMM speech synthesis.
  // Default value is -0.09.
  option.q1 = -0.15;

  // Important notice (2016/02/02)
  // You can control a parameter used for the lowest F0 in speech.
  // You must not set the f0_floor to 0.
  // It will cause a fatal error because fft_size indicates the infinity.
  // You must not change the f0_floor after memory allocation.
  // You should check the fft_size before excucing the analysis/synthesis.
  // The default value (71.0) is strongly recommended.
  // On the other hand, setting the lowest F0 of speech is a good choice
  // to reduce the fft_size.
  option.f0_floor = 71.0;

  // Parameters setting and memory allocation.
  if(fft_size == 0){
    world_parameters->fft_size =
      GetFFTSizeForCheapTrick(world_parameters->fs, &option);
  } else {
    world_parameters->fft_size = fft_size;
  }
  world_parameters->spectrogram = new double *[world_parameters->f0_length];
  for (int i = 0; i < world_parameters->f0_length; ++i) {
    world_parameters->spectrogram[i] =
      new double[world_parameters->fft_size / 2 + 1];
  }

  DWORD elapsed_time = timeGetTime();
  CheapTrick(x, x_length, world_parameters->fs, world_parameters->time_axis,
      world_parameters->f0, world_parameters->f0_length, &option,
      world_parameters->spectrogram);
  printf("fft size: %d\n", world_parameters->fft_size);
  printf("CheapTrick: %d [msec]\n", timeGetTime() - elapsed_time);
}

void AperiodicityEstimation(double *x, int x_length,
    WorldParameters *world_parameters) {
  D4COption option = {0};
  InitializeD4COption(&option);
  option.threshold = 0;
  
  world_parameters->aperiodicity = new double *[world_parameters->f0_length];
  for (int i = 0; i < world_parameters->f0_length; ++i) {
      world_parameters->aperiodicity[i] = 
        new double[world_parameters->fft_size / 2 + 1];
  }

  DWORD elapsed_time = timeGetTime();
  D4C(x, x_length, world_parameters->fs, world_parameters->time_axis,
      world_parameters->f0, world_parameters->f0_length,
      world_parameters->fft_size, &option, world_parameters->aperiodicity);
  printf("D4C: %d [msec]\n", timeGetTime() - elapsed_time);
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

void ToLF0(double *f0, int len, double *lf0){
  for(int i = 0; i < len; i ++){
    if(f0[i] != 0){
      lf0[i] = log(f0[i]);
    } else {
      lf0[i] = 0;
    }
  }
}

void ToFloat(double *input, int len, float *output){
  for(int i = 0; i < len; i ++){
    output[i] = (float)input[i];
  }
}

}  // namespace

//-----------------------------------------------------------------------------
// Test program.
// test.exe input.wav outout.wav f0 spec flag
// input.wav  : argv[1] Input file
// lf0        : argv[2] lf0 file
// mgc        : argv[3] mgc file
// bap        : argv[4] bap file
// dimension  : argv[5] dimension for mgc
//-----------------------------------------------------------------------------
int main(int argc, char *argv[]) {
  if (argc != 5 && argc != 6 && argc != 7 && argc != 8 && argc != 9) {
    printf("Usage: %s <input wav> <output f0/lf0> <output sp/mgc> <output ap/bap> [<frame period> <fft size> <enable compress & spec dimension> <aper dimension>]\n", argv[0]);
    return -2;
  }

  // 2016/01/28: Important modification.
  // Memory allocation is carried out in advanse.
  // This is for compatibility with C language.
  int x_length = GetAudioLength(argv[1]);
  if (x_length <= 0) {
    if (x_length == 0)
      printf("error: File not found.\n");
    else
      printf("error: The file is not .wav format.\n");
    return -1;
  }
  double *x = new double[x_length];
  // wavread() must be called after GetAudioLength().
  int fs, nbit;
  wavread(argv[1], &fs, &nbit, x);
  DisplayInformation(fs, nbit, x_length);

  //---------------------------------------------------------------------------
  // Analysis part
  //---------------------------------------------------------------------------
  // 2016/02/02
  // A new struct is introduced to implement safe program.
  WorldParameters world_parameters = { 0 };
  // You must set fs and frame_period before analysis/synthesis.
  world_parameters.fs = fs;

  // 5.0 ms is the default value.
  // Generally, the inverse of the lowest F0 of speech is the best.
  // However, the more elapsed time is required.
  if(argc >= 6){
    world_parameters.frame_period = atof(argv[5]);
  } else {
    world_parameters.frame_period = 5.0;
  }

  // F0 estimation
  F0Estimation(x, x_length, &world_parameters);

  // Spectral envelope estimation
  int fft_size = 0;
  if(argc >= 7) fft_size = atoi(argv[6]);
  SpectralEnvelopeEstimation(x, x_length, fft_size, &world_parameters);

  int number_of_dimensions = world_parameters.fft_size / 2 + 1;
  if(argc >= 8 && atoi(argv[7]) != 0){
    number_of_dimensions = atoi(argv[7]);
    double **coded_spectrogram = new double *[world_parameters.f0_length];
    for (int i = 0; i < world_parameters.f0_length; ++i){
      for(int j = 0; j < world_parameters.fft_size / 2 + 1; j ++)
        world_parameters.spectrogram[i][j] *= 32768.0;
      coded_spectrogram[i] = new double[number_of_dimensions];
    }
    CodeSpectralEnvelope(world_parameters.spectrogram, world_parameters.f0_length, world_parameters.fs,
      world_parameters.fft_size, number_of_dimensions, coded_spectrogram);
    for(int i = 0; i < world_parameters.f0_length; i ++){
      delete [] world_parameters.spectrogram[i];
      coded_spectrogram[i][0] += 12.0;
      /*for(int j = 0; j < number_of_dimensions; i ++){
        coded_spectrogram[i][j] /= 2;
      }*/
    }
    delete [] world_parameters.spectrogram;
    world_parameters.spectrogram = coded_spectrogram;
  }

  // Aperiodicity estimation by D4C
  AperiodicityEstimation(x, x_length, &world_parameters);

  int number_of_aperiodicities = world_parameters.fft_size / 2 + 1;
  if(argc >= 8 && atoi(argv[7]) != 0){
    bool oddApl = false;
    if(argc >= 9){
      number_of_aperiodicities = atoi(argv[8]);
    } else {
      number_of_aperiodicities = 24;
    }
    if(number_of_aperiodicities % 2 == 1){
      oddApl = true;
    }
    printf("number of aperiodicities: %d\n", number_of_aperiodicities);
    double **coded_aperiodicity = new double *[world_parameters.f0_length];
    for (int i = 0; i < world_parameters.f0_length; ++i){
      for(int j = 0; j < world_parameters.fft_size / 2 + 1; j ++)
        world_parameters.aperiodicity[i][j] = world_parameters.aperiodicity[i][j] * 32768.0;
      coded_aperiodicity[i] = new double[number_of_aperiodicities];
    }
    for (int i = 0; i < world_parameters.f0_length; ++i){
      mcep(world_parameters.aperiodicity[i], world_parameters.fft_size / 2 + 1, coded_aperiodicity[i], 
        oddApl ? number_of_aperiodicities - 1 : number_of_aperiodicities,
        0.77, 2, 0, 0.001, 1, 1.0E-8, 0.0, 3);
      if(oddApl){
        coded_aperiodicity[i][number_of_aperiodicities - 1] = 0;
      }
    }
    CodeSpectralEnvelope(world_parameters.aperiodicity, world_parameters.f0_length, world_parameters.fs,
      world_parameters.fft_size, number_of_aperiodicities, coded_aperiodicity);
    for(int i = 0; i < world_parameters.f0_length; i ++){
      delete [] world_parameters.aperiodicity[i];
    }
    delete [] world_parameters.aperiodicity;
    world_parameters.aperiodicity = coded_aperiodicity;
  }
  
  FILE * file = fopen(argv[2], "wb");
  if(argc >= 8 && atoi(argv[7]) != 0){ //to lf0
    double *lf0 = new double[world_parameters.f0_length];
    ToLF0(world_parameters.f0, world_parameters.f0_length, lf0);
    delete [] world_parameters.f0;
    world_parameters.f0 = lf0;
  }
  float *t;
  t = new float[world_parameters.f0_length];
  ToFloat(world_parameters.f0, world_parameters.f0_length, t);
  fwrite(t, sizeof(float), world_parameters.f0_length, file);
  fclose(file);
  delete [] t;

  FILE * fsp = fopen(argv[3], "wb");
  t = new float[number_of_dimensions];
  for(int i = 0; i < world_parameters.f0_length; i++) {
      ToFloat(world_parameters.spectrogram[i], number_of_dimensions, t);
      fwrite(t, sizeof(float), number_of_dimensions, fsp);
  }
  fclose(fsp);
  delete [] t;

  FILE * fap = fopen(argv[4], "wb");
  t = new float[number_of_aperiodicities];
  for  (int i = 0; i < world_parameters.f0_length; i++) {
      //fwrite(world_parameters.aperiodicity[i], sizeof(double), world_parameters.number_of_aperiodicities, fap);
      ToFloat(world_parameters.aperiodicity[i], number_of_aperiodicities, t);
      fwrite(t, sizeof(float), number_of_aperiodicities, fap);
  }
  fclose(fap);
    
    
  delete[] x;
  DestroyMemory(&world_parameters);

  printf("complete.\n");
  return 0;
}
