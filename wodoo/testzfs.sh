#!/bin/bash

set -ex

name1=/var/lib/docker/volumes/test1
name2=/var/lib/docker/volumes/test2
name3=/var/lib/docker/volumes/test3
pool=rpool/ROOT/ubuntu_srb0yj

if [[ -e $name1 ]]; then
	zfs destroy -R $pool$name1 || true
	rm -Rf $name1 || true
	if [[ -e $name1 ]]; then
		exit -1
	fi
fi
if [[ -e $name2 ]]; then
	zfs destroy -R $pool$name2 || true
	rm -Rf $name2 || true
	if [[ -e $name2 ]]; then
		exit -1
	fi
fi

if [[ "$1" == "clear" ]]; then
	exit 0
fi


mkdir $name1
zfs create $pool$name1
touch $name1/f1
zfs snapshot $pool$name1@s1
touch $name1/f2
zfs snapshot $pool$name1@s2

echo $pool$name1
ls -lhtra $name1

# zfs rollback -r $pool$name1@s1

zfs clone $pool$name1@s2 $pool$name2
touch $name2/f3
zfs snapshot $pool$name2@sub1

zfs list -t snapshot $name2

zfs rename $pool$name2 $pool$name3
