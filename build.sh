#!/usr/bin/env bash

FNS=("gitlab")

rm -rf bin
mkdir bin

for fn in "${FNS[@]}"; do
  (
    cd "$fn"
    env GOOS="linux" go build -ldflags="-s -w" -o "../bin/$fn"
  )
done
