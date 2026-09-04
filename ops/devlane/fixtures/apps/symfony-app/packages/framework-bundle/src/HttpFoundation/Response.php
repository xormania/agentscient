<?php

namespace Symfony\Component\HttpFoundation;

final class Response
{
    public const HTTP_NOT_FOUND = 404;

    public function __construct(private readonly string $content = '', public readonly int $status = 200)
    {
    }

    public function getContent(): string
    {
        return $this->content;
    }
}
