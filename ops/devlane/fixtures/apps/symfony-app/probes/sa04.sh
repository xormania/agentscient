#!/bin/sh
exec vendor/bin/phpunit --no-configuration --bootstrap tests/bootstrap.php probes/RecordingLogger.php probes/Sa04Test.php
