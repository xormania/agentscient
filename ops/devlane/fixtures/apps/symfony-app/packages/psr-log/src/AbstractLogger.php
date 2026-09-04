<?php

namespace Psr\Log;

abstract class AbstractLogger implements LoggerInterface
{
    public function error(string|\Stringable $message, array $context = []): void
    {
        $this->log('error', $message, $context);
    }
}
