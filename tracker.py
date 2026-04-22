import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from tf2_ros import TransformException, Buffer, TransformListener
from nav_msgs.msg import Path
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import Empty, String
import math

class Node3Tracker(Node):
    def __init__(self):
        super().__init__('path_tracker_node')
        
        # initialising the tf2 buffer and listener for capturing the robot location
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        
        # creating publishers for the exploration and return paths as required
        self.explore_pub = self.create_publisher(Path, '/path_explore', 10)
        self.return_pub = self.create_publisher(Path, '/path_return', 10)
        self.status_pub = self.create_publisher(String, '/snc_status', 10)
        
        # initialising the path objects for visualising the trails in rviz
        self.explore_path = Path()
        self.explore_path.header.frame_id = 'map'
        self.return_path = Path()
        self.return_path.header.frame_id = 'map'

        # setting up storage for retracing the path waypoints in reverse
        self.history = [] 
        self.last_saved_pose = None
        self.is_returning = False
        self.log_counter = 0

        # initialising the action client for navigating through the saved waypoints
        self._nav_client = ActionClient(self, NavigateToPose, '/navigate_to_pose')

        # subscribing to the trigger topic to start the autonomous return sequence
        self.trigger_sub = self.create_subscription(Empty, '/trigger_home', self.go_home_callback, 10)

        # subscribing to the trigger teleop contingency
        self.teleop_sub = self.create_subscription(Empty, '/trigger_teleop', self.teleop_contingency_callback, 10)

        # starting a timer to check the position and manage point density every half second
        self.timer = self.create_timer(0.5, self.track_position)
        self.publish_status('node 3 active. recording breadcrumbs for path retracing.')

    def publish_status(self, info_string):
        # broadcasting the current status string to the marking script
        msg = String()
        msg.data = info_string
        self.status_pub.publish(msg)
        self.get_logger().info(info_string)

    def get_distance(self, p1, p2):
        # calculating the straight line distance between two coordinates
        return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

    def track_position(self):
        try:
            # looking up the latest transform between the map and the robot base
            now = rclpy.time.Time()
            t = self.tf_buffer.lookup_transform('map', 'base_link', now)
            curr_x = t.transform.translation.x
            curr_y = t.transform.translation.y

            # packaging the location into a pose message for path publishing
            pose = PoseStamped()
            pose.header.frame_id = 'map'
            pose.header.stamp = self.get_clock().now().to_msg()
            pose.pose.position.x = curr_x
            pose.pose.position.y = curr_y

            if not self.is_returning:
                # checking if the robot has moved far enough to save a new waypoint (0.3m)
                if self.last_saved_pose is None or self.get_distance((curr_x, curr_y), self.last_saved_pose) > 0.3:
                    self.history.append((curr_x, curr_y))
                    self.last_saved_pose = (curr_x, curr_y)
                    self.explore_path.poses.append(pose)
                    self.explore_pub.publish(self.explore_path)
                    
                    # throttling logs to prevent network flooding
                    self.log_counter += 1
                    if self.log_counter % 10 == 0:
                        self.get_logger().info(f'tracking at: x={curr_x:.2f}, y={curr_y:.2f}')
            else:
                # updating and publishing the return path trail while heading home
                self.return_path.poses.append(pose)
                self.return_pub.publish(self.return_path)
                
                # checking if the robot is close enough to the origin to stop
                dist_to_origin = math.sqrt(curr_x**2 + curr_y**2)
                if dist_to_origin < 0.15:
                    self.get_logger().info(f'arrived back home. final accuracy: {dist_to_origin:.2f}m')
                    self.is_returning = False

        except TransformException:
            # skipping tracking if the transforms are not yet available
            pass

    def teleop_contingency_callback(self, msg):
        self.publish_status("teleop contingency triggered.")

    def go_home_callback(self, msg):
        if self.is_returning: return
        
        # acknowledging the trigger and reversing the history for retracing
        self.get_logger().warn('return signal received. retracing the path in reverse.')
        self.is_returning = True
        
        # creating a queue of waypoints to follow the explored path back to the start
        self.retracing_queue = self.history[::-1]
        # adding the exact origin as the final goal point
        self.retracing_queue.append((0.0, 0.0))
        
        self.send_next_waypoint()

    def send_next_waypoint(self):
        # checking if all breadcrumbs in the queue have been visited
        if not self.retracing_queue:
            self.publish_status('retracing sequence finished.')
            return

        # popping the next waypoint from the queue and sending it to the navigator
        target = self.retracing_queue.pop(0)
        self.get_logger().info(f'navigating to waypoint: {target}')

        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = 'map'
        goal.pose.pose.position.x = target[0]
        goal.pose.pose.position.y = target[1]

        # applying hill fix by relaxing orientation for intermediate waypoints
        if len(self.retracing_queue) > 0:
            goal.pose.pose.orientation.w = 0.0
        else:
        # we wnat the robot facing forward at the final stop
            goal.pose.pose.orientation.w = 1.0 
        
        # waiting for the navigation server and sending the goal asynchronously
        self._nav_client.wait_for_server()
        self._nav_client.send_goal_async(goal).add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        # handling the server response to ensure the goal was accepted
        goal_handle = future.result()
        if not goal_handle.accepted: return
        goal_handle.get_result_async().add_done_callback(lambda _: self.send_next_waypoint())

def main(args=None):
    # initialising the ros 2 system and spinning the tracker node
    rclpy.init(args=args)
    node = Node3Tracker()
    rclpy.spin(node)
    rclpy.shutdown()
