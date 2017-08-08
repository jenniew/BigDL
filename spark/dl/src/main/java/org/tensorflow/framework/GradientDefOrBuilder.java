// Generated by the protocol buffer compiler.  DO NOT EDIT!
// source: function.proto

package org.tensorflow.framework;

public interface GradientDefOrBuilder extends
    // @@protoc_insertion_point(interface_extends:tensorflow.GradientDef)
    com.google.protobuf.MessageOrBuilder {

  /**
   * <pre>
   * The function name.
   * </pre>
   *
   * <code>optional string function_name = 1;</code>
   */
  java.lang.String getFunctionName();
  /**
   * <pre>
   * The function name.
   * </pre>
   *
   * <code>optional string function_name = 1;</code>
   */
  com.google.protobuf.ByteString
      getFunctionNameBytes();

  /**
   * <pre>
   * The gradient function's name.
   * </pre>
   *
   * <code>optional string gradient_func = 2;</code>
   */
  java.lang.String getGradientFunc();
  /**
   * <pre>
   * The gradient function's name.
   * </pre>
   *
   * <code>optional string gradient_func = 2;</code>
   */
  com.google.protobuf.ByteString
      getGradientFuncBytes();
}
