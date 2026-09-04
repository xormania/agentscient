<?php

namespace Symfony\Component\Console\Tester;

use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Output\OutputInterface;

final class CommandTester
{
    private string $display = '';

    public function __construct(private readonly Command $command)
    {
    }

    public function execute(array $arguments): int
    {
        $input = new class($arguments) implements InputInterface {
            public function __construct(private readonly array $arguments)
            {
            }

            public function getArgument(string $name): mixed
            {
                return $this->arguments[$name] ?? null;
            }
        };
        $output = new class($this) implements OutputInterface {
            public function __construct(private readonly CommandTester $tester)
            {
            }

            public function writeln(string $message): void
            {
                $this->tester->append($message."\n");
            }
        };

        return $this->command->run($input, $output);
    }

    public function append(string $text): void
    {
        $this->display .= $text;
    }

    public function getDisplay(): string
    {
        return $this->display;
    }
}
