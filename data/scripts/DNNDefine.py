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

from six.moves import xrange
import tensorflow as tf


def get_activation_function(string):
    word = string.lower()
    if word == 'linear':
        return tf.identity
    elif word == 'sigmoid':
        return tf.nn.sigmoid
    elif word == 'tanh':
        return tf.nn.tanh
    elif word == 'relu':
        return tf.nn.relu
    else:
        raise NotImplementedError


def get_optimizer(string, learning_rate):
    word = string.lower()
    if word == 'sgd':
        return tf.train.GradientDescentOptimizer(learning_rate)
    elif word == 'momentum':
        return tf.train.MomentumOptimizer(learning_rate, 0.9)
    elif word == 'adagrad':
        return tf.train.AdagradOptimizer(learning_rate)
    elif word == 'adadelta':
        return tf.train.AdadeltaOptimizer(learning_rate)
    elif word == 'adam':
        return tf.train.AdamOptimizer(learning_rate)
    elif word == 'rmsprop':
        return tf.train.RMSPropOptimizer(learning_rate)
    else:
        raise NotImplementedError


def get_num_params():
    total_params = 0
    for variable in tf.trainable_variables():
        num_params = 1
        for dimension in variable.get_shape():
            num_params *= dimension.value
        total_params += num_params
    return total_params


def get_params(name, find=True):
    params = []
    for variable in tf.trainable_variables():
        if find and variable.name.find(name) != -1:
            params.append(variable)
        elif not find and variable.name.find(name) == -1:
            params.append(variable)
    return params


def get_variables(name, find=True):
    params = []
    for variable in tf.global_variables():
        if find and variable.name.find(name) != -1:
            params.append(variable)
        elif not find and variable.name.find(name) == -1:
            params.append(variable)
    return params


def inference(inputs, spkr_ids, num_io_units, num_hidden_units, num_spkrs, num_feats,
              hidden_activation, output_activation, keep_prob, mode, seed=None,
              initial_variances=None, initial_gv_variances=None):
    tf.set_random_seed(seed)

    num_input_units, num_output_units = num_io_units
    hidden_activation_function = get_activation_function(hidden_activation)
    output_activation_function = get_activation_function(output_activation)
    auxially_inputs = tf.squeeze(tf.one_hot(spkr_ids, num_spkrs), axis=1)

    hidden_outputs = None
    num_hidden_layers = len(num_hidden_units)

    for i in xrange(num_hidden_layers):
        with tf.variable_scope('hidden' + str(i)):
            if i == 0:
                hidden_inputs = inputs
                num_prev_hidden_units = num_input_units
            else:
                hidden_inputs = hidden_outputs
                num_prev_hidden_units = num_hidden_units[i - 1]

            si_weights = tf.get_variable(
                'si_weights', [num_prev_hidden_units, num_hidden_units[i]],
                initializer=tf.truncated_normal_initializer(
                    stddev=1.0 / np.sqrt(float(num_prev_hidden_units))))
            si_biases = tf.get_variable(
                'si_biases', [num_hidden_units[i]],
                initializer=tf.constant_initializer())

            if mode == 'SAT' or mode == 'ADAPT':
                sd_weights = tf.get_variable(
                    'sd_weights', [num_spkrs, num_hidden_units[i]],
                    initializer=tf.truncated_normal_initializer(
                        stddev=1.0 / np.sqrt(float(num_spkrs))))

            if mode == 'SD':
                hidden_outputs = hidden_activation_function(
                    tf.matmul(hidden_inputs, si_weights) + si_biases)
            elif mode == 'SAT' or mode == 'ADAPT':
                hidden_outputs = hidden_activation_function(
                    tf.matmul(hidden_inputs, si_weights) + si_biases +
                    tf.matmul(auxially_inputs, sd_weights))

            hidden_outputs = tf.nn.dropout(hidden_outputs, keep_prob)

    with tf.variable_scope('output'):
        if hidden_outputs is None:
            hidden_outputs = inputs
            num_prev_output_units = num_input_units
        else:
            num_prev_output_units = num_hidden_units[num_hidden_layers - 1]

        si_weights = tf.get_variable(
            'si_weights', [num_prev_output_units, num_output_units],
            initializer=tf.truncated_normal_initializer(
                stddev=1.0 / np.sqrt(float(num_prev_output_units))))
        si_biases = tf.get_variable(
            'si_biases', [num_output_units],
            initializer=tf.constant_initializer())

        outputs = output_activation_function(
            tf.matmul(hidden_outputs, si_weights) + si_biases)

    with tf.variable_scope('variance'):
        if initial_variances is None:
            initial_variances = np.ones(
                [num_spkrs, num_output_units], np.float32)
        variances = tf.get_variable(
            'variances', [num_spkrs, num_output_units],
            initializer=tf.constant_initializer(initial_variances))
        if initial_gv_variances is None:
            initial_gv_variances = np.ones([num_spkrs, num_feats], np.float32)
        gv_variances = initial_gv_variances

        picked_variances = tf.matmul(auxially_inputs, variances)
        picked_gv_variances = tf.matmul(auxially_inputs, gv_variances)

    return outputs, picked_variances, picked_gv_variances


