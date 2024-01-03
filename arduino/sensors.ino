// Define a struct to hold the sensor data
struct SensorData {
  bool topLimitSwitch;
  bool bottomLimitSwitch;
  uint16_t frontLeftEncoder;
  uint16_t frontRightEncoder;
  uint16_t backLeftEncoder;
  uint16_t backRightEncoder;
};

// Define the sensor pins here
#define FRONT_LEFT_ENCODER A0
#define FRONT_RIGHT_ENCODER A1
#define BACK_LEFT_ENCODER A2
#define BACK_RIGHT_ENCODER A3
#define TOP_LIMIT_SWITCH 2
#define BOTTOM_LIMIT_SWITCH 3

void setup() {
  // Initialize serial communication
  Serial.begin(9600);

  // Initialize the analog inputs (absolute encoders)
  pinMode(FRONT_LEFT_ENCODER, INPUT);
  pinMode(FRONT_RIGHT_ENCODER, INPUT);
  pinMode(BACK_LEFT_ENCODER, INPUT);
  pinMode(BACK_RIGHT_ENCODER, INPUT);

  // Initialize the digital inputs (limit switches)
  pinMode(TOP_LIMIT_SWITCH, INPUT_PULLUP);
  pinMode(BOTTOM_LIMIT_SWITCH, INPUT_PULLUP);
}

void loop() {
  // Create a SensorData struct
  SensorData data;

  // Read from the analog inputs (absolute encoders)
  data.frontLeftEncoder = (uint16_t)analogRead(FRONT_LEFT_ENCODER);
  data.frontRightEncoder = (uint16_t)analogRead(FRONT_RIGHT_ENCODER);
  data.backLeftEncoder = (uint16_t)analogRead(BACK_LEFT_ENCODER);
  data.backRightEncoder = (uint16_t)analogRead(BACK_RIGHT_ENCODER);

  // Read from the digital inputs (limit switches)
  data.topLimitSwitch = (bool)digitalRead(TOP_LIMIT_SWITCH);
  data.bottomLimitSwitch = (bool)digitalRead(BOTTOM_LIMIT_SWITCH);

  // Send the struct over the serial bus to the Nvidia Jetson
  Serial.write((byte *)&data, sizeof(SensorData));

  // Wait 100ms before the next loop iteration
  delay(100);
}
