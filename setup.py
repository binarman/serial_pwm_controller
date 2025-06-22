#!/usr/bin/env python3

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http:#www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import os
import sensors
import serial
import serial.tools.list_ports
import stat
import time
import yaml

import serial_pwm

def gather_sensors():
  sensors.init()
  sensor_chips = list(sensors.iter_detected_chips())
  if len(sensor_chips) == 0:
    print("No sensors found")
    exit(1)
  return sensor_chips

def gather_controllers():
  serial_ports = serial.tools.list_ports.comports()
  usb_serial_ports = [p for p in serial_ports if p.usb_device_path]
  controllers = []
  for port in usb_serial_ports:
    try:
      s = serial.Serial(port=port.device, baudrate=115200, timeout=0, write_timeout=1, stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE)
      # ask for functionality
      # flush previous data
      s.reset_input_buffer()
      s.reset_output_buffer()
      time.sleep(0.5)
      s.write(serial_pwm.device_request_message)
      time.sleep(0.5)
      streaming=True
      answer=b''
      while streaming:
        transaction = s.readall()
        if transaction:
          answer += transaction
          streaming = True
        else:
          streaming = False
      if b'PWM ctrl\n' in answer:
        controllers += [port]
    except serial.SerialException as e:
      print("can not use device {}: {}".format(port.device, e))
  del usb_serial_ports
  del serial_ports
  if len(controllers) == 0:
    print("No supported PWM controllers found")
    exit(1)
  return controllers

def print_info(sensors, controllers):
  print("Found following sensors:")
  for idx, chip in enumerate(sensors):
    print("  {}: {}".format(idx, serial_pwm.getSensorDisplayName(chip)))
    print("  Adapter: " + chip.adapter_name)
    for feature in chip:
      print("    {}: {}".format(feature.name, feature.get_value()))
  print("")
  print("Found following PWM controllers:")
  for idx, controller in enumerate(controllers):
    print("  {}: {}".format(idx, serial_pwm.getControllerDisplayName(controller)))

def inputNumericalValue(prompt, low = None, high = None):
  accepted = False
  while not accepted:
    print(prompt, end="")
    try:
      value = float(input())
      if low is not None and value < low:
        print("expect value to be greater than {}".format(low))
      if high is not None and value > high:
        print("expect value to be less than {}".format(high))
      accepted = True
    except ValueError as e:
      print("expected floating point value")
  return value

def configure_controller(controller, sensors):
  config = {"sensors": [], "low_sensor": -1, "high_sensor": -1, "low_pwm": 0.0, "high_pwm": 1.0 }
  print("Configuring controller {}\n".format(serial_pwm.getControllerDisplayName(controller)))
  for sensor in sensors:
    accepted = False
    while not accepted:
      sensor_name = serial_pwm.getSensorDisplayName(sensor)
      print("  use sensor \"{}\" values for this controller?[Y/n]:".format(sensor_name), end="")
      answer = input()
      if answer == "" or answer.lower() == "y":
        config["sensors"] += [sensor_name]
        accepted = True
      if answer.lower() == "n":
        accepted = True;
  config["low_sensor"] = low_sensor = inputNumericalValue("  low sensor value?:")
  # User can select low_sensor == high_sensor, which is probably incorrect, but I am lazy, will not fix
  config["high_sensor"] = inputNumericalValue("  high sensor value?:", low_sensor)
  config["low_pwm"] = inputNumericalValue("  low PWM dyty cycle? Value between 0.0 and 1.0: ", 0.0, 1.0)
  config["high_pwm"] = inputNumericalValue("  high PWM duty cycle? Value between 0.0 and 1.0: ", 0.0, 1.0)
  return config

def backup_old_file(path):
  file_exists = os.path.isfile(path)
  if file_exists:
    suffix = 1
    while os.path.isfile(path + "." + str(suffix)):
      suffix += 1
    backup = path + "." + str(suffix)
    print("file {} exists, backuping to {}".format(path, backup))
    os.rename(path, backup)

def save_config(config, filename):
  backup_old_file(filename)
  with open(filename, "w") as f:
    print("# Configuration file for PWM generators controlled over Serial interface", file = f)
    yaml.dump(config, f)

def copy_file(src, dst, executable = False):
  backup_old_file(dst)
  file_size = os.path.getsize(src)
  dst_fd = os.open(dst, os.O_RDWR | os.O_CREAT)
  src_fd = os.open(src, os.O_RDONLY)
  os.sendfile(dst_fd, src_fd, offset = 0, count = file_size)
  permissions = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH | stat.S_IWUSR
  if executable:
    permissions = permissions | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
  os.fchmod(dst_fd, permissions)

def install_service():
  base_path = os.path.abspath(os.path.dirname(__file__))
  script_path = os.path.join(base_path, "serial_pwm.py")
  service_path = os.path.join(base_path, "serial_pwm.service")
  copy_file(script_path, "/usr/bin/serial_pwm", executable = True)
  copy_file(service_path, "/etc/systemd/system/serial_pwm.service")

if __name__ == "__main__":
  parser = argparse.ArgumentParser(prog="setup.py")
  parser.add_argument("--path", type=str, default=serial_pwm.default_config_path, help="path to output config file, default is {}".format(serial_pwm.default_config_path))
  args = parser.parse_args()

  sensors = gather_sensors()
  controllers = gather_controllers()
  print_info(sensors, controllers)
  configs = {}
  print("Each controller is configured with a list of sensors, low/high PWM values and low/high sensor values.\n" +
        "PWM level is lineary interpolated between two points depending on max value from selected sensors.\n" +
        "If all sensor values are equal or lower than `low value`, PWM duty cycle is set to `low_pwm`,\n" +
        "If any of sensor values are equal or higher that `high value`, PWM duty cycle is set to `high_pwm`")
  for controller in controllers:
    configs[controller.hwid] = configure_controller(controller, sensors)
  save_config(configs, args.path)
  install_service()

