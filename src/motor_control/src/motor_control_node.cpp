// This node publishes CAN bus messages to our VESC brushless motor controllers.
// Original Author: Jude Sauve <sauve031@umn.edu> in 2018
// Maintainer: Anthony Brogni <brogn002@umn.edu>
// Last Updated: November 2023

// Import the ROS 2 Library
#include "rclcpp/rclcpp.hpp"

// Import ROS 2 Formatted Message Types
#include "can_msgs/msg/frame.hpp"
#include "geometry_msgs/msg/twist.hpp"
#include "std_msgs/msg/float32.hpp"
#include "std_msgs/msg/string.hpp"

// Import custom ROS 2 interfaces
#include "rovr_interfaces/srv/motor_command_get.hpp"
#include "rovr_interfaces/srv/motor_command_set.hpp"

// Import Native C++ Libraries
#include <chrono>
#include <map>
#include <memory>
#include <stdint.h>
#include <string>
#include <tuple> // for tuples
#include <vector>

using namespace std::chrono_literals;
using std::placeholders::_1;
using std::placeholders::_2;

// Define a struct to store motor data
struct MotorData {
  float dutyCycle;
  float velocity;
  int tachometer;
  std::chrono::time_point<std::chrono::steady_clock> timestamp;
};

class PIDController {
private:
  const int DEAD_BAND = 1;
  int COUNTS_PER_REVOLUTION; // Steps for one 360 degree rotation

  float kp, ki, kd;
  float gravComp;

  int32_t targTach, totalError;

  std::optional<int32_t> prevError;

public:
  bool isActive;

  PIDController(int CountsPerRevolution, float kp, float ki = 0, float kd = 0, float gravComp = 0) {
    this->COUNTS_PER_REVOLUTION = CountsPerRevolution;

    this->kp = kp;
    this->ki = ki;
    this->kd = kd;
    this->gravComp = gravComp;

    this->totalError = 0;
    this->isActive = false;
    this->prevError = std::nullopt;
  }

  float update(int32_t currTach) {
    float currError = (this->targTach - currTach); // Whats the error
    if (abs(currError) <= DEAD_BAND) { return 0; } // If the error is inside the band, return 0
  
    this->totalError += currError;
  
    float PIDResult = (currError * this->kp) + (this->totalError * this->ki) + (this->prevError.has_value() ? currError - this->prevError.value() : 0) * this->kd;

    PIDResult = std::clamp(PIDResult, (float)(-1), (float)(1)); // Clamp the PIDResult between -1 and 1

    // Uncomment the line below for debug values:
    // std::cout << "Target Tachometer: " << targTach << ", Current Tachometer: " << currTach << ", Current Error: " << currError << ", PIDResult: " << PIDResult << ", Total Error: " << totalError << ", D: " << (this->prevError.has_value() ? currError - this->prevError.value() : 0) << std::endl;
    
    this->prevError = currError; // Assign the previous error to the current error

    return PIDResult;
  }

  void setRotation(float degrees) {
    this->isActive = true;
    this->targTach = static_cast<int32_t>((degrees / 360.0) * this->COUNTS_PER_REVOLUTION);
    this->totalError = 0;
    this->prevError = std::nullopt;
  }

  int getCountsPerRevolution() {
    return this->COUNTS_PER_REVOLUTION;
  }
};

class MotorControlNode : public rclcpp::Node {
  // Generic method for sending data over the CAN bus
  void send_can(uint32_t id, int32_t data) const {
    can_msgs::msg::Frame can_msg; // Construct a new CAN message

    can_msg.is_rtr = false;
    can_msg.is_error = false;
    can_msg.is_extended = true;

    can_msg.id = id; // Set the CAN ID for this message

    can_msg.dlc = 4;                       // Size of the data array (how many bytes to use, maximum of 8)
    can_msg.data[0] = (data >> 24) & 0xFF; // First byte of data
    can_msg.data[1] = (data >> 16) & 0xFF; // Second byte of data
    can_msg.data[2] = (data >> 8) & 0xFF;  // Third byte of data
    can_msg.data[3] = data & 0xFF;         // Fourth byte of data

    can_pub->publish(can_msg); // Publish the CAN message to the ROS 2 topic
  }

