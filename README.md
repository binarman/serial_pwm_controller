## MCU based PWM fan controller for linux

The goal of the project is to add more PWM controlled fans it linux PC.
PWM controller has two parts: MCU based hardware generator of PWM signal and linux service. These two parts communicate via USB UART interface, available on most cheap Arduino compatible boards.

Project is tested with Arduino nano with atmega328p MCU and NodeMCU esp32 dev board.

Linux should use **systemd**. You can check it with `ps -A|grep systemd` command.

Thanks for atmega PWM initialization to [hlovdal](https://stackoverflow.com/users/23118/hlovdal) for [this post](https://stackoverflow.com/a/64864315/15324164), which saved me a lot of time.

## How to build

After flashing firmware on MCU, need to connect MCU board with usb to PC, and connect one pin to PWM fan pin, no resistors are needed.
Only 9 pin is supported as a PWM signal generator on atmega chips. With esp32 you can choose any free IO pin by changing `OUTPUT_PIN` value, default is 4.

## How to use

- Install python dependencies: `pip3 install -r requirements.txt`. Make sure root user can use these packages, if not, run installation from root user.
- Run `./setup.py` as a root, answer questions regarding system.
- Run service: `systemctl start serial_pwm`
- Stop service: `systemctl stop serial_pwm`
- Check service status: `systemctl status serial_pwm`
