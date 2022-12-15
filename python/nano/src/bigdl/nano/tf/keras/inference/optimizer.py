#
# Copyright 2016 The BigDL Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import os
import time
import numpy as np
import tensorflow as tf
from typing import Dict, Optional, List, Union
from bigdl.nano.utils.inference.common.base_optimizer import BaseInferenceOptimizer
from bigdl.nano.utils.inference.common.checker import available_acceleration_combination
from bigdl.nano.utils.inference.common.utils import AccelerationOption,\
    throughput_calculate_helper, format_optimize_result
from bigdl.nano.tf.keras import Model as NanoModel
from bigdl.nano.utils.log4Error import invalidInputError
from tensorflow.keras import Model as Model
from tensorflow.data import Dataset
from tensorflow.keras.metrics import Metric
from bigdl.nano.deps.neural_compressor.inc_api import quantize as inc_quantzie
from bigdl.nano.deps.openvino.openvino_api import KerasOpenVINOModel
from bigdl.nano.deps.onnxruntime.onnxruntime_api import KerasONNXRuntimeModel


class TFAccelerationOption(AccelerationOption):
    def optimize(self, model, x=None, y=None,
                 thread_num=None, logging=False, sample_size_for_pot=100):
        accelerator = self.get_accelerator()
        if self.get_precision() == "fp32":
            # trace
            if accelerator is None:
                return model
            else:
                acce_model = InferenceOptimizer.trace(model=model,
                                                      accelerator=accelerator,
                                                      thread_num=thread_num,
                                                      # remove output of openvino
                                                      logging=logging)
        else:
            # quantize
            ort_method: str = self.method
            acce_model = InferenceOptimizer.quantize(model=model,
                                                     precision=self.get_precision(),
                                                     accelerator=accelerator,
                                                     x=x,
                                                     y=y,
                                                     method=ort_method,
                                                     thread_num=thread_num,
                                                     sample_size=sample_size_for_pot,
                                                     # remove output of openvino
                                                     logging=logging)
        return acce_model


