#!/bin/bash

### install user; imap cannot login with root
useradd -m postmaster
echo "postmaster:postmaster" | chpasswd