def training(cost, optimizer_type, learning_rate, adapt_learning_rate, variance_learning_rate):
    if adapt_learning_rate > 0.0:
        optimizer1 = get_optimizer(optimizer_type, learning_rate)
        optimizer2 = get_optimizer(optimizer_type, adapt_learning_rate)
        optimizer3 = get_optimizer(optimizer_type, variance_learning_rate)
        var_list1 = get_params('si_', True)
        var_list2 = get_params('sd_', True)
        var_list3 = get_params('variance', True)
        grads = tf.gradients(cost, var_list1 + var_list2 + var_list3)
        grads1 = grads[:len(var_list1)]
        grads2 = grads[len(var_list1):-len(var_list3)]
        grads3 = grads[-len(var_list3):]
        global_step = tf.Variable(0, name='global_step', trainable=False)
        train_op1 = optimizer1.apply_gradients(
            zip(grads1, var_list1), global_step=global_step)
        train_op2 = optimizer2.apply_gradients(
            zip(grads2, var_list2), global_step=global_step)
        train_op3 = optimizer3.apply_gradients(
            zip(grads3, var_list3), global_step=global_step)
        train_op = tf.group(train_op1, train_op2, train_op3)
    else:
        optimizer1 = get_optimizer(optimizer_type, learning_rate)
        optimizer2 = get_optimizer(optimizer_type, variance_learning_rate)
        var_list1 = get_params('variance', False)
        var_list2 = get_params('variance', True)
        grads = tf.gradients(cost, var_list1 + var_list2)
        grads1 = grads[:len(var_list1)]
        grads2 = grads[len(var_list1):]
        global_step = tf.Variable(0, name='global_step', trainable=False)
        train_op1 = optimizer1.apply_gradients(
            zip(grads1, var_list1), global_step=global_step)
        train_op2 = optimizer2.apply_gradients(
            zip(grads2, var_list2), global_step=global_step)
        train_op = tf.group(train_op1, train_op2)
    return train_op


def cost(predicted_outputs, observed_outputs, variances):
    gconst = tf.cast(np.log(2.0 * np.pi), tf.float32)
    covdet = tf.reduce_mean(tf.log(variances))
    mahala = tf.reduce_mean(tf.divide(
        tf.square(observed_outputs - predicted_outputs), variances))
    cost = 0.5 * (gconst + covdet + mahala)
    return cost, predicted_outputs


