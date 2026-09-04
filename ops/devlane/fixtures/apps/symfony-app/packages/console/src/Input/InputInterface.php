<?php

namespace Symfony\Component\Console\Input;

interface InputInterface
{
    public function getArgument(string $name): mixed;
}
