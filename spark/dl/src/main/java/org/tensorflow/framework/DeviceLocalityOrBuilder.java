// Generated by the protocol buffer compiler.  DO NOT EDIT!
// source: device_attributes.proto

package org.tensorflow.framework;

public interface DeviceLocalityOrBuilder extends
    // @@protoc_insertion_point(interface_extends:tensorflow.DeviceLocality)
    com.google.protobuf.MessageOrBuilder {

  /**
   * <pre>
   * Optional bus locality of device.  Default value of 0 means
   * no specific locality.  Specific localities are indexed from 1.
   * </pre>
   *
   * <code>optional int32 bus_id = 1;</code>
   */
  int getBusId();
}
