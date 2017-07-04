#!/bin/python
"""
Copyright 2017, Bal Chettri

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in 
the Software without restriction, including without limitation the rights to 
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so, 
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

depends.py - Dependency graph generator for C/C++.

usage: depends.py [options] [input-dir]
"""

##############################################################################
import sys
import os
import re
import getopt

# File types to scan directly.
CPP_FILE_TYPES = [ '.c', '.cpp', '.cxx' ]

# Regular expressions to match include directives.
CPP_INC_PATTERN = re.compile( '# *include *([<"])([^>"]*)([>"])' )

# System header files include paths.
SYS_INC_PATHS = []

# List of file types to ignore
IGNORE_LIST = [ '.git' ]

# Constants.
MAX_DEPTH = 1000
INDENT = 2

# Globals.
graph = None
verbose = False
output_format = 'txt'
depth = 0
max_depth_reached = 0

# Array of include search paths if your code uses #include <filename> style
# file inclusion.
inc_search_paths = []

##############################################################################

def log(s):
    if verbose == True:
        print(s)

def error(s):
    print('ERROR: ' + s)

def usage():
    print(
    'usage: depends [options]\r\n\r\n' +
    'Options are:\r\n' +
    '    -h             print this help and exit\r\n' +
    '    -i             specify input directory\r\n' +
    '    -I             add include search path\r\n' +
    '    -f             specify format of output file. Supported are txt, html\r\n' +
    '    -o             specify output file name to create (default is stdout)\r\n' +
    '    -v             enable verbose mode\r\n' +
    '    --node         print depedencies of node\r\n' +
    '    --top-level    print top level files only\r\n' +
    '    --leaf-level   print leaf level files only\r\n\r\n' +

    'If "input-dir" is not specified, depends will scan current directory.\r\n'
    )

"""
Node class.  Defines an object representing a node in the dependency graph.
"""
class Node(object):
    def __init__(self, file):
        self.file = file
        self.children = []
        self.has_parent = False
        self.visited = False
        self.missing = False
        return

    def get_file(self):
        return self.file

    def add_child(self, node):
        for node_ in self.children:
            if node_ == node:
                return
        self.children.append(node)
        node.has_parent = True

    def has_child(self, node):
        if node in self.children:
            return True
        return False

    def has_children(self):
        return len(self.children) > 0

    def get_children(self):
        return self.children

    def print_node(self):
        s = self.file

        # Remove "./" prefix in path, if any.
        if s.startswith('./') or s.startswith('.\\'):
            s = s[2:]

        # Indent by current depth.
        for i in range(0, depth * INDENT):
            s = ' ' + s
        if self.visited:
            s = s + ' *'
        if self.missing:
            s = s + ' ?'

        print(s)

    def print_tree(self):
        global depth, max_depth_reached
        
        if depth > MAX_DEPTH:
            print('MAX depth reached ' + str(depth))
            return False

        self.print_node()

        if self.visited:
            return
        self.visited = True

        depth = depth + 1
        max_depth_reached = depth
        
        for child in self.children:
            if not child.print_tree():
                return False
        depth = depth - 1

        return True

"""
Graph class.  Defines an object representing a module dependency graph.
"""
class Graph(object):
    def __init__(self):
        self.nodes = {}

    def get_node(self, file):
        if not file in self.nodes:
            self.nodes[file] = Node(file)
        return self.nodes[file]

    def get_nodes(self):
        return self.nodes

    def print_graph(self):
        global indent
        indent = 0
        self.clear_visisted()
        for file in self.nodes:
            node = self.nodes[file]
            if not node.has_parent:
                node.print_tree()

    def print_leaf_nodes(self):
        self.clear_visisted()
        for file in self.nodes:
            node = self.nodes[file]
            if node.has_children() == False:
                node.print_node()

    def print_top_level_nodes(self):        
        self.clear_visisted()        
        for file in self.nodes:
            node = self.nodes[file]
            if not node.has_parent:
                node.print_node()

    def print_node(self, name):
        self.clear_visisted()
        if name in self.nodes:
            node = self.nodes[name]
            node.print_tree()
        
    def clear_visisted(self):
        global depth, max_depth_reached
        depth = max_depth_reached = 0
        for file in self.nodes:
            node = self.nodes[file]
            node.visited = False

def resolve_path(dir_path, inc_path, relative):
    if relative:
        full_path = os.path.join(dir_path, inc_path)
        if os.path.isfile(full_path):
            return full_path    
    for search_path in inc_search_paths:
        full_path = os.path.join(search_path, inc_path)
        if os.path.isfile(full_path):
            return full_path
    return inc_path

def is_sys_header_path(dir_path):
    for path in SYS_INC_PATHS:
        if dir_path.startswith(path):
            return True
    return False
    
