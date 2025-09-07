#!/usr/bin/env bash
set -e
curl -s -X POST -F "files=@tests/data/the_code_of_criminal_procedure,_1973.pdf" -F "files=@tests/data/a2019-35.pdf" -F "files=@tests/data/repealedfileopen.pdf" \
  http://localhost:8000/ingest | jq
  #!/usr/bin/env bash
