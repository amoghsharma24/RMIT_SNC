#!/usr/bin/env python3

import math
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.time import Time
from rclpy.duration import Duration
from nav2_msgs.action import NavigateToPose
from action_msgs.msg import GoalStatus
from tf2_ros import TransformException, Buffer, TransformListener
from nav_msgs.msg import Path
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import Empty, String

class PathTrackingNode(Node):
    def __init__(self):
        super().__init__("snc_path_tracking_node")

        # --- Parameters ---
        self.map_frame = "map"
        self.robot_frame = "base_link"
        self.min_spacing_m = 0.20  
        self.goal_timeout_sec = 12.0

        # --- State ---
        self.is_returning = False
        self.is_complete = False
        self.history = []         
        self.return_history = []  
        self.retracing_queue = []
        self.goal_active = False
        self.current_goal_handle = None
        self.goal_sent_time = None
        
        self.mission_start_time = self.get_clock().now()
        self.auto_return_triggered = False

        # --- Publishers ---
        self.explore_pub = self.create_publisher(Path, '/path_explore', 10)
        self.return_pub  = self.create_publisher(Path, '/path_return', 10)
        self.status_pub  = self.create_publisher(String, '/snc_status', 10)

        # --- Subscribers ---
        self.create_subscription(Empty, '/trigger_home', self.go_home_callback, 10)
        self.create_subscription(Empty, '/trigger_teleop', self.teleop_callback, 10)

        # --- TF & Actions ---
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.nav_client = ActionClient(self, NavigateToPose, "/navigate_to_pose")

        # --- Timers ---
        self.create_timer(0.5, self.track_position)
        self.create_timer(1.0, self.mission_watchdog) 

        self.get_logger().info("Node 3: Final Challenge Version Active.")
        self.publish_status("STATUS: Exploration Active. Recording path.")

    def publish_status(self, text):
        msg = String()
        msg.data = text
        self.status_pub.publish(msg)
        self.get_logger().info(text)

    def teleop_callback(self, _msg):
        self.publish_status("CONTINGENCY: Manual Teleop Active.")

    def track_position(self):
        if self.is_complete: return
        try:
            t = self.tf_buffer.lookup_transform(self.map_frame, self.robot_frame, Time(), timeout=Duration(seconds=0.2))
            curr_x, curr_y = t.transform.translation.x, t.transform.translation.y
            curr_quat = t.transform.rotation

            if not self.is_returning:
                dist = math.hypot(curr_x - self.history[-1][0], curr_y - self.history[-1][1]) if self.history else 999
                if dist > self.min_spacing_m:
                    self.history.append((curr_x, curr_y, curr_quat))
                    self.publish_path(self.history, self.explore_pub)
            else:
                self.return_history.append((curr_x, curr_y, curr_quat))
                self.publish_path(self.return_history, self.return_pub)

        except TransformException:
            pass

    def mission_watchdog(self):
        if self.goal_active and self.goal_sent_time:
            elapsed = (self.get_clock().now() - self.goal_sent_time).nanoseconds / 1e9
            if elapsed > self.goal_timeout_sec:
                self.get_logger().warn(f"Watchdog: Waypoint stalled ({elapsed:.1f}s). Skipping.")
                if self.current_goal_handle: self.current_goal_handle.cancel_goal_async()
                self.advance_queue()

        mission_elapsed = (self.get_clock().now() - self.mission_start_time).nanoseconds / 1e9
        if mission_elapsed > 240.0 and not self.is_returning and not self.auto_return_triggered:
            self.auto_return_triggered = True
            self.get_logger().error("MISSION CLOCK: 4 Minutes elapsed. Auto-returning home.")
            self.go_home_callback(None)

    def go_home_callback(self, _msg):
        if self.is_returning or not self.history: return
        self.is_returning = True
        self.publish_status(f"STATUS: Returning Home. Retracing {len(self.history)} crumbs.")
        
        # Section 3.9.2: LIFO Retracing Logic
        self.retracing_queue = list(reversed(self.history))
        # Ensure the final target is the exact starting pose for 100% accuracy
        self.retracing_queue.append(self.history[0]) 
        self.send_next_waypoint()

    def send_next_waypoint(self):
        if not self.retracing_queue:
            self.is_complete = True
            self.publish_status("STATUS: CHALLENGE COMPLETE. Arrived Home. Stopping.")
            return

        if not self.nav_client.wait_for_server(timeout_sec=1.0):
            return

        target = self.retracing_queue.pop(0)
        crumb_num = len(self.history) - len(self.retracing_queue)
        self.publish_status(f"STATUS: Retracing Crumb {crumb_num}/{len(self.history)}")

        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = self.map_frame
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x = target[0]
        goal.pose.pose.position.y = target[1]
        
        # Final point uses original orientation, others use identity
        goal.pose.pose.orientation = target[2] if not self.retracing_queue else self.get_identity_quat()

        self.goal_active = True
        self.goal_sent_time = self.get_clock().now()
        self.nav_client.send_goal_async(goal).add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        handle = future.result()
        if not handle.accepted:
            self.advance_queue()
            return
        self.current_goal_handle = handle
        handle.get_result_async().add_done_callback(lambda _: self.advance_queue())

    def advance_queue(self):
        self.goal_active = False
        self.current_goal_handle = None
        self.goal_sent_time = None
        self.send_next_waypoint()

    def get_identity_quat(self):
        from geometry_msgs.msg import Quaternion
        return Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)

    def publish_path(self, coords, publisher):
        msg = Path()
        msg.header.frame_id = self.map_frame
        msg.header.stamp = self.get_clock().now().to_msg()
        for x, y, q in coords:
            ps = PoseStamped()
            ps.header.frame_id = self.map_frame
            ps.pose.position.x, ps.pose.position.y = x, y
            ps.pose.orientation = q
            msg.poses.append(ps)
        publisher.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = PathTrackingNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()
