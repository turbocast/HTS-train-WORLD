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

use strict;

if ( @ARGV != 1 ) {
   die "ERROR: makequestion.pl config_file \n";
}

my $config_file = $ARGV[0];

my @reserved_feature_name = ( "Pos_C-State_in_Phone(Fw)", "Pos_C-State_in_Phone(Bw)", "Pos_C-Frame_in_State(Fw)", "Pos_C-Frame_in_State(Bw)", "Pos_C-Frame_in_Phone(Fw)", "Pos_C-Frame_in_Phone(Bw)" );

my @feature_name = ();
my @feature_type = ();    # reserved, float,  binary
my @feature_patt = ();
my @feature_min  = ();
my @feature_max  = ();

open( I, $config_file ) || die "ERROR: Cannot open file : $config_file\n";
while ( my $line = <I> ) {
   chomp($line);

   # remove initial/final spaces
   $line =~ s/^\s*(.*?)\s*$/$1/;

   # skip comments
   if ( index( $line, "#" ) == 0 || length($line) == 0 ) {
      next;
   }

   # temporary array
   my @arr = split( /\s+/, $line );

   # temporary variables
   my $name = "";
   my $type = "";
   my $patt = "";
   my $min  = "";
   my $max  = "";

   # name
   if ( @arr > 0 ) {
      $name = $arr[0];
   }

   # type
   for ( my $i = 0 ; $i < @reserved_feature_name ; $i++ ) {
      if ( $name eq $reserved_feature_name[$i] ) {
         $type = "reserved";
         last;
      }
   }
   if ( $type eq "" && @arr > 1 ) {
      if ( index( $arr[1], "\%d" ) > 0 ) {
         $type = "float";
      }
      else {
         $type = "binary";
      }
   }

   # patt (first "{" and final "}" are removed)
   if ( ( $type eq "float" || $type eq "binary" ) && @arr > 1 && index( $arr[1], "{" ) == 0 && rindex( $arr[1], "}" ) == length( $arr[1] ) - 1 ) {
      $patt = substr( $arr[1], length("{"), -length("{") );
   }

   # min & max
   {
      my $search_index = 0;
      if ( $type eq "reserved" ) {
         $search_index = 1;
      }
      elsif ( $type eq "float" ) {
         $search_index = 2;
      }
      for ( my $i = $search_index ; $i < @arr ; $i++ ) {
         my $str = $arr[$i];
         if ( index( $arr[$i], "MIN=" ) == 0 ) {
            $min = substr( $arr[$i], length("MIN=") );
         }
         elsif ( index( $arr[$i], "MAX=" ) == 0 ) {
            $max = substr( $arr[$i], length("MAX=") );
         }
      }
   }

   # check name
   if ( $name eq "" ) {
      die "ERROR: There is not feature name : $line\n";
   }

   # check type
   if ( $type eq "" ) {
      die "ERROR: Cannot specify feature type : $line\n";
   }

   # check pattern
   if ( $type eq "float" || $type eq "binary" ) {
      if ( $patt eq "" ) {
         die "ERROR: There is not feature patten : $line\n";
      }
   }
   if ( $type eq "float" ) {
      if ( index( $patt, "\%d" ) < 0 ) {
         die "ERROR: There is not '\%d' in feature pattern : $line\n";
      }
      if ( index( $patt, "\%d" ) != rindex( $patt, "\%d" ) ) {
         die "ERROR: There are multiple '\%d' in feature pattern : $line\n";
      }
      if ( index( $patt, "," ) >= 0 ) {
         die "ERROR: There are multiple patterns for float in feature pattern : $line\n";
      }
   }

   # check min & max
   if ( $type eq "float" || $type eq "reserved" ) {
      if ( $min eq "" || $max eq "" ) {
         die "ERROR: Min and max values are required : $line\n";
      }
      if ( $min !~ /^[+-]?[0-9]+$/ || $max !~ /^[+-]?[0-9]+$/ ) {
         die "ERROR: Min and max values must be integer : $line\n";
      }
   }

   # store
   push( @feature_name, $name );
   push( @feature_type, $type );
   push( @feature_patt, $patt );
   push( @feature_min,  $min );
   push( @feature_max,  $max );
}
close(I);

for ( my $i = 0 ; $i < @feature_name ; $i++ ) {
   if ( $feature_type[$i] eq "reserved" ) {

      # do nothing
   }
   elsif ( $feature_type[$i] eq "float" ) {
      {
         my $patt = $feature_patt[$i];
         $patt =~ s/\%d/xx/g;
         printf "QS \"$feature_name[$i]==xx\" \{$patt\}\n";
      }
      for ( my $j = $feature_min[$i] ; $j <= @feature_max[$i] ; $j++ ) {
         my $patt = $feature_patt[$i];
         $patt =~ s/\%d/$j/g;
         printf "QS \"$feature_name[$i]==$j\" \{$patt\}\n";
      }
      for ( my $j = $feature_min[$i] + 1 ; $j < $feature_max[$i] ; $j++ ) {
         my $patt = "";
         my @patt_list = get_patt( $feature_min[$i], $j );
         for ( my $k = 0 ; $k < @patt_list ; $k++ ) {
            my $p = $feature_patt[$i];
            $p =~ s/\%d/${patt_list[$k]}/g;
            if ( $patt ne "" ) {
               $patt .= ",";
            }
            $patt .= $p;
         }
         printf "QS \"$feature_name[$i]<=$j\" \{$patt\}\n";
      }
   }
   elsif ( $feature_type[$i] eq "binary" ) {
      printf "QS \"$feature_name[$i]\" \{$feature_patt[$i]\}\n";
   }
   else {
      die "ERROR: Unknown feature type\n";
   }
}

exit(0);

sub get_patt {
   my ( $start, $end ) = @_;

   if ( $start > $end ) {
      die "ERROR: Cannot make patterns\n";
   }

   if ( $start < 0 && $end < 0 ) {
      my @tmp = get_patt( -$end, -$start );
      for ( my $i = $#tmp ; $i >= 0 ; $i-- ) {
         $tmp[$i] = "-" . $tmp[$i];
      }
      return reverse(@tmp);
   }

   if ( $start < 0 && $end >= 0 ) {
      my @tmp1 = get_patt( 0, -$start );
      my @tmp2;
      for ( my $i = $#tmp1 ; $i >= 0 ; $i-- ) {
         if ( $tmp1[$i] ne "0" ) {
            push( @tmp2, "-" . $tmp1[$i] );
         }
      }
      @tmp1 = get_patt( 0, $end );
      return ( @tmp2, @tmp1 );
   }

   my @arr;
   {
      my $last_start = -1;
      my $last_end   = -1;
      my @remain     = ();
      for ( my $i = $start ; $i <= $end ; $i++ ) {
         my $j = $i % 10;
         if ( $i % 10 == 0 ) {
            $last_start = $i;
            $last_end   = -1;
         }
         elsif ( $i % 10 == 9 ) {
            $last_end = $i;
         }

         if ( $last_start >= 0 && $last_end >= 0 ) {
            my $str = $i;
            substr( $str, -1, 1 ) = "?";
            push( @arr, $str );
            @remain     = ();
            $last_start = -1;
            $last_end   = -1;
         }
         elsif ( $last_start >= 0 && $last_end < 0 ) {
            push( @remain, $i );
         }
         else {
            push( @arr, $i );
         }
      }
      push( @arr, @remain );
   }

   return @arr;
}
