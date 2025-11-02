#!/bin/bash

# Kill any existing processes first
pkill -9 -f cluster.pl 2>/dev/null || true
sleep 2

echo "========================================="
echo "Starting DXSpider POTA Cluster"
echo "========================================="
echo "Callsign: $CALLSIGN"
echo "Location: $QTH"
echo "========================================="

# Ensure required directories exist
mkdir -p /spider/local
mkdir -p /spider/local_cmd
mkdir -p /spider/msg
mkdir -p /spider/data

# Remove stale lockfiles
echo "Cleaning up lockfiles..."
rm -f /spider/local/cluster.lck
rm -f /spider/local/*.lck

# Generate DXVars.pm
cat > /spider/local/DXVars.pm << EOF
package DXVars;

require Exporter;
@ISA = qw(Exporter);
@EXPORT = qw(\$mycall \$myname \$myalias \$mylatitude \$mylongitude 
             \$mylocator \$myqth \$myemail \$myprot_v);

use vars qw(\$mycall \$myname \$myalias \$mylatitude \$mylongitude 
            \$mylocator \$myqth \$myemail \$myprot_v);

\$mycall = "$CALLSIGN-10";
\$myname = "$OPERATOR_NAME";
\$myalias = "$CALLSIGN-2";
\$mylatitude = "+36.00";
\$mylongitude = "-94.33";
\$mylocator = "$GRID";
\$myqth = "$QTH";
\$myemail = '$EMAIL';
\$myprot_v = "5.1";

1;
EOF

echo "DXVars.pm generated with callsign: $CALLSIGN"

# Create sysop users
echo "Creating sysop users $CALLSIGN and $CALLSIGN-2..."
cd /spider/perl

perl << 'PERLSCRIPT'
use lib '/spider/perl';
use lib '/spider/local';
use DXUser;

my $call = $ENV{CALLSIGN} . "-10";
my $alias = $ENV{CALLSIGN} . "-2";

DXUser->init('/spider/data/users', 1);

my $user = DXUser->get($call);
if (!$user) {
    $user = DXUser->new($call);
}

$user->name($ENV{OPERATOR_NAME});
$user->qth($ENV{QTH});
$user->lat($ENV{LATITUDE});
$user->long($ENV{LONGITUDE});
$user->qra($ENV{GRID});
$user->email($ENV{EMAIL});
$user->homenode($call);
$user->lockout(0);
$user->priv(9);
$user->sort('S');
$user->put();

my $alias_user = DXUser->get($alias);
if (!$alias_user) {
    $alias_user = DXUser->new($alias);
}

$alias_user->name($ENV{OPERATOR_NAME});
$alias_user->qth($ENV{QTH});
$alias_user->lat($ENV{LATITUDE});
$alias_user->long($ENV{LONGITUDE});
$alias_user->qra($ENV{GRID});
$alias_user->email($ENV{EMAIL});
$alias_user->homenode($call);
$alias_user->lockout(0);
$alias_user->priv(9);
$alias_user->sort('U');
$alias_user->put();

DXUser->sync();
DXUser->finish();

print "Users created successfully\n";
PERLSCRIPT

echo "Users created successfully"
# Create message of the day
cat > /spider/data/motd << 'EOF'
Welcome to AI5KP POTA DX Cluster
================================
POTA spots are automatically imported every 60 seconds.
Spots are for Parks on the Air activations across North America.

For help, type: help
To see spots, type: sh/dx 20

73!
EOF

echo "MOTD file created"
# Start DXSpider
echo "Starting DXSpider cluster..."
./cluster.pl &
SPIDER_PID=$!

echo "DXSpider starting (PID: $SPIDER_PID)..."
echo "Waiting 30 seconds for cluster initialization..."
sleep 30

echo "DXSpider running successfully"

# Start telnet server for external connections on port 7300
echo "Starting telnet server on port 7300..."
python3 /home/sysop/telnet_server.py &
sleep 2

echo "Starting POTA bridge..."

# Start POTA bridge (writes directly to database)
python3 /home/sysop/pota_bridge.py