#!/usr/bin/env python
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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import datetime
import glob
import numpy as np
import os
import sys
import time

from six.moves import xrange
import tensorflow as tf

import DNNDataIO
import DNNDefine


parser = argparse.ArgumentParser()
parser.add_argument('-w', metavar='dir', dest='window_dir', type=str, default=None,
                    help='set window used for trajectory training')
parser.add_argument('-C', metavar='cf', dest='config', type=str, required=True,
                    help='set config file to cf')
parser.add_argument('-H', metavar='dir', dest='model_dir', type=str, required=True,
                    help='set directory to load a model')
parser.add_argument('-M', metavar='dir', dest='gen_dir', type=str, default='.',
                    help='set directory to write outputs')
parser.add_argument('-S', metavar='f', dest='script', type=str, required=True,
                    help='set generation script file to f')
parser.add_argument('-X', metavar='ext', dest='extension', type=str, default='ffo',
                    help='set output file extension')
args = parser.parse_args()


def print_time(message):
    date = datetime.datetime.today().strftime('%x %X')
    print(message, 'at', date)


def format_duration(duration):
    if duration >= 1000:
        return '%.1f hour' % (duration / 3600)
    elif duration >= 100:
        return '%.1f min' % (duration / 60)
    else:
        return '%.2f sec' % (duration)


def main():
    config = DNNDataIO.load_config(args.config)

    if len(config['all_spkrs']) > 1:
        mode = 'SAT'
    else:
        mode = 'SD'

    # Make directories
    if not os.path.exists(args.gen_dir):
        os.mkdir(args.gen_dir)
    model_path = os.path.join(args.model_dir, 'model.ckpt')
    if config['restore_ckpt'] > 0:
        model_path = '-'.join([model_path, str(config['restore_ckpt'])])
    if len(glob.glob("%s*" % model_path)) == 0:
        sys.exit('  ERROR  main: No such file %s' % model_path)

    # Load window for trajectory training
    windows = []
    if args.window_dir is not None:
        for filename in config['window_filenames']:
            windows.append(
                DNNDataIO.load_window(os.path.join(args.window_dir, filename)))
        # Assume that all features have the same number of windows.
        num_windows = (len(config['window_filenames']) //
                       len(config['num_feature_dimensions']))
        window_width = len(windows[0])
        window_vector = []
        for i in xrange(len(config['num_feature_dimensions'])):
            for j in xrange(window_width - 1, -1, -1):
                for k in xrange(num_windows):
                    window_vector.append(windows[i * num_windows + k][j])
        window_vector = np.reshape(
            window_vector, [len(config['num_feature_dimensions']), -1])
        window_vector = np.repeat(
            window_vector, config['num_feature_dimensions'], axis=0)
        window_vector = window_vector.astype(np.float32)

    with tf.Graph().as_default():
        inputs = tf.placeholder(dtype=tf.float32,
                                shape=[None, config['num_input_units']])
        outputs = tf.placeholder(dtype=tf.float32,
                                 shape=[None, config['num_output_units']])

        with tf.variable_scope('model'):
            (predicted_outputs, trained_variances, trained_gv_variances) = (
                DNNDefine.inference(
                    inputs,
                    [[len(config['all_spkrs']) - 1]],
                    config['num_io_units'],
                    config['num_hidden_units'],
                    len(config['all_spkrs']),
                    sum(config['num_feature_dimensions']),
                    config['hidden_activation'],
                    config['output_activation'],
                    1.0,
                    mode))

        if config['frame_by_frame']:
            cost_op, _ = DNNDefine.cost(
                predicted_outputs,
                outputs,
                trained_variances)
        else:
            cost_op, predicted_outputs = DNNDefine.trajectory_cost(
                predicted_outputs,
                outputs,
                trained_variances,
                trained_gv_variances,
                config['num_feature_dimensions'],
                config['msd_flags'],
                num_windows,
                window_vector)

        init_op = tf.group(
            tf.global_variables_initializer(),
            tf.local_variables_initializer())

        sess = tf.Session(config=tf.ConfigProto(
            intra_op_parallelism_threads=config['num_threads']))

        sess.run(init_op)

        saver = tf.train.Saver()
        saver.restore(sess, model_path)

        input_filenames, output_filenames = DNNDataIO.get_filenames(
            args.script)

        print_time('Start forwarding')
        for i in xrange(len(input_filenames)):
            print('  Processing %s' % input_filenames[i])
            input_data = DNNDataIO.load_binary_data(input_filenames[i],
                                                    config['num_input_units'])
            if output_filenames[i] is not None:
                output_data = DNNDataIO.load_binary_data(output_filenames[i],
                                                         config['num_output_units'])
            num_examples = len(input_data)

            basename = os.path.splitext(
                os.path.basename(input_filenames[i]))[0]
            basename = os.path.join(args.gen_dir, basename)
            if args.extension == '':
                predict_filename = basename
            else:
                predict_filename = basename + '.' + args.extension

            total_cost = 0.0
            start_time = time.time()

            if config['frame_by_frame']:
                DNNDataIO.write_binary_data(basename + '.var',
                                            sess.run(trained_variances))
                for j in xrange(num_examples):
                    if output_filenames[i] is None:
                        predicts = sess.run(predicted_outputs,
                                            feed_dict={inputs: [input_data[j]]})
                    else:
                        predicts, cost = sess.run([predicted_outputs, cost_op],
                                                  feed_dict={
                                                      inputs: [input_data[j]],
                                                      outputs: [output_data[j]]})
                        total_cost += cost
                    append = False if j == 0 else True
                    DNNDataIO.write_binary_data(
                        predict_filename, predicts, append)
                total_cost = total_cost / num_examples
            else:
                if output_filenames[i] is None:
                    predicts = sess.run(predicted_outputs,
                                        feed_dict={inputs: input_data})
                else:
                    predicts, cost = sess.run([predicted_outputs, cost_op],
                                              feed_dict={
                                                  inputs: input_data,
                                                  outputs: output_data})
                    total_cost = cost
                append = False
                DNNDataIO.write_binary_data(predict_filename, predicts, append)

            if output_filenames[i] is not None:
                duration = format_duration(time.time() - start_time)
                print('    Evaluation: cost = %e (%s)' % (total_cost, duration))

        sess.close()

    print_time('End forwarding')
    print()


if __name__ == '__main__':
    main()
