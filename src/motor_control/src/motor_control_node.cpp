// This node publishes CAN bus messages to our VESC brushless motor controllers.
// Original Author: Jude Sauve <sauve031@umn.edu> in 2018
// Maintainer: Anthony Brogni <brogn002@umn.edu>
// Last Updated: September 2023

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

// Our VESC CAN IDs should be between 1 and NUMBER_OF_MOTORS
const uint32_t NUMBER_OF_MOTORS = 8;

// Define a struct to store motor data
struct MotorData {
  float dutyCycle;
  float velocity;
  float current;
  float position;
  std::chrono::time_point<std::chrono::steady_clock> timestamp;
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

    can_pub->publish(can_msg); // Publish our new CAN message to the ROS 2 topic
  }

  // Set the percent power of the motor between -1.0 and 1.0
  void vesc_set_duty_cycle(uint32_t id, float percentPower) {
    // Do not allow setting more than 100% power in either direction
    percentPower = std::clamp(percentPower, (float)(-1), (float)(1));

    int32_t data = percentPower * 100000; // Convert from percent power to a signed 32-bit integer

    send_can(id + 0x00000000, data); // ID does NOT need to be modified to signify this is a duty cycle command
    this->current_msg[id] = std::make_tuple(id + 0x00000000, data); // update the hashmap
    // RCLCPP_INFO(this->get_logger(), "Setting the duty cycle of CAN ID: %u to %f", id, percentPower);
  }

  // Set the velocity of the motor in RPM (Rotations Per Minute)
  void vesc_set_velocity(uint32_t id, int rpm) {
    int32_t data = rpm;

    send_can(id + 0x00000300, data); // ID must be modified to signify this is an RPM command
    this->current_msg[id] = std::make_tuple(id + 0x00000300, data);                  // update the hashmap
    // RCLCPP_INFO(this->get_logger(), "Setting the RPM of CAN ID: %u to %d", id, rpm); // Print to the terminal
  }

  // Set the position of the motor in _____ (degrees? encoder counts?)
  void vesc_set_position(uint32_t id, int position) {
    // TODO: Implement this method!
  }

  // Set the current draw of the motor in amps
  void vesc_set_current(uint32_t id, float current) {
    // TODO: Implement this method!
  }

  // Get the current duty cycle of the motor
  float vesc_get_duty_cycle(uint32_t id) {
    if (std::chrono::steady_clock::now() - this->can_data[id].timestamp < this->threshold) {
      return this->can_data[id].dutyCycle;
    } else {
      return -1; // Return -1 if the data is stale
    }
  }
  // Get the current velocity of the motor in RPM (Rotations Per Minute)
  float vesc_get_velocity(uint32_t id) {
    if (std::chrono::steady_clock::now() - this->can_data[id].timestamp < this->threshold) {
      return this->can_data[id].velocity;
    } else {
      return -1; // Return -1 if the data is stale
    }
  }
  // Get the current position of the motor
  float vesc_get_position(uint32_t id) {
    if (std::chrono::steady_clock::now() - this->can_data[id].timestamp < this->threshold) {
      return this->can_data[id].position;
    } else {
      return -1; // Return -1 if the data is stale
    }
  }
  // Get the current draw of the motor in amps
  float vesc_get_current(uint32_t id) {
    if (std::chrono::steady_clock::now() - this->can_data[id].timestamp < this->threshold) {
      return this->can_data[id].current;
    } else {
      return -1; // Return -1 if the data is stale
    }
  }

public:
  MotorControlNode() : Node("MotorControlNode") {
    // Initialize services here
    srv_motor_set = this->create_service<rovr_interfaces::srv::MotorCommandSet>(
        "motor/set", std::bind(&MotorControlNode::set_callback, this, _1, _2));
    srv_motor_get = this->create_service<rovr_interfaces::srv::MotorCommandGet>(
        "motor/get", std::bind(&MotorControlNode::get_callback, this, _1, _2));

    // Initialize timers here
    timer = this->create_wall_timer(500ms, std::bind(&MotorControlNode::timer_callback, this));

    // Initialize publishers and subscribers below //
    // The name of this topic is determined by ros2socketcan_bridge
    can_pub = this->create_publisher<can_msgs::msg::Frame>("CAN/slcan0/transmit", 100);
    // The name of this topic is determined by ros2socketcan_bridge
    can_sub = this->create_subscription<can_msgs::msg::Frame>("CAN/slcan0/receive", 10,
                                                              std::bind(&MotorControlNode::CAN_callback, this, _1));
  }

private:
  // Continuously send CAN messages to our motor controllers so they don't timeout
  void timer_callback() {
    for (uint32_t id = 1; id <= NUMBER_OF_MOTORS; id++) {
      // If the motor controller has previously received a command, continue to send the most recent command
      if (current_msg.count(id) == 1) {
        send_can(std::get<0>(current_msg[id]), std::get<1>(current_msg[id]));
      }
    }
  }

  // Listen for CAN status frames sent by our VESC motor controllers
  void CAN_callback(const can_msgs::msg::Frame::SharedPtr can_msg) {
    uint32_t id = can_msg->id & 0xFF;

    float RPM = static_cast<float>((can_msg->data[0] << 24) + (can_msg->data[1] << 16) + (can_msg->data[2] << 8) + can_msg->data[3]);
    float dutyCycleNow = static_cast<float>(((can_msg->data[6] << 8) + can_msg->data[7]) / 10);
    float current = -1;  // TODO: calculate the current draw of the motor from the CAN data
    float position = -1; // TODO: calculate the position of the motor from the CAN data

    // Store the most recent motor data in our hashmap
    this->can_data[id] = {dutyCycleNow, RPM, current, position, std::chrono::steady_clock::now()};

    // Uncomment the lines below to print the received data to the terminal
    // RCLCPP_INFO(this->get_logger(), "Received status frame from CAN ID %u with the following data:", id);
    // RCLCPP_INFO(this->get_logger(), "RPM: %.2f Duty Cycle: %.2f%% Current: %.2f A Position: %.2f", RPM, dutyCycleNow,
    // current, position);
  }

  // Initialize a hashmap to store the most recent motor data for each CAN ID
  std::map<uint32_t, MotorData> can_data;
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
    } else if (request->type == "current") {
      vesc_set_current(request->can_id, request->value);
      response->success = 1; // indicates success
    } else {
      RCLCPP_ERROR(this->get_logger(), "Unknown motor SET command type: '%s'", request->type.c_str());
      response->success = 1; // indicates failure
    }
  }

  // Callback method for the MotorCommandGet service
  void get_callback(const std::shared_ptr<rovr_interfaces::srv::MotorCommandGet::Request> request,
                    std::shared_ptr<rovr_interfaces::srv::MotorCommandGet::Response> response) {
    if (request->type == "velocity") {
      response->result = vesc_get_velocity(request->can_id);
      response->success = response->result == -1 ? 0 : 1;
    } else if (request->type == "duty_cycle") {
      response->result = vesc_get_duty_cycle(request->can_id);
      response->success = response->success = response->result == -1 ? 0 : 1;
    } else if (request->type == "position") {
      response->result = vesc_get_position(request->can_id);
      response->success = response->success = response->result == -1 ? 0 : 1;
    } else if (request->type == "current") {
      response->result = vesc_get_current(request->can_id);
      response->success = response->success = response->result == -1 ? 0 : 1;
    } else {
      RCLCPP_ERROR(this->get_logger(), "Unknown motor GET command type: '%s'", request->type.c_str());
      response->success = 1; // indicates failure
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
