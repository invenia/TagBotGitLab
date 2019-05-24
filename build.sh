#!/usr/bin/env bash

rm -rf bin
mkdir bin

(
  cd gitlab
  env GOOS="linux" go build -ldflags="-s -w" -o "../bin/gitlab"
)
