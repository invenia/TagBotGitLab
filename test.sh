#!/usr/bin/env bash

FNS=("gitlab")

for fn in "${FNS[@]}"; do
  (
    cd "$fn"
    go test -v
  )
done
