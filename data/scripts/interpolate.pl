#!/usr/bin/perl
# ----------------------------------------------------------------- #
#           The HMM-Based Speech Synthesis System (HTS)             #
#           developed by HTS Working Group                          #
#           http://hts.sp.nitech.ac.jp/                             #
# ----------------------------------------------------------------- #
#                                                                   #
#  Copyright (c) 2014-2017  Nagoya Institute of Technology          #
#                           Department of Computer Science          #
#                                                                   #
# All rights reserved.                                              #
#                                                                   #
# Redistribution and use in source and binary forms, with or        #
# without modification, are permitted provided that the following   #
# conditions are met:                                               #
#                                                                   #
# - Redistributions of source code must retain the above copyright  #
#   notice, this list of conditions and the following disclaimer.   #
# - Redistributions in binary form must reproduce the above         #
#   copyright notice, this list of conditions and the following     #
#   disclaimer in the documentation and/or other materials provided #
#   with the distribution.                                          #
# - Neither the name of the HTS working group nor the names of its  #
#   contributors may be used to endorse or promote products derived #
#   from this software without specific prior written permission.   #
#                                                                   #
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND            #
# CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,       #
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF          #
# MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE          #
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS #
# BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,          #
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED   #
# TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,     #
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON #
# ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,   #
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY    #
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE           #
# POSSIBILITY OF SUCH DAMAGE.                                       #
# ----------------------------------------------------------------- #

if ( @ARGV < 1 ) {
   print "interpolate.pl dimensionality infile \n";
   exit(0);
}

$magicnumber = -1.0e+10;

# dimensionality of input vector
$dim = $ARGV[0];

# open infile as a sequence of static coefficients
open( INPUT, "$ARGV[1]" ) || die "cannot open file : $ARGV[1]";
@STAT = stat(INPUT);
read( INPUT, $data, $STAT[7] );
close(INPUT);

$n = $STAT[7] / 4;    # number of data
$T = $n / $dim;       # number of frames of original data

# load original data
@original = unpack( "f$n", $data );    # original data must be stored in float, natural endian

# copy original data
@interpolated = @original;

# interpolate
for ( $i = 0 ; $i < $dim ; $i++ ) {
   $lastvalue = $magicnumber;
   for ( $t = 0 ; $t < $T ; $t++ ) {
      if ( $original[ $t * $dim + $i ] == $magicnumber ) {
         for ( $t1 = $t + 1 ; $t1 < $T ; $t1++ ) {
            last if ( $original[ $t1 * $dim + $i ] != $magicnumber );
         }
         if ( $t1 < $T ) {
            if ( $lastvalue == $magicnumber ) {
               for ( $s = $t ; $s < $t1 ; $s++ ) {
                  $interpolated[ $s * $dim + $i ] = $original[ $t1 * $dim + $i ];
               }
            }
            else {
               $step = ( $original[ $t1 * $dim + $i ] - $original[ ( $t - 1 ) * $dim + $i ] ) / ( $t1 - $t + 1 );
               for ( $s = $t ; $s < $t1 ; $s++ ) {
                  $interpolated[ $s * $dim + $i ] = $original[ ( $t - 1 ) * $dim + $i ] + $step * ( $s - $t + 1 );
               }
            }
         }
         else {
            if ( $lastvalue == $magicnumber ) {
               die "no valid value\n";
            }
            else {
               for ( $s = $t ; $s < $T ; $s++ ) {
                  $interpolated[ $s * $dim + $i ] = $lastvalue;
               }
            }
         }
         $t = $t1 - 1;
      }
      else {
         $lastvalue = $original[ $t * $dim + $i ];
         $interpolated[ $t * $dim + $i ] = $original[ $t * $dim + $i ];
      }
   }
}

$data = pack( "f$n", @interpolated );

print $data;
