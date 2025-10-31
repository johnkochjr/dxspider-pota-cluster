package DXVars;

use vars qw($mycall $myname $myalias $mylatitude $mylongitude 
            $mylocator $myqth $myemail $myprot_v);

$mycall = $ENV{CALLSIGN} || "N0CALL";
$myname = $ENV{OPERATOR_NAME} || "Operator";
$myalias = "POTA";
$mylatitude = $ENV{LATITUDE} || "+0.0";
$mylongitude = $ENV{LONGITUDE} || "+0.0";
$mylocator = $ENV{GRID} || "AA00aa";
$myqth = $ENV{QTH} || "Docker Container";
$myemail = $ENV{EMAIL} || "sysop@localhost";
$myprot_v = "5.1";

1;