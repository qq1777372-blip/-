"""Test package marker.

Without this file `python -m unittest discover -s tests` fails with
"Start directory is not importable", because discovery imports the start
directory as a package. Individual modules still run via
`python -m tests.test_route_contract`.
"""
