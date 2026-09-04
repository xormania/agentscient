<?php

namespace Symfony\Component\Dotenv;

final class Dotenv
{
    public function bootEnv(string $path): void
    {
        $_SERVER['APP_DEBUG'] = $_ENV['APP_DEBUG'] = false;
    }
}
