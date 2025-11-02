#!/bin/bash

echo "========================================="
echo "Starting DXSpider POTA Cluster"
echo "========================================="
echo "Callsign: $CALLSIGN"
echo "Location: $QTH"
echo "========================================="

# Generate DXVars.pm with environment variables
cat > /home/sysop/spider/local/DXVars.pm << EOF
package DXVars;

use vars qw(\$mycall \$myname \$myalias \$mylatitude \$mylongitude 
            \$mylocator \$myqth \$myemail \$myprot_v);

\$mycall = "$CALLSIGN";
\$myname = "$OPERATOR_NAME";
\$myalias = "POTA";
\$mylatitude = "$LATITUDE";
\$mylongitude = "$LONGITUDE";
\$mylocator = "$GRID";
\$myqth = "$QTH";
\$myemail = '$EMAIL';
\$myprot_v = "5.1";

1;
EOF

echo "DXVars.pm generated with callsign: $CALLSIGN"

# Start DXSpider in background
cd /home/sysop/spider/perl
./cluster.pl &
SPIDER_PID=$!

echo "DXSpider starting (PID: $SPIDER_PID)..."
echo "Waiting 15 seconds for cluster to initialize..."
sleep 15

# Check if DXSpider is running
if ! kill -0 $SPIDER_PID 2>/dev/null; then
    echo "ERROR: DXSpider failed to start"
    exit 1
fi

echo "DXSpider running successfully"
echo "Starting POTA bridge..."

# Start POTA bridge (this runs in foreground)
python3 /home/sysop/pota_bridge.py