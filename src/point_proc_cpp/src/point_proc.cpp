#include <cstdio>
#include <functional>
#include <memory>
#include <string>

#include "point_proc_cpp/point_proc.h"
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/PointCloud2.hpp"
#include "std_msgs/msg/string.hpp"

class Costmap_Publisher : public rclcpp : Node {
public:
  Costmap_Publisher() : Node("costmap-gen"), count(0) {
    publisher_ = this->create_publisher<std_msgs::msg::String>("costmap", 10); // create costmap publisher
    subscription_ = this->create_subscription<sensor_msgs::msg::PointCloud2>(
        "/zed2i/zed_node/mapping/fused_cloud", 10,
        std::bind(&MinimalSubscriber::topic_callback, this, _1)); // create pointcloud subscriber
  }

private:
  void topic_callback(const std_msgs::msg::String &msg) const { // runs when subscriber gets new information from topic
    //
    auto message = std_msgs::msg::String(); // this is a placeholder message
    message.data = "Hello, world! " + std::to_string(count_++);
    RCLCPP_INFO(this->get_logger(), "Publishing: '%s'", message.data.c_str());
    // publisher_->publish(message);//this doesn't publish yet
  }
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr publisher_;
  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr subscription_;
}



int main(int argc, char ** argv){
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<Costmap_Publisher>());
  rclcpp::shutdown();
  return 0;
}