  // Set the percent power of the motor between -1.0 and 1.0
  void vesc_set_duty_cycle(uint32_t id, float percentPower) {
    // Do not allow setting more than 100% power in either direction
    this->pid_controllers[id]->isActive = false;
    percentPower = std::clamp(percentPower, (float)(-1), (float)(1));
    int32_t data = percentPower * 100000; // Convert from percent power to a signed 32-bit integer

    send_can(id + 0x00000000, data); // ID does NOT need to be modified to signify this is a duty cycle command
    this->current_msg[id] = std::make_tuple(id + 0x00000000, data); // update the hashmap
    RCLCPP_DEBUG(this->get_logger(), "Setting the duty cycle of CAN ID: %u to %f", id, percentPower); // Print Statement
  }

  // Set the velocity of the motor in RPM (Rotations Per Minute)
  void vesc_set_velocity(uint32_t id, int rpm) {
    this->pid_controllers[id]->isActive = false;
    int32_t data = rpm;

    send_can(id + 0x00000300, data); // ID must be modified to signify this is a RPM command
    this->current_msg[id] = std::make_tuple(id + 0x00000300, data); // update the hashmap
    RCLCPP_DEBUG(this->get_logger(), "Setting the velocity of CAN ID: %u to %d RPM", id, rpm); // Print Statement
  }

  // Set the position of the motor in degrees
  void vesc_set_position(uint32_t id, int position) {
    this->pid_controllers[id]->setRotation(position);
    RCLCPP_DEBUG(this->get_logger(), "Setting the position of CAN ID: %u to %d degrees", id, position); // Print Statement
  }

