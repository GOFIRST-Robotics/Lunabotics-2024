# This is an implementation of the full updated point method for point processing: https://www.notion.so/Ground-Algorithm-ab538c4bde484908abdde515edaa24a0?pvs=4
# Original Author: Eric Patton (with code from others) in Spring 2023
# Maintainer: Eric Patton
# Last Updated: April 2023
# FIXME: Not currently functional

import struct
import math
import sys

import rclpy
from rclpy.node import Node
import sensor_msgs.msg as sensor_msgs
from sensor_msgs.msg import PointCloud2, PointField

import numpy as np
import open3d as o3d

# define constants
CELL_SIZE = 40  # size of each cell in mm
CELL_POINTS_CUTOFF = 2  # minimum number of points required for a cell to be considered statistically valuable\
GRAD_THRESH = 1  # gradient threshold to mark a cell as dangerous, always positive, 1 = 45 degrees


class Cell:
    def __init__(self):
        self.points = []
        self.danger = 0  # 0 is no danger, 1 is lacking info, 2 is high slope
        self.avg = None


class PointcloudSubscriber(Node):
    def __init__(self):  # this function just initializes the node
        super().__init__("pointcloud_subscriber")
        #
        # debug to see if starting correctly
        self.get_logger().info("Node trying to start")
        #
        # This is for visualization of the received point cloud.
        self.vis = o3d.visualization.Visualizer()
        self.vis.create_window()
        self.o3d_pcd = o3d.geometry.PointCloud()
        #
        self.subscription = self.create_subscription(
            sensor_msgs.PointCloud2,
            "points",  # this is the topic which the node is subscribed to
            self.listener_callback,
            10,
        )
        self.subscription  # prevent unused variable warning
        #
        self.get_logger().info("Node started successfully")  # isn't running

    #

    # this function is called whenever the node detects an update to the pointcloud
    def listener_callback(self, msg):
        # receive the list of all points in the point cloud
        all_points = np.array(list(read_points(msg)))
        # log the shape of the list
        self.get_logger().info(f"received message: {all_points.shape}")
        #
        sorted_points = self.points_to_cells(all_points)  # sort all points into cells
        #
        # flag cells which are dangerous
        sorted_points = self.flag_cells(sorted_points)
        #
        # add here a publisher to export information to pathfinder
        #
        # for row in sorted_points: # print danger level of all cells, can be used for debugging
        #    self.get_logger().info(f'{np.array([cell.danger for cell in row])}')
        # self.get_logger().info(f'new line')
        #
        # The rest here is for visualization. (modified from https://github.com/SebastianGrans/ROS2-Point-Cloud-Demo/blob/master/pcd_demo/pcd_subscriber/pcd_subscriber_node.py)
        self.vis.remove_geometry(self.o3d_pcd)
        self.o3d_pcd = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(all_points))
        #
        self.color_points(self.o3d_pcd, sorted_points)
        #
        self.vis.add_geometry(self.o3d_pcd)
        #
        self.vis.poll_events()
        self.vis.update_renderer()

    #

    def points_to_cells(self, all_points):
        """convert list of points from pointcloud input into 2d array of lists of points"""
        #
        # initialize variables for minimum and maximum in every axis
        self.minx = maxx = all_points[0][0]
        self.miny = maxy = all_points[0][1]
        minz = maxz = all_points[0][2]
        #
        for i in range(len(all_points)):  # loop through all points to find min and max
            if all_points[i][0] > maxx:
                maxx = all_points[i][0]
            elif all_points[i][0] < self.minx:
                self.minx = all_points[i][0]
            #
            if all_points[i][1] > maxy:
                maxy = all_points[i][1]
            elif all_points[i][1] < self.miny:
                self.miny = all_points[i][1]
            #
            if all_points[i][2] > maxz:
                maxz = all_points[i][2]
            elif all_points[i][2] < minz:
                minz = all_points[i][2]
        #
        # calculate number of cells in x and y axis based on cell size and min/maxes
        cell_num_x = int((maxx - self.minx) / CELL_SIZE) + 1
        cell_num_y = int((maxy - self.miny) / CELL_SIZE) + 1
        # cell_num_z = (maxz - minz) / CELL_SIZE
        #
        cells = []
        for _ in range(cell_num_x):  # fill every cell with a cell object in a new 2d array
            new_list = []
            for _ in range(cell_num_y):
                new_list.append(Cell())
            cells.append(new_list)
        # cells = np.empty((cell_num_x, cell_num_y), dtype=object) # create cells array
        # for cell_row in cells:
        #    for cell in cell_row:
        #        cell = Cell()
        #
        for point in all_points:  # organize all points into cells
            # use cell size and minimum to calc cell index to insert into
            x_index = int(point[0] / CELL_SIZE - (self.minx / CELL_SIZE))
            y_index = int(point[1] / CELL_SIZE - (self.miny / CELL_SIZE))
            #
            # TODO: thinks cell retrived is None
            cells[x_index][y_index].points.append(point)
        #
        return cells

    #

    def flag_cells(self, sorted_points):
        """Take cells of points and find the dangerous ones"""
        # the follow could be improved by screening out outliers in the cell or marking as dangeorus cells with high variance
        for i, cell_row in enumerate(sorted_points):
            # self.get_logger().info(f'{len(cell_row)}')
            for j, cell in enumerate(cell_row):
                # self.get_logger().info(f'cell at {i}, {j}, len {len(cell.points)}')
                # determine if the cell has too few points to be valuable
                if len(cell.points) < CELL_POINTS_CUTOFF:
                    # self.get_logger().info(f'setting danger to 1')
                    cell.danger = 1
                    # self.get_logger().info(f'cell danger at {cell.danger}')
                else:  # cell has enough points, now check gradients to neighboring cells
                    #
                    # set average z value of the cell
                    cell.avg = sum(v[2] for v in cell.points) / len(cell.points)
                    #
                    if j == 0:  # only check gradient left
                        if i != 0:  # cell isn't first to be checked
                            if sorted_points[i - 1][0].danger == 1:
                                cell.danger = 2
                                continue
                            x_grad = self.get_gradient(cell.avg, sorted_points[i - 1][0].avg)
                            if x_grad > GRAD_THRESH:
                                cell.danger = 2
                    else:
                        if sorted_points[i][j - 1].danger == 1:
                            cell.danger = 2
                            continue
                        y_grad = self.get_gradient(cell.avg, sorted_points[i][j - 1].avg)  # check top gradient
                        if y_grad > GRAD_THRESH:
                            cell.danger = 2
                            continue
                        if i != 0:  # check left gradient also
                            if sorted_points[i - 1][0].danger == 1:
                                cell.danger = 2
                                continue
                            x_grad = self.get_gradient(cell.avg, sorted_points[i - 1][0].avg)
                            if x_grad > GRAD_THRESH:
                                cell.danger = 2
        #
        return sorted_points

    #

    def get_gradient(self, avg_a, avg_b):
        """get z gradient between two cells averages"""
        return abs(
            (avg_b - avg_a) / CELL_SIZE
        )  # every cell average is separated by the cell size (there are no diagonals)

    #

    def color_points(self, cloud, cells):
        """color all points according to their danger level"""
        cloud.paint_uniform_color([0, 1, 0])  # 0-255 rgb scale
        #
        colors = cloud.colors
        for i, point_color in enumerate(colors):
            point = cloud.points[i]  # get point coordinates
            #
            x_index = int(point[0] / CELL_SIZE - (self.minx / CELL_SIZE))
            y_index = int(point[1] / CELL_SIZE - (self.miny / CELL_SIZE))
            #
            # self.get_logger().info(f'index: {x_index}, {y_index} out of {len(cells)}, {len(cells[0])}')
            #
            cell = cells[x_index][y_index]
            if cell.danger == 1:
                pass  # 0-1 rgb scale
            elif cell.danger == 2:
                pass
        # no return value because object is directly edited


