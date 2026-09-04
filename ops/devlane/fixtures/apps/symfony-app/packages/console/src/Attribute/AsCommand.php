<?php

namespace Symfony\Component\Console\Attribute;

#[\Attribute(\Attribute::TARGET_CLASS)]
final class AsCommand
{
    public function __construct(public readonly string $name)
    {
    }
}
