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

if ( @ARGV != 1 && @ARGV != 3 ) {
   my $msg = "";
   $msg .= "ERROR: makefeature.pl config_file                                    (output number of features)\n";
   $msg .= "       makefeature.pl config_file frame_shift(0.00001sec) input_file (output features)\n";
   die "$msg";
}

my $config_file = $ARGV[0];
my $frame_shift = $ARGV[1];
my $input_file  = $ARGV[2];

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
   if (  ( $type eq "float" || $type eq "binary" )
      && @arr > 1
      && index( $arr[1], "{" ) == 0
      && rindex( $arr[1], "}" ) == length( $arr[1] ) - 1 )
   {
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

if ( $frame_shift eq "" || $input_file eq "" ) {
   my $size = @feature_name;
   print "$size\n";
   exit(0);
}

my $label_level       = "";    # state, phoneme
my @label_start       = ();
my @label_end         = ();
my @label_str         = ();
my @label_state_index = ();

open( I, $input_file ) || die "ERROR: Cannot open file : $input_file\n";
while ( my $line = <I> ) {
   chomp($line);

   # remove initial/final spaces
   $line =~ s/^\s*(.*?)\s*$/$1/;

   # temporary array
   my @arr = split( /\s+/, $line );

   # temporary variables
   my $start          = "";
   my $end            = "";
   my $str            = "";
   my $is_state_level = 0;
   my $state_index    = 0;

   # start
   if ( @arr > 0 ) {
      $start = int( 0.5 + $arr[0] / $frame_shift );
   }

   # end
   if ( @arr > 1 ) {
      $end = int( 0.5 + $arr[1] / $frame_shift );
   }

   # str
   if ( @arr > 2 ) {
      $str = $arr[2];
   }

   # state index with detecting label level (state or phoneme)
   {
      my $state_separator_left  = rindex( $str, "[" );
      my $state_separator_right = rindex( $str, "]" );
      my $state_index_str       = "";
      if (  $state_separator_left > 0
         && $state_separator_right > 0
         && $state_separator_left < $state_separator_right )
      {
         $state_index_str =
           substr( $str, $state_separator_left + length("["), -length("]") );
         if ( $state_index_str =~ /^[+-]?[0-9]+$/
            && 2 <= int($state_index_str) )
         {
            $is_state_level = 1;
            $state_index    = int($state_index_str);
         }
      }
   }

   # remove state index from str
   if ( $is_state_level == 1 ) {
      substr( $str, rindex( $str, "[" ) ) = "";
   }

   # check start & end
   if ( $start eq "" || $end eq "" ) {
      die "ERROR: There is not start/end time in label : $line\n";
   }
   if ( $start !~ /^[+-]?[0-9]+$/ || $end !~ /^[+-]?[0-9]+$/ ) {
      die "ERROR: Start/end must be integer in label : $line\n";
   }
   if ( $end <= $start || $start < 0 ) {
      die "ERROR: There is error of start/end value in label : $line\n";
   }

   # check str
   if ( $str eq "" ) {
      die "ERROR: There is not model name in label : $line\n";
   }

   # check label level
   if ( $label_level eq "" ) {
      if ( $is_state_level == 1 ) {
         $label_level = "state";
      }
      else {
         $label_level = "phoneme";
      }
   }
   elsif ( $label_level eq "state" && $is_state_level != 1 ) {
      die "ERROR: There is phoneme-level line in state-level label : $line\n";
   }
   elsif ( $label_level eq "phomeme" && $is_state_level != 0 ) {
      die "ERROR: There is state-level line in phoneme-level label : $line\n";
   }

   # store
   push( @label_start,       $start );
   push( @label_end,         $end );
   push( @label_str,         $str );
   push( @label_state_index, $state_index );
}
close(I);

my @label_phoneme_start_index = ();
my @label_phoneme_end_index   = ();

if ( $label_level eq "phoneme" ) {
   for ( my $i = 0 ; $i < @label_start ; $i++ ) {
      push( @label_phoneme_start_index, $i );
      push( @label_phoneme_end_index,   $i );
   }
}
elsif ( $label_level eq "state" ) {
   for ( my $i = 0 ; $i < @label_start ; $i++ ) {
      my $start = $i;
      my $end   = $i;
      while ( $start != 0
         && $label_state_index[ $start - 1 ] < $label_state_index[$start] )
      {
         $start--;
      }
      while ( $end != $#label_start
         && $label_state_index[$end] < $label_state_index[ $end + 1 ] )
      {
         $end++;
      }
      push( @label_phoneme_start_index, $start );
      push( @label_phoneme_end_index,   $end );
   }
}
else {
   die "ERROR: Unknown label level\n";
}

for ( my $i = 0 ; $i < @label_start ; $i++ ) {

   # create label-line-level features
   my @feature = ();
   for ( my $j = 0 ; $j < @feature_name ; $j++ ) {
      my $name = $feature_name[$j];
      my $type = $feature_type[$j];
      my $patt = $feature_patt[$j];
      my $max  = $feature_max[$j];
      my $min  = $feature_min[$j];
      if ( $type eq "reserved" ) {
         push( @feature, 0.0 );    # dummy
      }
      elsif ( $type eq "float" ) {
         my ( $match, $value ) =
           do_match_and_get_digit( $label_str[$i], $patt );
         if ( $match == 1 ) {
            my ( $norm_result, $norm_value ) = norm( $value, $min, $max );
            if ( $norm_result != 1 ) {
               print STDERR "WARNING: Out of range $value : $name MIN=$min MAX=$max\n";
            }
            if ( $norm_value < 0.0 || 1.0 < $norm_value ) {
               die "ERROR: Normalization error $value : $name MIN=$min MAX=$max\n";
            }
            push( @feature, $norm_value );
         }
         else {
            push( @feature, 0.0 );
         }
      }
      elsif ( $type eq "binary" ) {
         my @arr = split( ',', $patt );
         my $value = 0.0;
         for ( my $k = 0 ; $k < @arr ; $k++ ) {
            my $p = $arr[$k];
            if ( do_match( $label_str[$i], $p ) == 1 ) {
               $value = 1.0;
               last;
            }
         }
         push( @feature, $value );
      }
      else {
         die "ERROR: Unknown feature type\n";
      }
   }

   # output frame-level features
   for ( my $j = $label_start[$i] ; $j < $label_end[$i] ; $j++ ) {
      for ( my $k = 0 ; $k < @feature_name ; $k++ ) {
         my $name = $feature_name[$k];
         my $type = $feature_type[$k];
         my $patt = $feature_patt[$k];
         my $max  = $feature_max[$k];
         my $min  = $feature_min[$k];
         if ( $type eq "reserved" ) {
            my $value;
            if ( $name eq "Pos_C-State_in_Phone(Fw)" ) {
               if ( $label_level ne "state" ) {
                  print STDERR "WARNING: There is not state-level information in label\n";
                  $value = $min;
               }
               else {
                  $value = $label_state_index[$i];
               }
            }
            elsif ( $name eq "Pos_C-State_in_Phone(Bw)" ) {
               if ( $label_level ne "state" ) {
                  print STDERR "WARNING: There is not state-level information in label\n";
                  $value = $min;
               }
               else {
                  $value = $max - $label_state_index[$i] + $min;
               }
            }
            elsif ( $name eq "Pos_C-Frame_in_State(Fw)" ) {
               if ( $label_level ne "state" ) {
                  print STDERR "WARNING: There is not state-level information in label\n";
                  $value = $min;
               }
               else {
                  $value = 1 + $j - $label_start[$i];
               }
            }
            elsif ( $name eq "Pos_C-Frame_in_State(Bw)" ) {
               if ( $label_level ne "state" ) {
                  print STDERR "WARNING: There is not state-level information in label\n";
                  $value = $min;
               }
               else {
                  $value = $label_end[$i] - $j;
               }
            }
            elsif ( $name eq "Pos_C-Frame_in_Phone(Fw)" ) {
               $value = 1 + $j - $label_start[ $label_phoneme_start_index[$i] ];
            }
            elsif ( $name eq "Pos_C-Frame_in_Phone(Bw)" ) {
               $value = $label_end[ $label_phoneme_end_index[$i] ] - $j;
            }
            else {
               die "ERROR: Unknown reserved feature name\n";
            }
            my ( $norm_result, $norm_value ) = norm( $value, $min, $max );
            if ( $norm_result != 1 ) {
               print STDERR "WARNING: Out of range $value : $name MIN=$min MAX=$max\n";
            }
            if ( $norm_value < 0.0 || 1.0 < $norm_value ) {
               die "ERROR: Normalization error $value : $name MIN=$min MAX=$max\n";
            }
            print "$norm_value\n";
         }
         else {
            print "$feature[$k]\n";
         }
      }
   }
}

exit(0);

sub norm {
   my ( $value, $min, $max ) = @_;

   if ( $value < $min ) {
      return ( 0, 0.0 );
   }
   elsif ( $max < $value ) {
      return ( 0, 1.0 );
   }
   else {
      return ( 1, ( $value - $min ) / ( $max - $min ) );
   }
}

sub do_match {
   my ( $str, $patt ) = @_;

   $patt =~ s/\*/\.\*/g;
   $patt =~ s/\?/\.\?/g;
   $patt =~ s/\+/\\\+/g;
   $patt =~ s/\|/\\\|/g;
   $patt =~ s/\^/\\\^/g;
   $patt =~ s/\$/\\\$/g;
   $patt =~ s/\[/\\\[/g;
   $patt =~ s/\]/\\\]/g;

   if ( $str =~ /^$patt$/ ) {
      return 1;
   }
   else {
      return 0;
   }
}

sub do_match_and_get_digit {
   my ( $str, $patt ) = @_;

   $patt =~ s/\*/\.\*/g;
   $patt =~ s/\?/\.\?/g;
   $patt =~ s/\+/\\\+/g;
   $patt =~ s/\|/\\\|/g;
   $patt =~ s/\^/\\\^/g;
   $patt =~ s/\$/\\\$/g;
   $patt =~ s/\[/\\\[/g;
   $patt =~ s/\]/\\\]/g;

   $patt =~ s/\%d/\(\[\+\-\]\?\[0\-9\]\+\)/g;

   if ( $str =~ /^$patt$/ ) {
      return ( 1, $1 );
   }
   else {
      return ( 0, 0.0 );
   }
}

sub recursive_match {
   my ( $str, $patt, $str_len, $min_patt_len, $num_stars ) = @_;

   if ( $str_len == 0 && $min_patt_len == 0 ) {
      return 1;
   }
   if ( $num_stars == 0 && $min_patt_len != $str_len ) {
      return 0;
   }
   if ( $min_patt_len > $str_len ) {
      return 0;
   }

   if ( substr( $patt, 0, 1 ) eq "*" ) {
      if (  recursive_match( substr( $str, 1 ), substr( $patt, 1 ), $str_len - 1, $min_patt_len, $num_stars - 1 ) == 1
         || recursive_match( $str, substr( $patt, 1 ), $str_len, $min_patt_len, $num_stars - 1 ) == 1
         || recursive_match( substr( $str, 1 ), $patt, $str_len - 1, $min_patt_len, $num_stars ) == 1 )
      {
         return 1;
      }
      else {
         return 0;
      }
   }
   if (  substr( $patt, 0, 1 ) eq substr( $str, 0, 1 )
      || substr( $patt, 0, 1 ) eq "?" )
   {
      return recursive_match( substr( $str, 1 ), substr( $patt, 1 ), $str_len - 1, $min_patt_len - 1, $num_stars );
   }
   else {
      return 0;
   }
}
