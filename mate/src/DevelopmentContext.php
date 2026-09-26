<?php

namespace Mate;

use Composer\InstalledVersions;
use Symfony\AI\Mate\Agent\AgentInstructionsAggregator;
use Symfony\AI\Mate\Attribute\MateTool;
use Symfony\AI\Mate\Skill\SkillManager;
use Symfony\Component\DependencyInjection\Attribute\Autowire;
use Symfony\Component\Filesystem\Path;

/** Supplies the guidance that MCP-only participants cannot open with native file tools. */
final readonly class DevelopmentContext
{
    public function __construct(
        private AgentInstructionsAggregator $instructions,
        private SkillManager $skills,
        #[Autowire(param: 'mate.root_dir')] private string $rootDir,
        #[Autowire(param: 'mate.extensions')] private array $extensions,
    ) {
    }

    #[MateTool(name: 'development-context', description: 'Load installed PHP/Symfony versions, project reuse guidance and official reference locations before designing product changes. Distinguishes installed features from observed wiring.')]
    public function context(): array
    {
        $symfony = explode('.', ltrim(InstalledVersions::getPrettyVersion('symfony/framework-bundle'), 'v'));
        $packages = [];
        foreach (InstalledVersions::getInstalledPackages() as $package) {
            if (str_starts_with($package, 'symfony/') || 'mcp/sdk' === $package) {
                if (null !== $version = InstalledVersions::getPrettyVersion($package)) {
                    $packages[$package] = $version;
                }
            }
        }

        return [
            'php' => PHP_VERSION,
            'installed_packages' => $packages,
            'composer_lock_sha256' => hash_file('sha256', $this->rootDir.'/composer.lock'),
            'guidance' => $this->instructions->aggregate(['_custom' => $this->extensions['_custom']]),
            'guidance_source' => 'mate/INSTRUCTIONS.md',
            'guidance_sha256' => hash_file('sha256', $this->rootDir.'/mate/INSTRUCTIONS.md'),
            'references' => [
                'php' => 'https://www.php.net/manual/en/',
                'php_changes' => 'https://www.php.net/manual/en/migration'.PHP_MAJOR_VERSION.PHP_MINOR_VERSION.'.php',
                'symfony' => 'https://symfony.com/doc/'.$symfony[0].'.'.$symfony[1].'/index.html',
                'mate' => 'https://symfony.com/doc/current/ai/components/mate.html',
                'mcp' => 'https://symfony.com/doc/current/ai/bundles/mcp-bundle.html',
            ],
            'next' => 'Load relevant mate_skills/mate_skill, inspect wiring with mate_services/mate_service, then inspect existing code with Serena. Online docs may describe a newer release; compare with the installed versions above.',
        ];
    }

    #[MateTool(name: 'development-skill', description: 'Read one enabled Mate skill by its discovered name, using the installed package source or the project override. Returns provenance and the body for an MCP-only participant.')]
    public function skill(string $name): array
    {
        $matches = $this->skills->statusFor($name);
        if (1 !== count($matches) || !$matches[0]->enabled) {
            throw new \InvalidArgumentException('Select one enabled skill from mate_skills.');
        }
        $skill = $matches[0];
        $directory = 'override' === $skill->mode
            ? $this->skills->overrideCopyPath($skill->originalName)
            : $skill->source;
        $file = realpath($this->rootDir.'/'.$directory.'/SKILL.md');
        if (false === $file || !Path::isBasePath(realpath($this->rootDir), $file) || !is_file($file)) {
            throw new \RuntimeException('The selected skill source is unavailable inside this worktree.');
        }
        if (filesize($file) > 131072) {
            throw new \RuntimeException('The selected skill exceeds the bounded guidance size.');
        }

        return [
            'name' => $skill->installedName,
            'package' => $skill->package,
            'package_version' => InstalledVersions::isInstalled($skill->package)
                ? InstalledVersions::getPrettyVersion($skill->package) : null,
            'source' => Path::makeRelative($file, $this->rootDir),
            'sha256' => hash_file('sha256', $file),
            'generated_copy_status' => $skill->status,
            'body' => file_get_contents($file),
            'invocation' => 'In an MCP-only session, use the named dev-lane capabilities instead of the CLI examples in this skill.',
        ];
    }
}
