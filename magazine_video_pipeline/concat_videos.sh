#!/bin/bash
# Helper script to concatenate an intro and the generated scenes

OUTPUT_FILE="${@: -1}"
INPUTS="${@:1:$#-1}"

echo "" > inputs.txt
for input in $INPUTS; do
    echo "file '$input'" >> inputs.txt
done

ffmpeg -f concat -safe 0 -i inputs.txt -c copy "$OUTPUT_FILE" -y
rm inputs.txt
