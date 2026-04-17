#!/bin/bash

# this gets the version of from pyproject with no external dependencies
head -n 5 < pyproject.toml | grep "version = " | awk '{ gsub("\"", "", $3); print $3}'
