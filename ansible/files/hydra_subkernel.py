#!/usr/bin/env python
# Copyright 2021 University of Chicago
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import argparse
import sys

from jupyter_client.kernelapp import KernelApp

argv = sys.argv[1:]
parser = argparse.ArgumentParser("hydra-subkernel")
parser.add_argument("--log-file", help="Output log to file")
args, argv = parser.parse_known_args(argv)

if args.log_file:
    sys.stderr = sys.stdout = open(args.log_file, "w")

KernelApp.launch_instance(argv)