def cpp_scan_file(path):
    global graph

    # Create or get a node for this file.
    this_node = graph.get_node(path)
    if this_node.visited:
        log('Ignoring scanned file: ' + path)
        return
    this_node.visited = True

    if not os.path.isfile(path):
        this_node.missing = True
        error(path + ' is missing. Did you add include search paths?')
        return

    dir_path,filename = os.path.split(path)
    log('Scanning ' + path)

    # Build list of files this file depends on.
    includes = []
    f = open(path, "rt")
    line_num = 1
    for line in f:
        match = CPP_INC_PATTERN.match(line)
        if match is not None:
            first = match.groups(1)[0]
            last = match.groups(1)[2]
            if ((first == '<' and last == '"') or (first == '"' and last == '>')):
                error(path + ': Invalid #include directive at line ' + str(line_num) + ': ' + line.strip())
            else:
                isrelative = first == '"'
                inc_path = match.groups(1)[1]
                inc_path = resolve_path(dir_path, inc_path, isrelative)
                base_dir, inc_file = os.path.split(inc_path)
                if is_sys_header_path(base_dir):
                    log('Ignoring system header file: ' + inc_path)
                else:
                    log('  ' + path + ' >> ' + inc_path)
                    includes.append(inc_path)
        line_num = line_num + 1

    f.close()

    # Add this node to its parent node and scan files recursively.
    for inc_path in includes:
        include_node = graph.get_node(inc_path)
        include_node.add_child(this_node)
        cpp_scan_file(inc_path)

def cpp_scan_dir(dirpath):
    log('Scanning dir ' + dirpath)

    files = os.listdir(dirpath)
    for file in files:
        path = os.path.join(dirpath, file)
        if os.path.isfile(path):
            name,ext = os.path.splitext('x' + file)
            if ext in IGNORE_LIST:
                log('Ignoring ' + file)
            elif ext in CPP_FILE_TYPES:
                cpp_scan_file(path)            

    # Recursively scan sub directories.
    for file in files:
        path = os.path.join(dirpath, file)
        if os.path.isdir(path):
            name,ext = os.path.splitext('x' + file)
            if ext in IGNORE_LIST:
                log('Ignoring ' + file)
            else:
                cpp_scan_dir(path)            

def main(argv):
    global verbose, inc_search_paths, output_format, graph, max_depth_reached

    input_dir = '.'
    only_top_level = False
    only_leaf_level = False
    node = None
    
    try:
        opts, args = getopt.getopt(argv, "I:f:i:o:v", ["top-level","leaf-level","node="])
    except getopt.GetoptError:
        usage()
        sys.exit(-1)

    for opt, arg in opts:
        # print(opt + ' > ' + arg)
        if opt == '-h':
            usage()
            sys.exit(0)
        elif opt == '-I':
            inc_search_paths.append(arg)
        elif opt == '-i':
            input_dir = arg
        elif opt == '-f':
            output_format = arg
        elif opt == '-v':
            verbose = True
        elif opt == '--node':
            node = arg
        elif opt == '--top-level':
            only_top_level = True
        elif opt == '--only_leaf_level':
            only_leaf_level = True
        else:
            print('Invalid option "' + opt + '"')
            usage()
            sys.exit(1)

    if only_top_level and only_leaf_level:
        error("Both --top-level and --leaf-level flags present.")
        usage()
        sys.exit(1)

    # Build paths for system headers.
    if sys.platform in ['cygwin', 'linux2', 'darwin']:
        SYS_INC_PATHS.append('/usr/include')
        
    # Add windows headers path to system includes.
    # TODO: Better way to do this instead of guessing.
    if os.name == 'nt' and sys.platform == 'win32':
        for path in [
            'C:\\Program Files\\Microsoft Visual Studio 9.0\\VC\\include',
            'C:\\Program Files\\Microsoft Visual Studio 10.0\\VC\\include',
            'C:\\Program Files\\Microsoft SDKs\\Windows\\v7.0A\\Include'
            ]:
            if os.path.isdir(path):
                SYS_INC_PATHS.append(path)
    # Add cygwin C/C++ library header paths to system includes.
    if os.name == 'posix' and sys.platform == 'cygwin':
        for path in [
            '/lib/gcc/i686-pc-cygwin/5.4.0/include',
            '/lib/gcc/i686-pc-cygwin/5.4.0/include/c++'
            ]:
            if os.path.isdir(path):
                SYS_INC_PATHS.append(path)

    # Add all system paths to include search path array.
    for path in SYS_INC_PATHS:
        inc_search_paths.append(path)

    # Do some logging
    log('os.name = ' + os.name)
    log('sys.platform = ' + sys.platform)
    log('system includes:')
    for path in SYS_INC_PATHS:
        log('  ' + path)

    # Create a graph object and beginning scanning input dir.
    graph = Graph()
    cpp_scan_dir(input_dir)
    log('Scan complete.')

    # Print results.
    
    # If node is specified only print its dependencies    
    if node != None:
        print(node + ' dependencies:')
        if node in graph.get_nodes():
            graph.print_node(node)
        else:
            print('[none]')
    else:
        if not only_top_level and not only_leaf_level:
            log('')
            print('Full dependency graph:')
            graph.print_graph();

        if only_top_level:
            print('')
            print('Top level files:')
            graph.print_top_level_nodes()

        if only_leaf_level:
            print('')
            print('Leaf level files:')
            graph.print_leaf_nodes()

if __name__ == '__main__':
    main(sys.argv[1:])
