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

import time
import serial
import serial.tools.list_ports
import sensors
import yaml
import argparse

device_request_message = bytearray([0x80])

default_config_path = "/etc/serial_pwm.conf"

max_pwm = 63

def getSensorDisplayName(sensor):
  return str(sensor.prefix, "UTF-8") + "-" + hex(sensor.addr)

def getControllerDisplayName(controller):
  return "{} path:{}".format(controller.hwid, controller.device)

def init(config_file, verbose):
  try:
    with open(config_file, "r") as f:
      config = yaml.safe_load(f)
  except:
    print("Can not load config file")
    exit(1)

  sensors.init()
  detected_sensors = {}
  for chip in sensors.iter_detected_chips():
    detected_sensors[getSensorDisplayName(chip)] = chip

  com_ports =  serial.tools.list_ports.comports()
  detected_hwids = {}
  configured_pwm_devices = []
  for port in com_ports:
    detected_hwids[port.hwid] = port
  for dev_id in config:
    if dev_id not in detected_hwids:
      print("Can not find device for configured controller: {}".format(dev_id))
      continue
    try:
      s = serial.Serial(port=detected_hwids[dev_id].device, baudrate=115200, timeout=0, write_timeout=1, stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE)
      # ask for functionality
      # flush previous data
      s.reset_input_buffer() # no effect on arduino nano
      s.reset_output_buffer() # no effect on arduino nano
      time.sleep(1)
      s.write(device_request_message)
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
        if verbose:
          print("detected PWM controller: {}\n".format(getControllerDisplayName(port)))
        controller_sensors = []
        for sensor_id in config[dev_id]["sensors"]:
          if sensor_id not in detected_sensors:
            print("can not use selected sensor \"{}\" for controller \"{}\"".format(sensor_id, dev_id))
            exit(1)
          controller_sensors.append(detected_sensors[sensor_id])
        configured_device = {
            "interface": s,
            "sensors": controller_sensors,
            "low_sensor": config[dev_id]["low_sensor"],
            "high_sensor": config[dev_id]["high_sensor"],
            "low_pwm": config[dev_id]["low_pwm"],
            "high_pwm": config[dev_id]["high_pwm"]
        }
        configured_pwm_devices += [configured_device]
      else:
        print("configured controller \"{}\" do not follow commands. Skipping it".format(dev_id))
    except serial.SerialException as e:
      print("can not use device {}: {}".format(dev_id, e))

  if len(configured_pwm_devices) == 0:
    print("No supported controllers found")
    exit(0)
  return configured_pwm_devices

def makePWMCommand(level):
  '''
  level is a floating point number between 0.0 and 1.0
  '''
  clamp_level = min(max(level, 0.0), 1.0)
  int_level = int(clamp_level * max_pwm)
  parity = bin(int_level)[2:].count('1') & 1
  if not parity:
    return bytearray([0x40 + int_level])
  else:
    return bytearray([int_level])

def runServiceLoop(controllers, verbose):
  while True:
    try:
      for controller in controllers:
        low_sensor = controller["low_sensor"]
        high_sensor = controller["high_sensor"]
        low_pwm = controller["low_pwm"]
        high_pwm = controller["high_pwm"]
        max_sensor_val = 0.0
        for chip in controller["sensors"]:
          for feature in chip:
            max_sensor_val = max(feature.get_value(), max_sensor_val)
        if verbose:
          print("Max sensor value:", max_sensor_val)
        normalized_sensor_value = (max_sensor_val - low_sensor) / (high_sensor - low_sensor)
        pwm_level = normalized_sensor_value * high_pwm + (1 - normalized_sensor_value) * low_pwm
        pwm_level = min(max(pwm_level, low_pwm), high_pwm)
        if verbose:
          print("Setting {} PWM level to {:.2f}".format(controller["interface"].port, pwm_level))
        controller["interface"].write(makePWMCommand(pwm_level))
      time.sleep(1)
    except serial.serialutil.SerialException as e:
      print("Detected failure: \"{}\"".format(e))
      break

if __name__ == "__main__":
  parser = argparse.ArgumentParser(prog="serial_pwm.py")
  parser.add_argument("--path", type=str, default=default_config_path, help="path to config file, default is {}".format(default_config_path))
  parser.add_argument("--verbose", action="store_true", help="enable verbose mode")
  args = parser.parse_args()

  controllers = init(args.path, args.verbose)
  runServiceLoop(controllers, args.verbose)

