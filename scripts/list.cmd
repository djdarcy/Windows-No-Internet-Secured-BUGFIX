@echo off
listall.py -d . -xd .git -xd private -xd revisions -xd __py*__ -fmt summary %*