class InferenceOptimizer(BaseInferenceOptimizer):

    # acceleration method combinations, developers may want to register some new
    # combinations here
    ALL_INFERENCE_ACCELERATION_METHOD: Dict = \
        {  # type: ignore
            "original": TFAccelerationOption(),
            "int8": TFAccelerationOption(inc=True),
            "openvino_fp32": TFAccelerationOption(openvino=True),
            "openvino_int8": TFAccelerationOption(openvino=True, pot=True),
            "onnxruntime_fp32": TFAccelerationOption(onnxruntime=True),
            "onnxruntime_int8_qlinear": TFAccelerationOption(onnxruntime=True, inc=True,
                                                             method="qlinear"),
            "onnxruntime_int8_integer": TFAccelerationOption(onnxruntime=True, inc=True,
                                                             method="integer"),
        }  # type: ignore

    def optimize(self, model: Model,
                 x: Union[tf.Tensor, np.ndarray, tf.data.Dataset],
                 y: Union[tf.Tensor, np.ndarray] = None,
                 validation_data: Optional[Dataset] = None,
                 batch_size: int = 1,
                 metric: Optional[Metric] = None,
                 direction: str = "max",
                 thread_num: Optional[int] = None,
                 logging: bool = False,
                 latency_sample_num: int = 100,
                 includes: Optional[List[str]] = None,
                 excludes: Optional[List[str]] = None) -> None:
        '''
        This function will give all available inference acceleration methods a try
        and record the latency, accuracy and model instance inside the Optimizer for
        future usage. All model instance is setting to eval mode.

        The available methods are "original", "openvino_fp32", "onnxruntime_fp32", "int8".

        :param model: A keras.Model to be optimized
        :param x: Input data which is used for training. It could be:
                  | 1. a Numpy array (or array-like), or a list of arrays (in case the model
                  | has multiple inputs).
                  |
                  | 2. a TensorFlow tensor, or a list of tensors (in case the model has
                  | multiple inputs).
                  |
                  | 3. an unbatched tf.data.Dataset. Should return a tuple of (inputs, targets).

                  X will be used as calibration dataset for Post-Training Static Quantization (PTQ),
                  as well as be used for generating input_sample to calculate latency.
                  To avoid data leak during calibration, please use training dataset.
        :param y: Target data. Like the input data x, it could be either Numpy array(s) or
                  TensorFlow tensor(s). Its length should be consistent with x.
                  If x is a dataset, y will be ignored (since targets will be obtained from x).
        :param validation_data: (optional) An unbatched tf.data.Dataset object for accuracy
               evaluation. This is only needed when users care about the possible accuracy drop.
        :param metric: (optional) A tensorflow.keras.metrics.Metric object which is used for
               calculating accuracy.
        :param direction: (optional) A string that indicates the higher/lower
               better for the metric, "min" for the lower the better and "max" for the
               higher the better. Default value is "max".
        :param thread_num: (optional) a int represents how many threads(cores) is needed for
               inference.
        :param logging: whether to log detailed information of model conversion.
               Default: False.
        :param latency_sample_num: (optional) a int represents the number of repetitions
               to calculate the average latency. The default value is 100.
        :param includes: (optional) a list of acceleration methods that will be included in the
               search. Default to None meaning including all available methods. "original" method
               will be automatically add to includes.
        :param excludes: (optional) a list of acceleration methods that will be excluded from the
               search. "original" will be ignored in the excludes.
        '''
        # check if model is a nn.Module or inherited from a nn.Module
        invalidInputError(isinstance(model, Model), "model should be a Keras Model.")
        invalidInputError(direction in ['min', 'max'],
                          "Only support direction 'min', 'max'.")
        invalidInputError(y is not None or isinstance(x, tf.data.Dataset),
                          "y can be omitted only when x is a Dataset which returns \
                              tuples of (inputs, targets)")

        if not isinstance(model, NanoModel):
            # turn model into NanoModel to obtain trace and quantize method
            model = NanoModel(inputs=model.inputs, outputs=model.outputs)

        # get the available methods whose dep is met
        available_dict: Dict =\
            available_acceleration_combination(excludes=excludes,
                                               includes=includes,
                                               full_methods=self.ALL_INFERENCE_ACCELERATION_METHOD)

        self._direction: str = direction  # save direction as attr
        # record whether calculate accuracy in optimize by this attr
        if validation_data is None or metric is None:
            self._calculate_accuracy = False
        else:
            # test whether accuracy calculation works later
            # make sure dataset don't have batch
            batched_validation_data = validation_data.batch(batch_size)
            self._calculate_accuracy = True

        if os.getenv('OMP_NUM_THREADS') is not None:
            default_threads: int = int(os.getenv('OMP_NUM_THREADS'))  # type: ignore
        else:
            # TODO: how to get and control thread num in tf?
            default_threads = None  # type: ignore
        thread_num = default_threads if thread_num is None else int(thread_num)  # type: ignore

        result_map: Dict[str, Dict] = {}

        if isinstance(x, Dataset):
            batched_training_dataset = x.batch(batch_size)
            input_sample = next(iter(batched_training_dataset))
            # TODO: how to obtain input from output of training_dataset
            input_sample = input_sample[:-1]
        else:
            input_sample = tf.convert_to_tensor(x[:batch_size])

        if isinstance(input_sample, (list, tuple)) and len(input_sample) == 1:
            input_sample = input_sample[0]

        st = time.perf_counter()
        try:
            if isinstance(input_sample, tf.Tensor):
                model(input_sample)
            else:
                model(*input_sample)
        except Exception:
            invalidInputError(False,
                              "x is incompatible with your model input.")
        baseline_time = time.perf_counter() - st
        if baseline_time > 0.1:  # 100ms
            sample_size_for_pot = 15
        else:
            sample_size_for_pot = 100

        print("==========================Start Optimization==========================")
        start_time = time.perf_counter()
        for idx, (method, available) in enumerate(available_dict.items()):
            result_map[method] = {}
            if available is False:
                result_map[method]["status"] = "lack dependency"
            else:
                print(f"----------Start test {method} model "
                      f"({idx+1}/{len(available_dict)})----------")
                option: AccelerationOption = self.ALL_INFERENCE_ACCELERATION_METHOD[method]
                precision: str = option.get_precision()
                try:
                    acce_model = option.optimize(model=model,
                                                 x=x,
                                                 y=y,
                                                 thread_num=thread_num,
                                                 logging=logging,
                                                 sample_size_for_pot=sample_size_for_pot)
                except Exception as e:
                    print(e)
                    result_map[method]["status"] = "fail to convert"
                    print(f"----------Failed to convert to {method}----------")
                    continue

                result_map[method]["status"] = "successful"

                def func_test(model, sample):
                    model(sample)
                try:
                    result_map[method]["latency"], status =\
                        throughput_calculate_helper(latency_sample_num, baseline_time,
                                                    func_test, acce_model, input_sample)
                    if status is False and method != "original":
                        result_map[method]["status"] = "early stopped"
                        continue
                except Exception as e:
                    print(e)
                    result_map[method]["status"] = "fail to forward"
                    print(f"----------{method} failed to forward----------")
                    continue

                if self._calculate_accuracy:
                    # here we suppose trace don't change accuracy,
                    # so we jump it to reduce time cost of optimize
                    if precision == "fp32" and method != "original":
                        result_map[method]["accuracy"] = "not recomputed"
                    else:
                        if method == "original":
                            # test whether metric works
                            try:
                                result_map[method]["accuracy"] =\
                                    _accuracy_calculate_helper(acce_model, metric,
                                                               batched_validation_data)
                            except Exception as e:
                                print(e)
                                self._calculate_accuracy = False
                        else:
                            result_map[method]["accuracy"] =\
                                _accuracy_calculate_helper(acce_model, metric,
                                                           batched_validation_data)
                else:
                    result_map[method]["accuracy"] = None

                result_map[method]["model"] = acce_model
                print(f"----------Finish test {method} model "
                      f"({idx+1}/{len(available_dict)})----------")

        self.optimized_model_dict: Dict = result_map
        print("\n\n==========================Optimization Results==========================")

        self._optimize_result = format_optimize_result(self.optimized_model_dict,
                                                       self._calculate_accuracy)
        # save time cost to self._optimize_result
        time_cost = time.perf_counter() - start_time
        time_cost_str = f"Optimization cost {time_cost:.1f}s in total."
        self._optimize_result += time_cost_str
        print(self._optimize_result)
        print("===========================Stop Optimization===========================")

    @staticmethod
    def trace(model: Model,
              accelerator: Optional[str] = None,
              input_spec=None,
              thread_num: Optional[int] = None,
              onnxruntime_session_options=None,
              openvino_config=None,
              logging=True):
        """
        Trace a Keras model and convert it into an accelerated module for inference.

        :param model: The Keras model to trace.
        :param accelerator: The accelerator to use, defaults to None meaning staying in Keras
                            backend. 'openvino' and 'onnxruntime' are supported for now.
        :param input_spec: A (tuple or list of) tf.TensorSpec or numpy array defining the
                           shape/dtype of the input when using 'onnxruntime' accelerator.
                           It will be ignored if accelerator is 'openvino'.
        :param thread_num: (optional) a int represents how many threads(cores) is needed for
                           inference, only valid for accelerator='onnxruntime'
                           or accelerator='openvino'.
        :param onnxruntime_session_options: The session option for onnxruntime, only valid when
                                            accelerator='onnxruntime', otherwise will be ignored.
        :param openvino_config: The config to be inputted in core.compile_model. Only valid when
                                accelerator='openvino', otherwise will be ignored.
        :param logging: whether to log detailed information of model conversion, only valid when
                        accelerator='openvino', otherwise will be ignored. Default: ``True``.
        :return: Model with different acceleration(OpenVINO/ONNX Runtime).
        """
        if accelerator == 'openvino':
            final_openvino_option = {"INFERENCE_PRECISION_HINT": "f32"}
            if openvino_config is not None:
                final_openvino_option.update(openvino_config)
            return KerasOpenVINOModel(model,
                                      thread_num=thread_num,
                                      config=final_openvino_option,
                                      logging=logging)
        elif accelerator == 'onnxruntime':
            if onnxruntime_session_options is None:
                import onnxruntime
                onnxruntime_session_options = onnxruntime.SessionOptions()
                if thread_num is not None:
                    onnxruntime_session_options.intra_op_num_threads = thread_num
                    onnxruntime_session_options.inter_op_num_threads = thread_num
            return KerasONNXRuntimeModel(model, input_spec, onnxruntime_session_options)
        else:
            invalidInputError(False, "Accelerator {} is invalid.".format(accelerator))

    @staticmethod
    def quantize(model: Model,
                 x: Union[tf.Tensor, np.ndarray, tf.data.Dataset],
                 y: Union[tf.Tensor, np.ndarray] = None,
                 precision: str = 'int8',
                 accelerator: Optional[str] = None,
                 metric: Optional[Metric] = None,
                 accuracy_criterion: Optional[dict] = None,
                 approach: str = 'static',
                 method: Optional[str] = None,
                 conf: Optional[str] = None,
                 tuning_strategy: Optional[str] = None,
                 timeout: Optional[int] = None,
                 max_trials: Optional[int] = None,
                 batch: Optional[int] = None,
                 thread_num: Optional[int] = None,
                 inputs: List[str] = None,
                 outputs: List[str] = None,
                 sample_size: int = 100,
                 onnxruntime_session_options=None,
                 openvino_config=None,
                 logging: bool = True):
        """
        Post-training quantization on a keras model.

        :param model: The Keras model to quantize.
        :param x: Input data which is used for training. It could be:
                  | 1. a Numpy array (or array-like), or a list of arrays (in case the model
                  | has multiple inputs).
                  |
                  | 2. a TensorFlow tensor, or a list of tensors (in case the model has
                  | multiple inputs).
                  |
                  | 3. an unbatched tf.data.Dataset. Should return a tuple of (inputs, targets).

                  X will be used as calibration dataset for Post-Training Static Quantization (PTQ),
                  as well as be used for generating input_sample to calculate latency.
                  To avoid data leak during calibration, please use training dataset.
        :param y: Target data. Like the input data x, it could be either Numpy array(s) or
                  TensorFlow tensor(s). Its length should be consistent with x.
                  If x is a dataset, y will be ignored (since targets will be obtained from x).
        :param precision:       Global precision of quantized model,
                                supported type: 'int8', defaults to 'int8'.
        :param accelerator:     Use accelerator 'None', 'onnxruntime', 'openvino', defaults to None.
                                None means staying in tensorflow.
        :param metric:          A tensorflow.keras.metrics.Metric object for evaluation.
        :param accuracy_criterion:  Tolerable accuracy drop.
                                    accuracy_criterion = {'relative': 0.1, 'higher_is_better': True}
                                    allows relative accuracy loss: 1%. accuracy_criterion =
                                    {'absolute': 0.99, 'higher_is_better':False} means accuracy
                                    must be smaller than 0.99.
        :param approach:        'static' or 'dynamic'.
                                'static': post_training_static_quant,
                                'dynamic': post_training_dynamic_quant.
                                Default: 'static'. Only 'static' approach is supported now.
        :param method:      Method to do quantization. When accelerator=None, supported methods:
                None. When accelerator='onnxruntime', supported methods: 'qlinear', 'integer',
                defaults to 'qlinear'. Suggest 'qlinear' for lower accuracy drop if using
                static quantization.
                More details in https://onnxruntime.ai/docs/performance/quantization.html.
                This argument doesn't take effect for OpenVINO, don't change it for OpenVINO.
        :param conf:        A path to conf yaml file for quantization.
                                Default: None, using default config.
        :param tuning_strategy:    'bayesian', 'basic', 'mse', 'sigopt'. Default: 'bayesian'.
        :param timeout:     Tuning timeout (seconds). Default: None,  which means early stop.
                            Combine with max_trials field to decide when to exit.
        :param max_trials:  Max tune times. Default: None, which means no tuning.
                            Combine with timeout field to decide when to exit.
                            "timeout=0, max_trials=1" means it will try quantization only once and
                            return satisfying best model.
        :param batch:       Batch size of dataloader for calib_dataset. Defaults to None, if the
                            dataset is not a BatchDataset, batchsize equals to 1. Otherwise,
                            batchsize complies with the dataset._batch_size.
        :param thread_num:  (optional) a int represents how many threads(cores) is needed for
                            inference, only valid for accelerator='onnxruntime'
                            or accelerator='openvino'.
        :param inputs:      A list of input names.
                            Default: None, automatically get names from graph.
        :param outputs:     A list of output names.
                            Default: None, automatically get names from graph.
        :param sample_size: (optional) a int represents how many samples will be used for
                            Post-training Optimization Tools (POT) from OpenVINO toolkit,
                            only valid for accelerator='openvino'. Default to 100.
                            The larger the value, the more accurate the conversion,
                            the lower the performance degradation, but the longer the time.
        :param onnxruntime_session_options: The session option for onnxruntime, only valid when
                                            accelerator='onnxruntime', otherwise will be ignored.
        :param openvino_config: The config to be inputted in core.compile_model. Only valid when
                                accelerator='openvino', otherwise will be ignored.
        :param logging: whether to log detailed information of model conversion, only valid when
                        accelerator='openvino', otherwise will be ignored. Default: ``True``.
        :return:            A TensorflowBaseModel for INC. If there is no model found, return None.
        """
        invalidInputError(approach == 'static', "Only 'static' approach is supported now.")
        invalidInputError(y is not None or isinstance(x, tf.data.Dataset),
                          "y can be omitted only when x is a Dataset which returns \
                              tuples of (inputs, targets)")
        if accelerator is None:
            if isinstance(x, tf.data.Dataset):
                calib_dataset = x
            else:
                calib_dataset = tf.data.Dataset.from_tensor_slices((x, y))
            if batch:
                calib_dataset = calib_dataset.batch(batch)
            return inc_quantzie(model, dataloader=calib_dataset,
                                metric=metric,
                                framework='tensorflow',
                                conf=conf,
                                approach=approach,
                                tuning_strategy=tuning_strategy,
                                accuracy_criterion=accuracy_criterion,
                                timeout=timeout,
                                max_trials=max_trials,
                                inputs=inputs,
                                outputs=outputs)
        elif accelerator == 'openvino':
            from bigdl.nano.deps.openvino.tf.model import KerasOpenVINOModel    # type: ignore
            if isinstance(model, KerasOpenVINOModel):    # type: ignore
                openvino_model = model
            else:
                openvino_model = InferenceOptimizer.trace(model=model,
                                                          accelerator='openvino',
                                                          thread_num=thread_num,
                                                          logging=logging,
                                                          openvino_config=openvino_config)
            if metric:
                if not isinstance(accuracy_criterion, dict):
                    accuracy_criterion = {'relative': 0.99, 'higher_is_better': True}
                drop_type = 'relative' if 'relative' in accuracy_criterion else 'absolute'
                higher_is_better = accuracy_criterion.get('higher_is_better', None)
                maximal_drop = accuracy_criterion.get(drop_type, None)
            else:
                drop_type, higher_is_better, maximal_drop = None, None, None
            return openvino_model.pot(x=x,  # type: ignore
                                      y=y,
                                      metric=metric,
                                      higher_better=higher_is_better,
                                      drop_type=drop_type,
                                      maximal_drop=maximal_drop,
                                      max_iter_num=max_trials,
                                      sample_size=sample_size,
                                      config=openvino_config,
                                      thread_num=thread_num)
        elif accelerator == 'onnxruntime':
            # convert tensorflow model to onnx model
            from bigdl.nano.deps.onnxruntime.tensorflow.tensorflow_onnxruntime_model \
                import KerasONNXRuntimeModel
            if isinstance(model, KerasONNXRuntimeModel):     # type: ignore
                onnx_model = model
            else:
                onnx_model = InferenceOptimizer.trace(model=model, accelerator='onnxruntime',
                                                      thread_num=thread_num)

            # trace onnx model
            method_map = {
                'qlinear': 'onnxrt_qlinearops',
                'integer': 'onnxrt_integerops',
                None: 'onnxrt_qlinearops'  # default
            }
            framework = method_map.get(method, None)
            return inc_quantzie(onnx_model, dataloader=(x, y),
                                metric=metric,
                                framework=framework,
                                conf=conf,
                                approach=approach,
                                tuning_strategy=tuning_strategy,
                                accuracy_criterion=accuracy_criterion,
                                timeout=timeout,
                                max_trials=max_trials,
                                inputs=inputs,
                                outputs=outputs,
                                onnx_option='tensorflow',
                                onnxruntime_session_options=onnxruntime_session_options)
        else:
            invalidInputError(False, "Accelerator {} is invalid.".format(accelerator))


def _accuracy_calculate_helper(model, metric, data):
    '''
    A quick helper to calculate accuracy
    '''
    for data_input, target in data:
        metric.update_state(y_true=target, y_pred=model(data_input))
    return metric.result().numpy()
