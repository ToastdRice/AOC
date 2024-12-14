#!/usr/bin/python
"""Advent of Code Helper File"""

from sys import argv

#===============================================================================
def arg_check():
    """Checks for valid number of args"""
    if len(argv) != 2:
        print("Invalid # of arguments")
        exit(1)

#===============================================================================
def read_line(filename):
    """Extract lines from file"""
    with open(filename,encoding="utf8") as file:
        return file.read()[:-1]

#===============================================================================
def read_lines(filename):
    """Extract lines from file"""
    content = []
    with open(filename,encoding="utf8") as file:
        lines = file.read().split('\n')
    for line in lines:
        if line:
            content.append(line)
    return content

#===============================================================================
def read_sections(filename):
    """Extract lines from file"""
    content = []
    section = []
    with open(filename,encoding="utf8") as file:
        lines = file.read().split('\n')
    for line in lines:
        if line:
            section.append(line)
        else:
            content.append(section)
            section = []
    content.append(section)
    return content

#===============================================================================
def read_arg():
    return argv[1]

#===============================================================================
def read_args():
    return argv[1:]
