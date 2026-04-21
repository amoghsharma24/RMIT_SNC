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
        
        # initialising the tf2 buffer and listener for capturing robot location
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        
        # creating publishers for paths and the required status topic
        self.explore_pub = self.create_publisher(Path, '/path_explore', 10)
        self.return_pub = self.create_publisher(Path, '/path_return', 10)
        self.status_pub = self.create_publisher(String, '/snc_status', 10)
        
        self.explore_path = Path()
        self.explore_path.header.frame_id = 'map'
        self.return_path = Path()
        self.return_path.header.frame_id = 'map'

        self.history = [] 
        self.last_saved_pose = None
        self.is_returning = False

        self._nav_client = ActionClient(self, NavigateToPose, '/navigate_to_pose')

        # subscribing to triggers for manual contingencies
        self.trigger_sub = self.create_subscription(Empty, '/trigger_home', self.go_home_callback, 10)
        self.teleop_sub = self.create_subscription(Empty, '/trigger_teleop', self.teleop_contingency_callback, 10)

        # starting timer for position tracking and point density management
        self.timer = self.create_timer(0.5, self.track_position)
        self.publish_status("status: initialised - waiting for start")

    def publish_status(self, info_string):
        # broadcasting current logic state to the marking script
        msg = String()
        msg.data = info_string
        self.status_pub.publish(msg)
        self.get_logger().info(info_string)

    def track_position(self):
        try:
            # looking up the latest transform between map and robot base link
            now = rclpy.time.Time()
            t = self.tf_buffer.lookup_transform('map', 'base_link', now)
            curr_x = t.transform.translation.x
            curr_y = t.transform.translation.y
            
            pose = PoseStamped()
            pose.header.frame_id = 'map'
            pose.header.stamp = self.get_clock().now().to_msg()
            pose.pose.position.x = curr_x
            pose.pose.position.y = curr_y

            if not self.is_returning:
                # recording breadcrumbs every 0.3 metres for high fidelity retracing
                if self.last_saved_pose is None or self.get_distance((curr_x, curr_y), self.last_saved_pose) > 0.3:
                    self.history.append((curr_x, curr_y))
                    self.last_saved_pose = (curr_x, curr_y)
                    self.explore_path.poses.append(pose)
                    self.explore_pub.publish(self.explore_path)
                    self.get_logger().info(f'tracking at: x={curr_x:.2f}, y={curr_y:.2f}')
            else:
                # updating the return path trail while heading back to the centre
                self.return_path.poses.append(pose)
                self.return_pub.publish(self.return_path)
                
                # checking arrival accuracy when nearing the origin
                dist_to_origin = math.sqrt(curr_x**2 + curr_y**2)
                if dist_to_origin < 0.15:
                    self.publish_status(f"status: arrived - accuracy {dist_to_origin:.2f}m")

        except TransformException:
            # ignoring transform errors while the system is booting up
            pass

    def get_distance(self, p1, p2):
        # calculating the straight line distance between waypoints
        return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

    def teleop_contingency_callback(self, msg):
        # acknowledging manual teleoperation contingency
        self.publish_status("status: contingency - manual teleop active")

    def go_home_callback(self, msg):
        if self.is_returning: return
        # switching to return mode and reversing the breadcrumb queue
        self.publish_status("status: returning - reversing path lifo")
        self.is_returning = True
        self.retracing_queue = self.history[::-1]
        self.retracing_queue.append((0.0, 0.0))
        self.send_next_waypoint()

    def send_next_waypoint(self):
        # checking if all saved breadcrumbs have been visited
        if not self.retracing_queue:
            self.publish_status("status: completed - sequence finished")
            return
            
        target = self.retracing_queue.pop(0)
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = 'map'
        goal.pose.pose.position.x = target[0]
        goal.pose.pose.position.y = target[1]
        
        # applying hill fix by relaxing orientation for intermediate waypoints
        if len(self.retracing_queue) > 0:
            goal.pose.pose.orientation.w = 0.0
        else:
            goal.pose.pose.orientation.w = 1.0 # facing forward at the final stop
            
        self._nav_client.wait_for_server()
        self._nav_client.send_goal_async(goal).add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        # verifying if the navigation goal was accepted by the server
        goal_handle = future.result()
        if not goal_handle.accepted: return
        goal_handle.get_result_async().add_done_callback(lambda _: self.send_next_waypoint())

def main(args=None):
    # initialising the ros 2 system and spinning the tracker node
    rclpy.init(args=args)
    node = Node3Tracker()
    rclpy.spin(node)
    rclpy.shutdown()