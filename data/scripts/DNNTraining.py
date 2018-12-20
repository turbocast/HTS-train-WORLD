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
import numpy as np
import os
import time
import traceback

from six.moves import xrange
import tensorflow as tf

import DNNDataIO
import DNNDefine


parser = argparse.ArgumentParser()
parser.add_argument('-w', metavar='dir', dest='window_dir', type=str, default=None,
                    help='set window used for trajectory training')
parser.add_argument('-z', metavar='dir', dest='variance_dir', type=str, default=None,
                    help='set variance used for error calculation')
parser.add_argument('-C', metavar='cf', dest='config', type=str, required=True,
                    help='set config file to cf')
parser.add_argument('-H', metavar='dir', dest='model_dir', type=str, required=True,
                    help='set directory to save trained models')
parser.add_argument('-N', metavar='f', dest='valid_script', type=str, default=None,
                    help='set validation script file to f')
parser.add_argument('-S', metavar='f', dest='train_script', type=str, required=True,
                    help='set training script file to f')
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


def format_num_parameters(num_parameters):
    if num_parameters >= 1e+6:
        return '%.1f M' % (num_parameters / 1e+6)
    elif num_parameters >= 1e+3:
        return '%.1f k' % (num_parameters / 1e+3)
    else:
        return num_parameters


