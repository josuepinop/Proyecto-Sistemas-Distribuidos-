#!/usr/bin/env bash
set -e

python client/cli.py health
python client/cli.py datanodes
python client/cli.py login --user santiago --password 1234
python scripts/create_sample_file.py --output tests/sample_files/demo.bin --size-mb 3
python client/cli.py put tests/sample_files/demo.bin --name demo.bin --block-size-mb 1
python client/cli.py ls
curl http://localhost:8001/blocks
curl http://localhost:8002/blocks
curl http://localhost:8003/blocks
python client/cli.py get demo.bin --output downloads/demo_recuperado.bin
