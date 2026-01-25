#!/bin/bash
# Find a free port in the range 8000-8999

MIN_PORT=8011
MAX_PORT=8999

# Get list of ports in use
used_ports=$(ss -tuln | awk 'NR>1 {print $5}' | grep -oE '[0-9]+$' | sort -u)

for port in $(seq $MIN_PORT $MAX_PORT); do
    if ! echo "$used_ports" | grep -q "^${port}$"; then
        echo $port
        exit 0
    fi
done

echo "No free port found in range $MIN_PORT-$MAX_PORT" >&2
exit 1