def main():
    config = DNNDataIO.load_config(args.config)

    if config['adaptation']:
        mode = 'ADAPT'
    elif len(config['all_spkrs']) > 1:
        mode = 'SAT'
    else:
        mode = 'SD'
        config['spkr_pattern'] = None

    # Make directories
    if not os.path.exists(args.model_dir):
        os.mkdir(args.model_dir)
    model_path = os.path.join(args.model_dir, 'model.ckpt')

    # Load variance
    if args.variance_dir is not None:
        variances = []
        if mode == 'SD':
            variance = DNNDataIO.load_binary_data(
                os.path.join(args.variance_dir, 'ffo.var'))
            variances.append(np.squeeze(variance))
        elif mode == 'SAT' or mode == 'ADAPT':
            for spkr in config['all_spkrs']:
                variance = DNNDataIO.load_binary_data(
                    os.path.join(args.variance_dir, spkr, 'ffo.var'))
                variances.append(np.squeeze(variance))
        variances = np.asarray(variances, np.float32)

        gv_variances = []
        if mode == 'SD':
            gv_variance = DNNDataIO.load_binary_data(
                os.path.join(args.variance_dir, 'gv.var'))
            gv_variances.append(np.squeeze(gv_variance))
        elif mode == 'SAT' or mode == 'ADAPT':
            for spkr in config['all_spkrs']:
                gv_variance = DNNDataIO.load_binary_data(
                    os.path.join(args.variance_dir, spkr, 'gv.var'))
                gv_variances.append(np.squeeze(gv_variance))
        gv_variances = np.asarray(gv_variances, np.float32)

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
        coord = tf.train.Coordinator()

        if mode == 'SD' or mode == 'SAT':
            print('Preparing to read training data...', end='')
        elif mode == 'ADAPT':
            print('Preparing to read adaptation data...', end='')
        train_reader = DNNDataIO.DataReader(
            config['num_io_units'],
            config['frame_by_frame'],
            config['queue_size'],
            args.train_script,
            coord,
            spkr_pattern=config['spkr_pattern'],
            train_spkrs=config['all_spkrs'],
            seed=config['random_seed'])
        train_inputs, train_outputs, train_spkr_ids = (
            train_reader.dequeue(config['batch_size']))
        if config['frame_by_frame']:
            num_train_steps = (config['num_epochs'] * train_reader.num_examples //
                               config['batch_size'])
            print(' %d examples will be read' % train_reader.num_examples)
        else:
            num_train_steps = (config['num_epochs'] * train_reader.num_files //
                               config['batch_size'])
            print(' %d files will be read' % train_reader.num_files)

        if args.valid_script is not None:
            print('Preparing to read validation data...', end='')
            valid_reader = DNNDataIO.DataReader(
                config['num_io_units'],
                config['frame_by_frame'],
                config['queue_size'],
                args.valid_script,
                coord,
                spkr_pattern=config['spkr_pattern'],
                train_spkrs=config['all_spkrs'],
                seed=config['random_seed'])
            valid_inputs, valid_outputs, valid_spkr_ids = (
                valid_reader.dequeue(config['batch_size']))
            if config['frame_by_frame']:
                num_valid_steps = (valid_reader.num_examples //
                                   config['batch_size'])
                print(' %d examples will be read' % valid_reader.num_examples)
            else:
                num_valid_steps = (valid_reader.num_files //
                                   config['batch_size'])
                print(' %d files will be read' % valid_reader.num_files)
        print('')

        with tf.variable_scope('model'):
            (predicted_train_outputs, train_variances, train_gv_variances) = (
                DNNDefine.inference(
                    train_inputs,
                    train_spkr_ids,
                    config['num_io_units'],
                    config['num_hidden_units'],
                    len(config['all_spkrs']),
                    sum(config['num_feature_dimensions']),
                    config['hidden_activation'],
                    config['output_activation'],
                    config['keep_prob'],
                    mode,
                    seed=config['random_seed'],
                    initial_variances=variances,
                    initial_gv_variances=gv_variances))

            if args.valid_script is not None:
                with tf.variable_scope('model', reuse=True):
                    (predicted_valid_outputs, valid_variances, valid_gv_variances) = (
                        DNNDefine.inference(
                            valid_inputs,
                            valid_spkr_ids,
                            config['num_io_units'],
                            config['num_hidden_units'],
                            len(config['all_spkrs']),
                            sum(config['num_feature_dimensions']),
                            config['hidden_activation'],
                            config['output_activation'],
                            1.0,
                            mode))

        num_parameters = DNNDefine.get_num_params()
        print('Number of parameters: %s' %
              format_num_parameters(num_parameters))

        if config['frame_by_frame']:
            train_cost_op, _ = DNNDefine.cost(
                predicted_train_outputs,
                train_outputs,
                train_variances)
        else:
            train_cost_op, _ = DNNDefine.trajectory_cost(
                predicted_train_outputs,
                train_outputs,
                train_variances,
                train_gv_variances,
                config['num_feature_dimensions'],
                config['msd_flags'],
                num_windows,
                window_vector,
                gv_weight=config['gv_weight'])

        if args.valid_script is not None:
            if config['frame_by_frame']:
                valid_cost_op, _ = DNNDefine.cost(
                    predicted_valid_outputs,
                    valid_outputs,
                    valid_variances)
            else:
                valid_cost_op, _ = DNNDefine.trajectory_cost(
                    predicted_valid_outputs,
                    valid_outputs,
                    valid_variances,
                    valid_gv_variances,
                    config['num_feature_dimensions'],
                    config['msd_flags'],
                    num_windows,
                    window_vector,
                    gv_weight=config['gv_weight'])

        if mode == 'SD':
            train_op = DNNDefine.training(
                train_cost_op,
                config['optimizer'],
                config['learning_rate'],
                0.0,
                config['learning_rate'] * 0.01)
        elif mode == 'SAT':
            train_op = DNNDefine.training(
                train_cost_op,
                config['optimizer'],
                config['learning_rate'],
                config['learning_rate'],
                config['learning_rate'] * 0.01)
        elif mode == 'ADAPT':
            train_op = DNNDefine.training(
                train_cost_op,
                config['optimizer'],
                0.0,
                config['learning_rate'],
                config['learning_rate'] * 0.01)

        init_op = tf.group(
            tf.global_variables_initializer(),
            tf.local_variables_initializer())

        sess = tf.Session(config=tf.ConfigProto(
            intra_op_parallelism_threads=config['num_threads']))

        sess.run(init_op)

        saver = tf.train.Saver(max_to_keep=config['num_models_to_keep'])
        if config['restore_ckpt'] >= 0:
            print('Restoring model... ', end='')
            filename = model_path
            if config['restore_ckpt'] > 0:
                filename = '-'.join([filename, str(config['restore_ckpt'])])
            saver.restore(sess, filename)
            print('done')

        if config['adaptation']:
            sd_tensors = DNNDefine.get_params('sd_', 'True')
            for i in xrange(len(sd_tensors)):
                sd_params = sess.run(sd_tensors[i])
                sd_params[-1] = np.mean(sd_params[:-1], 0)
                sess.run(tf.assign(sd_tensors[i], sd_params))

        threads = tf.train.start_queue_runners(sess=sess, coord=coord)
        train_reader.start(sess)
        if args.valid_script is not None:
            valid_reader.start(sess)

        print_time('Start model training')
        try:
            total_cost = 0.0
            start_time = time.time()

            for step in xrange(1, num_train_steps + 1):
                _, cost = sess.run([train_op, train_cost_op])
                total_cost += cost

                if step % config['log_interval'] == 0:
                    avg_cost = total_cost / config['log_interval']
                    duration = format_duration(time.time() - start_time)
                    print('  Step %7d: cost = %e (%s)' %
                          (step, avg_cost, duration))
                    total_cost = 0.0
                    start_time = time.time()

                if step % config['save_interval'] == 0:
                    print('Saving model... ', end='')
                    saver.save(sess, model_path, global_step=step)
                    print('done')

                    start_time = time.time()
                    if args.valid_script is not None:
                        cost = 0.0
                        for _ in xrange(num_valid_steps):
                            cost += sess.run(valid_cost_op)
                        avg_cost = cost / num_valid_steps
                        duration = format_duration(time.time() - start_time)
                        print('')
                        print('    Evaluation')
                        print('      validation cost = %e (%s)' %
                              (avg_cost, duration))
                        print('')
                        start_time = time.time()

        except KeyboardInterrupt:
            print()

        finally:
            print('Saving model... ', end='')
            saver.save(sess, model_path)
            print('done')
            coord.request_stop()
            coord.join(threads)

    print_time('End model training')
    print()


if __name__ == '__main__':
    main()