# The code below is "ported" from
# https://github.com/ros/common_msgs/tree/noetic-devel/sensor_msgs/src/sensor_msgs

_DATATYPES = {}
_DATATYPES[PointField.INT8] = ("b", 1)
_DATATYPES[PointField.UINT8] = ("B", 1)
_DATATYPES[PointField.INT16] = ("h", 2)
_DATATYPES[PointField.UINT16] = ("H", 2)
_DATATYPES[PointField.INT32] = ("i", 4)
_DATATYPES[PointField.UINT32] = ("I", 4)
_DATATYPES[PointField.FLOAT32] = ("f", 4)
_DATATYPES[PointField.FLOAT64] = ("d", 8)


def read_points(cloud, field_names=None, skip_nans=False, uvs=[]):
    """
    Read points from a L{sensor_msgs.PointCloud2} message.
    @param cloud: The point cloud to read from.
    @type  cloud: L{sensor_msgs.PointCloud2}
    @param field_names: The names of fields to read. If None, read all fields. [default: None]
    @type  field_names: iterable
    @param skip_nans: If True, then don't return any point with a NaN value.
    @type  skip_nans: bool [default: False]
    @param uvs: If specified, then only return the points at the given coordinates. [default: empty list]
    @type  uvs: iterable
    @return: Generator which yields a list of values for each point.
    @rtype:  generator
    """
    assert isinstance(cloud, PointCloud2), "cloud is not a sensor_msgs.msg.PointCloud2"
    fmt = _get_struct_fmt(cloud.is_bigendian, cloud.fields, field_names)
    width, height, point_step, row_step, data, isnan = (
        cloud.width,
        cloud.height,
        cloud.point_step,
        cloud.row_step,
        cloud.data,
        math.isnan,
    )
    unpack_from = struct.Struct(fmt).unpack_from

    if skip_nans:
        if uvs:
            for u, v in uvs:
                p = unpack_from(data, (row_step * v) + (point_step * u))
                has_nan = False
                for pv in p:
                    if isnan(pv):
                        has_nan = True
                        break
                if not has_nan:
                    yield p
        else:
            for v in range(height):
                offset = row_step * v
                for u in range(width):
                    p = unpack_from(data, offset)
                    has_nan = False
                    for pv in p:
                        if isnan(pv):
                            has_nan = True
                            break
                    if not has_nan:
                        yield p
                    offset += point_step
    else:
        if uvs:
            for u, v in uvs:
                yield unpack_from(data, (row_step * v) + (point_step * u))
        else:
            for v in range(height):
                offset = row_step * v
                for u in range(width):
                    yield unpack_from(data, offset)
                    offset += point_step


def _get_struct_fmt(is_bigendian, fields, field_names=None):
    fmt = ">" if is_bigendian else "<"

    offset = 0
    for field in (f for f in sorted(fields, key=lambda f: f.offset) if field_names is None or f.name in field_names):
        if offset < field.offset:
            fmt += "x" * (field.offset - offset)
            offset = field.offset
        if field.datatype not in _DATATYPES:
            print(
                "Skipping unknown PointField datatype [%d]" % field.datatype,
                file=sys.stderr,
            )
        else:
            datatype_fmt, datatype_length = _DATATYPES[field.datatype]
            fmt += field.count * datatype_fmt
            offset += field.count * datatype_length

    return fmt


def main(args=None):
    # Boilerplate code.
    rclpy.init(args=args)
    points_node = PointcloudSubscriber()
    rclpy.spin(points_node)

    # Destroy the node explicitly
    # (optional - otherwise it will be done automatically
    # when the garbage collector destroys the node object)
    points_node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
