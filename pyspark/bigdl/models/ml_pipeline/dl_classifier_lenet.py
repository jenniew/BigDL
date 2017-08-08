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
# Still in experimental stage!

from optparse import OptionParser
from bigdl.dataset import mnist
from bigdl.dataset.transformer import *
from bigdl.nn.layer import *
from bigdl.nn.criterion import *
from bigdl.optim.optimizer import *
from bigdl.util.common import *
from bigdl.ml.dl_classifier import *
from pyspark.sql.types import *


def build_model(class_num):
    model = Sequential()
    model.add(Reshape([1, 28, 28]))
    model.add(SpatialConvolution(1, 6, 5, 5))
    model.add(Tanh())
    model.add(SpatialMaxPooling(2, 2, 2, 2))
    model.add(Tanh())
    model.add(SpatialConvolution(6, 12, 5, 5))
    model.add(SpatialMaxPooling(2, 2, 2, 2))
    model.add(Reshape([12 * 4 * 4]))
    model.add(Linear(12 * 4 * 4, 100))
    model.add(Tanh())
    model.add(Linear(100, class_num))
    model.add(LogSoftMax())
    return model


def get_mnist(sc, data_type="train", location="/tmp/mnist"):
    """
    Get and normalize the mnist data. We would download it automatically
    if the data doesn't present at the specific location.

    :param sc: SparkContext
    :param data_type: training data or testing data
    :param location: Location storing the mnist
    :return: A RDD of Sample
    """
    (images, labels) = mnist.read_data_sets(location, data_type)
    images = sc.parallelize(images)
    labels = sc.parallelize(labels)
    # Target start from 1 in BigDL

    record = images.zip(labels).map(lambda features_label:
                                    Sample.from_ndarray(features_label[0], features_label[1] + 1))
    # record = images.zip(labels)
    return record


if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-b", "--batchSize", type=int, dest="batchSize", default="128")
    parser.add_option("-e", "--maxEpoch", type=int, dest="maxEpoch", default="20")

    (options, args) = parser.parse_args(sys.argv)

    sc = SparkContext(appName="lenet5", conf=create_spark_conf())
    init_engine()

    train_data = get_mnist(sc, "train").map(
        normalizer(mnist.TRAIN_MEAN, mnist.TRAIN_STD))
    test_data = get_mnist(sc, "test").map(
        normalizer(mnist.TEST_MEAN, mnist.TEST_STD))

    train_rdd = train_data.map(
        lambda sample: (sample.features.ravel().tolist(),
                                sample.label.ravel().tolist()))
    sqlContext = SQLContext(sc)
    schema = StructType([
        StructField("features",  ArrayType(DoubleType(),False), False),
        StructField("label", ArrayType(DoubleType(), False), False)])
    train_df = sqlContext.createDataFrame(train_rdd, schema)

    model = build_model(10)
    criterion = ClassNLLCriterion()
    featureSize = [28, 28]
    estimator = DLClassifier(model, criterion, featureSize).setFeaturesCol("features").setLabelCol(
        "label").setBatchSize(options.batchSize).setMaxEpoch(options.maxEpoch)
    transformer = estimator.fit(train_df)

    val_rdd = test_data.map(
        lambda sample: (sample.features.ravel().tolist(),
                                sample.label.ravel().tolist()))
    val_df = sqlContext.createDataFrame(val_rdd, schema)
    transformed = transformer.transform(val_df)
    transformed.show()
    sc.stop()