def trajectory_cost(predicted_outputs,
                    observed_outputs,
                    variances,
                    gv_variances,
                    num_feature_dimensions,
                    msd_flags,
                    num_windows,
                    window_vector,
                    msd_weight=1e-0,
                    gv_weight=1e-6):
    window_width = len(window_vector[0]) // num_windows
    half_window_width = (window_width - 1) // 2

    T = tf.shape(predicted_outputs)[0]
    float_T = tf.cast(T, tf.float32)
    D = sum(num_feature_dimensions)
    msd_D = sum(msd_flags)

    num_splits = []
    feature_types = []
    for i in xrange(len(num_feature_dimensions)):
        if msd_flags[i]:
            num_splits.append(1)
            feature_types.append(-1)
        for j in xrange(num_windows):
            num_splits.append(num_feature_dimensions[i])
            feature_types.append(j)

    split_predicted_outputs = tf.split(predicted_outputs, num_splits, axis=1)
    msd_predicted_outputs = []
    static_predicted_outputs = []
    delta_predicted_outputs = [[] for _ in xrange(num_windows - 1)]
    for i in xrange(len(feature_types)):
        if feature_types[i] == -1:
            msd_predicted_outputs.append(split_predicted_outputs[i])
        elif feature_types[i] == 0:
            static_predicted_outputs.append(split_predicted_outputs[i])
        else:
            delta_predicted_outputs[feature_types[i] -
                                    1].append(split_predicted_outputs[i])
    msd_predicted_outputs = tf.concat(msd_predicted_outputs, 1)
    static_predicted_outputs = tf.expand_dims(
        tf.concat(static_predicted_outputs, 1), 2)
    for i in xrange(num_windows - 1):
        delta_predicted_outputs[i] = tf.expand_dims(
            tf.concat(delta_predicted_outputs[i], 1), 2)
    sorted_predicted_outputs = tf.concat(
        [static_predicted_outputs, tf.concat(delta_predicted_outputs, 2)], 2)

    split_observed_outputs = tf.split(observed_outputs, num_splits, axis=1)
    msd_observed_outputs = []
    static_observed_outputs = []
    for i in xrange(len(feature_types)):
        if feature_types[i] == -1:
            msd_observed_outputs.append(split_observed_outputs[i])
        elif feature_types[i] == 0:
            static_observed_outputs.append(split_observed_outputs[i])
    msd_observed_outputs = tf.concat(msd_observed_outputs, 1)
    static_observed_outputs = tf.concat(static_observed_outputs, 1)

    split_precisions = tf.split(tf.reciprocal(variances), num_splits, axis=1)
    msd_precisions = []
    static_precisions = []
    delta_precisions = [[] for _ in xrange(num_windows - 1)]
    for i in xrange(len(feature_types)):
        if feature_types[i] == -1:
            msd_precisions.append(split_precisions[i])
        elif feature_types[i] == 0:
            static_precisions.append(split_precisions[i])
        else:
            delta_precisions[feature_types[i] - 1].append(split_precisions[i])
    msd_precisions = tf.concat(msd_precisions, 1)
    static_precisions = tf.concat(static_precisions, 1)
    for i in xrange(num_windows - 1):
        delta_precisions[i] = tf.concat(delta_precisions[i], 1)
    sorted_precisions = tf.transpose(tf.concat(
        [static_precisions, tf.concat(delta_precisions, 0)], 0))

    def create_window_matrix(window_vector, transpose=False):
        half_window_vector = tf.transpose(
            tf.slice(tf.transpose(window_vector), [0, 0],
                     [num_windows * (window_width + 1) // 2, D]))
        zero_vector = tf.zeros(
            [D, num_windows * (T - half_window_width)])

        W = tf.concat([window_vector, zero_vector], 1)
        W = tf.tile(W, [1, T - 1])
        W = tf.concat([W, half_window_vector], 1)
        W = tf.reshape(W, [D, T, -1])
        W = tf.slice(W, [0, 0, num_windows * half_window_width],
                     [D, T, 3 * T])
        if not transpose:
            W = tf.matrix_transpose(W)
        return W

    window_precision_vector = window_vector * tf.tile(
        tf.reshape(sorted_precisions, [D, num_windows]),
        [1, window_width])

    mu = tf.transpose(sorted_predicted_outputs, perm=[1, 0, 2])
    mu = tf.reshape(mu, [D, -1, 1])

    W = create_window_matrix(window_vector, False)
    WS = create_window_matrix(window_precision_vector, True)

    WSW = tf.matmul(WS, W)
    WSW_cholesky = tf.cholesky(WSW)

    P = tf.cholesky_solve(WSW_cholesky, tf.eye(T, batch_shape=[D]))
    r = tf.matmul(WS, mu)

    predicted_c = tf.matmul(P, r)
    observed_c = tf.expand_dims(tf.transpose(static_observed_outputs), -1)
    subtracted_c = observed_c - predicted_c

    trj_gconst = tf.cast(D * T * np.log(2.0 * np.pi), tf.float32)
    trj_covdet = -2.0 * \
        tf.reduce_sum(tf.log(tf.matrix_diag_part(WSW_cholesky)))
    trj_mahala = tf.reduce_sum(tf.matmul(tf.matrix_transpose(subtracted_c),
                                         tf.matmul(WSW, subtracted_c)))
    trj_cost = (trj_gconst + trj_covdet + trj_mahala) / (2.0 * D * float_T)

    msd_gconst = tf.cast(msd_D * T * np.log(2.0 * np.pi), tf.float32)
    msd_covdet = -float_T * tf.reduce_sum(tf.log(msd_precisions))
    msd_mahala = tf.reduce_sum(tf.multiply(
        tf.square(msd_predicted_outputs - msd_observed_outputs), msd_precisions))
    msd_cost = (msd_gconst + msd_covdet + msd_mahala) / (2.0 * msd_D * float_T)

    # GV
    gv_precisions = tf.reciprocal(gv_variances)
    mean_predicted_c = tf.reduce_mean(predicted_c, axis=1, keep_dims=True)
    mean_predicted_c = tf.tile(mean_predicted_c, [1, T, 1])
    predicted_v = tf.squeeze(
        tf.reduce_mean(tf.square(predicted_c - mean_predicted_c), axis=1), 1)
    mean_observed_c = tf.reduce_mean(observed_c, axis=1, keep_dims=True)
    mean_observed_c = tf.tile(mean_observed_c, [1, T, 1])
    observed_v = tf.squeeze(
        tf.reduce_mean(tf.square(observed_c - mean_observed_c), axis=1), 1)

    gv_gconst = tf.cast(D * np.log(2.0 * np.pi), tf.float32)
    gv_covdet = -tf.reduce_sum(tf.log(gv_precisions))
    gv_mahala = tf.reduce_sum(tf.multiply(
        tf.square(predicted_v - observed_v), gv_precisions))
    gv_cost = (gv_gconst + gv_covdet + gv_mahala) / (2.0 * D)

    cost = trj_cost + msd_weight * msd_cost + gv_weight * gv_cost

    predicted_c = tf.transpose(tf.squeeze(predicted_c, 2))
    split_predicted_c = tf.split(predicted_c, num_feature_dimensions, axis=1)
    split_predicted_msd = tf.split(msd_predicted_outputs, 1, axis=1)
    final_outputs = []
    j = 0
    for i in xrange(len(num_feature_dimensions)):
        if msd_flags[i]:
            final_outputs.append(split_predicted_msd[j])
            j = j + 1
        final_outputs.append(split_predicted_c[i])
    final_outputs = tf.concat(final_outputs, 1)

    return cost, final_outputs