  // Get the motor controller's current duty cycle command
  std::optional<float> vesc_get_duty_cycle(uint32_t id) {
    if (std::chrono::steady_clock::now() - this->can_data[id].timestamp < this->threshold) {
      return this->can_data[id].dutyCycle;
    } else {
      return std::nullopt; // The data is too stale
    }
  }
  // Get the current velocity of the motor in RPM (Rotations Per Minute)
  std::optional<float> vesc_get_velocity(uint32_t id) {
    if (std::chrono::steady_clock::now() - this->can_data[id].timestamp < this->threshold) {
      return this->can_data[id].velocity;
    } else {
      return std::nullopt; // The data is too stale
    }
  }
  // Get the current position (tachometer reading) of the motor
  std::optional<float> vesc_get_position(uint32_t id) {
    if (std::chrono::steady_clock::now() - this->can_data[id].timestamp < this->threshold) {
      return (static_cast<float>(this->can_data[id].tachometer) / static_cast<float>(this->pid_controllers[id]->getCountsPerRevolution())) * 360.0;
    } else {
      return std::nullopt; // The data is too stale
    }
  }

public:
  MotorControlNode() : Node("MotorControlNode") {
    // Define default values for our ROS parameters below #
    this->declare_parameter("CAN_INTERFACE_TRANSMIT", "can0");
    this->declare_parameter("CAN_INTERFACE_RECEIVE", "can0");
    this->declare_parameter("BACK_LEFT_TURN", 2);
    this->declare_parameter("FRONT_LEFT_TURN", 4);
    this->declare_parameter("BACK_RIGHT_TURN", 6);
    this->declare_parameter("FRONT_RIGHT_TURN", 8);
    this->declare_parameter("SKIMMER_LIFT_MOTOR", 10);

    // Print the ROS Parameters to the terminal below #
    RCLCPP_INFO(this->get_logger(), "CAN_INTERFACE_TRANSMIT parameter set to: %s", this->get_parameter("CAN_INTERFACE_TRANSMIT").as_string().c_str());
    RCLCPP_INFO(this->get_logger(), "CAN_INTERFACE_RECEIVE parameter set to: %s", this->get_parameter("CAN_INTERFACE_RECEIVE").as_string().c_str());
    RCLCPP_INFO(this->get_logger(), "BACK_LEFT_TURN parameter set to: %ld", this->get_parameter("BACK_LEFT_TURN").as_int());
    RCLCPP_INFO(this->get_logger(), "FRONT_LEFT_TURN parameter set to: %ld", this->get_parameter("FRONT_LEFT_TURN").as_int());
    RCLCPP_INFO(this->get_logger(), "BACK_RIGHT_TURN parameter set to: %ld", this->get_parameter("BACK_RIGHT_TURN").as_int());
    RCLCPP_INFO(this->get_logger(), "FRONT_RIGHT_TURN parameter set to: %ld", this->get_parameter("FRONT_RIGHT_TURN").as_int());
    RCLCPP_INFO(this->get_logger(), "SKIMMER_LIFT_MOTOR parameter set to: %ld", this->get_parameter("SKIMMER_LIFT_MOTOR").as_int());

    // Initialize services below //
    srv_motor_set = this->create_service<rovr_interfaces::srv::MotorCommandSet>(
        "motor/set", std::bind(&MotorControlNode::set_callback, this, _1, _2));
    srv_motor_get = this->create_service<rovr_interfaces::srv::MotorCommandGet>(
        "motor/get", std::bind(&MotorControlNode::get_callback, this, _1, _2));

    // Instantiate all of our PIDControllers here
    this->pid_controllers[this->get_parameter("BACK_LEFT_TURN").as_int()] = new PIDController(42, 0.01); // TODO: kp will need to be tuned on the real robot
    this->pid_controllers[this->get_parameter("FRONT_LEFT_TURN").as_int()] = new PIDController(42, 0.01); // TODO: kp will need to be tuned on the real robot
    this->pid_controllers[this->get_parameter("BACK_RIGHT_TURN").as_int()] = new PIDController(42, 0.01); // TODO: kp will need to be tuned on the real robot
    this->pid_controllers[this->get_parameter("FRONT_RIGHT_TURN").as_int()] = new PIDController(42, 0.01); // TODO: kp will need to be tuned on the real robot
    this->pid_controllers[this->get_parameter("SKIMMER_LIFT_MOTOR").as_int()] = new PIDController(42, 0.01); // TODO: kp will need to be tuned on the real robot

    // Initialize timers below //
    timer = this->create_wall_timer(500ms, std::bind(&MotorControlNode::timer_callback, this));

    // Initialize publishers and subscribers below //
    // The name of this topic is determined by ros2socketcan_bridge
    can_pub = this->create_publisher<can_msgs::msg::Frame>("CAN/" + this->get_parameter("CAN_INTERFACE_TRANSMIT").as_string() + "/transmit", 100);
    // The name of this topic is determined by ros2socketcan_bridge
    can_sub = this->create_subscription<can_msgs::msg::Frame>("CAN/" + this->get_parameter("CAN_INTERFACE_RECEIVE").as_string() + "/receive", 10, std::bind(&MotorControlNode::CAN_callback, this, _1));
  }

private:
  // Continuously send CAN messages to our motor controllers so they don't timeout
  void timer_callback() {
    // Loop through everything in the current_msg hashmap
    for (auto pair : this->current_msg) {
      uint32_t motorId = pair.first;
      // If the motor controller has previously received a command, send the most recent command again
      if (this->pid_controllers[motorId]->isActive == false) {
        send_can(std::get<0>(this->current_msg[motorId]), std::get<1>(this->current_msg[motorId]));
      }
    }
  }

