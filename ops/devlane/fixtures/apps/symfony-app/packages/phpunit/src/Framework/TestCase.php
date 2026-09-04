<?php

namespace PHPUnit\Framework;

abstract class TestCase
{
    public static int $assertions = 0;

    public static function assertSame(mixed $expected, mixed $actual, string $message = ''): void
    {
        self::$assertions++;
        if ($expected !== $actual) {
            self::fail($message ?: 'Values are not identical.');
        }
    }

    public static function assertNotSame(mixed $expected, mixed $actual, string $message = ''): void
    {
        self::$assertions++;
        if ($expected === $actual) {
            self::fail($message ?: 'Values are identical.');
        }
    }

    public static function assertTrue(bool $condition, string $message = ''): void
    {
        self::$assertions++;
        if (!$condition) {
            self::fail($message ?: 'Condition is not true.');
        }
    }

    public static function assertFalse(bool $condition, string $message = ''): void
    {
        self::$assertions++;
        if ($condition) {
            self::fail($message ?: 'Condition is not false.');
        }
    }

    public static function assertStringContainsString(string $needle, string $haystack, string $message = ''): void
    {
        self::$assertions++;
        if (!str_contains($haystack, $needle)) {
            self::fail($message ?: 'String does not contain the expected value.');
        }
    }

    public static function assertStringNotContainsString(string $needle, string $haystack, string $message = ''): void
    {
        self::$assertions++;
        if (str_contains($haystack, $needle)) {
            self::fail($message ?: 'String contains the unexpected value.');
        }
    }

    public static function assertFileDoesNotExist(string $path, string $message = ''): void
    {
        self::$assertions++;
        if (file_exists($path)) {
            self::fail($message ?: 'File exists.');
        }
    }

    public static function fail(string $message): never
    {
        throw new AssertionFailedError($message);
    }
}
