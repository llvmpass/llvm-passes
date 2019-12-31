# Extracting the set of passes from source code

This folder provides an `extract.py` script to parse all LLVM source code and
generate a list of passes. The default output format is YAML; this can be
converted to CSV files for Neo4j. Check the command-line help for details.

The YAML file `passdb.yaml` is the set of passes for a some release of LLVM 8.
`passdb-O3.yaml` is a restriction to passes that are executed at least one in
`-O3` in that release. They are meant for post-processing and analysis in
scripts.

The `csv` folder contain a CSV export of `passdb.yaml`, which can be imported
in Neo4j with the `load csv` command provided that it is copied (or symlinked)
to the Neo4j import folder. The Cyper script `passdb.cypher` clears any
existing database then imports the CSV files, and can be used from the
interactive databse browser.
