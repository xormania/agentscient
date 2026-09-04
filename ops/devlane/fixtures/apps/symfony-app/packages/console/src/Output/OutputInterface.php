<?php

namespace Symfony\Component\Console\Output;

interface OutputInterface
{
    public function writeln(string $message): void;
}
