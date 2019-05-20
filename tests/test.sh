#!/bin/bash
echo "Running tests:" && coverage run --omit="/usr/local/lib/python2.7/*","../backend/*Event.py" --source="../backend" --concurrency=thread test_*.py && echo ""; echo "Code coverage:" && coverage report -m 

