<?php

namespace App\Tests;

use App\Kernel;
use PHPUnit\Framework\TestCase;
use Symfony\Bundle\FrameworkBundle\Console\Application;

final class DevelopmentBoundaryTest extends TestCase
{
    public function testMakerAndProfilerAreAvailableForDevelopment(): void
    {
        $kernel = new Kernel('test', true);
        try {
            $application = new Application($kernel);
            $application->all();
            self::assertTrue($application->has('make:command'));
            self::assertTrue($kernel->getContainer()->has('profiler'));
            self::assertFalse($kernel->getContainer()->get('profiler')->isEnabled());
        } finally {
            $kernel->shutdown();
        }
    }

    public function testProductionHasMcpButNoMakerOrProfiler(): void
    {
        $kernel = new Kernel('prod', false);
        try {
            $application = new Application($kernel);
            $application->all();
            self::assertTrue($application->has('mcp:server'));
            self::assertFalse($application->has('make:command'));
            self::assertFalse($kernel->getContainer()->has('profiler'));
            self::assertArrayNotHasKey('MakerBundle', $kernel->getBundles());
        } finally {
            $kernel->shutdown();
        }
    }
}
