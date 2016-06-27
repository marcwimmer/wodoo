#!/bin/bash
set -e

echo "Compiling sphinx from: $(ls -Ad /in/*/)"
rm /out/* -Rf
sphinx-build /in /out