  // Listen for CAN status frames sent by our VESC motor controllers
  void CAN_callback(const can_msgs::msg::Frame::SharedPtr can_msg) {
    uint32_t motorId = can_msg->id & 0xFF;
    uint32_t statusId = (can_msg->id >> 8) & 0xFF; // Packet Status, not frame ID

    // If 'motorId' is not found in the 'can_data' hashmap, add it.
    if (this->can_data.count(motorId) == 0) {
      this->can_data[motorId] = {0, 0, 0, std::chrono::steady_clock::now()};
    }

    float dutyCycleNow = this->can_data[motorId].dutyCycle;
    float RPM = this->can_data[motorId].velocity;
    int32_t tachometer = this->can_data[motorId].tachometer;

    switch (statusId) {
    case 9: // Packet Status 9 (RPM & Duty Cycle)
      RPM = static_cast<float>((can_msg->data[0] << 24) + (can_msg->data[1] << 16) + (can_msg->data[2] << 8) + can_msg->data[3]);
      dutyCycleNow = static_cast<float>(((can_msg->data[6] << 8) + can_msg->data[7]) / 10.0);
      break;
    case 27: // Packet Status 27 (Tachometer)
      tachometer = static_cast<int32_t>((can_msg->data[0] << 24) + (can_msg->data[1] << 16) + (can_msg->data[2] << 8) + can_msg->data[3]);

      // Runs the PID controller for this motor if its active
      if (this->pid_controllers[motorId]->isActive) {
        float PIDResult = this->pid_controllers[motorId]->update(tachometer);

        int32_t data = PIDResult * 100000; // Convert from percent power to a signed 32-bit integer
        send_can(motorId + 0x00000000, data); // ID does NOT need to be modified to signify this is a duty cycle command
      }

      break;
    }

    // Store the most recent motor data in the hashmap
    this->can_data[motorId] = {dutyCycleNow, RPM, tachometer, std::chrono::steady_clock::now()};

    RCLCPP_DEBUG(this->get_logger(), "Received status frame %u from CAN ID %u with the following data:", statusId, motorId);
    RCLCPP_DEBUG(this->get_logger(), "RPM: %.2f, Duty Cycle: %.2f%%, Tachometer: %d", RPM, dutyCycleNow, tachometer);
  }

  // Initialize a hashmap to store the most recent motor data for each CAN ID
  std::map<uint32_t, MotorData> can_data;
  std::map<uint32_t, PIDController*> pid_controllers;
  // Adjust this data retention threshold as needed
  const std::chrono::seconds threshold = std::chrono::seconds(1);

  // Initialize a hashmap to store the most recent msg for each CAN ID
  std::map<uint32_t, std::tuple<uint32_t, int32_t>> current_msg;

  // Callback method for the MotorCommandSet service
  void set_callback(const std::shared_ptr<rovr_interfaces::srv::MotorCommandSet::Request> request,
                    std::shared_ptr<rovr_interfaces::srv::MotorCommandSet::Response> response) {

    if (request->type == "velocity") {
      vesc_set_velocity(request->can_id, request->value);
      response->success = 1; // indicates success
    } else if (request->type == "duty_cycle") {
      vesc_set_duty_cycle(request->can_id, request->value);
      response->success = 1; // indicates success
    } else if (request->type == "position") {
      vesc_set_position(request->can_id, request->value);
      response->success = 1; // indicates success
    } else {
      RCLCPP_ERROR(this->get_logger(), "Unknown motor SET command type: '%s'", request->type.c_str());
      response->success = 1; // indicates failure
    }
  }

  // Callback method for the MotorCommandGet service
  void get_callback(const std::shared_ptr<rovr_interfaces::srv::MotorCommandGet::Request> request,
                    std::shared_ptr<rovr_interfaces::srv::MotorCommandGet::Response> response) {
    std::optional<float> data = std::nullopt;

    if (request->type == "velocity") {
      data = vesc_get_velocity(request->can_id);
    } else if (request->type == "duty_cycle") {
      data = vesc_get_duty_cycle(request->can_id);
    } else if (request->type == "position") {
      data = vesc_get_position(request->can_id);
    } else {
      RCLCPP_ERROR(this->get_logger(), "Unknown motor GET command type: '%s'", request->type.c_str());
    }

    if (data.has_value()) {
      response->data = data.value();
      response->success = 0; // indicates success
    } else {
      response->success = 1; // indicates failure
      RCLCPP_ERROR(this->get_logger(), "GET command for CAN ID %u read stale data!", request->can_id);
    }
  }

  rclcpp::TimerBase::SharedPtr timer;
  rclcpp::Publisher<can_msgs::msg::Frame>::SharedPtr can_pub;
  rclcpp::Subscription<can_msgs::msg::Frame>::SharedPtr can_sub;
  rclcpp::Service<rovr_interfaces::srv::MotorCommandSet>::SharedPtr srv_motor_set;
  rclcpp::Service<rovr_interfaces::srv::MotorCommandGet>::SharedPtr srv_motor_get;
};

// Main method for the node
int main(int argc, char **argv) {
  // Initialize ROS 2
  rclcpp::init(argc, argv);

  // Spin the node
  rclcpp::spin(std::make_shared<MotorControlNode>());

  // Free up any resources being used by the node
  rclcpp::shutdown();
  return 0;
}
