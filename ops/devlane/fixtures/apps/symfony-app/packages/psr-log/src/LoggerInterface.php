<?php

namespace Psr\Log;

interface LoggerInterface
{
    public function error(string|\Stringable $message, array $context = []): void;

    public function log(mixed $level, string|\Stringable $message, array $context = []): void;
}
