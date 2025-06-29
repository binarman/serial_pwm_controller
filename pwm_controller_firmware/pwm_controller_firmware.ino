// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include <inttypes.h>
#include "Arduino.h"

#if defined(__AVR_ATmega328P__)
#include <avr/io.h>
#endif

#if defined(__AVR_ATmega328P__)
constexpr int OUTPUT_PIN = 9;
#endif
#if defined(ESP32)
constexpr int OUTPUT_PIN = 4;
#endif

constexpr int RESOLUTION = 8;
constexpr uint32_t PWM_FREQ = 25000;
constexpr int PWM_RESOLUTION = 6;
constexpr int MAX_LEVEL = (1 << PWM_RESOLUTION) - 1;
constexpr unsigned long MAX_IDLE_TIME = 2000;
constexpr uint32_t CHIP_FREQ = 16000000;

// computes parity bit for first byte in given value
// returns 0x40 or 0x00
int parity_bit(int value) {
  value = value & 0xff;
  value = (value & 0x0f) ^ (value >> 4);
  value = (value & 0x03) ^ (value >> 2);
  value = (value & 0x01) ^ (value >> 1);
  return value ? 0x00 : 0x40;
}

unsigned long last_set_time;
uint16_t current_duty_cycle = 0xffff;

void setDutyCycle(uint16_t duty_cycle) {
  last_set_time = millis();
  // do nothing is duty cycle did not change
  if (duty_cycle == current_duty_cycle)
    return;
  current_duty_cycle = duty_cycle;
#if defined(__AVR_ATmega328P__)

  uint8_t sreg = SREG;
  cli();

  // Stop timer before configuring
  TCCR1B = 0;

  // 16.11.1 TCCR1A – Timer/Counter1 Control Register A
  // Clear OC1A and OC1B on Compare Match, set OC1A and OC1B at BOTTOM (non-inverting mode)
  uint8_t channel_mode = (1 << COM1A1) | (0 << COM1A0) | (1 << COM1B1) | (0 << COM1B0);
  // Fast PWM mode 14 (TOP = ICR1), part 1/2
  uint8_t fast_mode = (1 << WGM11) | (0 << WGM10);
  TCCR1A = channel_mode | fast_mode;

  // 16.11.2 TCCR1B – Timer/Counter1 Control Register B
  TCCR1B = (1 << WGM13) | (1 << WGM12);   // Fast PWM mode 14 (TOP = ICR1), part 2/2

  // IMPORTANT NOTE ABOUT ORDER OF INITIALIZATION:
  //   "The ICR1 Register can only be written when using a Waveform
  //   Generation mode that utilizes the ICR1 Register for defining
  //   the counter’s TOP value. In these cases the Waveform
  //   Generation mode (WGM13:0) bits must be set before the TOP
  //   value can be written to the ICR1 Register."
  // Thus initializing OCR1 before TCCR1A and TCCR1B has been
  // configured with Fast PWM mode 14 is wrong.

  // Set TOP value
  constexpr uint16_t cycles_per_iteration = CHIP_FREQ / PWM_FREQ;
  ICR1 = cycles_per_iteration;

  // IMPORTANT NOTE ABOUT ORDER OF INITIALIZATION:
  //   "The OCR1x Register is double buffered when using any of the
  //   twelve Pulse Width Modulation (PWM) modes. For the Normal
  //   and Clear Timer on Compare (CTC) modes of operation, the
  //   double buffering is disabled."
  // If initializing OCR1A before configuring TCCR1A and TCCR1B to
  // a PWM mode the value is written to the non-buffered OCR1A
  // register and the buffered OCR1A register contains some "random",
  // unused garbage value. When later changing to PWM the buffered
  // register will be enabled, and its existing garbage value will
  // be used.
  // Thus initializing OCR1A/OCR1B before TCCR1A and TCCR1B has
  // been configured with Fast PWM is wrong.

  // Set duty cycle
  if (duty_cycle >= (1 << PWM_RESOLUTION) - 1)
    OCR1A = cycles_per_iteration;
  else
    OCR1A = ((uint32_t)duty_cycle * cycles_per_iteration) / (1 << PWM_RESOLUTION);
  //OCR1B = 0xBFFF;

  // 14.4.3 DDRB – The Port B Data Direction Register
  static_assert(OUTPUT_PIN == 9, "timer 1 supports only pins 9 and 10");
  DDRB = 1 << DDB1; // PB1 (aka OC1A) as output - pin 9 on Arduino Uno
//  DDRB = 1 << DDB2; // PB2 (aka OC1B) as output - pin 10 on Arduino Uno

  // Start the timer with no prescaler
  TCCR1B |= (0 << CS12) | (0 << CS11) | (1 << CS10);

  SREG = sreg;

#endif
#if defined(ESP32)
  bool res = ledcWrite(OUTPUT_PIN, duty_cycle);
  assert(res);
#endif
  Serial.print("duty cycle: ");
  Serial.print(duty_cycle);
  Serial.print("\n");
}

void setupPWM() {
#if defined(ESP32)
  bool res = ledcAttach(OUTPUT_PIN, PWM_FREQ, PWM_RESOLUTION);
  assert(res);
#endif
  setDutyCycle(MAX_LEVEL);
}

void setup() {
  Serial.begin(115200);
  setupPWM();
}

void loop() {
  while (Serial.available() > 0) {
    int command = Serial.read();
    Serial.print("received ");
    Serial.println(command);
    int request_bit= command & 0x80;
    switch (request_bit) {
      case 0x80: {
        if ((command ^ request_bit) == 0 )
          Serial.print("PWM ctrl\n");
        break;
      }
      case 0x00: {
        int level = command & 0x3f;
        int parity = command & 0x40;
        int expected_parity = parity_bit(level);
        if (parity == expected_parity)
          setDutyCycle(level);
        break;
      }
    }
  }
  if (millis() - last_set_time > MAX_IDLE_TIME)
    setDutyCycle(MAX_LEVEL*3/4);
  delay(500);
}
