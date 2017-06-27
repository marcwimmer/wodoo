#!/bin/bash

mkdir -p $INPUT
mkdir -p $OUTPUT

while true;
do
    ls $INPUT
    for f in $(ls $INPUT/*); do
        echo $f
        /usr/bin/soffice --headless --convert-to pdf --outdir $OUTPUT $f
        rm $f
    done
    sleep 0.4
done

