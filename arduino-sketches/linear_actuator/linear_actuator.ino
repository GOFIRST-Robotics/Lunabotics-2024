#include <ezButton.h> // This library makes it easier for us to work with limit switches
#include <Servo.h>    // Allows us to treat a PWM Talon SRX / Victor SP as a Servo with writeMicroseconds()

Servo linear_actuator;

ezButton limit_switch_extend(8);  // extend limit switch pin
ezButton limit_switch_retract(7); // retract limit switch pin

// These booleans help keep track of the current state of the linear actuator
bool extending = false;
bool retracting = false;

char buffer[2]; // Store serial data

// put setup code in this method to run once:
void setup()
{
  Serial.begin(9600); // open serial communication with a baud rate of 9600 bps

  linear_actuator.attach(9);   // Victor SP PWM pin

  pinMode(LED_BUILTIN, OUTPUT); // This is the built-in LED on the Arduino

  stop_actuator(); // stop the linear actuator by default
}

// put main loop code in this method to run repeatedly:
void loop()
{
  limit_switch_extend.loop();  // this method from the ezButton library needs to be called every code cycle
  limit_switch_retract.loop(); // this method from the ezButton library needs to be called every code cycle

  if (Serial.available())
  { // check if data is available to be read from the serial buffer
    Serial.readBytes(buffer, 2);

    if (buffer[0] == 'e')
      extend(buffer[1]); // extend the linear actuator
    if (buffer[0] == 'r')
      retract(buffer[1]); // retract the linear actuator
  }

  // check if the extend limit switch is pressed and we are currently extending
  if (limit_switch_extend.getState() == 0 && extending)
  {
    stop_actuator();   // stop the linear actuator
    Serial.write('f'); // send a message over serial to the Jetson
  }

  // check if the retract limit switch is pressed and we are currently retracting
  if (limit_switch_retract.getState() == 0 && retracting)
  {
    stop_actuator();   // stop the linear actuator
    Serial.write('s'); // send a message over serial to the Jetson
  }
}

// extend the linear actuator by running the motor forwards
void extend(char speed)
{
  extending = true;
  retracting = false;
  victor_set_forward_power(linear_actuator, speed);
  digitalWrite(LED_BUILTIN, HIGH); // Turn on the built-in LED
}
// retract the linear actuator by running the motor in reverse
void retract(char speed)
{
  retracting = true;
  extending = false;
  victor_set_reverse_power(linear_actuator, speed);
  digitalWrite(LED_BUILTIN, HIGH); // Turn on the built-in LED
}
// stop the linear actuator motor
void stop_actuator()
{
  victor_stop(linear_actuator);
  digitalWrite(LED_BUILTIN, LOW); // Turn off the built-in LED
  extending = false;
  retracting = false;
}

void victor_set_forward_power(Servo victor, char speed)
{ // input speed is 0-100
  long speed_long = speed;
  int microseconds = 1500 + ((speed_long * 500) / 100);
  victor.writeMicroseconds(microseconds); // 1500-2000 is forwards
}
void victor_set_reverse_power(Servo victor, char speed)
{ // input speed is 0-100
  long speed_long = speed;
  int microseconds = 1500 - ((speed_long * 500) / 100);
  victor.writeMicroseconds(microseconds); // 1000-1500 is reverse
}
void victor_stop(Servo victor)
{
  victor.writeMicroseconds(1500); // Puts the Victor in neutral mode
}