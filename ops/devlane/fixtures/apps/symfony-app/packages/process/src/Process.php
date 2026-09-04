<?php

namespace Symfony\Component\Process;

final class Process
{
    public function __construct(private readonly array|string $command)
    {
    }

    public static function fromShellCommandline(string $command): self
    {
        return new self($command);
    }

    public function run(): int
    {
        if (is_array($this->command)) {
            return 0;
        }

        passthru($this->command, $status);

        return $status;
    }
}
