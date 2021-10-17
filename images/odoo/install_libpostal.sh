#!/bin/bash
set -e
pip3 install postal || exit 0
cd libpostal 
./bootstrap.sh
./configure
make
make install
ldconfig