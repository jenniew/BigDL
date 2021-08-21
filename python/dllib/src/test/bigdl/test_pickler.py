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

from bigdl.dllib.nn.layer import *
from bigdl.dllib.nn.initialization_method import *
from bigdl.dllib.nn.criterion import *
from bigdl.dllib.optim.optimizer import *
<<<<<<< HEAD
from bigdl.dllib.utils.common import *
from bigdl.dllib.utils.common import _py2java
=======
from bigdl.utils.common import *
from bigdl.utils.common import _py2java
>>>>>>> upstream_bigdl-2.0
from bigdl.dllib.nn.initialization_method import *
from bigdl.dllib.feature.dataset import movielens
import numpy as np
import tempfile
import pytest
from numpy.testing import assert_allclose, assert_array_equal
<<<<<<< HEAD
from bigdl.dllib.utils.engine import compare_version
=======
from bigdl.utils.engine import compare_version
>>>>>>> upstream_bigdl-2.0
np.random.seed(1337)  # for reproducibility


class TestPickler():
    def setup_method(self, method):
        """ setup any state tied to the execution of the given method in a
        class.  setup_method is invoked for every test method of a class.
        """
        JavaCreator.add_creator_class("com.intel.analytics.bigdl.dllib.utils.python.api.PythonBigDLValidator")
        sparkConf = create_spark_conf().setMaster("local[4]").setAppName("test model")
        self.sc = get_spark_context(sparkConf)
        init_engine()

    def teardown_method(self, method):
        """ teardown any state that was previously setup with a setup_method
        call.
        """
        self.sc.stop()

    def test_activity_with_jtensor(self):
        back = callBigDlFunc("float", "testActivityWithTensor")
        assert isinstance(back.value, JTensor)

    def test_activity_with_table_of_tensor(self):
        back = callBigDlFunc("float", "testActivityWithTableOfTensor")
        assert isinstance(back.value, list)
        assert isinstance(back.value[0], JTensor)
        assert back.value[0].to_ndarray()[0] < back.value[1].to_ndarray()[0]
        assert back.value[1].to_ndarray()[0] < back.value[2].to_ndarray()[0]

    def test_activity_with_table_of_table(self):
        back = callBigDlFunc("float", "testActivityWithTableOfTable")
        assert isinstance(back.value, list)
        assert isinstance(back.value[0], list)
        assert isinstance(back.value[0][0], JTensor)

if __name__ == "__main__":
    pytest.main([__file__])
