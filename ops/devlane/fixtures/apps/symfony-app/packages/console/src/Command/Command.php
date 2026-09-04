<?php

namespace Symfony\Component\Console\Command;

use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Output\OutputInterface;

abstract class Command
{
    public const SUCCESS = 0;

    public function __construct()
    {
        $this->configure();
    }

    protected function configure(): void
    {
    }

    protected function addArgument(string $name, int $mode): static
    {
        return $this;
    }

    final public function run(InputInterface $input, OutputInterface $output): int
    {
        return $this->execute($input, $output);
    }

    abstract protected function execute(InputInterface $input, OutputInterface $output): int;
}
