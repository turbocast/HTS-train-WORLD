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

import numpy as np
import os
import re
import struct
import threading
import yaml
import ConfigParser

from six.moves import xrange
import tensorflow as tf


class DataReader(object):
    def __init__(self,
                 num_io_dimensions,
                 frame_by_frame,
                 queue_size,
                 script,
                 coord,
                 spkr_pattern=None,
                 train_spkrs=None,
                 seed=None):
        # Dimension
        self._num_input_dimensions, self._num_output_dimensions = num_io_dimensions

        # File
        size = 0
        files = []
        for filenames in open(script, 'r'):
            files.append(filenames.rstrip())
            input_filename, _ = filenames.split(' ', 1)
            stat = os.stat(input_filename)
            size = size + stat.st_size
        self._files = np.asarray(files)
        self._num_examples = size // (4 * self._num_input_dimensions)
        self._num_files = len(files)

        # Speaker
        self._spkr_pattern = spkr_pattern
        self._spkr2id = dict()
        for i in xrange(len(train_spkrs)):
            self._spkr2id[train_spkrs[i]] = i

        # Queue
        self._coord = coord
        self._frame_by_frame = frame_by_frame
        if frame_by_frame:
            min_after_dequeue = int(queue_size * 0.8)
            self._queue = tf.RandomShuffleQueue(
                queue_size, min_after_dequeue,
                ['float32', 'float32', 'int32'],
                shapes=[[self._num_input_dimensions],
                        [self._num_output_dimensions], [1]],
                seed=seed)
            self._input_placeholder = tf.placeholder(
                tf.float32, shape=[None, self._num_input_dimensions])
            self._output_placeholder = tf.placeholder(
                tf.float32, shape=[None, self._num_output_dimensions])
            self._spkr_ids_placeholder = tf.placeholder(
                tf.int32, shape=[None, 1])
            self._enqueue = self._queue.enqueue_many(
                [self._input_placeholder,
                 self._output_placeholder,
                 self._spkr_ids_placeholder])
        else:
            self._queue = tf.PaddingFIFOQueue(
                queue_size,
                ['float32', 'float32', 'int32'],
                shapes=[[None, self._num_input_dimensions],
                        [None, self._num_output_dimensions], [1]])
            self._input_placeholder = tf.placeholder(
                tf.float32, shape=None)
            self._output_placeholder = tf.placeholder(
                tf.float32, shape=None)
            self._spkr_ids_placeholder = tf.placeholder(
                tf.int32, shape=None)
            self._enqueue = self._queue.enqueue(
                [self._input_placeholder,
                 self._output_placeholder,
                 self._spkr_ids_placeholder])

        # Other
        self._rng = np.random.RandomState(seed)

    @property
    def num_input_dimensions(self):
        return self._num_input_dimensions

    @property
    def num_output_dimensions(self):
        return self._num_output_dimensions

    @property
    def num_examples(self):
        return self._num_examples

    @property
    def num_files(self):
        return self._num_files

    def dequeue(self, batch_size):
        inputs, outputs, spkr_ids = self._queue.dequeue_many(batch_size)
        if not self._frame_by_frame:
            inputs = tf.squeeze(inputs, axis=0)
            outputs = tf.squeeze(outputs, axis=0)
        return inputs, outputs, spkr_ids

    def start(self, sess, num_threads=1):
        for _ in xrange(num_threads):
            thread = threading.Thread(target=self.__loop, args=(sess,))
            thread.daemon = True
            thread.start()

    def __load_data(self):
        for filenames in self._files:
            input_filename, output_filename = filenames.split(' ', 1)
            inputs = load_binary_data(
                input_filename, self._num_input_dimensions)
            num_input_examples = inputs.shape[0]
            outputs = load_binary_data(
                output_filename, self._num_output_dimensions)
            num_output_examples = outputs.shape[0]
            assert num_input_examples == num_output_examples

            if len(self._spkr2id) <= 1:
                spkr_id = 0
            else:
                spkr = re.compile(self._spkr_pattern).search(
                    filenames).group(1)
                spkr_id = self._spkr2id[spkr]

            if self._frame_by_frame:
                spkr_ids = np.reshape([spkr_id] * num_input_examples, [-1, 1])
            else:
                spkr_ids = [spkr_id]

            yield inputs, outputs, spkr_ids, num_input_examples

    def __loop(self, sess):
        halt = False
        while not halt:
            self._rng.shuffle(self._files)
            for inputs, outputs, spkr_ids, num_examples in self.__load_data():
                if self._coord.should_stop():
                    halt = True
                    break

                sess.run(self._enqueue,
                         feed_dict={self._input_placeholder: inputs,
                                    self._output_placeholder: outputs,
                                    self._spkr_ids_placeholder: spkr_ids})


def load_binary_data(filename, num_dimensions=1, read_size=4):
    data = []
    with open(filename.rstrip(), 'rb') as f:
        packed_data = f.read(read_size)
        while packed_data != '':
            data.extend(struct.unpack('f', packed_data))
            packed_data = f.read(read_size)

    return np.reshape(np.asarray(data), [-1, num_dimensions])


def write_binary_data(filename, data, append=False):
    mode = 'ab' if append else 'wb'
    with open(filename, mode) as f:
        for row in data:
            for elem in row:
                f.write(struct.pack('f', elem))


def load_window(filename, padding=3):
    with open(filename, 'r') as f:
        lst = f.readline().rstrip().split(" ")
        width = int(lst.pop(0))
        window = [float(i) for i in lst]
        for i in xrange((padding - width) // 2):
            window.insert(0, 0.0)
        for i in xrange((padding - width) // 2):
            window.append(0.0)

    return window


def get_filenames(script_file):
    input_filenames = []
    output_filenames = []
    for filenames in open(script_file, 'r'):
        if re.search(' ', filenames) is None:
            input_filenames.append(filenames.rstrip())
            output_filenames.append(None)
        else:
            input_filename, output_filename = filenames.split(' ', 1)
            input_filenames.append(input_filename.rstrip())
            output_filenames.append(output_filename.rstrip())

    return input_filenames, output_filenames


def load_config(config_file, verbose=True):
    config_parser = ConfigParser.SafeConfigParser()
    config_parser.read(config_file)

    config = {}
    for section in config_parser.sections():
        for option in config_parser.options(section):
            config[option] = yaml.safe_load(config_parser.get(section, option))

    if verbose:
        print('Configuration Parameters[%d]' % len(config))
        print('              %-25s %20s' % ('Parameter', 'Value'))
        for key in sorted(config.keys()):
            print('              %-25s %20s' % (key, str(config[key])))
        print()

    config['num_io_units'] = (config['num_input_units'],
                              config['num_output_units'])

    return config
