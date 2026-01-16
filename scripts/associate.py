#!/usr/bin/env python3
"""
Associate RGB and depth images from TUM RGB-D dataset.

Based on TUM tools: https://cvg.cit.tum.de/data/datasets/rgbd-dataset/tools
"""

import argparse
import sys


def read_file_list(filename):
    """Read a list of data from file with timestamp."""
    file_list = []
    with open(filename) as f:
        for line in f:
            if line.startswith("#"):
                continue
            parts = line.strip().split()
            if len(parts) >= 2:
                timestamp = float(parts[0])
                data = " ".join(parts[1:])
                file_list.append((timestamp, data))
    return file_list


def associate(first_list, second_list, offset=0.0, max_difference=0.02):
    """
    Associate two lists based on timestamps.
    
    Args:
        first_list: [(timestamp, data), ...]
        second_list: [(timestamp, data), ...]
        offset: time offset added to second_list timestamps
        max_difference: search radius for matching
    
    Returns:
        List of matches: [(timestamp1, data1, timestamp2, data2), ...]
    """
    potential_matches = [(abs(a[0] - (b[0] + offset)), a, b)
                        for a in first_list
                        for b in second_list
                        if abs(a[0] - (b[0] + offset)) < max_difference]
    
    potential_matches.sort()
    matches = []
    first_used = set()
    second_used = set()
    
    for diff, first, second in potential_matches:
        if first in first_used or second in second_used:
            continue
        first_used.add(first)
        second_used.add(second)
        matches.append((first[0], first[1], second[0], second[1]))
    
    matches.sort()
    return matches


def main():
    parser = argparse.ArgumentParser(
        description="Associate RGB and depth images from TUM RGB-D dataset."
    )
    parser.add_argument("first_file", help="First txt file (e.g., rgb.txt)")
    parser.add_argument("second_file", help="Second txt file (e.g., depth.txt)")
    parser.add_argument(
        "--offset",
        type=float,
        default=0.0,
        help="Time offset added to second file timestamps (default: 0.0)"
    )
    parser.add_argument(
        "--max_difference",
        type=float,
        default=0.02,
        help="Maximum time difference for matching (default: 0.02)"
    )
    
    args = parser.parse_args()
    
    first_list = read_file_list(args.first_file)
    second_list = read_file_list(args.second_file)
    
    matches = associate(first_list, second_list, args.offset, args.max_difference)
    
    for match in matches:
        print(f"{match[0]} {match[1]} {match[2]} {match[3]}")
    
    if len(matches) == 0:
        print("# No matches found!", file=sys.stderr)


if __name__ == "__main__":
    main()
