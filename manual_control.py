#!/usr/bin/python3
import tkinter as tk
from tkinter import ttk
import time
import serial
import serial.tools.list_ports
import yaml
import argparse

device_request_message = bytearray([0x80])

# pwm command can take values 0 .. 63
max_pwm_command = 63
# duty can take values 0 .. 1.0
default_pwm_duty = 0.75

def get_controller_display_name(controller):
  return "{} path:{}".format(controller.hwid, controller.device)

def init(verbose):
  com_ports =  serial.tools.list_ports.comports()
  detected_hwids = {}
  configured_pwm_devices = []
  for port in com_ports:
    detected_hwids[port.hwid] = port
  for dev_id in detected_hwids:
    print(f"Probing {dev_id} device")
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
          print("detected PWM controller: {}\n".format(get_controller_display_name(port)))
        configured_device = {
            "interface": s,
            "duty": default_pwm_duty,
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


def make_PWM_command(level):
  '''
  level is a floating point number between 0.0 and 1.0
  '''
  clamp_level = min(max(level, 0.0), 1.0)
  int_level = int(clamp_level * max_pwm_command)
  parity = bin(int_level)[2:].count('1') & 1
  if not parity:
    return bytearray([0x40 + int_level])
  else:
    return bytearray([int_level])


def send_pwn_to_controllers(gui_root, controllers, verbose):
  try:
    for controller in controllers:
      pwm_level = controller["duty"]
      if verbose:
        print("Setting {} PWM level to {:.2f}".format(controller["interface"].port, pwm_level))
      controller["interface"].write(make_PWM_command(pwm_level))
    time.sleep(1)
  except serial.serialutil.SerialException as e:
    print("Detected failure: \"{}\"".format(e))
  gui_root.after(1000, lambda: send_pwn_to_controllers(gui_root, controllers, verbose))


def change_pwm(controller, value, verbose):
  if verbose:
    print(f"Slided {value} for {controller['interface'].port}") 
  controller["duty"] = int(value) / 100.0


def run_GUI(controllers, verbose):
  # Create main window
  root = tk.Tk()
  root.title("Manual PWM controllers")
  root.geometry(f"300x{150*len(controllers)}")

  for controller in controllers:
    # Top label
    label = tk.Label(root, text=f"Controller {controller['interface'].port}", font=("Arial", 12))
    label.pack(pady=10)

    # Slider
    on_slide = lambda value : change_pwm(controller, value, verbose)
    slider = tk.Scale(root, from_=0, to=100, orient="horizontal", command=on_slide)
    slider.set(int(default_pwm_duty * 100))
    slider.pack(pady=10, fill="x")
  
  send_pwn_to_controllers(root, controllers, verbose)

  # Run the application
  root.mainloop()


def main():
  parser = argparse.ArgumentParser(prog=__file__)
  parser.add_argument("--verbose", action="store_true", help="enable verbose mode")
  args = parser.parse_args()

  controllers = init(args.verbose)
  #runServiceLoop(controllers, args.verbose)
  run_GUI(controllers, args.verbose)


if __name__ == "__main__":
  main()
