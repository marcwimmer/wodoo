#!/bin/bash
set -e
git clone https://github.com/openvenues/libpostal /root/libpostal
cd /root/libpostal
./bootstrap.sh
./configure
make -j4
make install
ldconfig
pip3 install nose
pip3 install postal