/*
 * Licensed to Intel Corporation under one or more
 * contributor license agreements.  See the NOTICE file distributed with
 * this work for additional information regarding copyright ownership.
 * Intel Corporation licenses this file to You under the Apache License, Version 2.0
 * (the "License"); you may not use this file except in compliance with
 * the License.  You may obtain a copy of the License at
 *
 *    http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package com.intel.analytics.bigdl.torch

import com.intel.analytics.bigdl.nn.SelectTable
import com.intel.analytics.bigdl.tensor.Tensor
import com.intel.analytics.bigdl.utils.{T, Table}
import org.scalatest.{BeforeAndAfter, FlatSpec, Matchers}

import scala.collection.mutable.HashMap
import scala.util.Random

@com.intel.analytics.bigdl.tags.Serial
class SelectTableSpec extends FlatSpec with BeforeAndAfter with Matchers {
  before {
    if (!TH.hasTorch()) {
      cancel("Torch is not installed")
    }
  }

  "A SelectTable selects a tensor as an output" should "generate correct output and grad" in {
    val seed = 100
    Random.setSeed(seed)

    val module = new SelectTable[Double](1)
    val input1 = Tensor[Double](10).randn()
    val input2 = Tensor[Double](10).randn()
    val input = T(1.0 -> input1, 2.0 -> input2)
    val gradOutput = Tensor[Double](10).randn()
    val start = System.nanoTime()
    val output = module.forward(input)
    val gradInput = module.backward(input, gradOutput)
    val scalaTime = System.nanoTime() - start

    val code =
      s"""
      torch.manualSeed($seed)
      module = nn.SelectTable(1)
      output = module:forward(input)
      gradInput = module:backward(input, gradOutput)
      gradInput1 = gradInput[1]
      gradInput2 = gradInput[2]
               """.stripMargin

    val (luaTime, torchResult) = TH.run(code, Map("input" -> input, "gradOutput" -> gradOutput),
      Array("output", "gradInput1", "gradInput2"))
    val torchOutput = torchResult("output").asInstanceOf[Tensor[Double]]
    val torchgradInput1 = torchResult("gradInput1").asInstanceOf[Tensor[Double]]
    val torchgradInput2 = torchResult("gradInput2").asInstanceOf[Tensor[Double]]
    val torchgradInput = T(torchgradInput1, torchgradInput2)

    torchOutput should be(output)
    torchgradInput should be(gradInput)

    println("Test case : PairwiseDistance, Torch : " + luaTime +
      " s, Scala : " + scalaTime / 1e9 +
      " s")
  }

  "A SelectTable selects a table as an output" should "generate correct output and grad" in {
    val seed = 100
    Random.setSeed(seed)

    val module = new SelectTable[Double](1)
    val embeddedInput1 = T(
        1.0 -> Tensor[Double](10).randn(),
        2.0 -> Tensor[Double](10).randn())
    val embeddedInput2 = Tensor[Double](10).randn()
    val input = T(
      1.0 -> embeddedInput1,
      2.0 -> embeddedInput2)
    val gradOutput = T(
        1.0 -> Tensor[Double](10).randn(),
        2.0 -> Tensor[Double](10).randn())
    val start = System.nanoTime()
    val output = module.forward(input)
    val gradInput = module.backward(input, gradOutput)
    val g1 = gradInput.toTable[Table](1.0)
    val g1_1 = g1[Tensor[Double]](1.0)
    val g1_2 = g1[Tensor[Double]](2.0)
    val g2 = gradInput.toTable[Tensor[Double]](2.0)
    val scalaTime = System.nanoTime() - start

    val code =
      s"""
      torch.manualSeed($seed)
      module = nn.SelectTable(1)
      output = module:forward{embeddedInput1, embeddedInput2}
      gradInput = module:backward({embeddedInput1, embeddedInput2}, gradOutput)
      gradInput1 = gradInput[1]
      gradInput2 = gradInput[2]
               """.stripMargin

    val (luaTime, torchResult) = TH.run(code, Map("embeddedInput2" -> embeddedInput2,
      "embeddedInput1" -> embeddedInput1, "gradOutput" -> gradOutput),
      Array("output", "gradInput1", "gradInput2"))

    val torchOutput = torchResult("output").asInstanceOf[Table]
    val torchgradInput1 = torchResult("gradInput1").asInstanceOf[Table]
    val torchgradInput2 = torchResult("gradInput2").asInstanceOf[Tensor[Double]]
    val torchgradInput = T(torchgradInput1, torchgradInput2)

    torchOutput[Tensor[Double]](1.0) should be(output.toTable[Tensor[Double]](1.0))
    torchOutput[Tensor[Double]](2.0) should be(output.toTable[Tensor[Double]](2.0))

    torchgradInput1[Tensor[Double]](1.0) should be (g1_1)
    torchgradInput1[Tensor[Double]](2.0) should be (g1_2)
    torchgradInput2 should be(g2)

    println("Test case : PairwiseDistance, Torch : " + luaTime +
      " s, Scala : " + scalaTime / 1e9 +
      " s")
  }
}
